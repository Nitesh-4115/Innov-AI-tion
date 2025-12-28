"""
Drug Interaction Checker Tool
Checks for potential drug-drug interactions
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from config import settings


logger = logging.getLogger(__name__)


class InteractionSeverity(str, Enum):
    """Severity levels for drug interactions"""
    CONTRAINDICATED = "contraindicated"  # Should never be taken together
    MAJOR = "major"                      # Serious interaction, avoid
    MODERATE = "moderate"                # Use with caution
    MINOR = "minor"                      # Low risk, monitor
    UNKNOWN = "unknown"                  # Not enough data


@dataclass
class DrugInteraction:
    """Drug interaction details"""
    drug1: str
    drug2: str
    severity: InteractionSeverity
    description: str
    mechanism: Optional[str] = None
    clinical_effects: Optional[str] = None
    management: Optional[str] = None
    separation_hours: int = 0  # Hours to separate doses
    monitoring_required: bool = False
    avoid_combination: bool = False


# Comprehensive drug interaction database
INTERACTION_DATABASE: Dict[Tuple[str, str], DrugInteraction] = {
    # Anticoagulant interactions
    ("warfarin", "aspirin"): DrugInteraction(
        drug1="warfarin", drug2="aspirin",
        severity=InteractionSeverity.MAJOR,
        description="Increased risk of bleeding",
        mechanism="Both drugs affect hemostasis through different mechanisms",
        clinical_effects="Higher risk of GI bleeding, bruising, hemorrhage",
        management="Avoid combination unless specifically prescribed. Monitor for bleeding signs.",
        monitoring_required=True,
        avoid_combination=True
    ),
    ("warfarin", "ibuprofen"): DrugInteraction(
        drug1="warfarin", drug2="ibuprofen",
        severity=InteractionSeverity.MAJOR,
        description="Increased bleeding risk and anticoagulant effect",
        mechanism="NSAIDs inhibit platelet function and may increase warfarin levels",
        clinical_effects="GI bleeding, elevated INR",
        management="Use acetaminophen instead. If NSAID needed, use lowest dose for shortest time.",
        monitoring_required=True,
        avoid_combination=True
    ),
    
    # ACE inhibitor interactions
    ("lisinopril", "potassium"): DrugInteraction(
        drug1="lisinopril", drug2="potassium supplements",
        severity=InteractionSeverity.MAJOR,
        description="Risk of hyperkalemia",
        mechanism="ACE inhibitors reduce potassium excretion",
        clinical_effects="Dangerously high potassium levels, cardiac arrhythmias",
        management="Monitor potassium levels closely. Usually avoid combination.",
        monitoring_required=True
    ),
    ("lisinopril", "losartan"): DrugInteraction(
        drug1="lisinopril", drug2="losartan",
        severity=InteractionSeverity.MAJOR,
        description="Dual RAAS blockade - increased adverse effects",
        mechanism="Both block the renin-angiotensin system",
        clinical_effects="Hypotension, hyperkalemia, renal impairment",
        management="Generally avoid combination. Not recommended.",
        avoid_combination=True
    ),
    ("lisinopril", "spironolactone"): DrugInteraction(
        drug1="lisinopril", drug2="spironolactone",
        severity=InteractionSeverity.MODERATE,
        description="Increased risk of hyperkalemia",
        mechanism="Both drugs can increase potassium levels",
        clinical_effects="Hyperkalemia",
        management="Monitor potassium regularly. Low potassium diet may help.",
        monitoring_required=True
    ),
    
    # Statin interactions
    ("atorvastatin", "gemfibrozil"): DrugInteraction(
        drug1="atorvastatin", drug2="gemfibrozil",
        severity=InteractionSeverity.MAJOR,
        description="Increased risk of myopathy and rhabdomyolysis",
        mechanism="Gemfibrozil inhibits statin metabolism",
        clinical_effects="Muscle pain, weakness, potentially fatal rhabdomyolysis",
        management="Avoid combination. Use fenofibrate if fibrate needed.",
        avoid_combination=True
    ),
    ("atorvastatin", "clarithromycin"): DrugInteraction(
        drug1="atorvastatin", drug2="clarithromycin",
        severity=InteractionSeverity.MAJOR,
        description="Increased statin levels and myopathy risk",
        mechanism="Clarithromycin inhibits CYP3A4 metabolism of statin",
        clinical_effects="Elevated statin levels, increased myopathy risk",
        management="Temporarily suspend statin or use azithromycin instead.",
        avoid_combination=True
    ),
    ("simvastatin", "amlodipine"): DrugInteraction(
        drug1="simvastatin", drug2="amlodipine",
        severity=InteractionSeverity.MODERATE,
        description="Increased simvastatin levels",
        mechanism="Amlodipine inhibits CYP3A4",
        clinical_effects="Increased myopathy risk",
        management="Limit simvastatin to 20mg daily when combined with amlodipine."
    ),
    
    # Metformin interactions
    ("metformin", "contrast_dye"): DrugInteraction(
        drug1="metformin", drug2="iodinated contrast",
        severity=InteractionSeverity.MAJOR,
        description="Risk of contrast-induced nephropathy and lactic acidosis",
        mechanism="Contrast may impair renal function, affecting metformin clearance",
        clinical_effects="Lactic acidosis in patients with reduced kidney function",
        management="Hold metformin 48 hours before and after contrast procedures.",
        separation_hours=48
    ),
    ("metformin", "alcohol"): DrugInteraction(
        drug1="metformin", drug2="alcohol",
        severity=InteractionSeverity.MODERATE,
        description="Increased risk of lactic acidosis and hypoglycemia",
        mechanism="Alcohol impairs gluconeogenesis and lactate metabolism",
        clinical_effects="Hypoglycemia, lactic acidosis",
        management="Limit alcohol intake. Avoid binge drinking."
    ),
    
    # Thyroid interactions
    ("levothyroxine", "calcium"): DrugInteraction(
        drug1="levothyroxine", drug2="calcium supplements",
        severity=InteractionSeverity.MODERATE,
        description="Reduced levothyroxine absorption",
        mechanism="Calcium binds levothyroxine in GI tract",
        clinical_effects="Subtherapeutic thyroid hormone levels",
        management="Separate doses by at least 4 hours.",
        separation_hours=4
    ),
    ("levothyroxine", "iron"): DrugInteraction(
        drug1="levothyroxine", drug2="iron supplements",
        severity=InteractionSeverity.MODERATE,
        description="Reduced levothyroxine absorption",
        mechanism="Iron binds levothyroxine in GI tract",
        clinical_effects="Subtherapeutic thyroid hormone levels",
        management="Separate doses by at least 4 hours.",
        separation_hours=4
    ),
    ("levothyroxine", "omeprazole"): DrugInteraction(
        drug1="levothyroxine", drug2="omeprazole",
        severity=InteractionSeverity.MINOR,
        description="Potentially reduced levothyroxine absorption",
        mechanism="Altered gastric pH may affect absorption",
        clinical_effects="May need higher levothyroxine dose",
        management="Monitor thyroid function. May need dose adjustment."
    ),
    
    # SSRI interactions
    ("sertraline", "tramadol"): DrugInteraction(
        drug1="sertraline", drug2="tramadol",
        severity=InteractionSeverity.MAJOR,
        description="Risk of serotonin syndrome and seizures",
        mechanism="Both drugs increase serotonin activity",
        clinical_effects="Serotonin syndrome, lowered seizure threshold",
        management="Avoid combination if possible. Monitor for serotonin syndrome symptoms.",
        avoid_combination=True
    ),
    ("sertraline", "maoi"): DrugInteraction(
        drug1="sertraline", drug2="MAO inhibitors",
        severity=InteractionSeverity.CONTRAINDICATED,
        description="Life-threatening serotonin syndrome",
        mechanism="Severe excess serotonin activity",
        clinical_effects="Hyperthermia, rigidity, autonomic instability, death",
        management="NEVER combine. Wait 14 days between stopping MAOI and starting SSRI.",
        avoid_combination=True
    ),
    
    # Beta blocker interactions
    ("metoprolol", "verapamil"): DrugInteraction(
        drug1="metoprolol", drug2="verapamil",
        severity=InteractionSeverity.MAJOR,
        description="Additive cardiac depression",
        mechanism="Both drugs slow heart rate and conduction",
        clinical_effects="Severe bradycardia, heart block, hypotension",
        management="Avoid combination. Use with extreme caution if necessary.",
        monitoring_required=True
    ),
    ("metoprolol", "clonidine"): DrugInteraction(
        drug1="metoprolol", drug2="clonidine",
        severity=InteractionSeverity.MODERATE,
        description="Rebound hypertension risk if clonidine stopped",
        mechanism="Beta blockers can exacerbate clonidine withdrawal",
        clinical_effects="Severe rebound hypertension",
        management="Taper clonidine gradually. Stop beta blocker several days before clonidine."
    ),
    
    # Gabapentin interactions
    ("gabapentin", "opioids"): DrugInteraction(
        drug1="gabapentin", drug2="opioids",
        severity=InteractionSeverity.MAJOR,
        description="Increased risk of respiratory depression",
        mechanism="Additive CNS depression",
        clinical_effects="Sedation, respiratory depression, death",
        management="Use lowest effective doses. Monitor closely.",
        monitoring_required=True
    ),
    
    # PPI interactions
    ("omeprazole", "clopidogrel"): DrugInteraction(
        drug1="omeprazole", drug2="clopidogrel",
        severity=InteractionSeverity.MODERATE,
        description="Reduced clopidogrel effectiveness",
        mechanism="Omeprazole inhibits CYP2C19 activation of clopidogrel",
        clinical_effects="Reduced antiplatelet effect, increased cardiovascular events",
        management="Use pantoprazole instead if PPI needed."
    ),
    
    # Fluoroquinolone interactions
    ("ciprofloxacin", "antacids"): DrugInteraction(
        drug1="ciprofloxacin", drug2="antacids",
        severity=InteractionSeverity.MODERATE,
        description="Reduced ciprofloxacin absorption",
        mechanism="Metal cations bind ciprofloxacin",
        clinical_effects="Subtherapeutic antibiotic levels, treatment failure",
        management="Take ciprofloxacin 2 hours before or 6 hours after antacids.",
        separation_hours=2
    ),
    ("ciprofloxacin", "theophylline"): DrugInteraction(
        drug1="ciprofloxacin", drug2="theophylline",
        severity=InteractionSeverity.MAJOR,
        description="Increased theophylline toxicity",
        mechanism="Ciprofloxacin inhibits theophylline metabolism",
        clinical_effects="Nausea, vomiting, seizures, arrhythmias",
        management="Reduce theophylline dose by 30-50%. Monitor levels.",
        monitoring_required=True
    ),
}


class InteractionChecker:
    """
    Drug interaction checking service
    """
    
    def __init__(self):
        self.interaction_db = INTERACTION_DATABASE
        self._build_drug_index()
    
    def _build_drug_index(self):
        """Build index for faster lookups"""
        self._drug_pairs = set()
        for (drug1, drug2) in self.interaction_db.keys():
            self._drug_pairs.add((drug1.lower(), drug2.lower()))
            self._drug_pairs.add((drug2.lower(), drug1.lower()))  # Bidirectional
    
    def _normalize_drug_name(self, name: str) -> str:
        """Normalize drug name for comparison"""
        return name.lower().strip().replace("-", "").replace(" ", "")
    
    def _get_interaction(self, drug1: str, drug2: str) -> Optional[DrugInteraction]:
        """Get interaction between two drugs"""
        d1 = self._normalize_drug_name(drug1)
        d2 = self._normalize_drug_name(drug2)
        
        # Check both orderings
        if (d1, d2) in self.interaction_db:
            return self.interaction_db[(d1, d2)]
        if (d2, d1) in self.interaction_db:
            return self.interaction_db[(d2, d1)]
        
        return None
    
    def check_interaction(self, drug1: str, drug2: str) -> Optional[DrugInteraction]:
        """
        Check for interaction between two drugs
        
        Args:
            drug1: First drug name
            drug2: Second drug name
            
        Returns:
            DrugInteraction if found, None otherwise
        """
        return self._get_interaction(drug1, drug2)
    
    def check_all_interactions(
        self, 
        medications: List[str]
    ) -> List[DrugInteraction]:
        """
        Check for all interactions among a list of medications
        
        Args:
            medications: List of medication names
            
        Returns:
            List of all found interactions
        """
        interactions = []
        checked_pairs = set()
        
        for i, drug1 in enumerate(medications):
            for drug2 in medications[i+1:]:
                pair = tuple(sorted([drug1.lower(), drug2.lower()]))
                if pair in checked_pairs:
                    continue
                    
                checked_pairs.add(pair)
                interaction = self._get_interaction(drug1, drug2)
                
                if interaction:
                    interactions.append(interaction)
        
        # Sort by severity
        severity_order = {
            InteractionSeverity.CONTRAINDICATED: 0,
            InteractionSeverity.MAJOR: 1,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.MINOR: 3,
            InteractionSeverity.UNKNOWN: 4
        }
        interactions.sort(key=lambda x: severity_order.get(x.severity, 5))
        
        return interactions
    
    def get_interaction_summary(
        self, 
        medications: List[str]
    ) -> Dict[str, Any]:
        """
        Get a summary of all interactions for a medication list
        
        Args:
            medications: List of medication names
            
        Returns:
            Summary dict with counts and details
        """
        interactions = self.check_all_interactions(medications)
        
        summary = {
            "total_interactions": len(interactions),
            "by_severity": {
                "contraindicated": 0,
                "major": 0,
                "moderate": 0,
                "minor": 0
            },
            "interactions": [],
            "recommendations": [],
            "requires_action": False
        }
        
        for interaction in interactions:
            severity_key = interaction.severity.value
            if severity_key in summary["by_severity"]:
                summary["by_severity"][severity_key] += 1
            
            summary["interactions"].append({
                "drugs": [interaction.drug1, interaction.drug2],
                "severity": interaction.severity.value,
                "description": interaction.description,
                "management": interaction.management,
                "separation_hours": interaction.separation_hours,
                "avoid": interaction.avoid_combination
            })
            
            if interaction.management:
                summary["recommendations"].append(interaction.management)
        
        # Flag if action required
        if (summary["by_severity"]["contraindicated"] > 0 or 
            summary["by_severity"]["major"] > 0):
            summary["requires_action"] = True
        
        return summary
    
    def get_separation_requirements(
        self, 
        medications: List[str]
    ) -> Dict[Tuple[str, str], int]:
        """
        Get time separation requirements between drugs
        
        Args:
            medications: List of medication names
            
        Returns:
            Dict mapping drug pairs to required separation hours
        """
        separations = {}
        
        interactions = self.check_all_interactions(medications)
        
        for interaction in interactions:
            if interaction.separation_hours > 0:
                separations[(interaction.drug1, interaction.drug2)] = interaction.separation_hours
        
        return separations
    
    def can_take_together(self, drug1: str, drug2: str) -> Tuple[bool, str]:
        """
        Check if two drugs can be taken at the same time
        
        Returns:
            Tuple of (can_take_together, reason)
        """
        interaction = self._get_interaction(drug1, drug2)
        
        if not interaction:
            return True, "No known interaction"
        
        if interaction.severity == InteractionSeverity.CONTRAINDICATED:
            return False, f"CONTRAINDICATED: {interaction.description}"
        
        if interaction.avoid_combination:
            return False, f"Should be avoided: {interaction.description}"
        
        if interaction.separation_hours > 0:
            return False, f"Separate by {interaction.separation_hours} hours: {interaction.description}"
        
        if interaction.severity == InteractionSeverity.MAJOR:
            return False, f"Major interaction - use caution: {interaction.description}"
        
        return True, f"Can take together but monitor: {interaction.description}"
    
    def add_custom_interaction(self, interaction: DrugInteraction):
        """Add a custom interaction to the database"""
        key = (interaction.drug1.lower(), interaction.drug2.lower())
        self.interaction_db[key] = interaction
        self._build_drug_index()


# Singleton instance
interaction_checker = InteractionChecker()


def check_interactions(medications: List[str]) -> List[DrugInteraction]:
    """Convenience function to check interactions"""
    return interaction_checker.check_all_interactions(medications)


def get_interaction_summary(medications: List[str]) -> Dict[str, Any]:
    """Convenience function to get interaction summary"""
    return interaction_checker.get_interaction_summary(medications)
