"""
Schedules API Router
Endpoints for medication schedule management
"""

from typing import List, Optional
from datetime import time
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from api.deps import get_db, services


router = APIRouter(prefix="/schedules", tags=["schedules"])


# ==================== REQUEST SCHEMAS ====================

class ScheduleCreate(BaseModel):
    """Schema for creating a schedule"""
    patient_id: int
    medication_id: int
    scheduled_time: str = Field(..., description="Time in HH:MM format")
    day_of_week: Optional[List[int]] = Field(None, description="Days 0-6, None for daily")
    reminder_enabled: bool = True
    reminder_minutes_before: int = Field(default=15, ge=0, le=120)
    window_start_minutes: int = Field(default=30, ge=0)
    window_end_minutes: int = Field(default=60, ge=0)
    notes: Optional[str] = None


class ScheduleUpdate(BaseModel):
    """Schema for updating a schedule"""
    scheduled_time: Optional[str] = None
    day_of_week: Optional[List[int]] = None
    reminder_enabled: Optional[bool] = None
    reminder_minutes_before: Optional[int] = Field(None, ge=0, le=120)
    window_start_minutes: Optional[int] = Field(None, ge=0)
    window_end_minutes: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None
    active: Optional[bool] = None


class OptimizedSchedule(BaseModel):
    """Optimized schedule entry"""
    medication_id: int
    scheduled_time: str
    reminder_enabled: bool = True
    notes: Optional[str] = None


class ScheduleOptimizeRequest(BaseModel):
    """Request for schedule optimization"""
    patient_id: int
    optimized_times: List[OptimizedSchedule]


# ==================== RESPONSE SCHEMAS ====================

class ScheduleResponse(BaseModel):
    """Schema for schedule response"""
    id: int
    patient_id: int
    medication_id: Optional[int]
    scheduled_time: str
    day_of_week: Optional[List[int]]
    reminder_enabled: bool
    reminder_minutes_before: int
    window_start_minutes: int
    window_end_minutes: int
    notes: Optional[str]
    active: bool

    class Config:
        from_attributes = True


class TodaysDose(BaseModel):
    """Today's scheduled dose"""
    schedule_id: int
    medication_id: int
    medication_name: str
    dosage: str
    scheduled_time: str
    window_start: str
    window_end: str
    status: str
    reminder_enabled: bool
    notes: Optional[str]
    with_food: bool


class UpcomingDose(BaseModel):
    """Upcoming dose"""
    schedule_id: int
    medication_name: str
    dosage: str
    scheduled_time: str
    minutes_until: int
    reminder_enabled: bool


class OverdueDose(BaseModel):
    """Overdue dose"""
    schedule_id: int
    medication_id: int
    medication_name: str
    dosage: str
    scheduled_time: str
    window_end: str
    minutes_overdue: int


class ScheduleSummary(BaseModel):
    """Schedule summary by time period"""
    total_daily_doses: int
    morning: List[dict]
    afternoon: List[dict]
    evening: List[dict]
    night: List[dict]


# ==================== ENDPOINTS ====================

@router.post("/", response_model=ScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    schedule_data: ScheduleCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new medication schedule
    """
    schedule_service = services.get_schedule_service()
    
    try:
        # Parse time string to time object
        hour, minute = map(int, schedule_data.scheduled_time.split(":"))
        scheduled_time = time(hour, minute)
        
        schedule = await schedule_service.create_schedule(
            patient_id=schedule_data.patient_id,
            medication_id=schedule_data.medication_id,
            scheduled_time=scheduled_time,
            day_of_week=schedule_data.day_of_week,
            reminder_enabled=schedule_data.reminder_enabled,
            reminder_minutes_before=schedule_data.reminder_minutes_before,
            window_start_minutes=schedule_data.window_start_minutes,
            window_end_minutes=schedule_data.window_end_minutes,
            notes=schedule_data.notes,
            db=db
        )
        
        return ScheduleResponse(
            id=schedule.id,
            patient_id=schedule.patient_id,
            medication_id=schedule.medication_id,
            scheduled_time=schedule.scheduled_time if isinstance(schedule.scheduled_time, str) else schedule.scheduled_time.strftime("%H:%M"),
            day_of_week=schedule.day_of_week,
            reminder_enabled=schedule.reminder_enabled,
            reminder_minutes_before=schedule.reminder_minutes_before,
            window_start_minutes=schedule.window_start_minutes,
            window_end_minutes=schedule.window_end_minutes,
            notes=schedule.notes,
            active=schedule.active
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/patient/{patient_id}", response_model=List[ScheduleResponse])
async def get_patient_schedules(
    patient_id: int,
    active_only: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Get all schedules for a patient
    """
    schedule_service = services.get_schedule_service()
    
    schedules = await schedule_service.get_patient_schedules(
        patient_id,
        active_only=active_only,
        db=db
    )
    
    return [
        ScheduleResponse(
            id=s.id,
            patient_id=s.patient_id,
            medication_id=s.medication_id,
            scheduled_time=s.scheduled_time if isinstance(s.scheduled_time, str) else s.scheduled_time.strftime("%H:%M") if s.scheduled_time else "00:00",
            day_of_week=s.day_of_week,
            reminder_enabled=s.reminder_enabled,
            reminder_minutes_before=s.reminder_minutes_before,
            window_start_minutes=s.window_start_minutes,
            window_end_minutes=s.window_end_minutes,
            notes=s.notes,
            active=s.active
        ) for s in schedules
    ]


@router.get("/{schedule_id}", response_model=ScheduleResponse)
async def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific schedule
    """
    schedule_service = services.get_schedule_service()
    
    schedule = await schedule_service.get_schedule(schedule_id, db=db)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return ScheduleResponse(
        id=schedule.id,
        patient_id=schedule.patient_id,
        medication_id=schedule.medication_id,
        scheduled_time=schedule.scheduled_time if isinstance(schedule.scheduled_time, str) else schedule.scheduled_time.strftime("%H:%M") if schedule.scheduled_time else "00:00",
        day_of_week=schedule.day_of_week,
        reminder_enabled=schedule.reminder_enabled,
        reminder_minutes_before=schedule.reminder_minutes_before,
        window_start_minutes=schedule.window_start_minutes,
        window_end_minutes=schedule.window_end_minutes,
        notes=schedule.notes,
        active=schedule.active
    )


@router.put("/{schedule_id}", response_model=ScheduleResponse)
async def update_schedule(
    schedule_id: int,
    schedule_data: ScheduleUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a schedule
    """
    schedule_service = services.get_schedule_service()
    
    updates = schedule_data.model_dump(exclude_unset=True, exclude_none=True)
    
    # Convert time string if provided
    if "scheduled_time" in updates and updates["scheduled_time"]:
        hour, minute = map(int, updates["scheduled_time"].split(":"))
        updates["scheduled_time"] = time(hour, minute)
    
    schedule = await schedule_service.update_schedule(schedule_id, updates, db=db)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return ScheduleResponse(
        id=schedule.id,
        patient_id=schedule.patient_id,
        medication_id=schedule.medication_id,
        scheduled_time=schedule.scheduled_time if isinstance(schedule.scheduled_time, str) else schedule.scheduled_time.strftime("%H:%M") if schedule.scheduled_time else "00:00",
        day_of_week=schedule.day_of_week,
        reminder_enabled=schedule.reminder_enabled,
        reminder_minutes_before=schedule.reminder_minutes_before,
        window_start_minutes=schedule.window_start_minutes,
        window_end_minutes=schedule.window_end_minutes,
        notes=schedule.notes,
        active=schedule.active
    )


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_schedule(
    schedule_id: int,
    db: Session = Depends(get_db)
):
    """
    Deactivate a schedule
    """
    schedule_service = services.get_schedule_service()
    
    schedule = await schedule_service.deactivate_schedule(schedule_id, db=db)
    
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule {schedule_id} not found"
        )
    
    return None


@router.get("/patient/{patient_id}/today", response_model=List[TodaysDose])
async def get_todays_schedule(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get today's medication schedule for a patient
    """
    schedule_service = services.get_schedule_service()
    
    doses = await schedule_service.get_todays_schedule(patient_id, db=db)
    
    return [TodaysDose(**d) for d in doses]


@router.get("/patient/{patient_id}/upcoming", response_model=List[UpcomingDose])
async def get_upcoming_doses(
    patient_id: int,
    hours: int = Query(4, ge=1, le=24),
    db: Session = Depends(get_db)
):
    """
    Get doses scheduled in the next few hours
    """
    schedule_service = services.get_schedule_service()
    
    doses = await schedule_service.get_upcoming_doses(
        patient_id,
        hours=hours,
        db=db
    )
    
    return [UpcomingDose(**d) for d in doses]


@router.get("/patient/{patient_id}/overdue", response_model=List[OverdueDose])
async def get_overdue_doses(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get overdue doses for today
    """
    schedule_service = services.get_schedule_service()
    
    doses = await schedule_service.get_overdue_doses(patient_id, db=db)
    
    return [OverdueDose(**d) for d in doses]


@router.get("/patient/{patient_id}/summary", response_model=ScheduleSummary)
async def get_schedule_summary(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get summary of patient's medication schedule by time period
    """
    schedule_service = services.get_schedule_service()
    
    summary = await schedule_service.get_schedule_summary(patient_id, db=db)
    
    return ScheduleSummary(**summary)


@router.post("/patient/{patient_id}/optimize")
async def optimize_schedule(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get schedule optimization recommendations
    """
    schedule_service = services.get_schedule_service()
    
    result = await schedule_service.optimize_schedule(patient_id, db=db)
    
    return result


@router.post("/patient/{patient_id}/apply-optimized", response_model=List[ScheduleResponse])
async def apply_optimized_schedule(
    patient_id: int,
    request: ScheduleOptimizeRequest,
    db: Session = Depends(get_db)
):
    """
    Apply optimized schedule times
    """
    schedule_service = services.get_schedule_service()
    
    optimized = [
        {
            "medication_id": opt.medication_id,
            "scheduled_time": opt.scheduled_time,
            "reminder_enabled": opt.reminder_enabled,
            "notes": opt.notes
        }
        for opt in request.optimized_times
    ]
    
    schedules = await schedule_service.create_schedules_from_optimizer(
        patient_id,
        optimized,
        db=db
    )
    
    return [
        ScheduleResponse(
            id=s.id,
            patient_id=s.patient_id,
            medication_id=s.medication_id,
            scheduled_time=s.scheduled_time if isinstance(s.scheduled_time, str) else s.scheduled_time.strftime("%H:%M") if s.scheduled_time else "00:00",
            day_of_week=s.day_of_week,
            reminder_enabled=s.reminder_enabled,
            reminder_minutes_before=s.reminder_minutes_before,
            window_start_minutes=s.window_start_minutes,
            window_end_minutes=s.window_end_minutes,
            notes=s.notes,
            active=s.active
        ) for s in schedules
    ]
