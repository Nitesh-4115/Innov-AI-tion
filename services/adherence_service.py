"""
Adherence Service
Business logic for medication adherence tracking and analysis
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, desc

from database import get_db_context
import models
from models import AdherenceStatus


logger = logging.getLogger(__name__)


def _ensure_time(val):
    if val is None:
        return None
    if hasattr(val, 'hour') and hasattr(val, 'minute'):
        return val
    if isinstance(val, str):
        for fmt in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(val, fmt).time()
            except Exception:
                continue
        raise TypeError(f"Cannot parse scheduled_time string: {val}")
    raise TypeError(f"Unsupported scheduled_time type: {type(val)}")


class AdherenceService:
    """
    Service for adherence tracking and analysis
    """
    
    async def log_adherence(
        self,
        patient_id: int,
        schedule_id: int,
        medication_id: int,
        status: AdherenceStatus,
        taken_at: Optional[datetime] = None,
        deviation_minutes: int = 0,
        notes: Optional[str] = None,
        reported_by: str = "patient",
        db: Optional[Session] = None
    ) -> models.AdherenceLog:
        """
        Log an adherence event
        
        Args:
            patient_id: Patient ID
            schedule_id: Schedule ID
            medication_id: Medication ID
            status: Adherence status (taken, missed, skipped, delayed)
            taken_at: When medication was taken
            deviation_minutes: Minutes early/late from scheduled time
            notes: Additional notes
            reported_by: Who reported (patient, system, caregiver)
            db: Database session
            
        Returns:
            Created AdherenceLog object
        """
        def _log(session: Session) -> models.AdherenceLog:
            # Get scheduled time from schedule
            schedule = session.query(models.Schedule).filter(
                models.Schedule.id == schedule_id
            ).first()
            # Build a datetime for the scheduled_time (AdherenceLog.scheduled_time is DateTime)
            if schedule:
                try:
                    t = _ensure_time(schedule.scheduled_time)
                    scheduled_dt = datetime.combine(schedule.scheduled_date, t)
                except Exception:
                    # Fallback: use today's date with the taken_at time or now
                    scheduled_dt = datetime.combine(date.today(), taken_at.time()) if taken_at else datetime.utcnow()
            else:
                scheduled_dt = taken_at or datetime.utcnow()

            log = models.AdherenceLog(
                patient_id=patient_id,
                schedule_id=schedule_id,
                medication_id=medication_id,
                status=status,
                scheduled_time=scheduled_dt,
                actual_time=taken_at,
                deviation_minutes=deviation_minutes,
                notes=notes,
                logged_by=reported_by,
                taken=(status == AdherenceStatus.TAKEN or status == AdherenceStatus.DELAYED)
            )
            
            session.add(log)
            session.commit()
            session.refresh(log)
            
            logger.info(
                f"Logged adherence for patient {patient_id}, "
                f"medication {medication_id}: {status.value}"
            )
            # Update the corresponding Schedule row (if present) to reflect the adherence
            try:
                if schedule:
                    new_status = status.value if hasattr(status, 'value') else str(status)
                    schedule.status = new_status
                    session.add(schedule)
                    session.commit()
            except Exception:
                # Non-fatal: continue even if we cannot update schedule status
                logger.exception("Failed to update schedule status after logging adherence")
            return log
        
        if db:
            return _log(db)
        
        with get_db_context() as session:
            return _log(session)
    
    async def log_dose_taken(
        self,
        patient_id: int,
        schedule_id: int,
        medication_id: int,
        taken_at: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> models.AdherenceLog:
        """Convenience method to log a taken dose"""
        taken_at = taken_at or datetime.utcnow()
        
        # Calculate deviation from schedule
        deviation = 0
        with get_db_context() as session:
            schedule = session.query(models.Schedule).filter(
                models.Schedule.id == schedule_id
            ).first()
            if schedule and schedule.scheduled_time:
                # Calculate deviation in minutes
                t = _ensure_time(schedule.scheduled_time)
                scheduled_dt = datetime.combine(
                    taken_at.date(),
                    t
                )
                diff = (taken_at - scheduled_dt).total_seconds() / 60
                deviation = int(diff)
        
        status = AdherenceStatus.TAKEN
        if abs(deviation) > 30:  # More than 30 minutes off
            status = AdherenceStatus.DELAYED
        
        return await self.log_adherence(
            patient_id=patient_id,
            schedule_id=schedule_id,
            medication_id=medication_id,
            status=status,
            taken_at=taken_at,
            deviation_minutes=deviation,
            db=db
        )
    
    async def log_dose_missed(
        self,
        patient_id: int,
        schedule_id: int,
        medication_id: int,
        reason: Optional[str] = None,
        db: Optional[Session] = None
    ) -> models.AdherenceLog:
        """Log a missed dose"""
        return await self.log_adherence(
            patient_id=patient_id,
            schedule_id=schedule_id,
            medication_id=medication_id,
            status=AdherenceStatus.MISSED,
            notes=reason,
            reported_by="system",
            db=db
        )
    
    async def log_dose_skipped(
        self,
        patient_id: int,
        schedule_id: int,
        medication_id: int,
        reason: str,
        db: Optional[Session] = None
    ) -> models.AdherenceLog:
        """Log an intentionally skipped dose"""
        return await self.log_adherence(
            patient_id=patient_id,
            schedule_id=schedule_id,
            medication_id=medication_id,
            status=AdherenceStatus.SKIPPED,
            notes=reason,
            reported_by="patient",
            db=db
        )
    
    async def get_adherence_rate(
        self,
        patient_id: int,
        days: int = 30,
        medication_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Calculate adherence rate for a patient
        
        Args:
            patient_id: Patient ID
            days: Number of days to analyze
            medication_id: Optional specific medication
            db: Database session
            
        Returns:
            Adherence statistics
        """
        def _calculate(session: Session) -> Dict[str, Any]:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.logged_at >= start_date
                )
            )
            
            if medication_id:
                query = query.filter(
                    models.AdherenceLog.medication_id == medication_id
                )
            
            logs = query.all()
            
            if not logs:
                return {
                    "adherence_rate": 0.0,
                    "total_doses": 0,
                    "taken": 0,
                    "missed": 0,
                    "skipped": 0,
                    "delayed": 0,
                    "days_analyzed": days
                }
            
            total = len(logs)
            taken = sum(1 for l in logs if l.status == AdherenceStatus.TAKEN)
            missed = sum(1 for l in logs if l.status == AdherenceStatus.MISSED)
            skipped = sum(1 for l in logs if l.status == AdherenceStatus.SKIPPED)
            delayed = sum(1 for l in logs if l.status == AdherenceStatus.DELAYED)
            
            # Adherence rate: (taken + delayed) / total
            # Delayed is still considered adherent
            adherent = taken + delayed
            rate = (adherent / total) * 100 if total > 0 else 0.0
            
            # Calculate average deviation for taken doses
            deviations = [
                l.deviation_minutes for l in logs 
                if l.deviation_minutes is not None and 
                l.status in [AdherenceStatus.TAKEN, AdherenceStatus.DELAYED]
            ]
            avg_deviation = sum(deviations) / len(deviations) if deviations else 0
            
            return {
                "adherence_rate": round(rate, 1),
                "total_doses": total,
                "taken": taken,
                "missed": missed,
                "skipped": skipped,
                "delayed": delayed,
                "average_deviation_minutes": round(avg_deviation, 1),
                "days_analyzed": days
            }
        
        if db:
            return _calculate(db)
        
        with get_db_context() as session:
            return _calculate(session)
    
    async def get_adherence_streak(
        self,
        patient_id: int,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Get current and best adherence streaks
        
        Returns:
            Streak information
        """
        def _get_streak(session: Session) -> Dict[str, Any]:
            logs = session.query(models.AdherenceLog).filter(
                models.AdherenceLog.patient_id == patient_id
            ).order_by(desc(models.AdherenceLog.logged_at)).all()
            
            if not logs:
                return {
                    "current_streak": 0,
                    "best_streak": 0,
                    "streak_start": None
                }
            
            # Group logs by date
            daily_adherence = defaultdict(list)
            for log in logs:
                day = log.logged_at.date()
                daily_adherence[day].append(log)
            
            # Check each day for perfect adherence
            current_streak = 0
            best_streak = 0
            temp_streak = 0
            streak_start = None
            
            sorted_days = sorted(daily_adherence.keys(), reverse=True)
            
            for i, day in enumerate(sorted_days):
                day_logs = daily_adherence[day]
                # Day is adherent if no missed doses
                is_adherent = all(
                    l.status != AdherenceStatus.MISSED 
                    for l in day_logs
                )
                
                if is_adherent:
                    temp_streak += 1
                    if i == 0 or (sorted_days[i-1] - day).days == 1:
                        # Continue current streak
                        if current_streak == 0:
                            streak_start = day
                        current_streak = temp_streak
                    best_streak = max(best_streak, temp_streak)
                else:
                    temp_streak = 0
                    if current_streak == 0:
                        current_streak = 0  # Current streak broken
            
            return {
                "current_streak": current_streak,
                "best_streak": best_streak,
                "streak_start": streak_start.isoformat() if streak_start else None
            }
        
        if db:
            return _get_streak(db)
        
        with get_db_context() as session:
            return _get_streak(session)
    
    async def get_adherence_by_medication(
        self,
        patient_id: int,
        days: int = 30,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get adherence breakdown by medication"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            # Get patient's medications
            medications = session.query(models.Medication).filter(
                models.Medication.patient_id == patient_id
            ).all()
            
            results = []
            for med in medications:
                rate = self._sync_get_adherence_rate(
                    session, patient_id, days, med.id
                )
                results.append({
                    "medication_id": med.id,
                    "medication_name": med.name,
                    "dosage": med.dosage,
                    "adherence_rate": rate["adherence_rate"],
                    "total_doses": rate["total_doses"],
                    "missed_doses": rate["missed"]
                })
            
            # Sort by adherence rate (lowest first to highlight problems)
            results.sort(key=lambda x: x["adherence_rate"])
            return results
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    def _sync_get_adherence_rate(
        self,
        session: Session,
        patient_id: int,
        days: int,
        medication_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Synchronous version for internal use"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = session.query(models.AdherenceLog).filter(
            and_(
                models.AdherenceLog.patient_id == patient_id,
                models.AdherenceLog.logged_at >= start_date
            )
        )
        
        if medication_id:
            query = query.filter(
                models.AdherenceLog.medication_id == medication_id
            )
        
        logs = query.all()
        
        if not logs:
            return {"adherence_rate": 0.0, "total_doses": 0, "missed": 0}
        
        total = len(logs)
        taken = sum(1 for l in logs if l.status == AdherenceStatus.TAKEN)
        delayed = sum(1 for l in logs if l.status == AdherenceStatus.DELAYED)
        missed = sum(1 for l in logs if l.status == AdherenceStatus.MISSED)
        
        adherent = taken + delayed
        rate = (adherent / total) * 100 if total > 0 else 0.0
        
        return {
            "adherence_rate": round(rate, 1),
            "total_doses": total,
            "missed": missed
        }
    
    async def get_adherence_history(
        self,
        patient_id: int,
        days: int = 7,
        medication_id: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get detailed adherence history"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            query = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.logged_at >= start_date
                )
            )
            
            if medication_id:
                query = query.filter(
                    models.AdherenceLog.medication_id == medication_id
                )
            
            logs = query.order_by(desc(models.AdherenceLog.logged_at)).all()
            
            history = []
            for log in logs:
                # Get medication name
                med = session.query(models.Medication).filter(
                    models.Medication.id == log.medication_id
                ).first()
                
                history.append({
                    "log_id": log.id,
                    "medication_id": log.medication_id,
                    "medication_name": med.name if med else "Unknown",
                    "status": log.status.value,
                    "scheduled_time": log.scheduled_time.isoformat() if log.scheduled_time else None,
                    "taken_at": log.taken_at.isoformat() if log.taken_at else None,
                    "deviation_minutes": log.deviation_minutes,
                    "notes": log.notes,
                    "logged_at": log.logged_at.isoformat()
                })
            
            return history
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_daily_summary(
        self,
        patient_id: int,
        target_date: Optional[date] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Get adherence summary for a specific day"""
        def _get(session: Session) -> Dict[str, Any]:
            target = target_date or date.today()
            start = datetime.combine(target, datetime.min.time())
            end = datetime.combine(target, datetime.max.time())
            
            logs = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.logged_at >= start,
                    models.AdherenceLog.logged_at <= end
                )
            ).all()
            
            taken = sum(1 for l in logs if l.status == AdherenceStatus.TAKEN)
            missed = sum(1 for l in logs if l.status == AdherenceStatus.MISSED)
            delayed = sum(1 for l in logs if l.status == AdherenceStatus.DELAYED)
            skipped = sum(1 for l in logs if l.status == AdherenceStatus.SKIPPED)
            pending = sum(1 for l in logs if l.status == AdherenceStatus.PENDING)
            
            total_expected = taken + missed + delayed + skipped + pending
            adherent = taken + delayed
            
            return {
                "date": target.isoformat(),
                "total_scheduled": total_expected,
                "taken": taken,
                "missed": missed,
                "delayed": delayed,
                "skipped": skipped,
                "pending": pending,
                "adherence_rate": round((adherent / total_expected) * 100, 1) if total_expected > 0 else 100.0
            }
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def get_weekly_trend(
        self,
        patient_id: int,
        weeks: int = 4,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get weekly adherence trends"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            trends = []
            today = date.today()
            
            for week in range(weeks):
                week_end = today - timedelta(days=7 * week)
                week_start = week_end - timedelta(days=6)
                
                start_dt = datetime.combine(week_start, datetime.min.time())
                end_dt = datetime.combine(week_end, datetime.max.time())
                
                logs = session.query(models.AdherenceLog).filter(
                    and_(
                        models.AdherenceLog.patient_id == patient_id,
                        models.AdherenceLog.logged_at >= start_dt,
                        models.AdherenceLog.logged_at <= end_dt
                    )
                ).all()
                
                if logs:
                    total = len(logs)
                    adherent = sum(
                        1 for l in logs 
                        if l.status in [AdherenceStatus.TAKEN, AdherenceStatus.DELAYED]
                    )
                    rate = (adherent / total) * 100
                else:
                    total = 0
                    rate = 0.0
                
                trends.append({
                    "week_start": week_start.isoformat(),
                    "week_end": week_end.isoformat(),
                    "total_doses": total,
                    "adherence_rate": round(rate, 1)
                })
            
            return trends
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)
    
    async def identify_problem_times(
        self,
        patient_id: int,
        days: int = 30,
        db: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Identify times of day with highest missed dose rates"""
        def _get(session: Session) -> List[Dict[str, Any]]:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            logs = session.query(models.AdherenceLog).filter(
                and_(
                    models.AdherenceLog.patient_id == patient_id,
                    models.AdherenceLog.logged_at >= start_date,
                    models.AdherenceLog.scheduled_time.isnot(None)
                )
            ).all()
            
            # Group by hour
            hourly_stats = defaultdict(lambda: {"total": 0, "missed": 0})
            
            for log in logs:
                if log.scheduled_time:
                    hour = log.scheduled_time.hour
                    hourly_stats[hour]["total"] += 1
                    if log.status == AdherenceStatus.MISSED:
                        hourly_stats[hour]["missed"] += 1
            
            # Calculate miss rate and identify problems
            problem_times = []
            for hour, stats in hourly_stats.items():
                if stats["total"] > 0:
                    miss_rate = (stats["missed"] / stats["total"]) * 100
                    if miss_rate > 20:  # More than 20% missed
                        time_label = f"{hour:02d}:00"
                        if hour < 12:
                            period = "morning"
                        elif hour < 17:
                            period = "afternoon"
                        else:
                            period = "evening"
                        
                        problem_times.append({
                            "hour": hour,
                            "time_label": time_label,
                            "period": period,
                            "miss_rate": round(miss_rate, 1),
                            "total_doses": stats["total"],
                            "missed_doses": stats["missed"]
                        })
            
            # Sort by miss rate (highest first)
            problem_times.sort(key=lambda x: x["miss_rate"], reverse=True)
            return problem_times
        
        if db:
            return _get(db)
        
        with get_db_context() as session:
            return _get(session)


# Singleton instance
adherence_service = AdherenceService()
