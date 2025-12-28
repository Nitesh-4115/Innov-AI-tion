"""
API Dependencies
Common dependencies for FastAPI endpoints
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from database import SessionLocal, get_db_context
from config import settings


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency
    Yields a SQLAlchemy session and ensures cleanup
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Optional[str]:
    """
    API key authentication dependency
    Returns the API key if provided
    """
    return x_api_key


async def verify_api_key(
    api_key: Optional[str] = Depends(get_api_key)
) -> str:
    """
    Verify API key is valid
    Raises HTTPException if invalid
    """
    if not settings.API_KEY_ENABLED:
        return "no-key-required"
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "API-Key"},
        )
    
    # In production, validate against stored keys
    valid_keys = settings.VALID_API_KEYS if hasattr(settings, 'VALID_API_KEYS') else []
    
    if api_key not in valid_keys and api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )
    
    return api_key


class RateLimiter:
    """
    Simple rate limiter for API endpoints
    """
    
    def __init__(self, calls: int = 100, period: int = 60):
        self.calls = calls
        self.period = period
        self._requests: dict = {}
    
    async def __call__(
        self,
        api_key: str = Depends(get_api_key)
    ) -> bool:
        """Check rate limit for the given API key"""
        import time
        
        key = api_key or "anonymous"
        current_time = time.time()
        
        if key not in self._requests:
            self._requests[key] = []
        
        # Clean old requests
        self._requests[key] = [
            t for t in self._requests[key]
            if current_time - t < self.period
        ]
        
        if len(self._requests[key]) >= self.calls:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {self.calls} requests per {self.period}s",
            )
        
        self._requests[key].append(current_time)
        return True


# Rate limiter instances
default_rate_limiter = RateLimiter(calls=100, period=60)
strict_rate_limiter = RateLimiter(calls=20, period=60)


async def get_current_patient_id(
    patient_id: int,
    db: Session = Depends(get_db)
) -> int:
    """
    Validate patient exists and return patient ID
    """
    from models import Patient
    
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found"
        )
    
    if not patient.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Patient {patient_id} is not active"
        )
    
    return patient_id


def pagination_params(
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    Common pagination parameters
    """
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 20
    if page_size > 100:
        page_size = 100
    
    return {
        "page": page,
        "page_size": page_size,
        "offset": (page - 1) * page_size
    }


class ServiceDependency:
    """
    Dependency injection for services
    """
    
    @staticmethod
    def get_patient_service():
        from services.patient_service import patient_service
        return patient_service
    
    @staticmethod
    def get_medication_service():
        from services.medication_service import medication_service
        return medication_service
    
    @staticmethod
    def get_adherence_service():
        from services.adherence_service import adherence_service
        return adherence_service
    
    @staticmethod
    def get_schedule_service():
        from services.schedule_service import schedule_service
        return schedule_service
    
    @staticmethod
    def get_symptom_service():
        from services.symptom_service import symptom_service
        return symptom_service
    
    @staticmethod
    def get_report_service():
        from services.report_service import report_service
        return report_service
    
    @staticmethod
    def get_llm_service():
        from services.llm_service import llm_service
        return llm_service


# Service dependency instances
services = ServiceDependency()
