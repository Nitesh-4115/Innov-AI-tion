"""
Medications API Router
Endpoints for medication management
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, services
from api.schemas.medication import (
    MedicationCreate,
    MedicationUpdate,
    MedicationDiscontinue,
    InteractionCheckRequest,
    MedicationResponse,
    MedicationSummary,
    MedicationDetail,
    MedicationList,
    InteractionCheckResponse,
    DrugInteraction,
    DrugSearchResult,
    SideEffectsResponse,
    FoodRequirementsResponse,
    RefillList,
    RefillNeeded,
)


router = APIRouter(prefix="/medications", tags=["medications"])


@router.post("/", response_model=MedicationResponse, status_code=status.HTTP_201_CREATED)
async def create_medication(
    medication_data: MedicationCreate,
    db: Session = Depends(get_db)
):
    """
    Add a new medication for a patient
    
    - **patient_id**: Patient ID
    - **name**: Medication name
    - **dosage**: Dosage (e.g., "500mg")
    - **frequency**: Frequency description
    """
    medication_service = services.get_medication_service()
    
    try:
        medication = await medication_service.add_medication(
            patient_id=medication_data.patient_id,
            name=medication_data.name,
            dosage=medication_data.dosage,
            frequency=medication_data.frequency,
            frequency_per_day=medication_data.frequency_per_day,
            generic_name=medication_data.generic_name,
            rxnorm_id=medication_data.rxnorm_id,
            instructions=medication_data.instructions,
            with_food=medication_data.with_food,
            purpose=medication_data.purpose,
            start_date=medication_data.start_date,
            end_date=medication_data.end_date,
            db=db
        )
        return medication
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/patient/{patient_id}", response_model=MedicationList)
async def get_patient_medications(
    patient_id: int,
    active_only: bool = Query(True, description="Only return active medications"),
    db: Session = Depends(get_db)
):
    """
    Get all medications for a patient
    """
    medication_service = services.get_medication_service()
    
    medications = await medication_service.get_patient_medications(
        patient_id,
        active_only=active_only,
        db=db
    )
    
    active_count = sum(1 for m in medications if m.active)
    
    return MedicationList(
        medications=[
            MedicationSummary(
                id=m.id,
                name=m.name,
                dosage=m.dosage,
                frequency=m.frequency,
                active=m.active,
                with_food=m.with_food
            ) for m in medications
        ],
        total=len(medications),
        active_count=active_count
    )


@router.get("/search", response_model=List[DrugSearchResult])
@router.get("/search/drugs", response_model=List[DrugSearchResult])
async def search_drugs(
    query: Optional[str] = Query(None, description="Search query"),
    limit: int = Query(10, ge=1)
):
    """
    Search for medications in drug database
    """
    medication_service = services.get_medication_service()
    # Allow empty query to return top results (client-side preload use-case)
    q = (query or "").strip()
    results = await medication_service.search_medications(q, limit)
    return [
        DrugSearchResult(
            name=r.get("name", ""),
            generic_name=r.get("generic_name"),
            rxnorm_id=r.get("rxnorm_id"),
            drug_class=r.get("drug_class")
        ) for r in results
    ]


@router.get("/{medication_id}", response_model=MedicationDetail)
async def get_medication(
    medication_id: int,
    db: Session = Depends(get_db)
):
    """
    Get detailed medication information
    """
    medication_service = services.get_medication_service()
    
    details = await medication_service.get_medication_details(medication_id, db=db)
    
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return details


@router.put("/{medication_id}", response_model=MedicationResponse)
async def update_medication(
    medication_id: int,
    medication_data: MedicationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update medication information
    """
    medication_service = services.get_medication_service()
    
    updates = medication_data.model_dump(exclude_unset=True, exclude_none=True)
    
    if not updates:
        medication = await medication_service.get_medication(medication_id, db=db)
        if not medication:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Medication {medication_id} not found"
            )
        return medication
    
    medication = await medication_service.update_medication(
        medication_id,
        updates,
        db=db
    )
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return medication


@router.post("/{medication_id}/discontinue", response_model=MedicationResponse)
async def discontinue_medication(
    medication_id: int,
    discontinue_data: MedicationDiscontinue,
    db: Session = Depends(get_db)
):
    """
    Discontinue a medication
    """
    medication_service = services.get_medication_service()
    
    medication = await medication_service.discontinue_medication(
        medication_id,
        reason=discontinue_data.reason,
        db=db
    )
    
    if not medication:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Medication {medication_id} not found"
        )
    
    return medication


@router.post("/interactions/check", response_model=InteractionCheckResponse)
async def check_interactions(
    request: InteractionCheckRequest,
    db: Session = Depends(get_db)
):
    """
    Check for drug interactions among patient's medications
    """
    medication_service = services.get_medication_service()
    
    result = await medication_service.check_interactions(
        patient_id=request.patient_id,
        new_medication=request.new_medication,
        db=db
    )
    
    # Get medication names
    medications = await medication_service.get_patient_medications(
        request.patient_id,
        active_only=True,
        db=db
    )
    med_names = [m.name for m in medications]
    if request.new_medication:
        med_names.append(request.new_medication)
    
    interactions = []
    for interaction in result.get("interactions", []):
        interactions.append(DrugInteraction(
            drug1=interaction.get("drug1", ""),
            drug2=interaction.get("drug2", ""),
            severity=interaction.get("severity", "unknown"),
            description=interaction.get("description", ""),
            recommendation=interaction.get("recommendation")
        ))
    
    return InteractionCheckResponse(
        patient_id=request.patient_id,
        medications_checked=med_names,
        has_interactions=result.get("has_interactions", False),
        interaction_count=len(interactions),
        interactions=interactions,
        summary=result.get("summary", "No interactions found")
    )





@router.get("/{medication_name}/side-effects", response_model=SideEffectsResponse)
async def get_side_effects(
    medication_name: str
):
    """
    Get side effects information for a medication
    """
    medication_service = services.get_medication_service()
    
    result = await medication_service.get_side_effects(medication_name)
    
    return SideEffectsResponse(
        medication_name=medication_name,
        common_side_effects=result.get("common", []),
        serious_side_effects=result.get("serious", []),
        warnings=result.get("warnings", [])
    )


@router.get("/{medication_name}/food-requirements", response_model=FoodRequirementsResponse)
async def get_food_requirements(
    medication_name: str
):
    """
    Get food requirements for a medication
    """
    medication_service = services.get_medication_service()
    
    result = await medication_service.get_food_requirements(medication_name)
    
    return FoodRequirementsResponse(
        medication_name=medication_name,
        with_food=result.get("with_food", False),
        food_recommendation=result.get("recommendation", "No specific requirements"),
        avoid_foods=result.get("avoid_foods", []),
        timing_advice=result.get("timing_advice")
    )


@router.get("/patient/{patient_id}/refills", response_model=RefillList)
async def get_refills_needed(
    patient_id: int,
    days_threshold: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get medications that need refilling soon
    """
    medication_service = services.get_medication_service()
    
    refills = await medication_service.get_medications_needing_refill(
        patient_id,
        days_threshold=days_threshold,
        db=db
    )
    
    urgent_count = sum(1 for r in refills if r.get("quantity_remaining", 0) <= 3)
    
    return RefillList(
        patient_id=patient_id,
        refills_needed=[
            RefillNeeded(
                medication_id=r["medication_id"],
                medication_name=r["medication_name"],
                quantity_remaining=r.get("quantity_remaining", 0),
                days_remaining=r.get("quantity_remaining", 0),
                pharmacy=r.get("pharmacy"),
                pharmacy_phone=r.get("pharmacy_phone"),
                refills_remaining=r.get("refills_remaining")
            ) for r in refills
        ],
        urgent_count=urgent_count
    )


@router.get("/patient/{patient_id}/schedule-info")
async def get_medication_schedule_info(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get medication information formatted for scheduling
    """
    medication_service = services.get_medication_service()
    
    schedule_info = await medication_service.get_medication_schedule_info(
        patient_id,
        db=db
    )
    
    return {
        "patient_id": patient_id,
        "medications": schedule_info
    }
