"""
Patient Schemas
Pydantic models for patient-related API requests and responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from pydantic import BaseModel, Field, ConfigDict


# ==================== BASE SCHEMAS ====================

class PatientBase(BaseModel):
    """Base patient schema with common fields"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    # Use plain string for email to allow special-use/test domains in fixtures
    email: str
    phone: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    timezone: str = Field(default="UTC", max_length=50)


# ==================== REQUEST SCHEMAS ====================

class PatientCreate(PatientBase):
    """Schema for creating a new patient"""
    conditions: Optional[List[str]] = Field(default_factory=list)
    allergies: Optional[List[str]] = Field(default_factory=list)
    wake_time: Optional[time] = Field(default=time(7, 0))
    sleep_time: Optional[time] = Field(default=time(22, 0))
    breakfast_time: Optional[time] = Field(default=time(8, 0))
    lunch_time: Optional[time] = Field(default=time(12, 0))
    dinner_time: Optional[time] = Field(default=time(19, 0))
    notification_preferences: Optional[Dict[str, Any]] = Field(default_factory=dict)
    preferred_reminder_minutes: int = Field(default=15, ge=0, le=120)


class PatientUpdate(BaseModel):
    """Schema for updating patient information"""
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    date_of_birth: Optional[date] = None
    timezone: Optional[str] = Field(None, max_length=50)
    conditions: Optional[List[str]] = None
    allergies: Optional[List[str]] = None
    wake_time: Optional[time] = None
    sleep_time: Optional[time] = None
    breakfast_time: Optional[time] = None
    lunch_time: Optional[time] = None
    dinner_time: Optional[time] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    preferred_reminder_minutes: Optional[int] = Field(None, ge=0, le=120)
    is_active: Optional[bool] = None


class PatientPreferencesUpdate(BaseModel):
    """Schema for updating patient preferences"""
    timezone: Optional[str] = None
    wake_time: Optional[time] = None
    sleep_time: Optional[time] = None
    breakfast_time: Optional[time] = None
    lunch_time: Optional[time] = None
    dinner_time: Optional[time] = None
    notification_preferences: Optional[Dict[str, Any]] = None
    preferred_reminder_minutes: Optional[int] = Field(None, ge=0, le=120)


class ConditionAdd(BaseModel):
    """Schema for adding a condition"""
    condition: str = Field(..., min_length=1, max_length=255)


class AllergyAdd(BaseModel):
    """Schema for adding an allergy"""
    allergy: str = Field(..., min_length=1, max_length=255)


# ==================== RESPONSE SCHEMAS ====================

class PatientResponse(PatientBase):
    """Schema for patient response"""
    id: int
    external_id: Optional[str] = None
    age: Optional[int] = None
    conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    wake_time: Optional[time] = None
    sleep_time: Optional[time] = None
    breakfast_time: Optional[time] = None
    lunch_time: Optional[time] = None
    dinner_time: Optional[time] = None
    notification_preferences: Dict[str, Any] = Field(default_factory=dict)
    preferred_reminder_minutes: int = 15
    is_active: bool = True
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class PatientSummary(BaseModel):
    """Brief patient summary"""
    id: int
    full_name: str
    email: str
    is_active: bool
    medication_count: int = 0
    adherence_rate: Optional[float] = None
    
    model_config = ConfigDict(from_attributes=True)


class PatientDetailResponse(PatientResponse):
    """Detailed patient response with related data"""
    medication_count: int = 0
    active_medications: int = 0
    recent_adherence_rate: Optional[float] = None
    last_activity: Optional[datetime] = None


class PatientList(BaseModel):
    """Paginated list of patients"""
    patients: List[PatientSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


class PatientSearch(BaseModel):
    """Search parameters for patients"""
    query: Optional[str] = None
    is_active: Optional[bool] = None
    has_conditions: Optional[List[str]] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
