"""
Symptoms API Router
Endpoints for symptom reporting and analysis
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, services
from api.schemas.symptom import (
    SeverityLevelEnum,
    SymptomReportCreate,
    SymptomReportUpdate,
    SymptomResolve,
    SymptomReportResponse,
    SymptomReportDetail,
    SymptomSummary,
    CorrelationAnalysis,
    SideEffectsAnalysis,
    PotentialSideEffect,
    SymptomTrendList,
    SymptomTrend,
    SevereSymptomsResponse,
    SevereSymptom,
    SymptomProviderReport,
    SymptomList,
)
from models import SeverityLevel


router = APIRouter(prefix="/symptoms", tags=["symptoms"])


# Map schema enum to model enum
def _map_severity(severity: SeverityLevelEnum) -> SeverityLevel:
    """Map schema severity to model severity"""
    mapping = {
        SeverityLevelEnum.MILD: SeverityLevel.LOW,
        SeverityLevelEnum.MODERATE: SeverityLevel.MEDIUM,
        SeverityLevelEnum.SEVERE: SeverityLevel.HIGH,
        SeverityLevelEnum.CRITICAL: SeverityLevel.CRITICAL,
    }
    return mapping.get(severity, SeverityLevel.MEDIUM)


@router.post("/", response_model=SymptomReportResponse, status_code=status.HTTP_201_CREATED)
async def report_symptom(
    symptom_data: SymptomReportCreate,
    db: Session = Depends(get_db)
):
    """
    Report a new symptom
    
    - **symptom_name**: Name of the symptom
    - **severity**: mild, moderate, severe, or critical
    - **description**: Optional detailed description
    """
    symptom_service = services.get_symptom_service()
    
    severity = _map_severity(symptom_data.severity)
    
    report = await symptom_service.report_symptom(
        patient_id=symptom_data.patient_id,
        symptom_name=symptom_data.symptom_name,
        severity=severity,
        description=symptom_data.description,
        medication_id=symptom_data.medication_id,
        onset_time=symptom_data.onset_time,
        duration_minutes=symptom_data.duration_minutes,
        body_location=symptom_data.body_location,
        triggers=symptom_data.triggers,
        relieved_by=symptom_data.relieved_by,
        db=db
    )
    
    return SymptomReportResponse(
        id=report.id,
        patient_id=report.patient_id,
        symptom_name=report.symptom_name,
        severity=SeverityLevelEnum(report.severity.value) if report.severity else SeverityLevelEnum.MODERATE,
        description=report.description,
        medication_id=report.medication_id,
        onset_time=report.onset_time,
        duration_minutes=report.duration_minutes,
        additional_data=report.additional_data,
        resolved=getattr(report, 'resolved', False),
        resolved_at=getattr(report, 'resolved_at', None),
        reported_at=report.reported_at
    )


@router.get("/patient/{patient_id}", response_model=SymptomList)
async def get_patient_symptoms(
    patient_id: int,
    days: int = Query(30, ge=1, le=365),
    severity: Optional[SeverityLevelEnum] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get symptom reports for a patient
    """
    symptom_service = services.get_symptom_service()
    
    severity_filter = _map_severity(severity) if severity else None
    
    symptoms = await symptom_service.get_patient_symptoms(
        patient_id=patient_id,
        days=days,
        severity=severity_filter,
        db=db
    )
    
    total = len(symptoms)
    
    # Paginate
    start = (page - 1) * page_size
    end = start + page_size
    paginated = symptoms[start:end]
    
    return SymptomList(
        patient_id=patient_id,
        symptoms=[
            SymptomReportResponse(
                id=s.id,
                patient_id=s.patient_id,
                symptom_name=s.symptom_name,
                severity=SeverityLevelEnum(s.severity.value) if s.severity else SeverityLevelEnum.MODERATE,
                description=s.description,
                medication_id=s.medication_id,
                onset_time=s.onset_time,
                duration_minutes=s.duration_minutes,
                additional_data=s.additional_data,
                resolved=getattr(s, 'resolved', False),
                resolved_at=getattr(s, 'resolved_at', None),
                reported_at=s.reported_at
            ) for s in paginated
        ],
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{report_id}", response_model=SymptomReportDetail)
async def get_symptom_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific symptom report
    """
    symptom_service = services.get_symptom_service()
    
    report = await symptom_service.get_symptom_report(report_id, db=db)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symptom report {report_id} not found"
        )
    
    # Get medication name if linked
    medication_name = None
    if report.medication_id:
        medication_service = services.get_medication_service()
        med = await medication_service.get_medication(report.medication_id, db=db)
        medication_name = med.name if med else None
    
    additional = report.additional_data or {}
    
    return SymptomReportDetail(
        id=report.id,
        patient_id=report.patient_id,
        symptom_name=report.symptom_name,
        severity=SeverityLevelEnum(report.severity.value) if report.severity else SeverityLevelEnum.MODERATE,
        description=report.description,
        medication_id=report.medication_id,
        medication_name=medication_name,
        onset_time=report.onset_time,
        duration_minutes=report.duration_minutes,
        additional_data=report.additional_data,
        body_location=additional.get("body_location"),
        triggers=additional.get("triggers"),
        relieved_by=additional.get("relieved_by"),
        resolved=getattr(report, 'resolved', False),
        resolved_at=getattr(report, 'resolved_at', None),
        reported_at=report.reported_at
    )


@router.put("/{report_id}", response_model=SymptomReportResponse)
async def update_symptom_report(
    report_id: int,
    update_data: SymptomReportUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a symptom report
    """
    symptom_service = services.get_symptom_service()
    
    updates = update_data.model_dump(exclude_unset=True, exclude_none=True)
    
    # Convert severity if provided
    if "severity" in updates:
        updates["severity"] = _map_severity(updates["severity"])
    
    report = await symptom_service.update_symptom_report(report_id, updates, db=db)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symptom report {report_id} not found"
        )
    
    return SymptomReportResponse(
        id=report.id,
        patient_id=report.patient_id,
        symptom_name=report.symptom_name,
        severity=SeverityLevelEnum(report.severity.value) if report.severity else SeverityLevelEnum.MODERATE,
        description=report.description,
        medication_id=report.medication_id,
        onset_time=report.onset_time,
        duration_minutes=report.duration_minutes,
        additional_data=report.additional_data,
        resolved=getattr(report, 'resolved', False),
        resolved_at=getattr(report, 'resolved_at', None),
        reported_at=report.reported_at
    )


@router.post("/{report_id}/resolve", response_model=SymptomReportResponse)
async def resolve_symptom(
    report_id: int,
    resolve_data: SymptomResolve,
    db: Session = Depends(get_db)
):
    """
    Mark a symptom as resolved
    """
    symptom_service = services.get_symptom_service()
    
    report = await symptom_service.resolve_symptom(
        report_id,
        resolution_notes=resolve_data.resolution_notes,
        db=db
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Symptom report {report_id} not found"
        )
    
    return SymptomReportResponse(
        id=report.id,
        patient_id=report.patient_id,
        symptom_name=report.symptom_name,
        severity=SeverityLevelEnum(report.severity.value) if report.severity else SeverityLevelEnum.MODERATE,
        description=report.description,
        medication_id=report.medication_id,
        onset_time=report.onset_time,
        duration_minutes=report.duration_minutes,
        additional_data=report.additional_data,
        resolved=True,
        resolved_at=getattr(report, 'resolved_at', None),
        reported_at=report.reported_at
    )


@router.get("/patient/{patient_id}/summary", response_model=SymptomSummary)
async def get_symptom_summary(
    patient_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """
    Get summary of patient symptoms
    """
    symptom_service = services.get_symptom_service()
    
    summary = await symptom_service.get_symptom_summary(
        patient_id=patient_id,
        days=days,
        db=db
    )
    
    return SymptomSummary(**summary)


@router.get("/patient/{patient_id}/correlations", response_model=CorrelationAnalysis)
async def analyze_correlations(
    patient_id: int,
    days: int = Query(30, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Analyze symptom correlations with medications
    """
    symptom_service = services.get_symptom_service()
    
    analysis = await symptom_service.analyze_correlations(
        patient_id=patient_id,
        days=days,
        db=db
    )
    
    return CorrelationAnalysis(
        patient_id=patient_id,
        analysis_period_days=days,
        correlations=analysis.get("correlations", []),
        summary=analysis.get("summary", "No significant correlations found"),
        recommendations=analysis.get("recommendations", [])
    )


@router.get("/patient/{patient_id}/side-effects", response_model=SideEffectsAnalysis)
async def get_potential_side_effects(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Identify symptoms that may be medication side effects
    """
    symptom_service = services.get_symptom_service()
    
    results = await symptom_service.get_potential_side_effects(patient_id, db=db)
    
    requires_attention = sum(
        1 for r in results
        if r.get("likelihood") in ["probable", "likely"]
    )
    
    return SideEffectsAnalysis(
        patient_id=patient_id,
        potential_side_effects=[
            PotentialSideEffect(
                medication_name=r.get("medication_name", "Unknown"),
                symptom_name=r.get("symptom_name", ""),
                likelihood=r.get("likelihood", "possible"),
                known_side_effect=r.get("known_side_effect", False),
                recommendation=r.get("recommendation", "Monitor and consult provider if persistent")
            ) for r in results
        ],
        requires_attention=requires_attention,
        provider_notification_recommended=requires_attention > 0
    )


@router.get("/patient/{patient_id}/trends", response_model=SymptomTrendList)
async def get_symptom_trends(
    patient_id: int,
    symptom_name: Optional[str] = Query(None),
    weeks: int = Query(4, ge=1, le=12),
    db: Session = Depends(get_db)
):
    """
    Get symptom trends over time
    """
    symptom_service = services.get_symptom_service()
    
    trends = await symptom_service.get_symptom_trends(
        patient_id=patient_id,
        symptom_name=symptom_name,
        weeks=weeks,
        db=db
    )
    
    return SymptomTrendList(
        patient_id=patient_id,
        symptom_name=symptom_name,
        weeks=weeks,
        trends=[SymptomTrend(**t) for t in trends]
    )


@router.get("/patient/{patient_id}/severe", response_model=SevereSymptomsResponse)
async def get_severe_symptoms(
    patient_id: int,
    days: int = Query(7, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get severe symptoms requiring attention
    """
    symptom_service = services.get_symptom_service()
    
    symptoms = await symptom_service.get_severe_symptoms(
        patient_id=patient_id,
        days=days,
        db=db
    )
    
    unresolved = sum(1 for s in symptoms if not s.get("resolved", False))
    
    return SevereSymptomsResponse(
        patient_id=patient_id,
        days=days,
        severe_symptoms=[SevereSymptom(**s) for s in symptoms],
        total_count=len(symptoms),
        unresolved_count=unresolved
    )


@router.get("/patient/{patient_id}/provider-report", response_model=SymptomProviderReport)
async def get_symptoms_for_provider(
    patient_id: int,
    start_date: date = Query(...),
    end_date: date = Query(...),
    db: Session = Depends(get_db)
):
    """
    Get symptom data formatted for provider reports
    """
    symptom_service = services.get_symptom_service()
    
    report = await symptom_service.get_symptoms_for_provider_report(
        patient_id=patient_id,
        start_date=start_date,
        end_date=end_date,
        db=db
    )
    
    return SymptomProviderReport(**report)
