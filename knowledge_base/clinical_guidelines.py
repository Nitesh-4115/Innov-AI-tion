"""
Clinical Guidelines
Clinical practice guidelines for medication adherence
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .vector_store import knowledge_base, Document


logger = logging.getLogger(__name__)


@dataclass
class ClinicalGuideline:
    """Clinical guideline data structure"""
    title: str
    content: str
    condition: str
    source: str
    year: int
    recommendations: List[str]
    evidence_level: str = "moderate"  # high, moderate, low
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "condition": self.condition,
            "source": self.source,
            "year": self.year,
            "recommendations": self.recommendations,
            "evidence_level": self.evidence_level
        }


# Built-in clinical guidelines for medication adherence
CLINICAL_GUIDELINES: List[ClinicalGuideline] = [
    # General Medication Adherence
    ClinicalGuideline(
        title="Medication Adherence in Chronic Disease Management",
        content="""Medication adherence is crucial for optimal outcomes in chronic disease management. 
        Studies show that approximately 50% of patients with chronic diseases do not take medications as prescribed. 
        Non-adherence leads to increased hospitalizations, disease progression, and healthcare costs.
        Key factors affecting adherence include: complexity of regimen, side effects, cost, 
        patient understanding, and social support.""",
        condition="general",
        source="WHO Guidelines on Medication Adherence",
        year=2023,
        recommendations=[
            "Simplify medication regimens when possible",
            "Use pill organizers and medication reminders",
            "Provide clear patient education",
            "Address cost barriers through assistance programs",
            "Regular follow-up and monitoring"
        ],
        evidence_level="high"
    ),
    
    # Diabetes
    ClinicalGuideline(
        title="Diabetes Medication Adherence Guidelines",
        content="""For patients with diabetes, medication adherence is essential for glycemic control 
        and prevention of complications. Oral antidiabetic agents should be taken consistently. 
        Insulin timing is critical - rapid-acting insulin should be taken with meals, 
        long-acting insulin at the same time daily. Blood glucose monitoring helps assess 
        medication effectiveness and timing.""",
        condition="diabetes",
        source="American Diabetes Association Standards of Care",
        year=2024,
        recommendations=[
            "Take metformin with meals to reduce GI side effects",
            "Inject insulin at consistent times daily",
            "Monitor blood glucose regularly",
            "Store insulin properly (refrigerate unopened, room temp when in use)",
            "Rotate injection sites to prevent lipodystrophy",
            "Carry glucose tablets for hypoglycemia episodes"
        ],
        evidence_level="high"
    ),
    
    # Hypertension
    ClinicalGuideline(
        title="Hypertension Medication Adherence",
        content="""Blood pressure medications must be taken consistently for effective control. 
        Many antihypertensives require several weeks to reach full effect. 
        Missing doses can cause blood pressure spikes. Common classes include ACE inhibitors, 
        ARBs, calcium channel blockers, and diuretics. Each has specific timing considerations.""",
        condition="hypertension",
        source="American Heart Association Guidelines",
        year=2023,
        recommendations=[
            "Take blood pressure medications at the same time daily",
            "Diuretics are best taken in the morning to avoid nighttime urination",
            "Do not stop medications without consulting healthcare provider",
            "Monitor blood pressure at home regularly",
            "ACE inhibitors: take on empty stomach if possible",
            "Report persistent dry cough (ACE inhibitor side effect)"
        ],
        evidence_level="high"
    ),
    
    # Cardiovascular
    ClinicalGuideline(
        title="Cardiovascular Disease Medication Management",
        content="""Cardiovascular medications including statins, antiplatelet agents, and beta-blockers 
        require consistent adherence for prevention of cardiac events. Statins should be taken 
        at the same time daily - some are more effective in the evening. Aspirin and antiplatelet 
        therapy must not be interrupted without medical guidance.""",
        condition="cardiovascular",
        source="ACC/AHA Clinical Practice Guidelines",
        year=2023,
        recommendations=[
            "Take statins at the same time daily (simvastatin in evening)",
            "Do not stop aspirin/antiplatelet without consulting doctor",
            "Take beta-blockers with food to improve absorption",
            "Monitor for muscle pain with statins (rare but serious)",
            "Avoid grapefruit with certain statins",
            "Report any bleeding or bruising with antiplatelet therapy"
        ],
        evidence_level="high"
    ),
    
    # Mental Health
    ClinicalGuideline(
        title="Psychiatric Medication Adherence",
        content="""Mental health medications often require consistent long-term use. 
        Antidepressants may take 4-6 weeks to show full effect. Abrupt discontinuation 
        can cause withdrawal symptoms. Mood stabilizers and antipsychotics require 
        regular monitoring of blood levels and side effects.""",
        condition="mental_health",
        source="American Psychiatric Association Guidelines",
        year=2023,
        recommendations=[
            "Continue antidepressants even when feeling better",
            "Do not stop psychiatric medications abruptly",
            "Report side effects rather than stopping medication",
            "Set consistent daily reminder for medication",
            "Attend all lab monitoring appointments",
            "Avoid alcohol with psychiatric medications"
        ],
        evidence_level="high"
    ),
    
    # Respiratory
    ClinicalGuideline(
        title="Respiratory Medication Adherence (COPD/Asthma)",
        content="""Inhaled medications are the cornerstone of respiratory disease management. 
        Proper inhaler technique is crucial - incorrect use significantly reduces effectiveness. 
        Controller inhalers must be used daily, not just when symptomatic. 
        Rescue inhalers should be used for acute symptoms.""",
        condition="respiratory",
        source="GOLD Guidelines / GINA Guidelines",
        year=2023,
        recommendations=[
            "Use controller inhalers daily as prescribed",
            "Practice proper inhaler technique",
            "Rinse mouth after using corticosteroid inhalers",
            "Keep rescue inhaler accessible at all times",
            "Replace inhalers before they run out",
            "Clean inhaler devices regularly"
        ],
        evidence_level="high"
    ),
    
    # Anticoagulation
    ClinicalGuideline(
        title="Anticoagulation Therapy Management",
        content="""Anticoagulants (blood thinners) require strict adherence due to serious 
        consequences of both missed doses (clots) and extra doses (bleeding). 
        Warfarin requires regular INR monitoring and dietary vitamin K consistency. 
        DOACs have more predictable effects but timing is still important.""",
        condition="anticoagulation",
        source="CHEST Guidelines on Antithrombotic Therapy",
        year=2023,
        recommendations=[
            "Take anticoagulants at the same time daily",
            "Never double up on missed doses",
            "Maintain consistent vitamin K intake with warfarin",
            "Attend all INR monitoring appointments",
            "Report any unusual bleeding or bruising immediately",
            "Inform all healthcare providers about anticoagulant use",
            "Wear medical alert identification"
        ],
        evidence_level="high"
    ),
    
    # HIV/AIDS
    ClinicalGuideline(
        title="Antiretroviral Therapy Adherence",
        content="""HIV antiretroviral therapy (ART) requires near-perfect adherence (>95%) 
        to maintain viral suppression and prevent resistance. Missing doses allows 
        viral replication and can lead to treatment failure. 
        Many ART regimens are now once-daily single-tablet combinations.""",
        condition="hiv",
        source="HHS Guidelines for HIV Treatment",
        year=2024,
        recommendations=[
            "Take ART at exactly the same time daily",
            "Never skip or delay doses",
            "Use pill reminders and alarms",
            "Plan for travel with extra medication supply",
            "Do not share medications",
            "Report all side effects to healthcare provider"
        ],
        evidence_level="high"
    ),
    
    # Pain Management
    ClinicalGuideline(
        title="Chronic Pain Medication Management",
        content="""Chronic pain medications require careful adherence to prescribed schedules. 
        For opioids, taking medications as scheduled (not PRN) provides better pain control. 
        Non-opioid alternatives should be maximized. Opioid tolerance and physical 
        dependence are expected with long-term use but differ from addiction.""",
        condition="chronic_pain",
        source="CDC Clinical Practice Guideline for Prescribing Opioids",
        year=2022,
        recommendations=[
            "Take pain medications on schedule, not just when pain is severe",
            "Use non-medication pain management alongside medications",
            "Store controlled substances securely",
            "Never share pain medications",
            "Do not mix opioids with alcohol or sedatives",
            "Discuss any concerns about medications openly with provider"
        ],
        evidence_level="moderate"
    ),
    
    # Elderly/Polypharmacy
    ClinicalGuideline(
        title="Medication Management in Elderly Patients",
        content="""Elderly patients often take multiple medications (polypharmacy), 
        increasing complexity and interaction risks. Medication reconciliation is essential. 
        Age-related changes affect drug metabolism and sensitivity. 
        Simplifying regimens and using aids improves adherence.""",
        condition="elderly",
        source="AGS Beers Criteria and Polypharmacy Guidelines",
        year=2023,
        recommendations=[
            "Use pill organizers with day/time compartments",
            "Maintain complete medication list including OTC and supplements",
            "Review medications with pharmacist regularly",
            "Request larger print labels if needed",
            "Consider medication synchronization programs",
            "Have caregiver support for complex regimens",
            "Report any new symptoms that may be medication-related"
        ],
        evidence_level="high"
    )
]

# Adherence barrier-specific tips
ADHERENCE_BARRIER_TIPS: Dict[str, List[str]] = {
    "forgetfulness": [
        "Set daily alarms or reminders on your phone",
        "Use a pill organizer with compartments for each dose",
        "Link medication taking to daily routines (meals, brushing teeth)",
        "Keep medications in visible locations",
        "Use medication reminder apps",
        "Ask family members to provide reminders"
    ],
    "cost": [
        "Ask your doctor about generic alternatives",
        "Check patient assistance programs from pharmaceutical companies",
        "Look into prescription discount programs (GoodRx, RxAssist)",
        "Inquire about 90-day supplies for lower per-dose cost",
        "Contact local charitable organizations for assistance",
        "Ask about samples from your healthcare provider"
    ],
    "side_effects": [
        "Report side effects to your healthcare provider",
        "Ask about alternative medications with fewer side effects",
        "Ask about timing adjustments (taking with food, at bedtime)",
        "Some side effects improve after the first few weeks",
        "Never stop medication without consulting your provider",
        "Keep a symptom diary to track patterns"
    ],
    "complexity": [
        "Ask your doctor about combination pills to reduce pill burden",
        "Use a medication schedule chart",
        "Consider synchronized refill programs",
        "Ask pharmacist for blister packs or medication organizers",
        "Request once-daily formulations when available",
        "Consider pharmacy delivery services"
    ],
    "belief_concerns": [
        "Discuss your concerns openly with your healthcare provider",
        "Ask about the purpose and benefits of each medication",
        "Learn about what happens if the condition goes untreated",
        "Seek information from reliable medical sources",
        "Consider talking to others with similar conditions",
        "Ask for written information about your medications"
    ],
    "access": [
        "Set up automatic refills with your pharmacy",
        "Use mail-order pharmacy services for maintenance medications",
        "Plan refills ahead before running out",
        "Ask about emergency supply options",
        "Consider pharmacy delivery services",
        "Keep travel supplies for unexpected situations"
    ],
    "lifestyle": [
        "Choose medication forms that fit your lifestyle (extended-release)",
        "Discuss timing options that work with your schedule",
        "Plan for travel and schedule changes",
        "Communicate schedule constraints to your provider",
        "Use portable pill cases for on-the-go doses",
        "Set backup reminders for unusual days"
    ]
}


class ClinicalGuidelinesService:
    """Service for accessing clinical guidelines and adherence tips"""
    
    def __init__(self):
        self._guidelines_loaded = False
    
    def load_guidelines_to_vector_store(self):
        """Load all guidelines into the vector store for semantic search"""
        if self._guidelines_loaded:
            return
        
        try:
            for guideline in CLINICAL_GUIDELINES:
                # Add main guideline content
                knowledge_base.add_guideline(
                    content=f"{guideline.title}\n\n{guideline.content}",
                    condition=guideline.condition,
                    source=guideline.source,
                    year=guideline.year
                )
                
                # Add recommendations as separate documents
                for rec in guideline.recommendations:
                    knowledge_base.add_guideline(
                        content=f"Recommendation for {guideline.condition}: {rec}",
                        condition=guideline.condition,
                        source=guideline.source,
                        year=guideline.year
                    )
            
            # Add adherence tips
            for barrier_type, tips in ADHERENCE_BARRIER_TIPS.items():
                for tip in tips:
                    knowledge_base.add_adherence_tip(
                        content=f"Tip for {barrier_type}: {tip}",
                        barrier_type=barrier_type,
                        effectiveness_score=0.7
                    )
            
            self._guidelines_loaded = True
            logger.info("Loaded clinical guidelines to vector store")
            
        except Exception as e:
            logger.error(f"Failed to load guidelines: {e}")
    
    def get_guidelines_for_condition(
        self,
        condition: str
    ) -> List[ClinicalGuideline]:
        """Get guidelines for a specific condition"""
        condition_lower = condition.lower()
        
        matching = []
        for guideline in CLINICAL_GUIDELINES:
            if (guideline.condition.lower() == condition_lower or 
                condition_lower in guideline.content.lower() or
                guideline.condition == "general"):
                matching.append(guideline)
        
        return matching
    
    def search_guidelines(
        self,
        query: str,
        condition: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search guidelines using vector store"""
        self.load_guidelines_to_vector_store()
        
        results = knowledge_base.search_guidelines(
            query=query,
            condition=condition,
            n_results=5
        )
        
        return [r.to_dict() for r in results]
    
    def get_adherence_tips(
        self,
        barrier_type: str
    ) -> List[str]:
        """Get adherence tips for a specific barrier type"""
        barrier_lower = barrier_type.lower()
        
        # Direct match
        if barrier_lower in ADHERENCE_BARRIER_TIPS:
            return ADHERENCE_BARRIER_TIPS[barrier_lower]
        
        # Partial match
        for barrier, tips in ADHERENCE_BARRIER_TIPS.items():
            if barrier_lower in barrier or barrier in barrier_lower:
                return tips
        
        # Default general tips
        return [
            "Talk to your healthcare provider about your concerns",
            "Use medication reminders",
            "Keep a medication diary",
            "Ask your pharmacist for help"
        ]
    
    def search_adherence_tips(
        self,
        query: str,
        barrier_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search adherence tips using vector store"""
        self.load_guidelines_to_vector_store()
        
        results = knowledge_base.search_adherence_tips(
            query=query,
            barrier_type=barrier_type,
            n_results=5
        )
        
        return [r.to_dict() for r in results]
    
    def get_all_guidelines(self) -> List[Dict[str, Any]]:
        """Get all guidelines as dictionaries"""
        return [g.to_dict() for g in CLINICAL_GUIDELINES]
    
    def get_all_barrier_types(self) -> List[str]:
        """Get list of all barrier types"""
        return list(ADHERENCE_BARRIER_TIPS.keys())
    
    def get_condition_specific_recommendations(
        self,
        conditions: List[str]
    ) -> Dict[str, List[str]]:
        """Get recommendations for multiple conditions"""
        recommendations = {}
        
        for condition in conditions:
            guidelines = self.get_guidelines_for_condition(condition)
            condition_recs = []
            
            for g in guidelines:
                condition_recs.extend(g.recommendations)
            
            recommendations[condition] = list(set(condition_recs))  # Remove duplicates
        
        return recommendations


# Singleton instance
clinical_guidelines_service = ClinicalGuidelinesService()
