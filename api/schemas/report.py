"""
Report Schemas
Pydantic models for provider reports API requests and responses
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict


# ==================== REQUEST SCHEMAS ====================

class ReportCreate(BaseModel):
    """Schema for creating a provider report"""
    patient_id: int
    report_period_start: date
    report_period_end: date
    provider_id: Optional[str] = Field(None, max_length=100)
    include_fhir: bool = False


class ReportQuery(BaseModel):
    """Query parameters for reports"""
    patient_id: int
    limit: int = Field(default=10, ge=1, le=50)


class QuickSummaryRequest(BaseModel):
    """Request for quick summary"""
    patient_id: int
    days: int = Field(default=7, ge=1, le=90)


# ==================== RESPONSE SCHEMAS ====================

class AdherenceSummary(BaseModel):
    """Adherence summary for report"""
    adherence_rate: float
    total_doses: int
    taken: int
    missed: int
    skipped: int
    delayed: int
    average_time_deviation_minutes: Optional[float] = None


class MedicationSummaryItem(BaseModel):
    """Medication summary for report"""
    medication_id: int
    medication_name: str
    dosage: str
    frequency: str
    adherence_rate: float
    total_scheduled: int
    active: bool


class SymptomSummaryItem(BaseModel):
    """Symptom summary for report"""
    symptom: str
    occurrence_count: int
    max_severity: str


class SymptomReportSummary(BaseModel):
    """Symptoms summary for report"""
    total_reports: int
    unique_symptoms: int
    symptoms: List[SymptomSummaryItem]


class BarrierSummaryItem(BaseModel):
    """Barrier summary for report"""
    category: str
    description: str
    resolved: bool
    resolution: Optional[str] = None


class BarrierReportSummary(BaseModel):
    """Barriers summary for report"""
    total_identified: int
    resolved: int
    resolution_rate: float
    barriers: List[BarrierSummaryItem]


class InterventionItem(BaseModel):
    """Intervention for report"""
    type: str
    description: str
    outcome: Optional[str] = None
    date: str


class Recommendation(BaseModel):
    """Recommendation for provider"""
    category: str
    priority: str  # "low", "medium", "high"
    recommendation: str


class ProviderReportResponse(BaseModel):
    """Schema for provider report response"""
    id: int
    patient_id: int
    provider_id: Optional[str] = None
    report_period_start: date
    report_period_end: date
    overall_adherence_score: Optional[float] = None
    adherence_summary: Optional[Dict[str, Any]] = None
    medication_summary: Optional[List[Dict[str, Any]]] = None
    symptom_summary: Optional[Dict[str, Any]] = None
    barrier_summary: Optional[Dict[str, Any]] = None
    interventions: Optional[List[Dict[str, Any]]] = None
    recommendations: Optional[List[Dict[str, Any]]] = None
    generated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ProviderReportDetail(ProviderReportResponse):
    """Detailed provider report"""
    patient_name: Optional[str] = None
    fhir_available: bool = False


class ProviderReportSummary(BaseModel):
    """Brief report summary"""
    id: int
    patient_id: int
    report_period_start: date
    report_period_end: date
    overall_adherence_score: Optional[float] = None
    generated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ReportList(BaseModel):
    """List of provider reports"""
    patient_id: int
    reports: List[ProviderReportSummary]
    total: int


class QuickSummaryResponse(BaseModel):
    """Quick summary response"""
    patient_name: str
    period_days: int
    adherence_rate: float
    total_doses_scheduled: int
    doses_taken: int
    doses_missed: int
    symptom_reports: int
    severe_symptoms: int
    generated_at: str


class FHIRBundle(BaseModel):
    """FHIR R4 Bundle response"""
    resourceType: str = "Bundle"
    type: str = "collection"
    timestamp: str
    entry: List[Dict[str, Any]]


class FHIRExportResponse(BaseModel):
    """Response for FHIR export"""
    report_id: int
    patient_id: int
    fhir_bundle: FHIRBundle
    exported_at: str


class ReportExportResponse(BaseModel):
    """Response for report export"""
    report_id: int
    format: str  # "json", "fhir", "pdf"
    content: str
    exported_at: str


class ReportAnalytics(BaseModel):
    """Analytics for reports"""
    patient_id: int
    total_reports: int
    average_adherence: float
    adherence_trend: str  # "improving", "declining", "stable"
    reports_this_month: int
