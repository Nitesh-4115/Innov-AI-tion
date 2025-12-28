"""
API Module
FastAPI routers for the AdherenceGuardian application
"""

from api.patients import router as patients_router
from api.medications import router as medications_router
from api.adherence import router as adherence_router
from api.schedules import router as schedules_router
from api.symptoms import router as symptoms_router
from api.reports import router as reports_router
from api.chat import router as chat_router

from api.deps import (
    get_db,
    get_api_key,
    verify_api_key,
    RateLimiter,
    default_rate_limiter,
    strict_rate_limiter,
    get_current_patient_id,
    pagination_params,
    services,
)


__all__ = [
    # Routers
    "patients_router",
    "medications_router",
    "adherence_router",
    "schedules_router",
    "symptoms_router",
    "reports_router",
    "chat_router",
    # Dependencies
    "get_db",
    "get_api_key",
    "verify_api_key",
    "RateLimiter",
    "default_rate_limiter",
    "strict_rate_limiter",
    "get_current_patient_id",
    "pagination_params",
    "services",
]


def include_routers(app):
    """
    Include all API routers in the FastAPI app
    
    Usage:
        from api import include_routers
        include_routers(app)
    """
    app.include_router(patients_router, prefix="/api/v1")
    app.include_router(medications_router, prefix="/api/v1")
    app.include_router(adherence_router, prefix="/api/v1")
    app.include_router(schedules_router, prefix="/api/v1")
    app.include_router(symptoms_router, prefix="/api/v1")
    app.include_router(reports_router, prefix="/api/v1")
    app.include_router(chat_router, prefix="/api/v1")
