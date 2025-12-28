"""
Adherence API Router
Endpoints for medication adherence tracking
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Body
from sqlalchemy.orm import Session
from pydantic import ValidationError

from api.deps import get_db, services
from api.schemas.adherence import (
    AdherenceLogCreate,
    DoseTaken,
    DoseMissed,
    DoseSkipped,
    AdherenceLogResponse,
    AdherenceRate,
    AdherenceStreak,
    AdherenceByMedication,
    MedicationAdherence,
    AdherenceHistory,
    AdherenceHistoryEntry,
    DailySummary,
    WeeklyTrendList,
    WeeklyTrend,
    ProblemTimesResponse,
    ProblemTime,
    AdherenceDashboard,
)
from models import AdherenceStatus


router = APIRouter(prefix="/adherence", tags=["adherence"])


@router.post("/log", response_model=AdherenceLogResponse, status_code=status.HTTP_201_CREATED)
async def log_adherence(
    payload: dict = Body(...),
    db: Session = Depends(get_db)
):
    """
    Log a medication adherence event
    """
    adherence_service = services.get_adherence_service()
    # Normalize legacy/frontend payload shapes to the current schema
    data = dict(payload or {})

    # Legacy frontend keys mapping
    if "actual_time" in data and "taken_at" not in data:
        data["taken_at"] = data.pop("actual_time")
    if "scheduled_time" in data:
        # backend currently uses schedule_id as authoritative; keep scheduled_time if present
        data.setdefault("notes", f"scheduled_time={data.get('scheduled_time')}")
    # Map boolean `taken` / `skip_reason` to status
    if "status" not in data:
        if data.get("taken") is True:
            data["status"] = "taken"
        elif data.get("skip_reason"):
            data["status"] = "skipped"
        else:
            # default to missed if not explicit
            data["status"] = "missed"

    # Remove legacy keys that the schema does not expect
    for k in ("taken", "skip_reason", "scheduled_time", "actual_time"):
        data.pop(k, None)

    # If patient_id not provided, try to infer it from the schedule row
    if "patient_id" not in data and data.get("schedule_id"):
        from models import Schedule
        sched = db.query(Schedule).filter(Schedule.id == data.get("schedule_id")).first()
        if sched:
            data["patient_id"] = sched.patient_id

    # Ensure reported_by default
    data.setdefault("reported_by", "patient")

    # Validate against current schema
    try:
        log_body = AdherenceLogCreate(**data)
    except ValidationError as ve:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve))

    # Map string status to enum
    status_map = {
        "taken": AdherenceStatus.TAKEN,
        "missed": AdherenceStatus.MISSED,
        "skipped": AdherenceStatus.SKIPPED,
        "delayed": AdherenceStatus.DELAYED,
        "pending": AdherenceStatus.PENDING,
    }
    adherence_status = status_map.get(log_body.status.value, AdherenceStatus.PENDING)

    log = await adherence_service.log_adherence(
        patient_id=log_body.patient_id,
        schedule_id=log_body.schedule_id,
        medication_id=log_body.medication_id,
        status=adherence_status,
        taken_at=log_body.taken_at,
        deviation_minutes=log_body.deviation_minutes,
        notes=log_body.notes,
        reported_by=log_body.reported_by,
        db=db
    )

    return log


@router.post("/dose/taken", response_model=AdherenceLogResponse, status_code=status.HTTP_201_CREATED)
async def log_dose_taken(
    dose_data: DoseTaken,
    db: Session = Depends(get_db)
):
    """
    Quick log for a taken dose
    """
    adherence_service = services.get_adherence_service()
    
    log = await adherence_service.log_dose_taken(
        patient_id=dose_data.patient_id,
        schedule_id=dose_data.schedule_id,
        medication_id=dose_data.medication_id,
        taken_at=dose_data.taken_at,
        db=db
    )
    
    return log


@router.post("/dose/missed", response_model=AdherenceLogResponse, status_code=status.HTTP_201_CREATED)
async def log_dose_missed(
    dose_data: DoseMissed,
    db: Session = Depends(get_db)
):
    """
    Log a missed dose
    """
    adherence_service = services.get_adherence_service()
    
    log = await adherence_service.log_dose_missed(
        patient_id=dose_data.patient_id,
        schedule_id=dose_data.schedule_id,
        medication_id=dose_data.medication_id,
        reason=dose_data.reason,
        db=db
    )
    
    return log


@router.post("/dose/skipped", response_model=AdherenceLogResponse, status_code=status.HTTP_201_CREATED)
async def log_dose_skipped(
    dose_data: DoseSkipped,
    db: Session = Depends(get_db)
):
    """
    Log an intentionally skipped dose
    """
    adherence_service = services.get_adherence_service()
    
    log = await adherence_service.log_dose_skipped(
        patient_id=dose_data.patient_id,
        schedule_id=dose_data.schedule_id,
        medication_id=dose_data.medication_id,
        reason=dose_data.reason,
        db=db
    )
    
    return log


@router.get("/rate/{patient_id}", response_model=AdherenceRate)
async def get_adherence_rate(
    patient_id: int,
    days: int = Query(30, ge=1, le=365),
    medication_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get adherence rate for a patient
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_adherence_rate(
        patient_id=patient_id,
        days=days,
        medication_id=medication_id,
        db=db
    )
    
    return AdherenceRate(**result)


@router.get("/streak/{patient_id}", response_model=AdherenceStreak)
async def get_adherence_streak(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current and best adherence streaks
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_adherence_streak(patient_id, db=db)
    
    return AdherenceStreak(**result)


@router.get("/by-medication/{patient_id}", response_model=AdherenceByMedication)
async def get_adherence_by_medication(
    patient_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get adherence breakdown by medication
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_adherence_by_medication(
        patient_id=patient_id,
        days=days,
        db=db
    )
    
    return AdherenceByMedication(
        patient_id=patient_id,
        days_analyzed=days,
        medications=[
            MedicationAdherence(**m) for m in result
        ]
    )


@router.get("/history/{patient_id}", response_model=AdherenceHistory)
async def get_adherence_history(
    patient_id: int,
    days: int = Query(7, ge=1, le=90),
    medication_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get detailed adherence history
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_adherence_history(
        patient_id=patient_id,
        days=days,
        medication_id=medication_id,
        db=db
    )
    
    return AdherenceHistory(
        patient_id=patient_id,
        days=days,
        entries=[AdherenceHistoryEntry(**e) for e in result],
        total_entries=len(result)
    )


@router.get("/daily/{patient_id}", response_model=DailySummary)
async def get_daily_summary(
    patient_id: int,
    target_date: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get adherence summary for a specific day
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_daily_summary(
        patient_id=patient_id,
        target_date=target_date,
        db=db
    )
    
    return DailySummary(**result)


@router.get("/weekly-trend/{patient_id}", response_model=WeeklyTrendList)
async def get_weekly_trend(
    patient_id: int,
    weeks: int = Query(4, ge=1, le=12),
    db: Session = Depends(get_db)
):
    """
    Get weekly adherence trends
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.get_weekly_trend(
        patient_id=patient_id,
        weeks=weeks,
        db=db
    )
    
    return WeeklyTrendList(
        patient_id=patient_id,
        weeks=weeks,
        trends=[WeeklyTrend(**t) for t in result]
    )


@router.get("/problem-times/{patient_id}", response_model=ProblemTimesResponse)
async def get_problem_times(
    patient_id: int,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Identify times of day with highest missed dose rates
    """
    adherence_service = services.get_adherence_service()
    
    result = await adherence_service.identify_problem_times(
        patient_id=patient_id,
        days=days,
        db=db
    )
    
    recommendation = None
    if result:
        worst = result[0]
        recommendation = (
            f"Consider adjusting {worst['period']} doses. "
            f"Miss rate at {worst['time_label']} is {worst['miss_rate']}%"
        )
    
    return ProblemTimesResponse(
        patient_id=patient_id,
        days_analyzed=days,
        problem_times=[ProblemTime(**p) for p in result],
        recommendation=recommendation
    )


@router.get("/dashboard/{patient_id}", response_model=AdherenceDashboard)
async def get_adherence_dashboard(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get complete adherence dashboard data
    """
    adherence_service = services.get_adherence_service()
    
    # Gather all dashboard data
    overall_rate = await adherence_service.get_adherence_rate(patient_id, days=30, db=db)
    streak = await adherence_service.get_adherence_streak(patient_id, db=db)
    today = await adherence_service.get_daily_summary(patient_id, db=db)
    weekly_trends = await adherence_service.get_weekly_trend(patient_id, weeks=4, db=db)
    by_medication = await adherence_service.get_adherence_by_medication(patient_id, days=30, db=db)
    problem_times = await adherence_service.identify_problem_times(patient_id, days=30, db=db)
    
    return AdherenceDashboard(
        patient_id=patient_id,
        overall_rate=AdherenceRate(**overall_rate),
        streak=AdherenceStreak(**streak),
        today=DailySummary(**today),
        weekly_trends=[WeeklyTrend(**t) for t in weekly_trends],
        by_medication=[MedicationAdherence(**m) for m in by_medication],
        problem_times=[ProblemTime(**p) for p in problem_times]
    )
