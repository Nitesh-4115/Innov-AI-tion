"""
Configuration management for AdherenceGuardian
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "AdherenceGuardian"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENV: str = "development"
    
    # API
    API_PREFIX: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    DATABASE_URL: str = "sqlite:///./adherence_guardian.db"
    DATABASE_ECHO: bool = False
    
    # LLM Configuration
    LLM_PROVIDER: str = "cerebras"  # Cerebras only
    CEREBRAS_API_KEY: Optional[str] = None
    CEREBRAS_BASE_URL: str = "https://api.cerebras.ai/v1"
    LLM_MODEL: str = "llama3.1-8b"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 4096
    
    # Vector Database (ChromaDB)
    CHROMA_PERSIST_DIRECTORY: str = "./data/embeddings"
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    
    # External APIs
    DRUGBANK_API_KEY: Optional[str] = None
    RXNORM_API_URL: str = "https://rxnav.nlm.nih.gov/REST"
    GOODRX_API_KEY: Optional[str] = None
    
    # Notifications
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Agent-specific configurations
class AgentConfig:
    """Configuration for agent behaviors"""
    
    # Planning Agent
    PLANNING_MAX_MEDICATIONS: int = 20
    PLANNING_TIME_SLOTS: list[str] = [
        "06:00", "08:00", "12:00", "14:00", "18:00", "20:00", "22:00"
    ]
    
    # Monitoring Agent
    MONITORING_ADHERENCE_TARGET: float = 0.90  # 90% target
    MONITORING_ANOMALY_THRESHOLD: float = 0.15  # 15% deviation triggers alert
    MONITORING_WINDOW_DAYS: int = 7
    
    # Barrier Agent
    BARRIER_CATEGORIES: list[str] = [
        "cost", "side_effects", "complexity", "forgetfulness", 
        "lack_of_understanding", "access", "other"
    ]
    
    # Liaison Agent
    LIAISON_SEVERITY_LEVELS: list[str] = ["low", "medium", "high", "critical"]
    LIAISON_ESCALATION_THRESHOLD: str = "high"
    
    # Safety boundaries
    SAFETY_NEVER_DIAGNOSE: bool = True
    SAFETY_NEVER_CHANGE_DOSAGE: bool = True
    SAFETY_ALWAYS_ESCALATE_SEVERE: bool = True


# Database table names
class TableNames:
    PATIENTS = "patients"
    MEDICATIONS = "medications"
    PRESCRIPTIONS = "prescriptions"
    SCHEDULES = "schedules"
    ADHERENCE_LOGS = "adherence_logs"
    SYMPTOM_REPORTS = "symptom_reports"
    BARRIERS = "barriers"
    PROVIDER_REPORTS = "provider_reports"
    INTERVENTIONS = "interventions"
    AGENT_LOGS = "agent_logs"


settings = get_settings()
agent_config = AgentConfig()
