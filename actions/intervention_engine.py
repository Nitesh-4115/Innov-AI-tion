"""
Intervention Engine
Generates and manages interventions for medication adherence barriers
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid


logger = logging.getLogger(__name__)


class InterventionType(str, Enum):
    """Types of interventions"""
    EDUCATION = "education"
    REMINDER_ADJUSTMENT = "reminder_adjustment"
    SCHEDULE_CHANGE = "schedule_change"
    COST_ASSISTANCE = "cost_assistance"
    SIDE_EFFECT_MANAGEMENT = "side_effect_management"
    LIFESTYLE_MODIFICATION = "lifestyle_modification"
    PROVIDER_COMMUNICATION = "provider_communication"
    SUPPORT_SYSTEM = "support_system"
    SIMPLIFICATION = "simplification"
    MOTIVATIONAL = "motivational"


class InterventionStatus(str, Enum):
    """Intervention status"""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    DECLINED = "declined"
    INEFFECTIVE = "ineffective"
    PAUSED = "paused"


class BarrierCategory(str, Enum):
    """Categories of adherence barriers"""
    FORGETFULNESS = "forgetfulness"
    COST = "cost"
    SIDE_EFFECTS = "side_effects"
    COMPLEXITY = "complexity"
    BELIEFS = "beliefs"
    ACCESS = "access"
    LIFESTYLE = "lifestyle"
    KNOWLEDGE = "knowledge"
    MOTIVATION = "motivation"
    PHYSICAL = "physical"


@dataclass
class Intervention:
    """Intervention data structure"""
    id: str
    patient_id: int
    intervention_type: InterventionType
    barrier_category: BarrierCategory
    title: str
    description: str
    actions: List[str]
    status: InterventionStatus = InterventionStatus.PROPOSED
    priority: int = 5  # 1-10 scale
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    effectiveness_score: Optional[float] = None  # 0-100
    follow_up_date: Optional[datetime] = None
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "intervention_type": self.intervention_type.value,
            "barrier_category": self.barrier_category.value,
            "title": self.title,
            "description": self.description,
            "actions": self.actions,
            "status": self.status.value,
            "priority": self.priority,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "effectiveness_score": self.effectiveness_score,
            "follow_up_date": self.follow_up_date.isoformat() if self.follow_up_date else None,
            "notes": self.notes,
            "metadata": self.metadata
        }
    
    def accept(self):
        """Accept the intervention"""
        self.status = InterventionStatus.ACCEPTED
    
    def start(self):
        """Start the intervention"""
        self.status = InterventionStatus.ACTIVE
        self.started_at = datetime.utcnow()
    
    def complete(self, effectiveness: Optional[float] = None):
        """Complete the intervention"""
        self.status = InterventionStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if effectiveness is not None:
            self.effectiveness_score = effectiveness
    
    def decline(self):
        """Decline the intervention"""
        self.status = InterventionStatus.DECLINED
    
    def mark_ineffective(self, reason: str = ""):
        """Mark intervention as ineffective"""
        self.status = InterventionStatus.INEFFECTIVE
        if reason:
            self.notes.append(f"Marked ineffective: {reason}")
    
    def add_note(self, note: str):
        """Add a note to the intervention"""
        self.notes.append(f"[{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}] {note}")


# Intervention templates for different barriers
INTERVENTION_TEMPLATES: Dict[BarrierCategory, List[Dict[str, Any]]] = {
    BarrierCategory.FORGETFULNESS: [
        {
            "type": InterventionType.REMINDER_ADJUSTMENT,
            "title": "Enhanced Reminder System",
            "description": "Set up multiple reminder types and channels to help remember medications.",
            "actions": [
                "Enable push notifications 15 minutes before each dose",
                "Set up backup SMS reminder",
                "Add medication alarm on phone",
                "Place medications in visible location"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.LIFESTYLE_MODIFICATION,
            "title": "Routine Integration",
            "description": "Link medication taking to existing daily routines.",
            "actions": [
                "Take morning medications with breakfast",
                "Keep evening medications by toothbrush",
                "Use a weekly pill organizer",
                "Set medications next to coffee maker"
            ],
            "priority": 7
        }
    ],
    
    BarrierCategory.COST: [
        {
            "type": InterventionType.COST_ASSISTANCE,
            "title": "Generic Medication Switch",
            "description": "Explore generic alternatives to reduce medication costs.",
            "actions": [
                "Ask provider about generic alternatives",
                "Compare prices at different pharmacies",
                "Check manufacturer discount programs",
                "Apply for patient assistance programs"
            ],
            "priority": 9
        },
        {
            "type": InterventionType.COST_ASSISTANCE,
            "title": "Financial Assistance Programs",
            "description": "Connect with programs that help cover medication costs.",
            "actions": [
                "Review eligibility for manufacturer copay cards",
                "Apply to NeedyMeds or RxAssist programs",
                "Contact social worker for assistance",
                "Check state pharmaceutical assistance programs"
            ],
            "priority": 8
        }
    ],
    
    BarrierCategory.SIDE_EFFECTS: [
        {
            "type": InterventionType.SIDE_EFFECT_MANAGEMENT,
            "title": "Side Effect Mitigation Strategy",
            "description": "Implement strategies to reduce side effect impact.",
            "actions": [
                "Take medication with food if GI upset",
                "Adjust timing to minimize impact on daily activities",
                "Stay hydrated throughout the day",
                "Track symptoms to identify patterns"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.PROVIDER_COMMUNICATION,
            "title": "Provider Consultation for Side Effects",
            "description": "Schedule discussion with provider about side effect concerns.",
            "actions": [
                "Document all side effects experienced",
                "Note severity and timing of symptoms",
                "Schedule appointment with provider",
                "Ask about alternative medications"
            ],
            "priority": 9
        }
    ],
    
    BarrierCategory.COMPLEXITY: [
        {
            "type": InterventionType.SIMPLIFICATION,
            "title": "Regimen Simplification",
            "description": "Work with provider to simplify medication schedule.",
            "actions": [
                "Request once-daily formulations when available",
                "Ask about combination medications",
                "Consolidate medication times where possible",
                "Use a comprehensive pill organizer"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.EDUCATION,
            "title": "Medication Organization Education",
            "description": "Learn techniques to manage complex medication regimens.",
            "actions": [
                "Create a medication schedule chart",
                "Use color-coded pill organizers",
                "Set up a medication tracking app",
                "Attend medication management class"
            ],
            "priority": 7
        }
    ],
    
    BarrierCategory.BELIEFS: [
        {
            "type": InterventionType.EDUCATION,
            "title": "Medication Education Program",
            "description": "Provide education about medication importance and how it works.",
            "actions": [
                "Review how each medication helps your condition",
                "Discuss what happens if medications aren't taken",
                "Address specific concerns about medications",
                "Provide reliable educational resources"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.MOTIVATIONAL,
            "title": "Motivational Support",
            "description": "Strengthen motivation for medication adherence.",
            "actions": [
                "Set personal health goals",
                "Connect medication use to valued activities",
                "Track health improvements",
                "Celebrate adherence milestones"
            ],
            "priority": 7
        }
    ],
    
    BarrierCategory.ACCESS: [
        {
            "type": InterventionType.SIMPLIFICATION,
            "title": "Pharmacy Access Improvement",
            "description": "Improve access to medications through delivery or transfer.",
            "actions": [
                "Set up mail-order pharmacy service",
                "Arrange pharmacy delivery",
                "Transfer prescriptions to more convenient pharmacy",
                "Request 90-day supplies"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.SCHEDULE_CHANGE,
            "title": "Refill Management System",
            "description": "Establish system to prevent running out of medications.",
            "actions": [
                "Set up automatic refills",
                "Add refill reminders to calendar",
                "Sync all medication refill dates",
                "Keep emergency supply on hand"
            ],
            "priority": 7
        }
    ],
    
    BarrierCategory.LIFESTYLE: [
        {
            "type": InterventionType.SCHEDULE_CHANGE,
            "title": "Schedule Adjustment",
            "description": "Adjust medication timing to fit your lifestyle.",
            "actions": [
                "Review work schedule constraints",
                "Identify optimal medication times",
                "Discuss timing flexibility with provider",
                "Create portable medication kit"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.LIFESTYLE_MODIFICATION,
            "title": "Travel and Activity Planning",
            "description": "Plan for maintaining adherence during travel and activities.",
            "actions": [
                "Pack extra medication for trips",
                "Set alarms adjusted for time zones",
                "Carry medication list and prescriptions",
                "Plan for storage requirements (refrigeration)"
            ],
            "priority": 6
        }
    ],
    
    BarrierCategory.KNOWLEDGE: [
        {
            "type": InterventionType.EDUCATION,
            "title": "Comprehensive Medication Review",
            "description": "Learn about your medications in detail.",
            "actions": [
                "Review purpose of each medication",
                "Learn proper administration techniques",
                "Understand timing and food interactions",
                "Know which side effects to report"
            ],
            "priority": 9
        },
        {
            "type": InterventionType.SUPPORT_SYSTEM,
            "title": "Pharmacist Consultation",
            "description": "Schedule consultation with pharmacist for medication education.",
            "actions": [
                "Book medication therapy management session",
                "Ask questions about each medication",
                "Review potential interactions",
                "Get written medication information"
            ],
            "priority": 7
        }
    ],
    
    BarrierCategory.MOTIVATION: [
        {
            "type": InterventionType.MOTIVATIONAL,
            "title": "Goal Setting and Tracking",
            "description": "Set health goals and track progress to stay motivated.",
            "actions": [
                "Define personal health goals",
                "Track adherence streaks",
                "Celebrate achievements",
                "Connect with support community"
            ],
            "priority": 7
        },
        {
            "type": InterventionType.SUPPORT_SYSTEM,
            "title": "Support Network Activation",
            "description": "Engage family or friends to support medication adherence.",
            "actions": [
                "Identify an accountability partner",
                "Share medication schedule with family",
                "Join a patient support group",
                "Regular check-ins with support person"
            ],
            "priority": 6
        }
    ],
    
    BarrierCategory.PHYSICAL: [
        {
            "type": InterventionType.SIMPLIFICATION,
            "title": "Accessibility Adaptations",
            "description": "Address physical barriers to taking medications.",
            "actions": [
                "Request easy-open medication containers",
                "Use large-print labels",
                "Get pill splitter or crusher if needed",
                "Arrange medications at accessible height"
            ],
            "priority": 8
        },
        {
            "type": InterventionType.SUPPORT_SYSTEM,
            "title": "Caregiver Assistance Setup",
            "description": "Arrange for caregiver support with medications.",
            "actions": [
                "Identify caregiver for medication assistance",
                "Train caregiver on medication administration",
                "Set up medication preparation routine",
                "Establish communication for refills"
            ],
            "priority": 8
        }
    ]
}


class InterventionEngine:
    """
    Engine for generating and managing adherence interventions
    
    Responsibilities:
    - Identify barriers to adherence
    - Recommend appropriate interventions
    - Track intervention effectiveness
    - Manage intervention lifecycle
    """
    
    def __init__(self):
        self._interventions: Dict[str, Intervention] = {}
        self._patient_interventions: Dict[int, List[str]] = {}
        self._effectiveness_history: Dict[str, List[float]] = {}
    
    def _generate_id(self) -> str:
        """Generate unique intervention ID"""
        return str(uuid.uuid4())[:8]
    
    def _add_intervention(self, intervention: Intervention):
        """Add intervention to storage"""
        self._interventions[intervention.id] = intervention
        
        if intervention.patient_id not in self._patient_interventions:
            self._patient_interventions[intervention.patient_id] = []
        self._patient_interventions[intervention.patient_id].append(intervention.id)
        
        logger.info(f"Created intervention {intervention.id}: {intervention.title}")
    
    def recommend_interventions(
        self,
        patient_id: int,
        barrier: BarrierCategory,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Intervention]:
        """
        Recommend interventions for a specific barrier
        
        Args:
            patient_id: Patient ID
            barrier: Type of adherence barrier
            context: Additional context about the barrier
            
        Returns:
            List of recommended interventions
        """
        templates = INTERVENTION_TEMPLATES.get(barrier, [])
        interventions = []
        
        for template in templates:
            intervention = Intervention(
                id=self._generate_id(),
                patient_id=patient_id,
                intervention_type=template["type"],
                barrier_category=barrier,
                title=template["title"],
                description=template["description"],
                actions=template["actions"].copy(),
                priority=template.get("priority", 5),
                metadata={"context": context or {}}
            )
            
            self._add_intervention(intervention)
            interventions.append(intervention)
        
        # Sort by priority
        interventions.sort(key=lambda i: i.priority, reverse=True)
        
        return interventions
    
    def create_custom_intervention(
        self,
        patient_id: int,
        intervention_type: InterventionType,
        barrier: BarrierCategory,
        title: str,
        description: str,
        actions: List[str],
        priority: int = 5
    ) -> Intervention:
        """Create a custom intervention"""
        intervention = Intervention(
            id=self._generate_id(),
            patient_id=patient_id,
            intervention_type=intervention_type,
            barrier_category=barrier,
            title=title,
            description=description,
            actions=actions,
            priority=priority
        )
        
        self._add_intervention(intervention)
        return intervention
    
    def get_intervention(self, intervention_id: str) -> Optional[Intervention]:
        """Get intervention by ID"""
        return self._interventions.get(intervention_id)
    
    def get_patient_interventions(
        self,
        patient_id: int,
        status: Optional[InterventionStatus] = None,
        barrier: Optional[BarrierCategory] = None
    ) -> List[Intervention]:
        """Get interventions for a patient"""
        intervention_ids = self._patient_interventions.get(patient_id, [])
        interventions = [
            self._interventions[iid] 
            for iid in intervention_ids 
            if iid in self._interventions
        ]
        
        if status:
            interventions = [i for i in interventions if i.status == status]
        if barrier:
            interventions = [i for i in interventions if i.barrier_category == barrier]
        
        return interventions
    
    def get_active_interventions(self, patient_id: int) -> List[Intervention]:
        """Get active interventions for a patient"""
        return self.get_patient_interventions(patient_id, status=InterventionStatus.ACTIVE)
    
    def accept_intervention(self, intervention_id: str) -> bool:
        """Accept an intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.accept()
            logger.info(f"Intervention {intervention_id} accepted")
            return True
        return False
    
    def start_intervention(self, intervention_id: str) -> bool:
        """Start an intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.start()
            logger.info(f"Intervention {intervention_id} started")
            return True
        return False
    
    def complete_intervention(
        self,
        intervention_id: str,
        effectiveness: Optional[float] = None,
        notes: str = ""
    ) -> bool:
        """Complete an intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.complete(effectiveness)
            if notes:
                intervention.add_note(notes)
            
            # Track effectiveness
            if effectiveness is not None:
                key = f"{intervention.barrier_category.value}:{intervention.intervention_type.value}"
                if key not in self._effectiveness_history:
                    self._effectiveness_history[key] = []
                self._effectiveness_history[key].append(effectiveness)
            
            logger.info(f"Intervention {intervention_id} completed with effectiveness {effectiveness}")
            return True
        return False
    
    def decline_intervention(
        self,
        intervention_id: str,
        reason: str = ""
    ) -> bool:
        """Decline an intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.decline()
            if reason:
                intervention.add_note(f"Declined: {reason}")
            logger.info(f"Intervention {intervention_id} declined")
            return True
        return False
    
    def mark_ineffective(
        self,
        intervention_id: str,
        reason: str = ""
    ) -> bool:
        """Mark intervention as ineffective"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.mark_ineffective(reason)
            
            # Track as zero effectiveness
            key = f"{intervention.barrier_category.value}:{intervention.intervention_type.value}"
            if key not in self._effectiveness_history:
                self._effectiveness_history[key] = []
            self._effectiveness_history[key].append(0)
            
            logger.info(f"Intervention {intervention_id} marked as ineffective")
            return True
        return False
    
    def add_intervention_note(
        self,
        intervention_id: str,
        note: str
    ) -> bool:
        """Add note to an intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.add_note(note)
            return True
        return False
    
    def set_follow_up(
        self,
        intervention_id: str,
        follow_up_date: datetime
    ) -> bool:
        """Set follow-up date for intervention"""
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.follow_up_date = follow_up_date
            logger.info(f"Set follow-up for intervention {intervention_id}: {follow_up_date}")
            return True
        return False
    
    def get_due_follow_ups(
        self,
        patient_id: Optional[int] = None
    ) -> List[Intervention]:
        """Get interventions with due follow-ups"""
        now = datetime.utcnow()
        
        if patient_id:
            interventions = self.get_active_interventions(patient_id)
        else:
            interventions = [
                i for i in self._interventions.values()
                if i.status == InterventionStatus.ACTIVE
            ]
        
        return [
            i for i in interventions
            if i.follow_up_date and i.follow_up_date <= now
        ]
    
    def get_effectiveness_stats(
        self,
        barrier: Optional[BarrierCategory] = None,
        intervention_type: Optional[InterventionType] = None
    ) -> Dict[str, Any]:
        """Get effectiveness statistics"""
        if barrier and intervention_type:
            key = f"{barrier.value}:{intervention_type.value}"
            scores = self._effectiveness_history.get(key, [])
        elif barrier:
            scores = []
            for key, values in self._effectiveness_history.items():
                if key.startswith(barrier.value):
                    scores.extend(values)
        elif intervention_type:
            scores = []
            for key, values in self._effectiveness_history.items():
                if key.endswith(intervention_type.value):
                    scores.extend(values)
        else:
            scores = []
            for values in self._effectiveness_history.values():
                scores.extend(values)
        
        if not scores:
            return {"average": None, "count": 0}
        
        return {
            "average": sum(scores) / len(scores),
            "count": len(scores),
            "min": min(scores),
            "max": max(scores)
        }
    
    def get_best_intervention_type(
        self,
        barrier: BarrierCategory
    ) -> Optional[InterventionType]:
        """Get most effective intervention type for a barrier"""
        best_type = None
        best_avg = 0
        
        for int_type in InterventionType:
            key = f"{barrier.value}:{int_type.value}"
            scores = self._effectiveness_history.get(key, [])
            
            if scores:
                avg = sum(scores) / len(scores)
                if avg > best_avg:
                    best_avg = avg
                    best_type = int_type
        
        return best_type
    
    def get_intervention_summary(self, patient_id: int) -> Dict[str, Any]:
        """Get summary of interventions for a patient"""
        interventions = self.get_patient_interventions(patient_id)
        
        summary = {
            "total": len(interventions),
            "by_status": {},
            "by_barrier": {},
            "by_type": {},
            "active_count": 0,
            "completed_count": 0,
            "avg_effectiveness": None
        }
        
        effectiveness_scores = []
        
        for intervention in interventions:
            # By status
            status = intervention.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # By barrier
            barrier = intervention.barrier_category.value
            summary["by_barrier"][barrier] = summary["by_barrier"].get(barrier, 0) + 1
            
            # By type
            int_type = intervention.intervention_type.value
            summary["by_type"][int_type] = summary["by_type"].get(int_type, 0) + 1
            
            # Counts
            if intervention.status == InterventionStatus.ACTIVE:
                summary["active_count"] += 1
            elif intervention.status == InterventionStatus.COMPLETED:
                summary["completed_count"] += 1
                if intervention.effectiveness_score is not None:
                    effectiveness_scores.append(intervention.effectiveness_score)
        
        if effectiveness_scores:
            summary["avg_effectiveness"] = sum(effectiveness_scores) / len(effectiveness_scores)
        
        return summary
    
    def identify_barriers_from_data(
        self,
        adherence_rate: float,
        missed_times: List[str],
        reported_issues: List[str]
    ) -> List[BarrierCategory]:
        """Identify likely barriers from adherence data"""
        barriers = []
        
        # Check time patterns
        if missed_times:
            morning_misses = sum(1 for t in missed_times if "AM" in t.upper() or int(t.split(":")[0]) < 12)
            evening_misses = sum(1 for t in missed_times if "PM" in t.upper() or int(t.split(":")[0]) >= 12)
            
            if morning_misses > len(missed_times) * 0.6:
                barriers.append(BarrierCategory.LIFESTYLE)  # Morning routine issues
            if evening_misses > len(missed_times) * 0.6:
                barriers.append(BarrierCategory.FORGETFULNESS)
        
        # Check reported issues
        issue_text = " ".join(reported_issues).lower()
        
        if any(word in issue_text for word in ["forget", "remember", "missed"]):
            barriers.append(BarrierCategory.FORGETFULNESS)
        if any(word in issue_text for word in ["cost", "expensive", "afford", "money"]):
            barriers.append(BarrierCategory.COST)
        if any(word in issue_text for word in ["side effect", "nausea", "dizzy", "sick"]):
            barriers.append(BarrierCategory.SIDE_EFFECTS)
        if any(word in issue_text for word in ["many", "complicated", "confusing", "schedule"]):
            barriers.append(BarrierCategory.COMPLEXITY)
        if any(word in issue_text for word in ["don't need", "not working", "why"]):
            barriers.append(BarrierCategory.BELIEFS)
        
        # Default to forgetfulness if no specific barrier identified
        if not barriers and adherence_rate < 80:
            barriers.append(BarrierCategory.FORGETFULNESS)
        
        return list(set(barriers))


# Singleton instance
intervention_engine = InterventionEngine()
