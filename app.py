"""
AdherenceGuardian Backend
Main FastAPI application with multi-agent orchestration
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date, time
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
import os
import json

# Configuration and database
from config import settings, agent_config
from database import get_db, init_db, DatabaseHealthCheck

# Models
import models
from api import include_routers

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format=settings.LOG_FORMAT
)
logger = logging.getLogger(__name__)


# ==================== LIFESPAN ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup and shutdown"""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENV}")
    
    # Initialize database
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    # Initialize agents (lazy loading)
    logger.info("Agent orchestrator ready")
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}")


# ==================== APP INITIALIZATION ====================

app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## AdherenceGuardian API
    
    An Agentic AI System for Medication Adherence and Treatment Compliance.
    
    ### Features
    - **Intelligent Scheduling**: Optimizes medication timing based on lifestyle and drug interactions
    - **Adaptive Monitoring**: Learns individual patterns and adjusts interventions
    - **Barrier Resolution**: Proactively identifies and solves adherence obstacles
    - **Provider Communication**: Maintains structured logs and generates clinical summaries
    
    ### Agents
    - **Planning Agent**: Medication scheduling optimization
    - **Monitoring Agent**: Adherence tracking and anomaly detection
    - **Barrier Resolution Agent**: Identifies and resolves adherence barriers
    - **Healthcare Liaison Agent**: Provider communication and reporting
    """,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Attach modular API routers (prefix /api/v1)
include_routers(app)


# ==================== EXCEPTION HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "message": "An unexpected error occurred" if not settings.DEBUG else str(exc),
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


# ==================== PYDANTIC SCHEMAS ====================

class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    age: Optional[int] = None
    date_of_birth: Optional[date] = None
    conditions: List[str] = []
    allergies: List[str] = []
    timezone: str = "UTC"
    wake_time: Optional[time] = time(7, 0)
    sleep_time: Optional[time] = time(22, 0)
    breakfast_time: Optional[time] = time(8, 0)
    lunch_time: Optional[time] = time(12, 0)
    dinner_time: Optional[time] = time(19, 0)


class PatientUpdate(BaseModel):
    """Partial update schema for patient profile"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    age: Optional[int] = None
    date_of_birth: Optional[date] = None
    conditions: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    timezone: Optional[str] = None
    wake_time: Optional[time] = None
    sleep_time: Optional[time] = None
    breakfast_time: Optional[time] = None
    lunch_time: Optional[time] = None
    dinner_time: Optional[time] = None


def generate_schedule_times(start: time, end: time, count: int) -> List[str]:
    """Generate evenly spaced schedule times between wake and sleep."""
    if count <= 1:
        return [(start or time(8, 0)).strftime("%H:%M")]

    start_dt = datetime.combine(date.today(), start or time(8, 0))
    end_dt = datetime.combine(date.today(), end or time(22, 0))

    # If end wraps before start, default to 12 hours after start
    if end_dt <= start_dt:
        end_dt = start_dt + timedelta(hours=12)

    interval = (end_dt - start_dt) / (count - 1)
    return [
        (start_dt + (interval * i)).strftime("%H:%M")
        for i in range(count)
    ]


class PatientResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    conditions: List[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class MedicationCreate(BaseModel):
    name: str
    generic_name: Optional[str] = None
    dosage: str
    frequency: str
    frequency_per_day: int = 1
    with_food: bool = False
    instructions: Optional[str] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    start_date: Optional[date] = None
    custom_times: Optional[List[str]] = None


class MedicationResponse(BaseModel):
    id: int
    name: str
    dosage: str
    frequency: str
    with_food: bool
    active: bool
    adherence_rate: Optional[float] = None
    
    class Config:
        from_attributes = True


class SymptomReportCreate(BaseModel):
    medication_name: str
    symptom: str
    severity: int  # 1-10
    timing: str
    description: Optional[str] = None
    duration_minutes: Optional[int] = None


class CustomScheduleCreate(BaseModel):
    medication_id: int
    times: List[str]
    scheduled_date: Optional[date] = None
    meal_relation: Optional[str] = None
    notes: Optional[str] = None


class AdherenceLogCreate(BaseModel):
    medication_id: int
    taken: bool
    scheduled_time: datetime
    actual_time: Optional[datetime] = None
    notes: Optional[str] = None
    skip_reason: Optional[str] = None
    schedule_id: Optional[int] = None


class ChatMessage(BaseModel):
    patient_id: int
    message: str
    conversation_history: Optional[List[Dict[str, Any]]] = None
    context: Optional[Dict[str, Any]] = None


class ScheduleResponse(BaseModel):
    id: int
    time: str
    medications: List[str]
    status: str
    meal_relation: Optional[str] = None


# ==================== HEALTH ENDPOINTS ====================

@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - basic health check"""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check endpoint"""
    db_connected = DatabaseHealthCheck.is_connected()
    
    return {
        "status": "healthy" if db_connected else "degraded",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "database": {
                "status": "up" if db_connected else "down",
                "type": "sqlite" if "sqlite" in settings.DATABASE_URL else "postgresql"
            },
            "llm": {
                "provider": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
                "configured": bool(settings.ANTHROPIC_API_KEY or settings.OPENAI_API_KEY)
            },
            "agents": {
                "planning": "ready",
                "monitoring": "ready",
                "barrier": "ready",
                "liaison": "ready"
            }
        },
        "config": {
            "adherence_target": agent_config.MONITORING_ADHERENCE_TARGET,
            "anomaly_threshold": agent_config.MONITORING_ANOMALY_THRESHOLD
        },
        "version": settings.APP_VERSION,
        "environment": settings.ENV
    }


# ==================== PATIENT ENDPOINTS ====================

@app.post(f"{settings.API_PREFIX}/patients", tags=["Patients"])
async def create_patient(patient: PatientCreate, db: Session = Depends(get_db)):
    """Create a new patient profile"""
    # Check if email already exists
    existing = db.query(models.Patient).filter(models.Patient.email == patient.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    db_patient = models.Patient(
        first_name=patient.first_name,
        last_name=patient.last_name,
        email=patient.email,
        phone=patient.phone,
        age=patient.age,
        date_of_birth=patient.date_of_birth,
        conditions=patient.conditions,
        allergies=patient.allergies,
        timezone=patient.timezone or "UTC",
        wake_time=patient.wake_time,
        sleep_time=patient.sleep_time,
        breakfast_time=patient.breakfast_time,
        lunch_time=patient.lunch_time,
        dinner_time=patient.dinner_time
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)
    
    logger.info(f"Created patient: {db_patient.id} - {db_patient.full_name}")
    
    return {
        "id": db_patient.id,
        "first_name": db_patient.first_name,
        "last_name": db_patient.last_name,
        "name": db_patient.full_name,
        "email": db_patient.email,
        "phone": db_patient.phone,
        "date_of_birth": db_patient.date_of_birth,
        "conditions": db_patient.conditions or [],
        "allergies": db_patient.allergies or [],
        "timezone": db_patient.timezone or "UTC",
        "wake_time": str(db_patient.wake_time) if db_patient.wake_time else None,
        "sleep_time": str(db_patient.sleep_time) if db_patient.sleep_time else None,
        "breakfast_time": str(db_patient.breakfast_time) if db_patient.breakfast_time else None,
        "lunch_time": str(db_patient.lunch_time) if db_patient.lunch_time else None,
        "dinner_time": str(db_patient.dinner_time) if db_patient.dinner_time else None,
        "notification_preferences": db_patient.notification_preferences or {},
        "created_at": db_patient.created_at,
        "updated_at": db_patient.updated_at,
        "is_active": db_patient.is_active,
        "message": "Patient created successfully"
    }


@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}", tags=["Patients"])
async def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get patient details"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    return {
        "id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "full_name": patient.full_name,
        "email": patient.email,
        "phone": patient.phone,
        "age": patient.age,
        "conditions": patient.conditions,
        "allergies": patient.allergies,
        "timezone": patient.timezone,
        "lifestyle": {
            "wake_time": str(patient.wake_time) if patient.wake_time else None,
            "sleep_time": str(patient.sleep_time) if patient.sleep_time else None,
            "breakfast_time": str(patient.breakfast_time) if patient.breakfast_time else None,
            "lunch_time": str(patient.lunch_time) if patient.lunch_time else None,
            "dinner_time": str(patient.dinner_time) if patient.dinner_time else None
        },
        "created_at": patient.created_at,
        "is_active": patient.is_active
    }


@app.put(f"{settings.API_PREFIX}/patients/{{patient_id}}", tags=["Patients"])
async def update_patient(
    patient_id: int,
    patient_data: PatientUpdate,
    db: Session = Depends(get_db)
):
    """Update patient profile fields (including timezone and contact info)"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_fields = patient_data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)

    return {
        "id": patient.id,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "email": patient.email,
        "phone": patient.phone,
        "date_of_birth": patient.date_of_birth,
        "conditions": patient.conditions or [],
        "allergies": patient.allergies or [],
        "timezone": patient.timezone,
        "wake_time": str(patient.wake_time) if patient.wake_time else None,
        "sleep_time": str(patient.sleep_time) if patient.sleep_time else None,
        "breakfast_time": str(patient.breakfast_time) if patient.breakfast_time else None,
        "lunch_time": str(patient.lunch_time) if patient.lunch_time else None,
        "dinner_time": str(patient.dinner_time) if patient.dinner_time else None,
        "notification_preferences": patient.notification_preferences or {},
        "created_at": patient.created_at,
        "updated_at": patient.updated_at,
        "is_active": patient.is_active
    }


@app.delete(f"{settings.API_PREFIX}/patients/{{patient_id}}", tags=["Patients"])
async def delete_patient(patient_id: int, db: Session = Depends(get_db)):
    """Delete a patient account and related data"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    db.delete(patient)
    db.commit()

    return {"message": "Patient account deleted", "patient_id": patient_id}


@app.get(f"{settings.API_PREFIX}/patients", tags=["Patients"])
async def list_patients(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all patients"""
    patients = db.query(models.Patient).filter(
        models.Patient.is_active == True
    ).offset(skip).limit(limit).all()
    
    return [
        {
            "id": p.id,
            "name": p.full_name,
            "email": p.email,
            "conditions": p.conditions,
            "created_at": p.created_at
        }
        for p in patients
    ]


# ==================== MEDICATION ENDPOINTS ====================

@app.post(f"{settings.API_PREFIX}/patients/{{patient_id}}/medications", tags=["Medications"])
async def add_medication(
    patient_id: int, 
    medication: MedicationCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Add medication and trigger planning agent"""
    # Verify patient exists
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo("UTC")
    today_local = datetime.now(tz).date()
    
    # Create medication and (optionally) its initial schedule atomically
    db_med = models.Medication(
        patient_id=patient_id,
        name=medication.name,
        generic_name=medication.generic_name,
        dosage=medication.dosage,
        frequency=medication.frequency,
        frequency_per_day=medication.frequency_per_day,
        with_food=medication.with_food,
        instructions=medication.instructions,
        purpose=medication.purpose,
        notes=medication.notes,
        start_date=medication.start_date or date.today()
    )
    db.add(db_med)
    # Flush to assign an id without committing the transaction so schedule rows are created atomically
    db.flush()

    # Persist a recurring schedule template on the medication so it can be generated daily
    if getattr(medication, 'custom_times', None):
        recurring = medication.custom_times
    else:
        recurring = generate_schedule_times(
            patient.wake_time or time(8, 0),
            patient.sleep_time or time(22, 0),
            medication.frequency_per_day or 1
        )
    # Save recurring times on medication for on-demand generation
    try:
        db_med.recurring_times = recurring
        db.add(db_med)
    except Exception:
        # best-effort: ignore if DB doesn't accept it
        pass

    # Seed only today's schedule (future days will be generated on-demand)
    for t in recurring:
        entry = models.Schedule(
            patient_id=patient_id,
            medication_id=db_med.id,
            medications_list=[db_med.name],
            scheduled_date=today_local,
            scheduled_time=t,
            status="pending",
            meal_relation="with_meal" if medication.with_food else None,
            notes=f"Timezone: {patient.timezone or 'UTC'}"
        )
        db.add(entry)

    # Commit both medication and schedule rows together
    db.commit()
    db.refresh(db_med)
    
    # Log agent activity
    activity = models.AgentActivity(
        patient_id=patient_id,
        agent_name="Planning",
        agent_type=models.AgentType.PLANNING,
        action="New medication added - scheduling optimization triggered",
        activity_type="planning",
        input_data={"medication_id": db_med.id, "medication_name": db_med.name}
    )
    db.add(activity)
    db.commit()
    
    # TODO: Trigger planning agent in background
    # background_tasks.add_task(orchestrator.handle_new_medication, patient_id, db_med.id)
    
    logger.info(f"Added medication {db_med.name} for patient {patient_id}")
    
    return {
        "medication_id": db_med.id,
        "message": "Medication added. Planning agent is optimizing schedule...",
        "medication": {
            "name": db_med.name,
            "dosage": db_med.dosage,
            "frequency": db_med.frequency
        }
    }


@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/medications", tags=["Medications"])
async def get_medications(patient_id: int, active_only: bool = False, db: Session = Depends(get_db)):
    """Get all medications for a patient"""
    query = db.query(models.Medication).filter(models.Medication.patient_id == patient_id)
    
    if active_only:
        query = query.filter(models.Medication.active == True)
    
    medications = query.all()
    
    return [
        {
            "id": med.id,
            "name": med.name,
            "generic_name": med.generic_name,
            "dosage": med.dosage,
            "frequency": med.frequency,
            "frequency_per_day": med.frequency_per_day,
            "with_food": med.with_food,
            "instructions": med.instructions,
            "purpose": med.purpose,
            "active": med.active,
            "start_date": med.start_date,
            "adherence_rate": calculate_adherence(db, med.id)
        }
        for med in medications
    ]


class MedicationUpdate(BaseModel):
    """Schema for updating medication"""
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    frequency_per_day: Optional[int] = None
    instructions: Optional[str] = None
    with_food: Optional[bool] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


@app.put(f"{settings.API_PREFIX}/patients/{{patient_id}}/medications/{{medication_id}}", tags=["Medications"])
async def update_medication(
    patient_id: int,
    medication_id: int,
    medication_data: MedicationUpdate,
    db: Session = Depends(get_db)
):
    """Update a medication"""
    # Verify medication exists and belongs to patient
    medication = db.query(models.Medication).filter(
        models.Medication.id == medication_id,
        models.Medication.patient_id == patient_id
    ).first()
    
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    # Update fields
    update_data = medication_data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in update_data.items():
        setattr(medication, field, value)
    
    db.commit()
    db.refresh(medication)
    
    logger.info(f"Updated medication {medication_id} for patient {patient_id}")
    
    return {
        "id": medication.id,
        "name": medication.name,
        "generic_name": medication.generic_name,
        "dosage": medication.dosage,
        "frequency": medication.frequency,
        "frequency_per_day": medication.frequency_per_day,
        "with_food": medication.with_food,
        "instructions": medication.instructions,
        "purpose": medication.purpose,
        "active": medication.active,
        "start_date": medication.start_date
    }


@app.delete(f"{settings.API_PREFIX}/patients/{{patient_id}}/medications/{{medication_id}}", tags=["Medications"])
async def delete_medication(
    patient_id: int,
    medication_id: int,
    db: Session = Depends(get_db)
):
    """Delete a medication"""
    # Verify medication exists and belongs to patient
    medication = db.query(models.Medication).filter(
        models.Medication.id == medication_id,
        models.Medication.patient_id == patient_id
    ).first()
    
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")
    
    db.delete(medication)
    db.commit()
    
    logger.info(f"Deleted medication {medication_id} for patient {patient_id}")
    
    return {"message": "Medication deleted successfully"}


 


# ==================== SCHEDULE ENDPOINTS ====================

@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/schedule/today", tags=["Schedules"])
async def get_today_schedule(patient_id: int, db: Session = Depends(get_db)):
    """Get today's medication schedule"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo("UTC")
    today = datetime.now(tz).date()
    
    # Ensure schedule rows exist for today for active medications: generate on-demand from medication.recurring_times
    active_meds = db.query(models.Medication).filter(
        models.Medication.patient_id == patient_id,
        models.Medication.active == True
    ).all()

    for med in active_meds:
        exists = db.query(models.Schedule).filter(
            models.Schedule.patient_id == patient_id,
            models.Schedule.medication_id == med.id,
            models.Schedule.scheduled_date == today
        ).first()
        if not exists:
            # Build today's entries from med.recurring_times if present, otherwise infer
            times = med.recurring_times if getattr(med, 'recurring_times', None) else None
            if not times:
                times = generate_schedule_times(
                    patient.wake_time or time(8, 0),
                    patient.sleep_time or time(22, 0),
                    med.frequency_per_day or 1
                )
            for t in times:
                entry = models.Schedule(
                    patient_id=patient_id,
                    medication_id=med.id,
                    medications_list=[med.name],
                    scheduled_date=today,
                    scheduled_time=t,
                    status="pending",
                    meal_relation=None,
                    notes=f"Timezone: {patient.timezone or 'UTC'} (generated)"
                )
                db.add(entry)
    db.commit()

    # If there are no pending doses for today, proactively compute the next
    # occurrence from each medication's recurring_times and create schedule
    # rows for the next date (commonly tomorrow). This ensures callers of
    # /schedule/today can see the upcoming dose even if it's on the next day.
    now = datetime.now(tz)
    # Query today's schedules we just ensured exist
    schedules_today = db.query(models.Schedule).filter(
        models.Schedule.patient_id == patient_id,
        models.Schedule.scheduled_date == today
    ).order_by(models.Schedule.scheduled_time).all()

    pending_today = [s for s in schedules_today if s.status == 'pending']
    if len(pending_today) == 0:
        # No pending today; create next-occurrence rows for meds where the
        # next scheduled datetime is after today (usually tomorrow).
        created_next = []
        for med in active_meds:
            times = med.recurring_times if getattr(med, 'recurring_times', None) else None
            logger.info(f"Med {med.id} recurring_times: {times}")
            if not times:
                times = generate_schedule_times(
                    patient.wake_time or time(8, 0),
                    patient.sleep_time or time(22, 0),
                    med.frequency_per_day or 1
                )
            logger.info(f"Med {med.id} times used for next-occurrence calculation: {times}")

            # Find the earliest next datetime for this med (today or tomorrow)
            candidates: List[datetime] = []
            for t in times:
                try:
                    h, m = map(int, t.split(':'))
                except Exception:
                    continue
                dt_today = datetime.combine(today, time(h, m))
                dt_today = dt_today.replace(tzinfo=tz)
                if dt_today > now:
                    candidates.append(dt_today)
                else:
                    candidates.append(dt_today + timedelta(days=1))

            logger.info(f"Med {med.id} candidate datetimes (tz-aware): {candidates}")
            if not candidates:
                continue
            # Prefer candidates that fall after today (e.g., tomorrow). If none,
            # skip this med — we only want to create next-day rows here.
            future_candidates = [c for c in candidates if c.date() > today]
            if not future_candidates:
                logger.info(f"Med {med.id} has no candidates after today, skipping")
                continue
            next_dt = min(future_candidates)
            logger.info(f"Med {med.id} selected next_dt (after today): {next_dt.isoformat()}")

            # Create schedule rows for the target date (usually tomorrow).
            # We must create the full set of expected times for that date so
            # when the date rolls over we don't have only a single persisted
            # row (which previously blocked creation of the remaining doses).
            target_date = next_dt.date()
            # Query which times already exist for that med on the target date
            existing_times = {
                s.scheduled_time for s in db.query(models.Schedule).filter(
                    models.Schedule.patient_id == patient_id,
                    models.Schedule.medication_id == med.id,
                    models.Schedule.scheduled_date == target_date
                ).all()
            }

            created_for_med: List[models.Schedule] = []
            for t in times:
                if t in existing_times:
                    continue
                logger.info(f"Creating next-day schedule for med {med.id} at {t} on {target_date.isoformat()}")
                entry = models.Schedule(
                    patient_id=patient_id,
                    medication_id=med.id,
                    medications_list=[med.name],
                    scheduled_date=target_date,
                    scheduled_time=t,
                    status="pending",
                    meal_relation=None,
                    notes=f"Timezone: {patient.timezone or 'UTC'} (generated-next)"
                )
                db.add(entry)
                created_for_med.append(entry)

            if created_for_med:
                created_next.extend(created_for_med)

        if created_next:
            db.commit()
            # append newly created entries to schedules_today so they are returned
            schedules_today.extend(created_next)
        # Use schedules_today as the source for response below
        schedules = schedules_today
    else:
        schedules = schedules_today

    # `schedules` already holds today's schedule rows and may include
    # next-occurrence entries we created above. Return that combined list.
    # Map ORM schedule rows to serializable dicts
    mapped = [
        {
            "id": s.id,
            "medication_id": s.medication_id,
            "medication_name": s.medication.name if s.medication else (s.medications_list or ["Unknown"])[0],
            "dosage": s.medication.dosage if s.medication else "",
            "time": s.scheduled_time,
            "scheduled_date": s.scheduled_date.isoformat() if hasattr(s, 'scheduled_date') else None,
            "is_next": (s.scheduled_date != today) if hasattr(s, 'scheduled_date') else False,
            "medications": s.medications_list or [],
            "status": s.status,
            "meal_relation": s.meal_relation,
            "reminder_sent": s.reminder_sent,
            "notes": s.notes
        }
        for s in schedules
    ]

    # Compute non-persistent next-occurrence entries for each active medication
    # and append them to the mapped list if no existing next entry exists.
    now = datetime.now(tz)
    for med in active_meds:
        try:
            # Prefer any persisted future schedule rows for this medication
            future_row = db.query(models.Schedule).filter(
                models.Schedule.medication_id == med.id,
                models.Schedule.scheduled_date > today
            ).order_by(models.Schedule.scheduled_date, models.Schedule.scheduled_time).first()

            if future_row:
                next_dt = datetime.combine(future_row.scheduled_date, datetime.strptime(future_row.scheduled_time, '%H:%M').time()).replace(tzinfo=tz)
                if next_dt <= now:
                    # if persisted future row isn't actually in the future (unlikely), skip
                    continue
                exists = any(
                    (m.get('medication_id') == med.id and m.get('time') == next_dt.strftime('%H:%M') and m.get('scheduled_date') == next_dt.date().isoformat())
                    for m in mapped
                )
                if not exists:
                    mapped.append({
                        "id": future_row.id,
                        "medication_id": med.id,
                        "medication_name": future_row.medications_list[0] if future_row.medications_list else med.name,
                        "dosage": med.dosage or "",
                        "time": next_dt.strftime('%H:%M'),
                        "scheduled_date": next_dt.date().isoformat(),
                        "is_next": future_row.scheduled_date != today,
                        "medications": future_row.medications_list or [med.name],
                        "status": future_row.status,
                        "meal_relation": future_row.meal_relation,
                        "reminder_sent": future_row.reminder_sent,
                        "notes": future_row.notes or f"Timezone: {patient.timezone or 'UTC'} (persisted-next)"
                    })
                continue

            # Fall back to recurring_times generation
            times = med.recurring_times if getattr(med, 'recurring_times', None) else None
            if not times:
                times = generate_schedule_times(
                    patient.wake_time or time(8, 0),
                    patient.sleep_time or time(22, 0),
                    med.frequency_per_day or 1
                )

            candidates: List[datetime] = []
            for t in times:
                try:
                    h, m = map(int, t.split(':'))
                except Exception:
                    continue
                dt_today = datetime.combine(today, time(h, m)).replace(tzinfo=tz)
                if dt_today > now:
                    candidates.append(dt_today)
                else:
                    candidates.append(dt_today + timedelta(days=1))

            # pick the earliest candidate that's after now
            next_candidates = [c for c in candidates if c > now]
            if not next_candidates:
                continue
            next_dt = min(next_candidates)

            # skip if mapped already contains this med/time/date
            exists = any(
                (m.get('medication_id') == med.id and m.get('time') == next_dt.strftime('%H:%M') and m.get('scheduled_date') == next_dt.date().isoformat())
                for m in mapped
            )
            if exists:
                continue

            mapped.append({
                "id": None,
                "medication_id": med.id,
                "medication_name": med.name,
                "dosage": med.dosage or "",
                "time": next_dt.strftime('%H:%M'),
                "scheduled_date": next_dt.date().isoformat(),
                "is_next": True,
                "medications": [med.name],
                "status": "pending",
                "meal_relation": None,
                "reminder_sent": False,
                "notes": f"Timezone: {patient.timezone or 'UTC'} (computed-next)"
            })
        except Exception:
            continue

    return mapped


@app.post(f"{settings.API_PREFIX}/patients/{{patient_id}}/schedule/custom", tags=["Schedules"])
async def create_custom_schedule(
    patient_id: int,
    schedule_req: CustomScheduleCreate,
    db: Session = Depends(get_db)
):
    """Create custom schedule entries for a medication using explicit times (local timezone)."""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    medication = db.query(models.Medication).filter(
        models.Medication.id == schedule_req.medication_id,
        models.Medication.patient_id == patient_id
    ).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found for patient")

    scheduled_date = schedule_req.scheduled_date or date.today()
    created = []
    # Remove any existing schedule entries for this medication on the scheduled date
    db.query(models.Schedule).filter(
        models.Schedule.patient_id == patient_id,
        models.Schedule.medication_id == medication.id,
        models.Schedule.scheduled_date == scheduled_date
    ).delete()
    db.commit()
    for t in schedule_req.times:
        entry = models.Schedule(
            patient_id=patient_id,
            medication_id=medication.id,
            medications_list=[medication.name],
            scheduled_date=scheduled_date,
            scheduled_time=t,
            status="pending",
            meal_relation=schedule_req.meal_relation,
            notes=schedule_req.notes or f"Timezone: {patient.timezone or 'UTC'}"
        )
        db.add(entry)
        created.append(entry)
    db.commit()

    return [
        {
            "id": s.id,
            "time": s.scheduled_time,
            "medications": s.medications_list or [],
            "status": s.status,
            "meal_relation": s.meal_relation,
            "notes": s.notes
        }
        for s in created
    ]


@app.post(f"{settings.API_PREFIX}/patients/{{patient_id}}/schedule/regenerate", tags=["Schedules"])
async def regenerate_schedule(
    patient_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger planning agent to regenerate schedule"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Log activity
    activity = models.AgentActivity(
        patient_id=patient_id,
        agent_name="Planning",
        agent_type=models.AgentType.PLANNING,
        action="Schedule regeneration requested",
        activity_type="planning"
    )
    db.add(activity)
    db.commit()
    
    # TODO: Trigger planning agent
    # background_tasks.add_task(orchestrator.planning_agent.create_schedule, patient_id)
    
    return {
        "message": "Schedule regeneration triggered",
        "status": "processing",
        "patient_id": patient_id
    }


# ==================== ADHERENCE ENDPOINTS ====================

@app.post(f"{settings.API_PREFIX}/adherence/log", tags=["Adherence"])
async def log_adherence(
    log: AdherenceLogCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Log medication adherence and trigger monitoring agent"""
    # Verify medication exists
    medication = db.query(models.Medication).filter(models.Medication.id == log.medication_id).first()
    if not medication:
        raise HTTPException(status_code=404, detail="Medication not found")

    schedule_row = None
    if log.schedule_id:
        schedule_row = db.query(models.Schedule).filter(
            models.Schedule.id == log.schedule_id,
            models.Schedule.patient_id == medication.patient_id
        ).first()

    # Determine patient's timezone and normalize times for accurate day grouping
    patient = medication.patient
    tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo("UTC")

    # Normalize scheduled_time and actual_time to timezone-aware datetimes
    scheduled_dt = log.scheduled_time
    if scheduled_dt.tzinfo is None:
        # assume incoming times are in UTC if naive
        scheduled_dt = scheduled_dt.replace(tzinfo=ZoneInfo('UTC'))
    # Convert scheduled to patient local tz for date comparisons
    scheduled_local = scheduled_dt.astimezone(tz)

    actual_dt = log.actual_time
    if actual_dt:
        if actual_dt.tzinfo is None:
            actual_dt = actual_dt.replace(tzinfo=ZoneInfo('UTC'))
        actual_local = actual_dt.astimezone(tz)
    else:
        actual_local = None

    # Calculate deviation if applicable (use localized datetimes)
    deviation_minutes = None
    if actual_local and log.taken:
        delay = actual_local - scheduled_local
        deviation_minutes = int(delay.total_seconds() / 60) if delay.total_seconds() > 0 else 0

    # Determine status
    status = models.AdherenceStatus.TAKEN if log.taken else models.AdherenceStatus.MISSED
    if log.skip_reason:
        status = models.AdherenceStatus.SKIPPED
    elif deviation_minutes and deviation_minutes > 30:
        status = models.AdherenceStatus.DELAYED

    # Store times in UTC in the DB for consistency
    db_log = models.AdherenceLog(
        patient_id=medication.patient_id,
        medication_id=log.medication_id,
        scheduled_time=scheduled_local.astimezone(ZoneInfo('UTC')),
        actual_time=(actual_local.astimezone(ZoneInfo('UTC')) if actual_local else datetime.utcnow()),
        taken=log.taken,
        status=status,
        deviation_minutes=deviation_minutes,
        skip_reason=log.skip_reason,
        notes=log.notes
    )
    db.add(db_log)

    # Update schedule status if present
    # If a schedule row was provided, make sure it corresponds to the same local date/time
    if schedule_row:
        # If the schedule row's date doesn't match the localized scheduled date, try to find the correct row
        if schedule_row.scheduled_date != scheduled_local.date():
            alt = db.query(models.Schedule).filter(
                models.Schedule.patient_id == medication.patient_id,
                models.Schedule.medication_id == medication.id,
                models.Schedule.scheduled_date == scheduled_local.date(),
                models.Schedule.scheduled_time == scheduled_local.strftime("%H:%M")
            ).first()
            if alt:
                schedule_row = alt

        schedule_row.status = status.value
        schedule_row.updated_at = datetime.utcnow()
        db.add(schedule_row)

    db.commit()
    db.refresh(db_log)

    # Log monitoring activity
    activity = models.AgentActivity(
        patient_id=medication.patient_id,
        agent_name="Monitoring",
        agent_type=models.AgentType.MONITORING,
        action=f"Adherence logged: {'Taken' if log.taken else 'Missed'}",
        activity_type="monitoring",
        input_data={"medication_id": log.medication_id, "taken": log.taken, "schedule_id": log.schedule_id}
    )
    db.add(activity)
    db.commit()

    # TODO: Trigger monitoring agent
    # background_tasks.add_task(orchestrator.monitoring_agent.analyze_adherence, log.medication_id)

    return {
        "message": "Adherence logged successfully",
        "status": status.value,
        "monitoring_active": True,
        "schedule_id": log.schedule_id
    }


@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/adherence/stats", tags=["Adherence"])
async def get_adherence_stats(patient_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Get adherence statistics"""
    # Compute start datetime in patient's timezone and convert to UTC for DB filtering
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    tz = ZoneInfo(patient.timezone) if patient and patient.timezone else ZoneInfo('UTC')
    now_local = datetime.now(tz)
    start_local = now_local - timedelta(days=days)
    # Convert start_local to UTC to compare against stored UTC scheduled_time
    start_utc = start_local.astimezone(ZoneInfo('UTC'))

    logs = db.query(models.AdherenceLog).join(models.Medication).filter(
        models.Medication.patient_id == patient_id,
        models.AdherenceLog.scheduled_time >= start_utc
    ).all()
    
    total = len(logs)
    taken = len([log for log in logs if log.taken])
    missed = len([log for log in logs if log.status == models.AdherenceStatus.MISSED])
    delayed = len([log for log in logs if log.status == models.AdherenceStatus.DELAYED])
    
    adherence_rate = (taken / total * 100) if total > 0 else 0
    target_met = adherence_rate >= (agent_config.MONITORING_ADHERENCE_TARGET * 100)
    
    return {
        "period_days": days,
        "total_doses": total,
        "doses_taken": taken,
        "doses_missed": missed,
        "doses_delayed": delayed,
        "adherence_rate": round(adherence_rate, 2),
        "target_rate": agent_config.MONITORING_ADHERENCE_TARGET * 100,
        "target_met": target_met,
        "current_streak": calculate_streak(logs),
        "trend": calculate_trend(logs)
    }


@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/adherence/daily", tags=["Adherence"])
async def get_adherence_daily(patient_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Return daily adherence metrics for the past `days` days for charting."""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    tz = ZoneInfo(patient.timezone) if patient.timezone else ZoneInfo('UTC')
    today_local = datetime.now(tz).date()

    results = []
    for i in range(days - 1, -1, -1):
        day_local = today_local - timedelta(days=i)
        # day start/end in patient local tz
        day_start_local = datetime.combine(day_local, datetime.min.time()).replace(tzinfo=tz)
        day_end_local = datetime.combine(day_local, datetime.max.time()).replace(tzinfo=tz)
        # convert to UTC for stored times
        day_start_utc = day_start_local.astimezone(ZoneInfo('UTC'))
        day_end_utc = day_end_local.astimezone(ZoneInfo('UTC'))

        logs = db.query(models.AdherenceLog).filter(
            models.AdherenceLog.patient_id == patient_id,
            models.AdherenceLog.scheduled_time >= day_start_utc,
            models.AdherenceLog.scheduled_time <= day_end_utc
        ).all()

        total = len(logs)
        taken = len([l for l in logs if l.taken])
        missed = len([l for l in logs if l.status == models.AdherenceStatus.MISSED])
        delayed = len([l for l in logs if l.status == models.AdherenceStatus.DELAYED])
        adherence_rate = round((taken / total * 100), 2) if total > 0 else 0.0

        results.append({
            "date": day_local.isoformat(),
            "total": total,
            "taken": taken,
            "missed": missed,
            "delayed": delayed,
            "adherence_rate": adherence_rate,
        })

    return {"patient_id": patient_id, "days": days, "daily": results}


# ==================== SYMPTOM ENDPOINTS ====================

@app.post(f"{settings.API_PREFIX}/symptoms/report", tags=["Symptoms"])
async def report_symptom(
    patient_id: int,
    symptom: SymptomReportCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Report symptom and trigger barrier/monitoring agents"""
    db_symptom = models.SymptomReport(
        patient_id=patient_id,
        medication_name=symptom.medication_name,
        symptom=symptom.symptom,
        severity=symptom.severity,
        timing=symptom.timing,
        description=symptom.description,
        duration_minutes=symptom.duration_minutes,
        onset_datetime=datetime.utcnow()
    )
    db.add(db_symptom)
    db.commit()
    db.refresh(db_symptom)
    
    # Log agent activity
    activity = models.AgentActivity(
        patient_id=patient_id,
        agent_name="Monitoring",
        agent_type=models.AgentType.MONITORING,
        action=f"Symptom reported: {symptom.symptom} (severity: {symptom.severity}/10)",
        activity_type="monitoring",
        input_data={"symptom_id": db_symptom.id, "severity": symptom.severity}
    )
    db.add(activity)
    db.commit()
    
    # Escalate severe symptoms
    escalate = symptom.severity >= 7
    if escalate:
        db_symptom.escalated = True
        db.commit()
    
    # TODO: Trigger monitoring agent
    # background_tasks.add_task(orchestrator.monitoring_agent.analyze_symptom, db_symptom.id)
    
    return {
        "symptom_id": db_symptom.id,
        "message": "Symptom reported. AI agents are analyzing...",
        "escalated": escalate,
        "estimated_response_time": "30 seconds"
    }


@app.get(f"{settings.API_PREFIX}/symptoms/patient/{{patient_id}}", tags=["Symptoms"])
async def list_symptoms(patient_id: int, days: int = 30, db: Session = Depends(get_db)):
    """List recent symptom reports for a patient"""
    since = datetime.utcnow() - timedelta(days=days)
    symptoms = db.query(models.SymptomReport).filter(
        models.SymptomReport.patient_id == patient_id,
        models.SymptomReport.reported_at >= since
    ).order_by(models.SymptomReport.reported_at.desc()).all()

    return {
        "symptoms": [
            {
                "id": s.id,
                "patient_id": s.patient_id,
                "symptom_name": s.symptom,
                "severity": s.severity,
                "description": s.description,
                "medication_name": s.medication_name,
                "reported_at": s.reported_at,
            }
            for s in symptoms
        ]
    }


@app.get(f"{settings.API_PREFIX}/symptoms/{{symptom_id}}/analysis", tags=["Symptoms"])
async def get_symptom_analysis(symptom_id: int, db: Session = Depends(get_db)):
    """Get AI analysis of reported symptom"""
    symptom = db.query(models.SymptomReport).filter(models.SymptomReport.id == symptom_id).first()
    
    if not symptom:
        raise HTTPException(status_code=404, detail="Symptom report not found")
    
    return {
        "symptom_id": symptom.id,
        "symptom": symptom.symptom,
        "severity": symptom.severity,
        "medication": symptom.medication_name,
        "analyzed": symptom.analyzed,
        "analysis_result": symptom.analysis_result,
        "correlation_score": symptom.correlation_score,
        "escalated": symptom.escalated,
        "is_resolved": symptom.is_resolved,
        "reported_at": symptom.reported_at
    }


# ==================== CHAT ENDPOINT ====================

@app.post(f"{settings.API_PREFIX}/chat", tags=["Chat"])
async def chat(message: ChatMessage, db: Session = Depends(get_db)):
    """Delegate chat handling to the dedicated chat router (intent handling, med add, timezone-aware)."""
    from api.chat import ChatRequest as ChatRouterRequest, chat as chat_router_handler

    # Reuse the chat router logic so medication adds and schedule updates work consistently
    router_request = ChatRouterRequest(
        patient_id=message.patient_id,
        message=message.message,
        conversation_history=message.conversation_history or [],
        include_context=True
    )

    return await chat_router_handler(router_request, db)


# ==================== AGENT ACTIVITY ENDPOINTS ====================

@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/agent-activity", tags=["Agents"])
async def get_agent_activity(patient_id: int, limit: int = 20, db: Session = Depends(get_db)):
    """Get recent agent activity logs"""
    activities = db.query(models.AgentActivity).filter(
        models.AgentActivity.patient_id == patient_id
    ).order_by(models.AgentActivity.timestamp.desc()).limit(limit).all()
    
    return [
        {
            "id": a.id,
            "agent": a.agent_name,
            "agent_type": a.agent_type.value if a.agent_type else None,
            "action": a.action,
            "type": a.activity_type,
            "timestamp": a.timestamp,
            "is_successful": a.is_successful,
            "reasoning": a.reasoning
        }
        for a in activities
    ]


@app.get(f"{settings.API_PREFIX}/agents/status", tags=["Agents"])
async def get_agents_status():
    """Get status of all agents"""
    return {
        "agents": {
            "orchestrator": {
                "status": "ready",
                "description": "Multi-agent coordination via LangGraph"
            },
            "planning": {
                "status": "ready",
                "description": "Medication scheduling optimization",
                "config": {
                    "max_medications": agent_config.PLANNING_MAX_MEDICATIONS,
                    "time_slots": agent_config.PLANNING_TIME_SLOTS
                }
            },
            "monitoring": {
                "status": "ready",
                "description": "Adherence tracking and anomaly detection",
                "config": {
                    "adherence_target": agent_config.MONITORING_ADHERENCE_TARGET,
                    "anomaly_threshold": agent_config.MONITORING_ANOMALY_THRESHOLD
                }
            },
            "barrier": {
                "status": "ready",
                "description": "Barrier identification and resolution",
                "config": {
                    "categories": agent_config.BARRIER_CATEGORIES
                }
            },
            "liaison": {
                "status": "ready",
                "description": "Healthcare provider communication",
                "config": {
                    "escalation_threshold": agent_config.LIAISON_ESCALATION_THRESHOLD
                }
            }
        },
        "llm": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL
        },
        "safety": {
            "never_diagnose": agent_config.SAFETY_NEVER_DIAGNOSE,
            "never_change_dosage": agent_config.SAFETY_NEVER_CHANGE_DOSAGE,
            "always_escalate_severe": agent_config.SAFETY_ALWAYS_ESCALATE_SEVERE
        }
    }


# ==================== PROVIDER REPORT ENDPOINTS ====================

@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/provider-report", tags=["Reports"])
async def generate_provider_report(patient_id: int, days: int = 30, db: Session = Depends(get_db)):
    """Generate comprehensive provider report"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    start_date = date.today() - timedelta(days=days)
    end_date = date.today()
    
    # Get adherence stats
    adherence_stats = await get_adherence_stats(patient_id, days, db)
    
    # Get symptoms
    symptoms = db.query(models.SymptomReport).filter(
        models.SymptomReport.patient_id == patient_id,
        models.SymptomReport.reported_at >= datetime.combine(start_date, datetime.min.time())
    ).all()
    
    # Get barriers
    barriers = db.query(models.BarrierResolution).filter(
        models.BarrierResolution.patient_id == patient_id,
        models.BarrierResolution.identified_at >= datetime.combine(start_date, datetime.min.time())
    ).all()
    
    # Get medications
    medications = db.query(models.Medication).filter(
        models.Medication.patient_id == patient_id,
        models.Medication.active == True
    ).all()
    
    # Log activity
    activity = models.AgentActivity(
        patient_id=patient_id,
        agent_name="Liaison",
        agent_type=models.AgentType.LIAISON,
        action=f"Provider report generated for {days} days",
        activity_type="report"
    )
    db.add(activity)
    db.commit()
    
    return {
        "patient": {
            "id": patient.id,
            "name": patient.full_name,
            "conditions": patient.conditions
        },
        "report_period": {
            "start": start_date.isoformat(),
            "end": end_date.isoformat(),
            "days": days
        },
        "adherence": adherence_stats,
        "medications": [
            {
                "name": m.name,
                "dosage": m.dosage,
                "frequency": m.frequency,
                "adherence_rate": calculate_adherence(db, m.id, days)
            }
            for m in medications
        ],
        "symptoms_reported": len(symptoms),
        "symptoms_summary": [
            {
                "symptom": s.symptom,
                "severity": s.severity,
                "medication": s.medication_name,
                "escalated": s.escalated
            }
            for s in symptoms
        ],
        "barriers_identified": len(barriers),
        "barriers_resolved": len([b for b in barriers if b.resolved]),
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": "Liaison Agent"
    }


# ==================== INSIGHTS ENDPOINT ====================

@app.get(f"{settings.API_PREFIX}/patients/{{patient_id}}/insights", tags=["Insights"])
async def get_insights(patient_id: int, db: Session = Depends(get_db)):
    """Get AI-generated insights and recommendations"""
    patient = db.query(models.Patient).filter(models.Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get recent adherence
    adherence_stats = await get_adherence_stats(patient_id, 7, db)
    
    insights = []
    recommendations = []
    
    # Generate insights based on data
    if adherence_stats["adherence_rate"] < 80:
        insights.append({
            "type": "warning",
            "title": "Adherence Below Target",
            "message": f"Your adherence rate is {adherence_stats['adherence_rate']}%, below the 90% target.",
            "priority": "high"
        })
        recommendations.append({
            "action": "Set additional reminders",
            "reason": "Multiple reminders can help improve adherence"
        })
    
    if adherence_stats["doses_delayed"] > 0:
        insights.append({
            "type": "info",
            "title": "Delayed Doses Detected",
            "message": f"You had {adherence_stats['doses_delayed']} delayed doses this week.",
            "priority": "medium"
        })
    
    if adherence_stats["current_streak"] >= 7:
        insights.append({
            "type": "success",
            "title": "Great Streak!",
            "message": f"You're on a {adherence_stats['current_streak']} dose streak. Keep it up!",
            "priority": "low"
        })
    
    return {
        "patient_id": patient_id,
        "insights": insights,
        "recommendations": recommendations,
        "adherence_summary": adherence_stats,
        "generated_at": datetime.utcnow().isoformat()
    }


# ==================== HELPER FUNCTIONS ====================

def calculate_adherence(db: Session, medication_id: int, days: int = 30) -> float:
    """Calculate adherence rate for a medication"""
    start_date = datetime.utcnow() - timedelta(days=days)
    logs = db.query(models.AdherenceLog).filter(
        models.AdherenceLog.medication_id == medication_id,
        models.AdherenceLog.scheduled_time >= start_date
    ).all()
    
    if not logs:
        return 0.0
    
    taken = len([log for log in logs if log.taken])
    return round((taken / len(logs)) * 100, 2)


def calculate_streak(logs: List) -> int:
    """Calculate current adherence streak"""
    if not logs:
        return 0
    
    sorted_logs = sorted(logs, key=lambda x: x.scheduled_time, reverse=True)
    streak = 0
    
    for log in sorted_logs:
        if log.taken:
            streak += 1
        else:
            break
    
    return streak


def calculate_trend(logs: List) -> str:
    """Calculate adherence trend (improving, declining, stable)"""
    if len(logs) < 7:
        return "insufficient_data"
    
    sorted_logs = sorted(logs, key=lambda x: x.scheduled_time)
    
    # Split into two halves
    mid = len(sorted_logs) // 2
    first_half = sorted_logs[:mid]
    second_half = sorted_logs[mid:]
    
    first_rate = sum(1 for l in first_half if l.taken) / len(first_half) if first_half else 0
    second_rate = sum(1 for l in second_half if l.taken) / len(second_half) if second_half else 0
    
    diff = second_rate - first_rate
    
    if diff > 0.1:
        return "improving"
    elif diff < -0.1:
        return "declining"
    else:
        return "stable"


# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )