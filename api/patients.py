"""
Patients API Router
Endpoints for patient management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, services, pagination_params
from api.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientPreferencesUpdate,
    ConditionAdd,
    AllergyAdd,
    PatientResponse,
    PatientSummary,
    PatientDetailResponse,
    PatientList,
)


router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_data: PatientCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new patient
    
    - **email**: Unique email address
    - **first_name**: Patient's first name
    - **last_name**: Patient's last name
    """
    patient_service = services.get_patient_service()
    
    try:
        patient = await patient_service.create_patient(
            email=patient_data.email,
            first_name=patient_data.first_name,
            last_name=patient_data.last_name,
            phone=patient_data.phone,
            date_of_birth=patient_data.date_of_birth,
            timezone=patient_data.timezone,
            conditions=patient_data.conditions,
            allergies=patient_data.allergies,
            wake_time=patient_data.wake_time,
            sleep_time=patient_data.sleep_time,
            meal_times={
                "breakfast": patient_data.breakfast_time,
                "lunch": patient_data.lunch_time,
                "dinner": patient_data.dinner_time
            },
            notification_preferences=patient_data.notification_preferences,
            db=db
        )
        return patient
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/", response_model=PatientList)
async def list_patients(
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by name or email"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    List all patients with pagination
    """
    patient_service = services.get_patient_service()
    
    if search:
        patients = await patient_service.search_patients(search, db=db)
    else:
        patients = await patient_service.get_all_patients(
            active_only=is_active if is_active is not None else False,
            db=db
        )
    
    # Filter by active status if specified
    if is_active is not None and not search:
        patients = [p for p in patients if p.is_active == is_active]
    
    total = len(patients)
    total_pages = (total + page_size - 1) // page_size
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = patients[start:end]
    
    return PatientList(
        patients=[
            PatientSummary(
                id=p.id,
                full_name=p.full_name,
                email=p.email,
                is_active=p.is_active
            ) for p in paginated
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{patient_id}", response_model=PatientDetailResponse)
async def get_patient(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get patient by ID with detailed information
    """
    patient_service = services.get_patient_service()
    
    patient = await patient_service.get_patient(patient_id, db=db)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    # Get summary for additional details
    summary = await patient_service.get_patient_summary(patient_id, db=db)
    
    return PatientDetailResponse(
        id=patient.id,
        external_id=patient.external_id,
        first_name=patient.first_name,
        last_name=patient.last_name,
        email=patient.email,
        phone=patient.phone,
        date_of_birth=patient.date_of_birth,
        age=patient.age,
        timezone=patient.timezone,
        conditions=patient.conditions or [],
        allergies=patient.allergies or [],
        wake_time=patient.wake_time,
        sleep_time=patient.sleep_time,
        breakfast_time=patient.breakfast_time,
        lunch_time=patient.lunch_time,
        dinner_time=patient.dinner_time,
        notification_preferences=patient.notification_preferences or {},
        preferred_reminder_minutes=patient.preferred_reminder_minutes or 15,
        is_active=patient.is_active,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
        medication_count=summary.get("medication_count", 0),
        active_medications=summary.get("active_medications", 0),
        recent_adherence_rate=summary.get("recent_adherence_rate")
    )


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: int,
    patient_data: PatientUpdate,
    db: Session = Depends(get_db)
):
    """
    Update patient information
    """
    patient_service = services.get_patient_service()
    
    # Check patient exists
    existing = await patient_service.get_patient(patient_id, db=db)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    # Filter out None values
    updates = patient_data.model_dump(exclude_unset=True, exclude_none=True)
    
    if not updates:
        return existing
    
    patient = await patient_service.update_patient(patient_id, updates, db=db)
    return patient


@router.patch("/{patient_id}/preferences", response_model=PatientResponse)
async def update_patient_preferences(
    patient_id: int,
    preferences: PatientPreferencesUpdate,
    db: Session = Depends(get_db)
):
    """
    Update patient preferences (lifestyle and notifications)
    """
    patient_service = services.get_patient_service()
    
    updates = preferences.model_dump(exclude_unset=True, exclude_none=True)
    
    if not updates:
        patient = await patient_service.get_patient(patient_id, db=db)
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Patient {patient_id} not found"
            )
        return patient
    
    patient = await patient_service.update_preferences(patient_id, updates, db=db)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    return patient


@router.post("/{patient_id}/conditions", response_model=PatientResponse)
async def add_condition(
    patient_id: int,
    condition_data: ConditionAdd,
    db: Session = Depends(get_db)
):
    """
    Add a condition to patient's record
    """
    patient_service = services.get_patient_service()
    
    patient = await patient_service.add_condition(
        patient_id,
        condition_data.condition,
        db=db
    )
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    return patient


@router.post("/{patient_id}/allergies", response_model=PatientResponse)
async def add_allergy(
    patient_id: int,
    allergy_data: AllergyAdd,
    db: Session = Depends(get_db)
):
    """
    Add an allergy to patient's record
    """
    patient_service = services.get_patient_service()
    
    patient = await patient_service.add_allergy(
        patient_id,
        allergy_data.allergy,
        db=db
    )
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_patient(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Deactivate a patient (soft delete)
    """
    patient_service = services.get_patient_service()
    
    patient = await patient_service.deactivate_patient(patient_id, db=db)
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    return None


@router.get("/{patient_id}/summary")
async def get_patient_summary(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get patient summary including medication and adherence info
    """
    patient_service = services.get_patient_service()
    
    summary = await patient_service.get_patient_summary(patient_id, db=db)
    
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    return summary
