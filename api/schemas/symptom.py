"""
Symptom Schemas
Pydantic models for symptom reporting API requests and responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


class SeverityLevelEnum(str, Enum):
    """Severity level values"""
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    CRITICAL = "critical"


# ==================== REQUEST SCHEMAS ====================

class SymptomReportCreate(BaseModel):
    """Schema for creating a symptom report"""
    patient_id: int
    symptom_name: str = Field(..., min_length=1, max_length=255)
    severity: SeverityLevelEnum
    description: Optional[str] = Field(None, max_length=2000)
    medication_id: Optional[int] = None
    onset_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    body_location: Optional[str] = Field(None, max_length=100)
    triggers: Optional[List[str]] = None
    relieved_by: Optional[List[str]] = None


class SymptomReportUpdate(BaseModel):
    """Schema for updating a symptom report"""
    symptom_name: Optional[str] = Field(None, min_length=1, max_length=255)
    severity: Optional[SeverityLevelEnum] = None
    description: Optional[str] = Field(None, max_length=2000)
    medication_id: Optional[int] = None
    onset_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=0)
    resolved: Optional[bool] = None


class SymptomResolve(BaseModel):
    """Schema for resolving a symptom"""
    resolution_notes: Optional[str] = Field(None, max_length=1000)


class SymptomQuery(BaseModel):
    """Query parameters for symptoms"""
    patient_id: int
    days: int = Field(default=30, ge=1, le=365)
    severity: Optional[SeverityLevelEnum] = None
    symptom_name: Optional[str] = None


# ==================== RESPONSE SCHEMAS ====================

class SymptomReportResponse(BaseModel):
    """Schema for symptom report response"""
    id: int
    patient_id: int
    symptom_name: str
    severity: SeverityLevelEnum
    description: Optional[str] = None
    medication_id: Optional[int] = None
    onset_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    additional_data: Optional[Dict[str, Any]] = None
    resolved: bool = False
    resolved_at: Optional[datetime] = None
    reported_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SymptomReportDetail(SymptomReportResponse):
    """Detailed symptom report with medication info"""
    medication_name: Optional[str] = None
    body_location: Optional[str] = None
    triggers: Optional[List[str]] = None
    relieved_by: Optional[List[str]] = None


class SymptomSummary(BaseModel):
    """Summary of patient symptoms"""
    total_reports: int
    unique_symptoms: int
    most_common: List[Dict[str, Any]]
    severity_distribution: Dict[str, int]
    medication_related: Dict[str, List[str]]
    days_analyzed: int


class SymptomCorrelation(BaseModel):
    """Correlation between symptom and medication"""
    symptom_name: str
    medication_name: str
    correlation_score: float = Field(..., ge=0, le=1)
    occurrence_count: int
    likely_side_effect: bool


class CorrelationAnalysis(BaseModel):
    """Symptom-medication correlation analysis"""
    patient_id: int
    analysis_period_days: int
    correlations: List[SymptomCorrelation]
    summary: str
    recommendations: List[str]


class PotentialSideEffect(BaseModel):
    """Potential medication side effect"""
    medication_name: str
    symptom_name: str
    likelihood: str  # "possible", "probable", "likely"
    known_side_effect: bool
    recommendation: str


class SideEffectsAnalysis(BaseModel):
    """Analysis of potential side effects"""
    patient_id: int
    potential_side_effects: List[PotentialSideEffect]
    requires_attention: int
    provider_notification_recommended: bool


class SymptomTrend(BaseModel):
    """Weekly symptom trend"""
    week_start: str
    week_end: str
    total_reports: int
    average_severity: float


class SymptomTrendList(BaseModel):
    """List of symptom trends"""
    patient_id: int
    symptom_name: Optional[str] = None
    weeks: int
    trends: List[SymptomTrend]


class SevereSymptom(BaseModel):
    """Severe symptom requiring attention"""
    report_id: int
    symptom_name: str
    severity: str
    description: Optional[str] = None
    medication: Optional[str] = None
    reported_at: str
    resolved: bool


class SevereSymptomsResponse(BaseModel):
    """Response for severe symptoms query"""
    patient_id: int
    days: int
    severe_symptoms: List[SevereSymptom]
    total_count: int
    unresolved_count: int


class SymptomProviderReport(BaseModel):
    """Symptom data for provider report"""
    total_symptom_reports: int
    unique_symptoms: int
    symptoms: List[Dict[str, Any]]
    period: Dict[str, str]


class SymptomList(BaseModel):
    """Paginated list of symptom reports"""
    patient_id: int
    symptoms: List[SymptomReportResponse]
    total: int
    page: int
    page_size: int
