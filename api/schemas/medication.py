"""
Medication Schemas
Pydantic models for medication-related API requests and responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict


# ==================== BASE SCHEMAS ====================

class MedicationBase(BaseModel):
    """Base medication schema"""
    name: str = Field(..., min_length=1, max_length=255)
    dosage: str = Field(..., min_length=1, max_length=100)
    frequency: str = Field(..., min_length=1, max_length=100)


# ==================== REQUEST SCHEMAS ====================

class MedicationCreate(MedicationBase):
    """Schema for creating a new medication"""
    patient_id: int
    generic_name: Optional[str] = Field(None, max_length=255)
    rxnorm_id: Optional[str] = Field(None, max_length=50)
    ndc_code: Optional[str] = Field(None, max_length=20)
    dosage_form: Optional[str] = Field(None, max_length=100)
    strength: Optional[str] = Field(None, max_length=50)
    strength_unit: Optional[str] = Field(None, max_length=20)
    frequency_per_day: int = Field(default=1, ge=1, le=24)
    instructions: Optional[str] = None
    with_food: bool = False
    with_water: bool = True
    max_daily_doses: Optional[int] = Field(None, ge=1)
    min_hours_between_doses: Optional[float] = Field(None, ge=0)
    purpose: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class MedicationUpdate(BaseModel):
    """Schema for updating medication"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    generic_name: Optional[str] = Field(None, max_length=255)
    dosage: Optional[str] = Field(None, min_length=1, max_length=100)
    dosage_form: Optional[str] = Field(None, max_length=100)
    frequency: Optional[str] = Field(None, min_length=1, max_length=100)
    frequency_per_day: Optional[int] = Field(None, ge=1, le=24)
    instructions: Optional[str] = None
    with_food: Optional[bool] = None
    with_water: Optional[bool] = None
    max_daily_doses: Optional[int] = Field(None, ge=1)
    min_hours_between_doses: Optional[float] = Field(None, ge=0)
    purpose: Optional[str] = Field(None, max_length=255)
    notes: Optional[str] = None
    active: Optional[bool] = None
    end_date: Optional[date] = None


class MedicationDiscontinue(BaseModel):
    """Schema for discontinuing a medication"""
    reason: Optional[str] = Field(None, max_length=500)
    end_date: Optional[date] = None


class InteractionCheckRequest(BaseModel):
    """Schema for checking drug interactions"""
    patient_id: int
    new_medication: Optional[str] = None


class MedicationSearch(BaseModel):
    """Schema for searching medications"""
    query: str = Field(..., min_length=1)
    limit: int = Field(default=10, ge=1, le=50)


# ==================== RESPONSE SCHEMAS ====================

class MedicationResponse(MedicationBase):
    """Schema for medication response"""
    id: int
    patient_id: int
    generic_name: Optional[str] = None
    rxnorm_id: Optional[str] = None
    ndc_code: Optional[str] = None
    dosage_form: Optional[str] = None
    strength: Optional[str] = None
    strength_unit: Optional[str] = None
    frequency_per_day: int = 1
    instructions: Optional[str] = None
    with_food: bool = False
    with_water: bool = True
    max_daily_doses: Optional[int] = None
    min_hours_between_doses: Optional[float] = None
    purpose: Optional[str] = None
    notes: Optional[str] = None
    active: bool = True
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MedicationSummary(BaseModel):
    """Brief medication summary"""
    id: int
    name: str
    dosage: str
    frequency: str
    active: bool
    with_food: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class MedicationDetail(MedicationResponse):
    """Detailed medication with additional info"""
    adherence_rate: Optional[float] = None
    drug_info: Optional[Dict[str, Any]] = None
    interactions: Optional[List[Dict[str, Any]]] = None


class MedicationList(BaseModel):
    """List of medications"""
    medications: List[MedicationSummary]
    total: int
    active_count: int


class DrugInteraction(BaseModel):
    """Drug interaction details"""
    drug1: str
    drug2: str
    severity: str  # "mild", "moderate", "severe"
    description: str
    recommendation: Optional[str] = None


class InteractionCheckResponse(BaseModel):
    """Response for interaction check"""
    patient_id: int
    medications_checked: List[str]
    has_interactions: bool
    interaction_count: int
    interactions: List[DrugInteraction]
    summary: str


class DrugSearchResult(BaseModel):
    """Search result for drug database"""
    name: str
    generic_name: Optional[str] = None
    rxnorm_id: Optional[str] = None
    drug_class: Optional[str] = None


class SideEffectsResponse(BaseModel):
    """Side effects information"""
    medication_name: str
    common_side_effects: List[str]
    serious_side_effects: List[str]
    warnings: List[str]


class FoodRequirementsResponse(BaseModel):
    """Food requirements for medication"""
    medication_name: str
    with_food: bool
    food_recommendation: str
    avoid_foods: List[str]
    timing_advice: Optional[str] = None


class RefillNeeded(BaseModel):
    """Medication needing refill"""
    medication_id: int
    medication_name: str
    quantity_remaining: int
    days_remaining: int
    pharmacy: Optional[str] = None
    pharmacy_phone: Optional[str] = None
    refills_remaining: Optional[int] = None


class RefillList(BaseModel):
    """List of medications needing refill"""
    patient_id: int
    refills_needed: List[RefillNeeded]
    urgent_count: int
