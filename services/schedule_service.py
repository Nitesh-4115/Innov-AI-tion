"""
Schedule Service
Business logic for medication schedule management
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from database import get_db_context
import models
from tools.scheduler import medication_scheduler


logger = logging.getLogger(__name__)


def _ensure_time(val):
    """Ensure the provided value is a datetime.time.

    Accepts a time object or a string like 'HH:MM' or 'HH:MM:SS'.
    Raises TypeError if it cannot be converted.
    """
    if val is None:
        return None
    if isinstance(val, time):
        return val
    if isinstance(val, str):
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(val, fmt).time()
            except ValueError:
                continue
        raise TypeError(f"Cannot parse scheduled_time string: {val}")
    raise TypeError(f"Unsupported scheduled_time type: {type(val)}")


class ScheduleService:
    """
    Service for medication schedule management
    """
    
    async def create_schedule(
        self,
        patient_id: int,
        medication_id: int,
        scheduled_time: time,
        day_of_week: Optional[List[int]] = None,
        reminder_enabled: bool = True,
        reminder_minutes_before: int = 15,
        window_start_minutes: int = 30,
        window_end_minutes: int = 60,
        notes: Optional[str] = None,
        db: Optional[Session] = None
    ) -> models.Schedule:
        """
        Create a medication schedule entry
        
        Args:
            patient_id: Patient ID
            medication_id: Medication ID
            scheduled_time: Time of day for dose
            day_of_week: Days of week (0=Monday, 6=Sunday), None for daily
            reminder_enabled: Whether to send reminders
            reminder_minutes_before: Minutes before to send reminder
            window_start_minutes: Minutes before scheduled time when window opens
            window_end_minutes: Minutes after scheduled time when window closes
            notes: Additional notes
            db: Database session
            
        Returns:
            Created Schedule object
        """
        def _create(session: Session) -> models.Schedule:
            # Verify medication exists and belongs to patient
            medication = session.query(models.Medication).filter(
                and_(
                    models.Medication.id == medication_id,
                    models.Medication.patient_id == patient_id
                )
            ).first()
            
            if not medication:
                raise ValueError(
                    f"Medication {medication_id} not found for patient {patient_id}"
                )
            
            # Avoid creating duplicate schedule for same patient/medication/date/time
            from datetime import date as _date
            target_date = _date.today()
            time_str = scheduled_time.strftime("%H:%M") if hasattr(scheduled_time, 'strftime') else str(scheduled_time)
            existing = session.query(models.Schedule).filter(
                and_(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.medication_id == medication_id,
                    models.Schedule.scheduled_time == time_str,
                    models.Schedule.scheduled_date == target_date
                )
            ).first()

            if existing:
                return existing

            schedule = models.Schedule(
                patient_id=patient_id,
                medication_id=medication_id,
                scheduled_time=scheduled_time,
                day_of_week=day_of_week,  # JSON list
                reminder_enabled=reminder_enabled,
                reminder_minutes_before=reminder_minutes_before,
                window_start_minutes=window_start_minutes,
                window_end_minutes=window_end_minutes,
                notes=notes,
                active=True
            )
            
            session.add(schedule)
            session.commit()
            session.refresh(schedule)
            
            logger.info(
                f"Created schedule for medication {medication_id} "
                f"at {scheduled_time} for patient {patient_id}"
            )
            return schedule
        
        if db:
            return _create(db)
        
        with get_db_context() as session:
            return _create(session)
    
    async def get_schedule(
        self,
        schedule_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.Schedule]:
        """Get schedule by ID"""
        def _get(session: Session) -> Optional[models.Schedule]:
            return session.query(models.Schedule).filter(
                models.Schedule.id == schedule_id
            ).first()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_patient_schedules(
        self,
        patient_id: int,
        active_only: bool = True,
        db: Optional[Session] = None
    ) -> List[models.Schedule]:
        """Get all schedules for a patient"""
        def _get(session: Session) -> List[models.Schedule]:
            query = session.query(models.Schedule).filter(
                models.Schedule.patient_id == patient_id
            )
            
            if active_only:
                query = query.filter(models.Schedule.active == True)
            
            return query.order_by(models.Schedule.scheduled_time).all()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_medication_schedules(
        self,
        medication_id: int,
        db: Optional[Session] = None
    ) -> List[models.Schedule]:
        """Get all schedules for a medication"""
        def _get(session: Session) -> List[models.Schedule]:
            return session.query(models.Schedule).filter(
                and_(
                    models.Schedule.medication_id == medication_id,
                    models.Schedule.active == True
                )
            ).order_by(models.Schedule.scheduled_time).all()
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def update_schedule(
        self,
        schedule_id: int,
        updates: Dict[str, Any],
        db: Optional[Session] = None
    ) -> Optional[models.Schedule]:
        """Update a schedule"""
        def _update(session: Session) -> Optional[models.Schedule]:
            schedule = session.query(models.Schedule).filter(
                models.Schedule.id == schedule_id
            ).first()
            
            if not schedule:
                return None
            
            allowed_fields = {
                'scheduled_time', 'day_of_week', 'reminder_enabled',
                'reminder_minutes_before', 'window_start_minutes',
                'window_end_minutes', 'notes', 'active'
            }
            
            for field, value in updates.items():
                if field in allowed_fields and hasattr(schedule, field):
                    setattr(schedule, field, value)
            
            schedule.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(schedule)
            
            return schedule
        
        if db:
            return _update(db)
        
        with get_db_context() as session:
            return _update(session)
    
    async def deactivate_schedule(
        self,
        schedule_id: int,
        db: Optional[Session] = None
    ) -> Optional[models.Schedule]:
        """Deactivate a schedule"""
        return await self.update_schedule(schedule_id, {'active': False}, db)
    
    async def get_todays_schedule(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """
        Get today's medication schedule for a patient
        
        Returns:
            List of scheduled doses with details
        """
        def _get(session: Session) -> List[Dict[str, Any]]:
            today = date.today()
            day_of_week = today.weekday()
            
            schedules = session.query(models.Schedule).filter(
                and_(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.active == True
                )
            ).all()
            
            todays_doses = []
            for schedule in schedules:
                # Check if schedule applies today
                if schedule.day_of_week is None or day_of_week in schedule.day_of_week:
                    medication = session.query(models.Medication).filter(
                        models.Medication.id == schedule.medication_id
                    ).first()
                    
                    # Check if already taken today
                    adherence_log = session.query(models.AdherenceLog).filter(
                        and_(
                            models.AdherenceLog.schedule_id == schedule.id,
                            models.AdherenceLog.logged_at >= datetime.combine(today, time.min),
                            models.AdherenceLog.logged_at <= datetime.combine(today, time.max)
                        )
                    ).first()
                    
                    status = "pending"
                    if adherence_log:
                        status = adherence_log.status.value
                    
                    # Calculate time window (ensure scheduled_time is a time object)
                    t = _ensure_time(schedule.scheduled_time)
                    scheduled_dt = datetime.combine(today, t)
                    window_start = scheduled_dt - timedelta(minutes=schedule.window_start_minutes)
                    window_end = scheduled_dt + timedelta(minutes=schedule.window_end_minutes)
                    
                    todays_doses.append({
                        "schedule_id": schedule.id,
                        "medication_id": schedule.medication_id,
                        "medication_name": medication.name if medication else "Unknown",
                        "dosage": medication.dosage if medication else "",
                        "scheduled_time": t.strftime("%H:%M") if t else None,
                        "window_start": window_start.time().isoformat(),
                        "window_end": window_end.time().isoformat(),
                        "status": status,
                        "reminder_enabled": schedule.reminder_enabled,
                        "notes": schedule.notes,
                        "with_food": medication.with_food if medication else False
                    })
            
            # Sort by scheduled time
            todays_doses.sort(key=lambda x: x["scheduled_time"])
            return todays_doses
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_upcoming_doses(
        self,
        patient_id: int,
        hours: int = 4,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get doses scheduled in the next few hours"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            now = datetime.now()
            cutoff_time = (now + timedelta(hours=hours)).time()
            current_time = now.time()
            
            schedules = session.query(models.Schedule).filter(
                and_(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.active == True
                )
            ).all()
            
            upcoming = []
            for schedule in schedules:
                # Normalize scheduled_time and check if in time range
                try:
                    t = _ensure_time(schedule.scheduled_time)
                except TypeError:
                    continue
                if t is None:
                    continue
                if current_time <= t <= cutoff_time:
                    medication = session.query(models.Medication).filter(
                        models.Medication.id == schedule.medication_id
                    ).first()
                    
                    # Check if already taken
                    adherence_log = session.query(models.AdherenceLog).filter(
                        and_(
                            models.AdherenceLog.schedule_id == schedule.id,
                            models.AdherenceLog.logged_at >= datetime.combine(
                                date.today(), time.min
                            )
                        )
                    ).first()
                    
                    if not adherence_log:  # Not yet taken
                        upcoming.append({
                            "schedule_id": schedule.id,
                            "medication_name": medication.name if medication else "Unknown",
                            "dosage": medication.dosage if medication else "",
                            "scheduled_time": t.strftime("%H:%M"),
                            "minutes_until": int(
                                (datetime.combine(date.today(), t) - now
                                ).total_seconds() / 60
                            ),
                            "reminder_enabled": schedule.reminder_enabled
                        })
            
            upcoming.sort(key=lambda x: x["scheduled_time"])
            return upcoming
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_overdue_doses(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get doses that are overdue (past window end, not taken)"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            now = datetime.now()
            today = date.today()
            
            schedules = session.query(models.Schedule).filter(
                and_(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.active == True
                )
            ).all()
            
            overdue = []
            for schedule in schedules:
                try:
                    t = _ensure_time(schedule.scheduled_time)
                except TypeError:
                    continue
                if t is None:
                    continue
                scheduled_dt = datetime.combine(today, t)
                window_end = scheduled_dt + timedelta(minutes=schedule.window_end_minutes)
                
                if window_end < now:  # Past the window
                    # Check if taken
                    adherence_log = session.query(models.AdherenceLog).filter(
                        and_(
                            models.AdherenceLog.schedule_id == schedule.id,
                            models.AdherenceLog.logged_at >= datetime.combine(today, time.min),
                            models.AdherenceLog.logged_at <= datetime.combine(today, time.max)
                        )
                    ).first()
                    
                    if not adherence_log:  # Not logged at all
                        medication = session.query(models.Medication).filter(
                            models.Medication.id == schedule.medication_id
                        ).first()
                        
                        overdue.append({
                            "schedule_id": schedule.id,
                            "medication_id": schedule.medication_id,
                            "medication_name": medication.name if medication else "Unknown",
                            "dosage": medication.dosage if medication else "",
                            "scheduled_time": t.strftime("%H:%M"),
                            "window_end": window_end.time().isoformat(),
                            "minutes_overdue": int((now - window_end).total_seconds() / 60)
                        })
            
            overdue.sort(key=lambda x: x["minutes_overdue"], reverse=True)
            return overdue
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def optimize_schedule(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Use AI scheduler to optimize medication schedule
        
        Returns:
            Optimized schedule recommendations
        """
        def _optimize(session: Session) -> Dict[str, Any]:
            # Get patient info
            patient = session.query(models.Patient).filter(
                models.Patient.id == patient_id
            ).first()
            
            if not patient:
                raise ValueError(f"Patient {patient_id} not found")
            
            # Get medications with schedules
            medications = session.query(models.Medication).filter(
                and_(
                    models.Medication.patient_id == patient_id,
                    models.Medication.active == True
                )
            ).all()
            
            if not medications:
                return {"message": "No active medications to schedule"}
            
            # Prepare medication data for optimizer
            med_requirements = []
            for med in medications:
                med_requirements.append({
                    "medication_id": med.id,
                    "name": med.name,
                    "frequency_per_day": med.frequency_per_day,
                    "with_food": med.with_food,
                    "min_hours_between": getattr(med, 'min_hours_between_doses', None)
                })
            
            # Build preferences dict from patient fields so scheduler uses real times
            # Patient model stores times as time objects; ensure string HH:MM format
            def _time_to_str(val):
                if not val:
                    return None
                try:
                    # if it's a time object
                    return val.strftime("%H:%M")
                except Exception:
                    # if stored as string already
                    return str(val)

            preferences = {
                "wake_time": _time_to_str(getattr(patient, 'wake_time', None)) or "08:00",
                "sleep_time": _time_to_str(getattr(patient, 'sleep_time', None)) or "22:00",
                "breakfast_time": _time_to_str(getattr(patient, 'breakfast_time', None)) or "08:00",
                "lunch_time": _time_to_str(getattr(patient, 'lunch_time', None)) or "12:00",
                "dinner_time": _time_to_str(getattr(patient, 'dinner_time', None)) or "18:00",
            }
            
            return {
                "patient_id": patient_id,
                "medications": med_requirements,
                "preferences": preferences,
                "optimization_pending": True,
                "message": "Schedule optimization data prepared. Run scheduler optimizer."
            }
        
        if db:
            return _optimize(db)
        
        with get_db_context() as session:
            return _optimize(session)
    
    async def create_schedules_from_optimizer(
        self,
        patient_id: int,
        optimized_times: List[Dict[str, Any]],
        db: Optional[Session] = None
    ) -> List[models.Schedule]:
        """
        Create schedules from optimizer results
        
        Args:
            patient_id: Patient ID
            optimized_times: List of {medication_id, scheduled_time, ...}
            db: Database session
            
        Returns:
            Created schedules
        """
        created = []
        for opt in optimized_times:
            schedule = await self.create_schedule(
                patient_id=patient_id,
                medication_id=opt["medication_id"],
                scheduled_time=time.fromisoformat(opt["scheduled_time"]),
                reminder_enabled=opt.get("reminder_enabled", True),
                notes=opt.get("notes"),
                db=db
            )
            created.append(schedule)
        
        return created
    
    async def get_schedule_summary(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get summary of patient's medication schedule"""
        def _get(session: Session) -> Dict[str, Any]:
            schedules = session.query(models.Schedule).filter(
                and_(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.active == True
                )
            ).all()
            
            # Group by time period
            morning = []  # 5:00 - 11:59
            afternoon = []  # 12:00 - 16:59
            evening = []  # 17:00 - 20:59
            night = []  # 21:00 - 4:59
            
            for schedule in schedules:
                hour = schedule.scheduled_time.hour
                medication = session.query(models.Medication).filter(
                    models.Medication.id == schedule.medication_id
                ).first()
                
                entry = {
                    "schedule_id": schedule.id,
                    "medication": medication.name if medication else "Unknown",
                    "time": schedule.scheduled_time.isoformat()
                }
                
                if 5 <= hour < 12:
                    morning.append(entry)
                elif 12 <= hour < 17:
                    afternoon.append(entry)
                elif 17 <= hour < 21:
                    evening.append(entry)
                else:
                    night.append(entry)
            
            return {
                "total_daily_doses": len(schedules),
                "morning": morning,
                "afternoon": afternoon,
                "evening": evening,
                "night": night
            }
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)


# Singleton instance
schedule_service = ScheduleService()
