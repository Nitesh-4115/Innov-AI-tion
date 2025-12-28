"""
Adherence Schemas
Pydantic models for adherence tracking API requests and responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class AdherenceStatusEnum(str, Enum):
    """Adherence status values"""
    TAKEN = "taken"
    MISSED = "missed"
    SKIPPED = "skipped"
    DELAYED = "delayed"
    PENDING = "pending"


# ==================== REQUEST SCHEMAS ====================

class AdherenceLogCreate(BaseModel):
    """Schema for logging adherence"""
    patient_id: int
    schedule_id: int
    medication_id: int
    status: AdherenceStatusEnum
    taken_at: Optional[datetime] = None
    deviation_minutes: int = Field(default=0)
    notes: Optional[str] = None
    reported_by: str = Field(default="patient", max_length=50)


class DoseTaken(BaseModel):
    """Schema for logging a taken dose"""
    patient_id: int
    schedule_id: int
    medication_id: int
    taken_at: Optional[datetime] = None


class DoseMissed(BaseModel):
    """Schema for logging a missed dose"""
    patient_id: int
    schedule_id: int
    medication_id: int
    reason: Optional[str] = Field(None, max_length=500)


class DoseSkipped(BaseModel):
    """Schema for logging a skipped dose"""
    patient_id: int
    schedule_id: int
    medication_id: int
    reason: str = Field(..., min_length=1, max_length=500)


class AdherenceQuery(BaseModel):
    """Query parameters for adherence data"""
    patient_id: int
    days: int = Field(default=30, ge=1, le=365)
    medication_id: Optional[int] = None


# ==================== RESPONSE SCHEMAS ====================

class AdherenceLogResponse(BaseModel):
    """Schema for adherence log response"""
    id: int
    patient_id: int
    schedule_id: int
    medication_id: int
    status: AdherenceStatusEnum
    scheduled_time: Optional[datetime] = None
    taken_at: Optional[datetime] = None
    deviation_minutes: Optional[int] = None
    notes: Optional[str] = None
    reported_by: str
    logged_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AdherenceLogDetail(AdherenceLogResponse):
    """Detailed adherence log with medication info"""
    medication_name: str
    dosage: Optional[str] = None


class AdherenceRate(BaseModel):
    """Adherence rate statistics"""
    adherence_rate: float = Field(..., ge=0, le=100)
    total_doses: int
    taken: int
    missed: int
    skipped: int
    delayed: int
    average_deviation_minutes: Optional[float] = None
    days_analyzed: int


class AdherenceStreak(BaseModel):
    """Adherence streak information"""
    current_streak: int
    best_streak: int
    streak_start: Optional[str] = None


class MedicationAdherence(BaseModel):
    """Adherence breakdown by medication"""
    medication_id: int
    medication_name: str
    dosage: str
    adherence_rate: float
    total_doses: int
    missed_doses: int


class AdherenceByMedication(BaseModel):
    """List of adherence by medication"""
    patient_id: int
    days_analyzed: int
    medications: List[MedicationAdherence]


class AdherenceHistoryEntry(BaseModel):
    """Single adherence history entry"""
    log_id: int
    medication_id: int
    medication_name: str
    status: str
    scheduled_time: Optional[str] = None
    taken_at: Optional[str] = None
    deviation_minutes: Optional[int] = None
    notes: Optional[str] = None
    logged_at: str


class AdherenceHistory(BaseModel):
    """Adherence history list"""
    patient_id: int
    days: int
    entries: List[AdherenceHistoryEntry]
    total_entries: int


class DailySummary(BaseModel):
    """Daily adherence summary"""
    date: str
    total_scheduled: int
    taken: int
    missed: int
    delayed: int
    skipped: int
    pending: int
    adherence_rate: float


class WeeklyTrend(BaseModel):
    """Weekly adherence trend"""
    week_start: str
    week_end: str
    total_doses: int
    adherence_rate: float


class WeeklyTrendList(BaseModel):
    """List of weekly trends"""
    patient_id: int
    weeks: int
    trends: List[WeeklyTrend]


class ProblemTime(BaseModel):
    """Time period with adherence problems"""
    hour: int
    time_label: str
    period: str  # "morning", "afternoon", "evening"
    miss_rate: float
    total_doses: int
    missed_doses: int


class ProblemTimesResponse(BaseModel):
    """Problem times analysis response"""
    patient_id: int
    days_analyzed: int
    problem_times: List[ProblemTime]
    recommendation: Optional[str] = None


class AdherenceDashboard(BaseModel):
    """Complete adherence dashboard data"""
    patient_id: int
    overall_rate: AdherenceRate
    streak: AdherenceStreak
    today: DailySummary
    weekly_trends: List[WeeklyTrend]
    by_medication: List[MedicationAdherence]
    problem_times: List[ProblemTime]
