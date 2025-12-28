"""
Symptom Correlator Tool
Analyzes symptoms and correlates them with medication side effects
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

from tools.drug_database import drug_database, DrugInfo


logger = logging.getLogger(__name__)


class SymptomUrgency(str, Enum):
    """Urgency level for symptoms"""
    EMERGENCY = "emergency"      # Call 911
    URGENT = "urgent"            # See provider today
    SOON = "soon"                # See provider within 48 hours
    ROUTINE = "routine"          # Mention at next visit
    INFORMATIONAL = "informational"  # Monitor only


@dataclass
class SymptomAnalysis:
    """Analysis result for a symptom"""
    symptom: str
    severity: int  # 1-10
    correlation_score: float  # 0-1 likelihood it's medication-related
    urgency: SymptomUrgency
    likely_medications: List[str] = field(default_factory=list)
    possible_causes: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    requires_provider_attention: bool = False
    is_known_side_effect: bool = False
    red_flags: List[str] = field(default_factory=list)


# Emergency symptoms that always need immediate attention
EMERGENCY_SYMPTOMS = [
    "chest pain",
    "difficulty breathing",
    "severe allergic reaction",
    "anaphylaxis",
    "swelling of face",
    "swelling of throat",
    "trouble swallowing",
    "severe bleeding",
    "blood in urine",
    "blood in stool",
    "suicidal thoughts",
    "loss of consciousness",
    "seizure",
    "stroke symptoms",
    "sudden vision loss",
    "sudden severe headache"
]

# Symptoms that warrant urgent attention
URGENT_SYMPTOMS = [
    "severe abdominal pain",
    "high fever",
    "rapid heartbeat",
    "severe dizziness",
    "fainting",
    "severe muscle pain",
    "dark urine",
    "jaundice",
    "yellowing of skin",
    "severe rash",
    "hives",
    "confusion",
    "hallucinations",
    "severe mood changes"
]

# Common symptom to medication class mappings
SYMPTOM_MEDICATION_MAPPINGS: Dict[str, List[str]] = {
    "dry cough": ["ACE Inhibitor", "lisinopril", "enalapril", "ramipril"],
    "muscle pain": ["Statin", "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"],
    "nausea": ["metformin", "SSRI", "opioid", "antibiotic", "chemotherapy"],
    "diarrhea": ["metformin", "antibiotic", "SSRI", "PPI"],
    "dizziness": ["antihypertensive", "beta blocker", "calcium channel blocker", "gabapentin"],
    "fatigue": ["beta blocker", "metoprolol", "statin", "antihistamine"],
    "drowsiness": ["gabapentin", "antihistamine", "benzodiazepine", "opioid"],
    "headache": ["nitrate", "PDE5 inhibitor", "caffeine withdrawal"],
    "swelling": ["calcium channel blocker", "amlodipine", "NSAID", "corticosteroid"],
    "constipation": ["opioid", "calcium channel blocker", "iron supplement", "anticholinergic"],
    "weight gain": ["antipsychotic", "antidepressant", "corticosteroid", "insulin"],
    "insomnia": ["SSRI", "stimulant", "corticosteroid", "beta blocker"],
    "anxiety": ["stimulant", "bronchodilator", "levothyroxine", "corticosteroid"],
    "tremor": ["bronchodilator", "lithium", "antidepressant", "levothyroxine"],
    "metallic taste": ["metformin", "ACE inhibitor", "antibiotic"],
    "bruising": ["anticoagulant", "warfarin", "aspirin", "NSAID"],
    "bleeding gums": ["anticoagulant", "warfarin", "aspirin"],
    "hair loss": ["chemotherapy", "thyroid medication", "anticoagulant"],
    "cold extremities": ["beta blocker", "metoprolol", "atenolol"],
    "erectile dysfunction": ["beta blocker", "antidepressant", "diuretic"],
    "decreased libido": ["antidepressant", "SSRI", "beta blocker"],
    "memory problems": ["statin", "benzodiazepine", "anticholinergic", "opioid"],
    "ringing in ears": ["aspirin", "NSAID", "aminoglycoside", "loop diuretic"]
}


class SymptomCorrelator:
    """
    Analyzes patient symptoms and correlates with medication side effects
    """
    
    def __init__(self):
        self.emergency_symptoms = EMERGENCY_SYMPTOMS
        self.urgent_symptoms = URGENT_SYMPTOMS
        self.symptom_mappings = SYMPTOM_MEDICATION_MAPPINGS
    
    def _normalize_symptom(self, symptom: str) -> str:
        """Normalize symptom text for comparison"""
        return symptom.lower().strip()
    
    def _determine_urgency(
        self, 
        symptom: str, 
        severity: int,
        red_flags: List[str]
    ) -> SymptomUrgency:
        """Determine urgency level based on symptom and severity"""
        normalized = self._normalize_symptom(symptom)
        
        # Check for emergency symptoms
        for emergency in self.emergency_symptoms:
            if emergency in normalized or normalized in emergency:
                return SymptomUrgency.EMERGENCY
        
        # Check for urgent symptoms
        for urgent in self.urgent_symptoms:
            if urgent in normalized or normalized in urgent:
                return SymptomUrgency.URGENT
        
        # Red flags elevate urgency
        if red_flags:
            if severity >= 8:
                return SymptomUrgency.URGENT
            return SymptomUrgency.SOON
        
        # Severity-based
        if severity >= 9:
            return SymptomUrgency.URGENT
        elif severity >= 7:
            return SymptomUrgency.SOON
        elif severity >= 4:
            return SymptomUrgency.ROUTINE
        else:
            return SymptomUrgency.INFORMATIONAL
    
    def _find_red_flags(
        self, 
        symptom: str, 
        severity: int,
        medications: List[str]
    ) -> List[str]:
        """Identify red flags that require attention"""
        red_flags = []
        normalized = self._normalize_symptom(symptom)
        
        # Statin + muscle pain = possible rhabdomyolysis
        if "muscle" in normalized and any(
            med.lower() in ["atorvastatin", "simvastatin", "rosuvastatin", "pravastatin"] 
            for med in medications
        ):
            if severity >= 6:
                red_flags.append("Muscle symptoms with statin use - monitor for rhabdomyolysis")
        
        # Metformin + severe GI symptoms
        if any(gi in normalized for gi in ["nausea", "vomiting", "abdominal"]) and any(
            "metformin" in med.lower() for med in medications
        ):
            if severity >= 7:
                red_flags.append("Severe GI symptoms with metformin - check for lactic acidosis")
        
        # ACE inhibitor + swelling
        if "swelling" in normalized and any(
            med.lower() in ["lisinopril", "enalapril", "ramipril", "benazepril"]
            for med in medications
        ):
            if "face" in normalized or "throat" in normalized or "tongue" in normalized:
                red_flags.append("ANGIOEDEMA RISK - Stop ACE inhibitor and seek immediate care")
        
        # Anticoagulant + bleeding
        if any(bleed in normalized for bleed in ["bleeding", "blood", "bruising"]) and any(
            med.lower() in ["warfarin", "apixaban", "rivaroxaban", "dabigatran"]
            for med in medications
        ):
            red_flags.append("Bleeding with anticoagulant - may need INR check or dose adjustment")
        
        # SSRI + serotonin symptoms
        serotonin_symptoms = ["agitation", "confusion", "rapid heartbeat", "tremor", "sweating"]
        if any(s in normalized for s in serotonin_symptoms) and any(
            med.lower() in ["sertraline", "fluoxetine", "paroxetine", "citalopram", "escitalopram"]
            for med in medications
        ):
            red_flags.append("Possible serotonin syndrome - seek medical evaluation")
        
        return red_flags
    
    async def analyze_symptom(
        self,
        symptom: str,
        severity: int,
        patient_medications: List[str],
        timing: Optional[str] = None,
        duration_minutes: Optional[int] = None,
        additional_context: Optional[str] = None
    ) -> SymptomAnalysis:
        """
        Analyze a symptom and correlate with patient's medications
        
        Args:
            symptom: Description of the symptom
            severity: Severity on 1-10 scale
            patient_medications: List of medications the patient takes
            timing: When symptom occurred relative to medication
            duration_minutes: How long symptom has lasted
            additional_context: Any additional relevant information
            
        Returns:
            SymptomAnalysis with correlation and recommendations
        """
        normalized_symptom = self._normalize_symptom(symptom)
        likely_medications = []
        possible_causes = []
        recommendations = []
        is_known_side_effect = False
        correlation_score = 0.0
        
        # Find medications that commonly cause this symptom
        for symptom_pattern, med_list in self.symptom_mappings.items():
            if symptom_pattern in normalized_symptom or normalized_symptom in symptom_pattern:
                for med in patient_medications:
                    med_lower = med.lower()
                    for known_med in med_list:
                        if known_med.lower() in med_lower or med_lower in known_med.lower():
                            if med not in likely_medications:
                                likely_medications.append(med)
                            is_known_side_effect = True
        
        # Check drug database for side effects
        for med in patient_medications:
            drug_info = await drug_database.get_drug_info(med)
            if drug_info:
                # Check common side effects
                for side_effect in drug_info.common_side_effects:
                    if side_effect.lower() in normalized_symptom or normalized_symptom in side_effect.lower():
                        if med not in likely_medications:
                            likely_medications.append(med)
                        is_known_side_effect = True
                        possible_causes.append(f"Known side effect of {med}")
                
                # Check serious side effects
                for side_effect in drug_info.serious_side_effects:
                    if side_effect.lower() in normalized_symptom or normalized_symptom in side_effect.lower():
                        if med not in likely_medications:
                            likely_medications.append(med)
                        is_known_side_effect = True
                        possible_causes.append(f"Serious side effect of {med} - requires attention")
        
        # Find red flags
        red_flags = self._find_red_flags(symptom, severity, patient_medications)
        
        # Calculate correlation score
        if likely_medications:
            # Base score from having likely medications
            correlation_score = 0.5
            
            # Increase if timing suggests medication relationship
            if timing:
                timing_lower = timing.lower()
                if any(t in timing_lower for t in ["after taking", "after dose", "within hour", "shortly after"]):
                    correlation_score += 0.25
                elif any(t in timing_lower for t in ["before next dose", "wears off", "between doses"]):
                    correlation_score += 0.15
            
            # Increase if known side effect
            if is_known_side_effect:
                correlation_score += 0.2
            
            correlation_score = min(correlation_score, 1.0)
        elif is_known_side_effect:
            correlation_score = 0.4
        
        # Determine urgency
        urgency = self._determine_urgency(symptom, severity, red_flags)
        
        # Generate recommendations
        if urgency == SymptomUrgency.EMERGENCY:
            recommendations.append("Seek emergency medical care immediately")
        elif urgency == SymptomUrgency.URGENT:
            recommendations.append("Contact your healthcare provider today")
        elif red_flags:
            recommendations.extend(red_flags)
        
        if likely_medications and severity >= 5:
            recommendations.append(f"Discuss {', '.join(likely_medications)} with your provider")
        
        if is_known_side_effect and severity < 5:
            recommendations.append("Monitor symptom. It may improve as your body adjusts to the medication")
        
        if not recommendations:
            recommendations.append("Monitor symptoms and report if they worsen or persist")
        
        requires_provider = (
            urgency in [SymptomUrgency.EMERGENCY, SymptomUrgency.URGENT, SymptomUrgency.SOON]
            or severity >= 7
            or bool(red_flags)
        )
        
        return SymptomAnalysis(
            symptom=symptom,
            severity=severity,
            correlation_score=correlation_score,
            urgency=urgency,
            likely_medications=likely_medications,
            possible_causes=possible_causes if possible_causes else ["Unable to determine specific cause"],
            recommendations=recommendations,
            requires_provider_attention=requires_provider,
            is_known_side_effect=is_known_side_effect,
            red_flags=red_flags
        )
    
    async def analyze_multiple_symptoms(
        self,
        symptoms: List[Dict[str, Any]],
        patient_medications: List[str]
    ) -> Dict[str, Any]:
        """
        Analyze multiple symptoms together for patterns
        
        Args:
            symptoms: List of symptom dicts with 'symptom', 'severity', 'timing' keys
            patient_medications: List of patient's medications
            
        Returns:
            Combined analysis with patterns and overall recommendations
        """
        analyses = []
        medication_involvement = {}
        highest_urgency = SymptomUrgency.INFORMATIONAL
        all_red_flags = []
        
        urgency_priority = {
            SymptomUrgency.EMERGENCY: 5,
            SymptomUrgency.URGENT: 4,
            SymptomUrgency.SOON: 3,
            SymptomUrgency.ROUTINE: 2,
            SymptomUrgency.INFORMATIONAL: 1
        }
        
        for symptom_data in symptoms:
            analysis = await self.analyze_symptom(
                symptom=symptom_data.get("symptom", ""),
                severity=symptom_data.get("severity", 5),
                patient_medications=patient_medications,
                timing=symptom_data.get("timing"),
                duration_minutes=symptom_data.get("duration_minutes")
            )
            analyses.append(analysis)
            
            # Track medication involvement
            for med in analysis.likely_medications:
                medication_involvement[med] = medication_involvement.get(med, 0) + 1
            
            # Track highest urgency
            if urgency_priority.get(analysis.urgency, 0) > urgency_priority.get(highest_urgency, 0):
                highest_urgency = analysis.urgency
            
            all_red_flags.extend(analysis.red_flags)
        
        # Find patterns
        patterns = []
        if len(medication_involvement) > 0:
            most_involved = max(medication_involvement.items(), key=lambda x: x[1])
            if most_involved[1] >= 2:
                patterns.append(f"Multiple symptoms may be related to {most_involved[0]}")
        
        # Generate overall recommendations
        overall_recommendations = []
        if highest_urgency == SymptomUrgency.EMERGENCY:
            overall_recommendations.append("SEEK EMERGENCY CARE IMMEDIATELY")
        elif highest_urgency == SymptomUrgency.URGENT:
            overall_recommendations.append("Contact your healthcare provider today")
        
        if patterns:
            overall_recommendations.append(
                "Multiple symptoms appear medication-related. Discuss with your provider."
            )
        
        unique_red_flags = list(set(all_red_flags))
        
        return {
            "individual_analyses": [
                {
                    "symptom": a.symptom,
                    "severity": a.severity,
                    "correlation_score": a.correlation_score,
                    "urgency": a.urgency.value,
                    "likely_medications": a.likely_medications,
                    "is_known_side_effect": a.is_known_side_effect,
                    "recommendations": a.recommendations
                }
                for a in analyses
            ],
            "medication_involvement": medication_involvement,
            "patterns": patterns,
            "highest_urgency": highest_urgency.value,
            "red_flags": unique_red_flags,
            "overall_recommendations": overall_recommendations,
            "requires_immediate_attention": highest_urgency in [
                SymptomUrgency.EMERGENCY, 
                SymptomUrgency.URGENT
            ]
        }
    
    def is_emergency_symptom(self, symptom: str) -> bool:
        """Quick check if symptom is an emergency"""
        normalized = self._normalize_symptom(symptom)
        return any(
            emergency in normalized or normalized in emergency 
            for emergency in self.emergency_symptoms
        )


# Singleton instance
symptom_correlator = SymptomCorrelator()


async def analyze_symptom(
    symptom: str, 
    severity: int, 
    medications: List[str]
) -> SymptomAnalysis:
    """Convenience function to analyze a symptom"""
    return await symptom_correlator.analyze_symptom(symptom, severity, medications)
