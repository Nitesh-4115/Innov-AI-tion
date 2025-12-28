"""
Reports API Router
Endpoints for provider report generation
"""

from typing import Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from api.deps import get_db, services
from api.schemas.report import (
    ReportCreate,
    ProviderReportResponse,
    ProviderReportDetail,
    ProviderReportSummary,
    ReportList,
    QuickSummaryResponse,
    FHIRExportResponse,
    ReportExportResponse,
)


router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/", response_model=ProviderReportResponse, status_code=status.HTTP_201_CREATED)
async def create_provider_report(
    report_data: ReportCreate,
    db: Session = Depends(get_db)
):
    """
    Create a comprehensive provider report
    
    - **patient_id**: Patient ID
    - **report_period_start**: Start date of reporting period
    - **report_period_end**: End date of reporting period
    - **include_fhir**: Whether to include FHIR R4 bundle
    """
    report_service = services.get_report_service()
    
    try:
        report = await report_service.create_provider_report(
            patient_id=report_data.patient_id,
            report_period_start=report_data.report_period_start,
            report_period_end=report_data.report_period_end,
            provider_id=report_data.provider_id,
            include_fhir=report_data.include_fhir,
            db=db
        )
        
        return ProviderReportResponse(
            id=report.id,
            patient_id=report.patient_id,
            provider_id=report.provider_id,
            report_period_start=report.report_period_start,
            report_period_end=report.report_period_end,
            overall_adherence_score=report.overall_adherence_score,
            adherence_summary=report.adherence_summary,
            medication_summary=report.medication_summary,
            symptom_summary=report.symptom_summary,
            barrier_summary=report.barrier_summary,
            interventions=report.interventions,
            recommendations=report.recommendations,
            generated_at=report.generated_at
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/patient/{patient_id}", response_model=ReportList)
async def get_patient_reports(
    patient_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get recent provider reports for a patient
    """
    report_service = services.get_report_service()
    
    reports = await report_service.get_patient_reports(
        patient_id=patient_id,
        limit=limit,
        db=db
    )
    
    return ReportList(
        patient_id=patient_id,
        reports=[
            ProviderReportSummary(
                id=r.id,
                patient_id=r.patient_id,
                report_period_start=r.report_period_start,
                report_period_end=r.report_period_end,
                overall_adherence_score=r.overall_adherence_score,
                generated_at=r.generated_at
            ) for r in reports
        ],
        total=len(reports)
    )


@router.get("/{report_id}", response_model=ProviderReportDetail)
async def get_report(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific provider report
    """
    report_service = services.get_report_service()
    patient_service = services.get_patient_service()
    
    report = await report_service.get_report(report_id, db=db)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found"
        )
    
    # Get patient name
    patient = await patient_service.get_patient(report.patient_id, db=db)
    patient_name = patient.full_name if patient else None
    
    return ProviderReportDetail(
        id=report.id,
        patient_id=report.patient_id,
        patient_name=patient_name,
        provider_id=report.provider_id,
        report_period_start=report.report_period_start,
        report_period_end=report.report_period_end,
        overall_adherence_score=report.overall_adherence_score,
        adherence_summary=report.adherence_summary,
        medication_summary=report.medication_summary,
        symptom_summary=report.symptom_summary,
        barrier_summary=report.barrier_summary,
        interventions=report.interventions,
        recommendations=report.recommendations,
        generated_at=report.generated_at,
        fhir_available=report.fhir_bundle is not None
    )


@router.get("/{report_id}/fhir", response_model=FHIRExportResponse)
async def get_report_fhir(
    report_id: int,
    db: Session = Depends(get_db)
):
    """
    Get FHIR R4 bundle for a report
    """
    report_service = services.get_report_service()
    
    report = await report_service.get_report(report_id, db=db)
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found"
        )
    
    if not report.fhir_bundle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"FHIR bundle not available for report {report_id}. "
                   "Create report with include_fhir=true"
        )
    
    from datetime import datetime
    
    return FHIRExportResponse(
        report_id=report_id,
        patient_id=report.patient_id,
        fhir_bundle=report.fhir_bundle,
        exported_at=datetime.utcnow().isoformat()
    )


@router.get("/{report_id}/export", response_model=ReportExportResponse)
async def export_report(
    report_id: int,
    format: str = Query("json", description="Export format: json, fhir"),
    db: Session = Depends(get_db)
):
    """
    Export report in various formats
    """
    report_service = services.get_report_service()
    
    if format == "json":
        content = await report_service.export_report_json(report_id, db=db)
        
        if not content:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Report {report_id} not found"
            )
    elif format == "fhir":
        fhir = await report_service.get_report_as_fhir(report_id, db=db)
        
        if not fhir:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"FHIR export not available for report {report_id}"
            )
        
        import json
        content = json.dumps(fhir, indent=2)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format: {format}. Supported: json, fhir"
        )
    
    from datetime import datetime
    
    return ReportExportResponse(
        report_id=report_id,
        format=format,
        content=content,
        exported_at=datetime.utcnow().isoformat()
    )


@router.get("/patient/{patient_id}/quick-summary", response_model=QuickSummaryResponse)
async def get_quick_summary(
    patient_id: int,
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db)
):
    """
    Get a quick summary without creating a full report
    """
    report_service = services.get_report_service()
    
    try:
        summary = await report_service.generate_quick_summary(
            patient_id=patient_id,
            days=days,
            db=db
        )
        
        return QuickSummaryResponse(**summary)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/patient/{patient_id}/generate")
async def generate_report(
    patient_id: int,
    days: int = Query(30, ge=7, le=90),
    include_fhir: bool = Query(False),
    provider_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Generate a new report for the last N days
    """
    from datetime import timedelta
    
    report_service = services.get_report_service()
    
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    
    try:
        report = await report_service.create_provider_report(
            patient_id=patient_id,
            report_period_start=start_date,
            report_period_end=end_date,
            provider_id=provider_id,
            include_fhir=include_fhir,
            db=db
        )
        
        return {
            "report_id": report.id,
            "patient_id": report.patient_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days
            },
            "overall_adherence_score": report.overall_adherence_score,
            "generated_at": report.generated_at.isoformat(),
            "fhir_available": report.fhir_bundle is not None
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/patient/{patient_id}/analytics")
async def get_report_analytics(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get analytics across all reports for a patient
    """
    report_service = services.get_report_service()
    
    reports = await report_service.get_patient_reports(
        patient_id=patient_id,
        limit=50,
        db=db
    )
    
    if not reports:
        return {
            "patient_id": patient_id,
            "total_reports": 0,
            "average_adherence": None,
            "adherence_trend": "insufficient_data",
            "reports_this_month": 0
        }
    
    # Calculate analytics
    from datetime import datetime, timedelta
    
    adherence_scores = [
        r.overall_adherence_score for r in reports
        if r.overall_adherence_score is not None
    ]
    
    avg_adherence = sum(adherence_scores) / len(adherence_scores) if adherence_scores else None
    
    # Determine trend
    trend = "stable"
    if len(adherence_scores) >= 3:
        recent = adherence_scores[:3]
        older = adherence_scores[3:6] if len(adherence_scores) >= 6 else adherence_scores[3:]
        
        if older:
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            
            if recent_avg > older_avg + 5:
                trend = "improving"
            elif recent_avg < older_avg - 5:
                trend = "declining"
    
    # Count this month's reports
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    reports_this_month = sum(
        1 for r in reports
        if r.generated_at >= month_start
    )
    
    return {
        "patient_id": patient_id,
        "total_reports": len(reports),
        "average_adherence": round(avg_adherence, 1) if avg_adherence else None,
        "adherence_trend": trend,
        "reports_this_month": reports_this_month,
        "latest_report": {
            "id": reports[0].id,
            "date": reports[0].generated_at.isoformat(),
            "adherence_score": reports[0].overall_adherence_score
        } if reports else None
    }
