"""
Database Models
SQLAlchemy ORM models for AdherenceGuardian
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Date, Time, Enum, Index, UniqueConstraint, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, time
from enum import Enum as PyEnum

from database import Base


# ==================== ENUMS ====================

class AdherenceStatus(str, PyEnum):
    """Status of a scheduled medication dose"""
    TAKEN = "taken"
    MISSED = "missed"
    SKIPPED = "skipped"
    DELAYED = "delayed"
    PENDING = "pending"


class BarrierCategory(str, PyEnum):
    """Categories of adherence barriers"""
    COST = "cost"
    SIDE_EFFECTS = "side_effects"
    COMPLEXITY = "complexity"
    FORGETFULNESS = "forgetfulness"
    LACK_OF_UNDERSTANDING = "lack_of_understanding"
    ACCESS = "access"
    OTHER = "other"


class SeverityLevel(str, PyEnum):
    """Severity levels for symptoms and barriers"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AgentType(str, PyEnum):
    """Types of AI agents"""
    ORCHESTRATOR = "orchestrator"
    PLANNING = "planning"
    MONITORING = "monitoring"
    BARRIER = "barrier"
    LIAISON = "liaison"


class InterventionType(str, PyEnum):
    """Types of interventions"""
    REMINDER = "reminder"
    EDUCATION = "education"
    SCHEDULE_ADJUSTMENT = "schedule_adjustment"
    COST_ASSISTANCE = "cost_assistance"
    PROVIDER_ALERT = "provider_alert"
    BEHAVIORAL = "behavioral"


# ==================== MODELS ====================

class Patient(Base):
    """Patient profile with lifestyle preferences for scheduling"""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, index=True)  # For external integration
    
    # Personal info
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(20))
    date_of_birth = Column(Date)
    age = Column(Integer)
    
    # Medical info
    conditions = Column(JSON, default=list)  # List of chronic conditions
    allergies = Column(JSON, default=list)   # Drug allergies
    
    # Lifestyle preferences (for smart scheduling)
    timezone = Column(String(50), default="UTC")
    wake_time = Column(Time, default=time(7, 0))
    sleep_time = Column(Time, default=time(22, 0))
    breakfast_time = Column(Time, default=time(8, 0))
    lunch_time = Column(Time, default=time(12, 0))
    dinner_time = Column(Time, default=time(19, 0))
    
    # Notification preferences
    notification_preferences = Column(JSON, default=dict)
    preferred_reminder_minutes = Column(Integer, default=15)
    
    # Status
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    medications = relationship("Medication", back_populates="patient", cascade="all, delete-orphan")
    adherence_logs = relationship("AdherenceLog", back_populates="patient", cascade="all, delete-orphan")
    symptom_reports = relationship("SymptomReport", back_populates="patient", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="patient", cascade="all, delete-orphan")
    agent_activities = relationship("AgentActivity", back_populates="patient", cascade="all, delete-orphan")
    barriers = relationship("BarrierResolution", back_populates="patient", cascade="all, delete-orphan")
    provider_reports = relationship("ProviderReport", back_populates="patient", cascade="all, delete-orphan")
    interventions = relationship("Intervention", back_populates="patient", cascade="all, delete-orphan")
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def conditions_list(self) -> list:
        if isinstance(self.conditions, list):
            return self.conditions
        return self.conditions.split(",") if self.conditions else []

class Medication(Base):
    """Medication information with drug interaction support"""
    __tablename__ = "medications"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    
    # Drug identification
    name = Column(String(255), nullable=False)
    generic_name = Column(String(255))
    rxnorm_id = Column(String(50), index=True)  # RxNorm concept ID
    ndc_code = Column(String(20))  # National Drug Code
    
    # Dosage info
    dosage = Column(String(100), nullable=False)  # e.g., "500mg"
    dosage_form = Column(String(100))  # e.g., "tablet", "capsule"
    strength = Column(String(50))
    strength_unit = Column(String(20))  # e.g., "mg", "ml"
    
    # Frequency
    frequency = Column(String(100), nullable=False)  # "2x daily", "once daily"
    frequency_per_day = Column(Integer, default=1)
    
    # Instructions
    instructions = Column(Text)
    with_food = Column(Boolean, default=False)
    with_water = Column(Boolean, default=True)
    
    # Constraints
    max_daily_doses = Column(Integer)
    min_hours_between_doses = Column(Float)
    
    # Additional info
    notes = Column(Text)
    purpose = Column(String(255))  # Why prescribed
    # Recurring schedule template (list of HH:MM strings) - used to generate daily schedules
    recurring_times = Column(JSON, default=list)
    
    # Status
    active = Column(Boolean, default=True)
    start_date = Column(Date)
    end_date = Column(Date)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="medications")
    adherence_logs = relationship("AdherenceLog", back_populates="medication", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="medication", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("ix_medications_patient_active", "patient_id", "active"),
    )

class Schedule(Base):
    """Daily medication schedule with smart timing"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"))
    
    # Schedule details
    scheduled_date = Column(Date, nullable=False)
    scheduled_time = Column(String(10), nullable=False)  # "08:00", "20:00"
    
    # Medication info (can link to medication or store directly)
    medications_list = Column(JSON)  # List of medication names/ids for this slot
    
    # Context
    meal_relation = Column(String(20))  # "before", "with", "after"
    
    # Status
    status = Column(String(20), default="pending")  # pending, taken, missed, skipped
    
    # Reminders
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime)
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="schedules")
    medication = relationship("Medication", back_populates="schedules")
    
    __table_args__ = (
        Index("ix_schedules_patient_date", "patient_id", "scheduled_date"),
    )

class AdherenceLog(Base):
    """Log of medication adherence with detailed tracking"""
    __tablename__ = "adherence_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    schedule_id = Column(Integer, ForeignKey("schedules.id"))
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    
    # Timing
    scheduled_time = Column(DateTime, nullable=False)
    actual_time = Column(DateTime)
    deviation_minutes = Column(Integer)  # How late if delayed
    
    # Status
    status = Column(Enum(AdherenceStatus), default=AdherenceStatus.PENDING)
    taken = Column(Boolean, nullable=False, default=False)
    
    # Details
    dose_taken = Column(String(50))  # Actual dose if different
    skip_reason = Column(Text)
    notes = Column(Text)
    
    # Source
    logged_by = Column(String(50), default="user")  # "user", "caregiver", "system"
    confirmation_method = Column(String(50))  # "manual", "smart_pill_box", "voice"
    
    logged_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="adherence_logs")
    medication = relationship("Medication", back_populates="adherence_logs")
    schedule = relationship("Schedule")
    
    __table_args__ = (
        Index("ix_adherence_patient_date", "patient_id", "scheduled_time"),
        Index("ix_adherence_status", "status"),
    )

class SymptomReport(Base):
    """User-reported symptoms with AI correlation analysis"""
    __tablename__ = "symptom_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    
    # Symptom details
    symptom = Column(String(255), nullable=False)
    description = Column(Text)
    severity = Column(Integer, nullable=False)  # 1-10 scale
    
    # Suspected medication
    medication_name = Column(String(255))
    suspected_medication_id = Column(Integer, ForeignKey("medications.id"))
    timing = Column(String(200))  # When symptom occurred relative to dose
    
    # Timing details
    onset_datetime = Column(DateTime)
    duration_minutes = Column(Integer)
    frequency_pattern = Column(String(100))  # "constant", "intermittent", "first time"
    
    # AI Analysis
    analyzed = Column(Boolean, default=False)
    analysis_result = Column(JSON)  # AI analysis results
    correlation_score = Column(Float)  # Likelihood it's medication-related (0-1)
    
    # Resolution
    escalated = Column(Boolean, default=False)
    escalated_to_provider = Column(Boolean, default=False)
    is_resolved = Column(Boolean, default=False)
    resolution_notes = Column(Text)
    
    reported_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="symptom_reports")
    suspected_medication = relationship("Medication")
    
    __table_args__ = (
        Index("ix_symptoms_patient_date", "patient_id", "reported_at"),
    )

class AgentActivity(Base):
    """Log of agent actions for transparency and debugging"""
    __tablename__ = "agent_activities"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    
    # Agent info
    agent_name = Column(String(50), nullable=False)  # Planning, Monitoring, etc.
    agent_type = Column(Enum(AgentType))
    action = Column(String(200), nullable=False)
    activity_type = Column(String(50))  # planning, monitoring, alert, resolution
    
    # Input/Output
    input_data = Column(JSON)
    output_data = Column(JSON)
    details = Column(Text)  # JSON string with details
    reasoning = Column(Text)  # Chain of thought
    
    # Tool usage
    tools_used = Column(JSON)  # List of tools invoked
    
    # Performance
    execution_time_ms = Column(Integer)
    tokens_used = Column(Integer)
    
    # Status
    is_successful = Column(Boolean, default=True)
    error_message = Column(Text)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="agent_activities")
    
    __table_args__ = (
        Index("ix_agent_activities_patient", "patient_id"),
        Index("ix_agent_activities_type_date", "agent_type", "timestamp"),
    )

class DrugInteraction(Base):
    """Drug interaction database cache"""
    __tablename__ = "drug_interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Drug pair
    drug1 = Column(String(255), nullable=False, index=True)
    drug1_rxnorm_id = Column(String(50))
    drug2 = Column(String(255), nullable=False, index=True)
    drug2_rxnorm_id = Column(String(50))
    
    # Interaction details
    severity = Column(Enum(SeverityLevel))  # low, medium, high, critical
    severity_text = Column(String(20))  # mild, moderate, severe
    description = Column(Text)
    mechanism = Column(Text)
    management = Column(Text)  # How to manage the interaction
    
    # Timing constraints
    separation_hours = Column(Integer, default=0)
    
    # Source
    source = Column(String(100))  # DrugBank, RxNorm, etc.
    source_id = Column(String(100))
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint("drug1", "drug2", name="uq_drug_pair"),
        Index("ix_drug_interactions_pair", "drug1", "drug2"),
    )

class BarrierResolution(Base):
    """Tracked barriers and resolutions"""
    __tablename__ = "barrier_resolutions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"))
    
    # Barrier details
    barrier_type = Column(Enum(BarrierCategory), nullable=False)
    barrier_type_text = Column(String(50))  # cost, side_effect, complexity, etc.
    description = Column(Text, nullable=False)
    severity = Column(Enum(SeverityLevel), default=SeverityLevel.MEDIUM)
    
    identified_at = Column(DateTime, default=datetime.utcnow)
    
    # Agent handling
    identified_by_agent = Column(Enum(AgentType))
    resolved_by_agent = Column(Enum(AgentType))
    
    # Resolution
    resolved = Column(Boolean, default=False)
    resolution_strategy = Column(Text)
    resolution_actions = Column(JSON)  # List of actions taken
    resolved_at = Column(DateTime)
    
    # Effectiveness
    effectiveness_score = Column(Float)  # 0-1 scale
    patient_feedback = Column(Text)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient", back_populates="barriers")
    medication = relationship("Medication")
    interventions = relationship("Intervention", back_populates="barrier")

class ProviderReport(Base):
    """Generated provider reports with FHIR compatibility"""
    __tablename__ = "provider_reports"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    
    # Report period
    report_period_start = Column(Date, nullable=False)
    report_period_end = Column(Date, nullable=False)
    
    # Metrics
    overall_adherence = Column(Float)
    doses_taken = Column(Integer)
    doses_missed = Column(Integer)
    doses_delayed = Column(Integer)
    
    # Content
    summary = Column(Text)
    medications_summary = Column(JSON)  # Per-medication breakdown
    barriers_summary = Column(JSON)
    symptoms_summary = Column(JSON)
    recommendations = Column(JSON)
    concerns = Column(Text)
    
    # FHIR compatibility
    fhir_json = Column(JSON)  # FHIR-formatted report
    
    # Delivery status
    is_sent = Column(Boolean, default=False)
    sent_to = Column(String(255))  # Provider email/system
    sent_at = Column(DateTime)
    
    generated_at = Column(DateTime, default=datetime.utcnow)
    generated_by_agent = Column(Enum(AgentType), default=AgentType.LIAISON)
    
    # Relationships
    patient = relationship("Patient", back_populates="provider_reports")


class Intervention(Base):
    """Intervention records for tracking agent actions"""
    __tablename__ = "interventions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    barrier_id = Column(Integer, ForeignKey("barrier_resolutions.id"))
    
    # Intervention details
    type = Column(Enum(InterventionType), nullable=False)
    type_text = Column(String(50))
    description = Column(Text, nullable=False)
    action_taken = Column(Text)
    
    # Agent info
    initiated_by_agent = Column(Enum(AgentType))
    agent_reasoning = Column(Text)  # Why this intervention was chosen
    
    # Outcome
    is_successful = Column(Boolean)
    outcome_notes = Column(Text)
    patient_feedback = Column(Text)
    effectiveness_score = Column(Float)  # 0-1 scale
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    patient = relationship("Patient", back_populates="interventions")
    barrier = relationship("BarrierResolution", back_populates="interventions")


class Prescription(Base):
    """Prescription records from providers"""
    __tablename__ = "prescriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    
    # Prescription details
    prescriber_name = Column(String(255))
    prescriber_npi = Column(String(20))  # National Provider Identifier
    pharmacy_name = Column(String(255))
    pharmacy_phone = Column(String(20))
    
    # Quantities
    quantity_prescribed = Column(Integer)
    quantity_remaining = Column(Integer)
    refills_remaining = Column(Integer, default=0)
    
    # Dates
    prescribed_date = Column(Date)
    filled_date = Column(Date)
    expiration_date = Column(Date)
    next_refill_date = Column(Date)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    patient = relationship("Patient")
    medication = relationship("Medication")


class CostAssistanceProgram(Base):
    """Cost assistance programs database"""
    __tablename__ = "cost_assistance_programs"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Program info
    program_name = Column(String(255), nullable=False)
    provider = Column(String(255))  # Manufacturer, nonprofit, etc.
    program_type = Column(String(50))  # "manufacturer", "copay_card", "patient_assistance", "discount"
    
    # Drug coverage
    medications_covered = Column(JSON)  # List of medication names/rxnorm_ids
    
    # Eligibility
    eligibility_criteria = Column(Text)
    income_limit = Column(Integer)  # Annual income limit
    insurance_required = Column(Boolean)
    
    # Benefits
    savings_description = Column(Text)
    max_savings = Column(Float)
    
    # Contact
    website = Column(String(500))
    phone = Column(String(20))
    application_url = Column(String(500))
    
    # Status
    is_active = Column(Boolean, default=True)
    verified_date = Column(Date)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)