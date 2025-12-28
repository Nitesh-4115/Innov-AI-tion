"""
SIDER Data Loader
Loader for SIDER (Side Effect Resource) database
"""

import logging
import os
import csv
import gzip
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict

from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class SideEffect:
    """Side effect information from SIDER"""
    drug_name: str
    side_effect_name: str
    side_effect_id: str  # MedDRA ID
    frequency: str  # common, uncommon, rare, very rare, frequency unknown
    frequency_lower: Optional[float] = None  # Lower bound of frequency range
    frequency_upper: Optional[float] = None  # Upper bound of frequency range
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug_name": self.drug_name,
            "side_effect_name": self.side_effect_name,
            "side_effect_id": self.side_effect_id,
            "frequency": self.frequency,
            "frequency_lower": self.frequency_lower,
            "frequency_upper": self.frequency_upper
        }
    
    @property
    def severity_estimate(self) -> str:
        """Estimate severity based on common patterns"""
        severe_terms = {
            "death", "fatal", "hemorrhage", "stroke", "infarction",
            "failure", "anaphylaxis", "arrhythmia", "seizure",
            "respiratory depression", "cardiac arrest"
        }
        
        effect_lower = self.side_effect_name.lower()
        
        for term in severe_terms:
            if term in effect_lower:
                return "severe"
        
        moderate_terms = {
            "bleeding", "infection", "hypotension", "hypertension",
            "confusion", "pain", "swelling", "inflammation"
        }
        
        for term in moderate_terms:
            if term in effect_lower:
                return "moderate"
        
        return "mild"


@dataclass
class DrugSideEffects:
    """Collection of side effects for a drug"""
    drug_name: str
    drug_id: str
    side_effects: List[SideEffect] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug_name": self.drug_name,
            "drug_id": self.drug_id,
            "side_effects": [se.to_dict() for se in self.side_effects]
        }
    
    def get_by_frequency(self, frequency: str) -> List[SideEffect]:
        """Get side effects by frequency category"""
        return [se for se in self.side_effects if se.frequency.lower() == frequency.lower()]
    
    def get_common(self) -> List[SideEffect]:
        """Get common side effects"""
        return self.get_by_frequency("common")
    
    def get_serious(self) -> List[SideEffect]:
        """Get serious/severe side effects"""
        return [se for se in self.side_effects if se.severity_estimate == "severe"]


# Built-in side effects data for common medications
COMMON_DRUG_SIDE_EFFECTS: Dict[str, List[SideEffect]] = {
    "metformin": [
        SideEffect("Metformin", "Diarrhea", "C0011991", "common", 0.1, 0.3),
        SideEffect("Metformin", "Nausea", "C0027497", "common", 0.1, 0.2),
        SideEffect("Metformin", "Vomiting", "C0042963", "common", 0.05, 0.15),
        SideEffect("Metformin", "Abdominal pain", "C0000737", "common", 0.05, 0.1),
        SideEffect("Metformin", "Flatulence", "C0016204", "common", 0.1, 0.2),
        SideEffect("Metformin", "Decreased appetite", "C0003123", "common", 0.01, 0.05),
        SideEffect("Metformin", "Metallic taste", "C0240327", "uncommon", 0.01, 0.05),
        SideEffect("Metformin", "Vitamin B12 deficiency", "C0042845", "uncommon", 0.01, 0.1),
        SideEffect("Metformin", "Lactic acidosis", "C0001125", "rare", 0.0001, 0.001),
    ],
    
    "lisinopril": [
        SideEffect("Lisinopril", "Dry cough", "C0010200", "common", 0.05, 0.15),
        SideEffect("Lisinopril", "Dizziness", "C0012833", "common", 0.05, 0.1),
        SideEffect("Lisinopril", "Headache", "C0018681", "common", 0.05, 0.1),
        SideEffect("Lisinopril", "Fatigue", "C0015672", "common", 0.01, 0.05),
        SideEffect("Lisinopril", "Hypotension", "C0020649", "uncommon", 0.01, 0.05),
        SideEffect("Lisinopril", "Hyperkalemia", "C0020461", "uncommon", 0.01, 0.05),
        SideEffect("Lisinopril", "Angioedema", "C0002994", "rare", 0.001, 0.01),
        SideEffect("Lisinopril", "Renal impairment", "C1565489", "rare", 0.001, 0.01),
    ],
    
    "atorvastatin": [
        SideEffect("Atorvastatin", "Muscle pain", "C0231528", "common", 0.01, 0.1),
        SideEffect("Atorvastatin", "Joint pain", "C0003862", "common", 0.01, 0.05),
        SideEffect("Atorvastatin", "Headache", "C0018681", "common", 0.01, 0.05),
        SideEffect("Atorvastatin", "Nasopharyngitis", "C0027441", "common", 0.01, 0.05),
        SideEffect("Atorvastatin", "Diarrhea", "C0011991", "common", 0.01, 0.05),
        SideEffect("Atorvastatin", "Elevated liver enzymes", "C0151766", "uncommon", 0.001, 0.01),
        SideEffect("Atorvastatin", "Myopathy", "C0026848", "rare", 0.0001, 0.001),
        SideEffect("Atorvastatin", "Rhabdomyolysis", "C0035410", "very rare", 0.00001, 0.0001),
    ],
    
    "amlodipine": [
        SideEffect("Amlodipine", "Peripheral edema", "C0085649", "common", 0.05, 0.15),
        SideEffect("Amlodipine", "Headache", "C0018681", "common", 0.05, 0.1),
        SideEffect("Amlodipine", "Flushing", "C0016382", "common", 0.01, 0.05),
        SideEffect("Amlodipine", "Dizziness", "C0012833", "common", 0.01, 0.05),
        SideEffect("Amlodipine", "Fatigue", "C0015672", "common", 0.01, 0.05),
        SideEffect("Amlodipine", "Palpitations", "C0030252", "uncommon", 0.01, 0.05),
        SideEffect("Amlodipine", "Nausea", "C0027497", "uncommon", 0.01, 0.05),
    ],
    
    "omeprazole": [
        SideEffect("Omeprazole", "Headache", "C0018681", "common", 0.01, 0.05),
        SideEffect("Omeprazole", "Diarrhea", "C0011991", "common", 0.01, 0.05),
        SideEffect("Omeprazole", "Nausea", "C0027497", "common", 0.01, 0.05),
        SideEffect("Omeprazole", "Abdominal pain", "C0000737", "common", 0.01, 0.05),
        SideEffect("Omeprazole", "Flatulence", "C0016204", "common", 0.01, 0.05),
        SideEffect("Omeprazole", "Vitamin B12 deficiency", "C0042845", "uncommon", 0.001, 0.01),
        SideEffect("Omeprazole", "Hypomagnesemia", "C0151723", "uncommon", 0.001, 0.01),
        SideEffect("Omeprazole", "C. difficile infection", "C0009434", "rare", 0.0001, 0.001),
        SideEffect("Omeprazole", "Bone fracture", "C0016658", "rare", 0.001, 0.01),
    ],
    
    "sertraline": [
        SideEffect("Sertraline", "Nausea", "C0027497", "common", 0.1, 0.25),
        SideEffect("Sertraline", "Diarrhea", "C0011991", "common", 0.1, 0.2),
        SideEffect("Sertraline", "Insomnia", "C0917801", "common", 0.1, 0.2),
        SideEffect("Sertraline", "Headache", "C0018681", "common", 0.1, 0.2),
        SideEffect("Sertraline", "Dry mouth", "C0043352", "common", 0.1, 0.15),
        SideEffect("Sertraline", "Dizziness", "C0012833", "common", 0.05, 0.1),
        SideEffect("Sertraline", "Fatigue", "C0015672", "common", 0.05, 0.1),
        SideEffect("Sertraline", "Sexual dysfunction", "C0549622", "common", 0.05, 0.2),
        SideEffect("Sertraline", "Tremor", "C0040822", "common", 0.05, 0.1),
        SideEffect("Sertraline", "Sweating", "C0038990", "common", 0.05, 0.1),
        SideEffect("Sertraline", "Serotonin syndrome", "C0024586", "rare", 0.0001, 0.001),
        SideEffect("Sertraline", "Suicidal ideation", "C0424000", "rare", 0.001, 0.01),
    ],
    
    "levothyroxine": [
        SideEffect("Levothyroxine", "Palpitations", "C0030252", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Tachycardia", "C0039231", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Tremor", "C0040822", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Headache", "C0018681", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Insomnia", "C0917801", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Nervousness", "C0027769", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Weight loss", "C1262477", "common", 0.01, 0.1),
        SideEffect("Levothyroxine", "Heat intolerance", "C0085590", "common", 0.01, 0.05),
        SideEffect("Levothyroxine", "Arrhythmia", "C0003811", "rare", 0.001, 0.01),
    ],
    
    "gabapentin": [
        SideEffect("Gabapentin", "Dizziness", "C0012833", "common", 0.1, 0.3),
        SideEffect("Gabapentin", "Somnolence", "C2830004", "common", 0.1, 0.2),
        SideEffect("Gabapentin", "Peripheral edema", "C0085649", "common", 0.05, 0.1),
        SideEffect("Gabapentin", "Ataxia", "C0004134", "common", 0.05, 0.15),
        SideEffect("Gabapentin", "Fatigue", "C0015672", "common", 0.05, 0.1),
        SideEffect("Gabapentin", "Nausea", "C0027497", "common", 0.01, 0.05),
        SideEffect("Gabapentin", "Weight gain", "C0043094", "common", 0.01, 0.05),
        SideEffect("Gabapentin", "Respiratory depression", "C0235063", "rare", 0.001, 0.01),
    ],
    
    "warfarin": [
        SideEffect("Warfarin", "Bleeding", "C0019080", "common", 0.05, 0.2),
        SideEffect("Warfarin", "Bruising", "C0009938", "common", 0.05, 0.15),
        SideEffect("Warfarin", "Nosebleed", "C0014591", "common", 0.01, 0.1),
        SideEffect("Warfarin", "Gum bleeding", "C0017565", "common", 0.01, 0.05),
        SideEffect("Warfarin", "Hematuria", "C0018965", "uncommon", 0.01, 0.05),
        SideEffect("Warfarin", "GI bleeding", "C0017181", "uncommon", 0.01, 0.05),
        SideEffect("Warfarin", "Intracranial hemorrhage", "C0151699", "rare", 0.001, 0.01),
        SideEffect("Warfarin", "Skin necrosis", "C0151799", "rare", 0.0001, 0.001),
    ],
    
    "metoprolol": [
        SideEffect("Metoprolol", "Fatigue", "C0015672", "common", 0.05, 0.15),
        SideEffect("Metoprolol", "Bradycardia", "C0428977", "common", 0.01, 0.1),
        SideEffect("Metoprolol", "Dizziness", "C0012833", "common", 0.05, 0.1),
        SideEffect("Metoprolol", "Depression", "C0011570", "common", 0.01, 0.05),
        SideEffect("Metoprolol", "Cold extremities", "C0234226", "common", 0.01, 0.05),
        SideEffect("Metoprolol", "Hypotension", "C0020649", "uncommon", 0.01, 0.05),
        SideEffect("Metoprolol", "Bronchospasm", "C0006266", "rare", 0.001, 0.01),
        SideEffect("Metoprolol", "Heart block", "C0018794", "rare", 0.001, 0.01),
    ]
}


# Symptom to side effect mapping for correlation
SYMPTOM_SIDE_EFFECT_MAP: Dict[str, List[str]] = {
    "headache": ["Headache", "Migraine", "Tension headache"],
    "nausea": ["Nausea", "Vomiting", "Stomach upset"],
    "dizziness": ["Dizziness", "Vertigo", "Lightheadedness"],
    "fatigue": ["Fatigue", "Tiredness", "Lethargy", "Weakness"],
    "diarrhea": ["Diarrhea", "Loose stools", "Frequent bowel movements"],
    "constipation": ["Constipation", "Decreased bowel movements"],
    "dry mouth": ["Dry mouth", "Xerostomia"],
    "drowsiness": ["Somnolence", "Drowsiness", "Sedation"],
    "insomnia": ["Insomnia", "Sleep disorder", "Difficulty sleeping"],
    "muscle pain": ["Muscle pain", "Myalgia", "Muscle ache"],
    "joint pain": ["Joint pain", "Arthralgia", "Joint ache"],
    "rash": ["Rash", "Skin rash", "Dermatitis"],
    "swelling": ["Edema", "Peripheral edema", "Swelling"],
    "cough": ["Cough", "Dry cough"],
    "weight gain": ["Weight gain", "Weight increase"],
    "weight loss": ["Weight loss", "Weight decrease"],
    "anxiety": ["Anxiety", "Nervousness", "Agitation"],
    "depression": ["Depression", "Low mood", "Depressed mood"],
    "palpitations": ["Palpitations", "Heart racing", "Tachycardia"],
    "shortness of breath": ["Dyspnea", "Shortness of breath", "Breathing difficulty"]
}


class SIDERLoader:
    """
    Loader for SIDER side effects database
    
    Can use:
    1. SIDER database files (if available)
    2. Built-in common drug side effects as fallback
    """
    
    def __init__(self, data_dir: Optional[str] = None, parsed_dir: Optional[str] = None):
        self.data_dir = data_dir or "./data/drugs/sider"
        self.parsed_dir = parsed_dir or "./data/drugs/sider/parsed"
        self._side_effects: Dict[str, DrugSideEffects] = {}
        self._symptom_drug_map: Dict[str, List[Tuple[str, SideEffect]]] = defaultdict(list)
        
        # Load built-in data first
        self._load_builtin_data()
        
        # Then try to load parsed SIDER data
        self._load_parsed_sider_data()
    
    def _load_builtin_data(self):
        """Load built-in side effects data"""
        for drug_name, effects in COMMON_DRUG_SIDE_EFFECTS.items():
            self._side_effects[drug_name.lower()] = DrugSideEffects(
                drug_name=drug_name.title(),
                drug_id=f"DB_{drug_name.upper()}",
                side_effects=effects
            )
        
        # Build symptom-drug map
        self._build_symptom_map()
        
        logger.info(f"Loaded side effects for {len(self._side_effects)} drugs")
    
    def _load_parsed_sider_data(self):
        """Load parsed SIDER data from JSON files"""
        import json
        
        parsed_path = Path(self.parsed_dir)
        se_file = parsed_path / "side_effects.json"
        freq_file = parsed_path / "side_effect_frequencies.json"
        
        if not se_file.exists():
            logger.info("Parsed SIDER files not found, using built-in data")
            return
        
        try:
            # Load side effects
            with open(se_file, 'r', encoding='utf-8') as f:
                se_data = json.load(f)
            
            # Load frequencies
            freq_data = {}
            if freq_file.exists():
                with open(freq_file, 'r', encoding='utf-8') as f:
                    freq_data = json.load(f)
            
            count = 0
            for drug_name, effects in se_data.items():
                drug_key = drug_name.lower()
                
                if drug_key not in self._side_effects:
                    self._side_effects[drug_key] = DrugSideEffects(
                        drug_name=drug_name.title(),
                        drug_id=f"SIDER_{drug_name.upper()}",
                        side_effects=[]
                    )
                
                # Get frequencies for this drug
                drug_freq = {}
                for freq_entry in freq_data.get(drug_name, []):
                    if freq_entry.get('side_effect') and freq_entry.get('frequency'):
                        drug_freq[freq_entry['side_effect'].lower()] = freq_entry
                
                # Add side effects
                for effect in effects:
                    se_name = effect.get('side_effect', '')
                    if not se_name:
                        continue
                    
                    # Get frequency if available
                    freq_info = drug_freq.get(se_name.lower(), {})
                    frequency = freq_info.get('frequency', 'frequency unknown')
                    
                    side_effect = SideEffect(
                        drug_name=drug_name.title(),
                        side_effect_name=se_name,
                        side_effect_id=effect.get('meddra_concept', ''),
                        frequency=frequency,
                        frequency_lower=None,
                        frequency_upper=None
                    )
                    
                    # Parse frequency bounds if present
                    try:
                        if freq_info.get('frequency_lower'):
                            side_effect.frequency_lower = float(freq_info['frequency_lower'])
                        if freq_info.get('frequency_upper'):
                            side_effect.frequency_upper = float(freq_info['frequency_upper'])
                    except (ValueError, TypeError):
                        pass
                    
                    self._side_effects[drug_key].side_effects.append(side_effect)
                    count += 1
            
            # Rebuild symptom map
            self._build_symptom_map()
            
            logger.info(f"Loaded {count} side effects from parsed SIDER data for {len(se_data)} drugs")
            
        except Exception as e:
            logger.warning(f"Failed to load parsed SIDER data: {e}")
    
    def _build_symptom_map(self):
        """Build reverse mapping from symptoms to drugs"""
        for drug_name, drug_effects in self._side_effects.items():
            for effect in drug_effects.side_effects:
                effect_lower = effect.side_effect_name.lower()
                self._symptom_drug_map[effect_lower].append((drug_name, effect))
                
                # Also map by synonyms
                for symptom, synonyms in SYMPTOM_SIDE_EFFECT_MAP.items():
                    if effect.side_effect_name in synonyms or effect_lower == symptom:
                        self._symptom_drug_map[symptom].append((drug_name, effect))
    
    def load_sider_files(self) -> bool:
        """
        Load SIDER database files
        
        Expected files in data_dir:
        - meddra_all_se.tsv.gz: All side effects
        - meddra_freq.tsv.gz: Frequency information
        """
        se_file = Path(self.data_dir) / "meddra_all_se.tsv.gz"
        freq_file = Path(self.data_dir) / "meddra_freq.tsv.gz"
        
        if not se_file.exists():
            logger.info("SIDER files not found, using built-in data")
            return False
        
        try:
            # Load side effects
            with gzip.open(se_file, 'rt') as f:
                reader = csv.reader(f, delimiter='\t')
                for row in reader:
                    if len(row) >= 6:
                        drug_id, drug_name = row[0], row[1]
                        se_id, se_name = row[4], row[5]
                        
                        drug_key = drug_name.lower()
                        
                        if drug_key not in self._side_effects:
                            self._side_effects[drug_key] = DrugSideEffects(
                                drug_name=drug_name,
                                drug_id=drug_id,
                                side_effects=[]
                            )
                        
                        self._side_effects[drug_key].side_effects.append(
                            SideEffect(
                                drug_name=drug_name,
                                side_effect_name=se_name,
                                side_effect_id=se_id,
                                frequency="frequency unknown"
                            )
                        )
            
            # Load frequencies if available
            if freq_file.exists():
                with gzip.open(freq_file, 'rt') as f:
                    reader = csv.reader(f, delimiter='\t')
                    for row in reader:
                        if len(row) >= 6:
                            drug_name = row[1]
                            se_name = row[5]
                            freq = row[3] if len(row) > 3 else "unknown"
                            freq_lower = float(row[4]) if len(row) > 4 else None
                            freq_upper = float(row[5]) if len(row) > 5 else None
                            
                            # Update frequency for matching side effect
                            drug_key = drug_name.lower()
                            if drug_key in self._side_effects:
                                for se in self._side_effects[drug_key].side_effects:
                                    if se.side_effect_name == se_name:
                                        se.frequency = freq
                                        se.frequency_lower = freq_lower
                                        se.frequency_upper = freq_upper
            
            # Rebuild symptom map
            self._build_symptom_map()
            
            logger.info(f"Loaded SIDER data for {len(self._side_effects)} drugs")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load SIDER files: {e}")
            return False
    
    def get_side_effects(
        self,
        drug_name: str
    ) -> Optional[DrugSideEffects]:
        """
        Get all side effects for a drug
        
        Args:
            drug_name: Drug name
            
        Returns:
            DrugSideEffects or None if not found
        """
        return self._side_effects.get(drug_name.lower())
    
    def get_common_side_effects(
        self,
        drug_name: str
    ) -> List[SideEffect]:
        """Get common side effects for a drug"""
        drug_effects = self.get_side_effects(drug_name)
        if drug_effects:
            return drug_effects.get_common()
        return []
    
    def get_serious_side_effects(
        self,
        drug_name: str
    ) -> List[SideEffect]:
        """Get serious side effects for a drug"""
        drug_effects = self.get_side_effects(drug_name)
        if drug_effects:
            return drug_effects.get_serious()
        return []
    
    def find_drugs_causing_symptom(
        self,
        symptom: str
    ) -> List[Tuple[str, SideEffect]]:
        """
        Find drugs that can cause a specific symptom
        
        Args:
            symptom: Symptom to search for
            
        Returns:
            List of (drug_name, side_effect) tuples
        """
        symptom_lower = symptom.lower()
        
        # Direct lookup
        if symptom_lower in self._symptom_drug_map:
            return self._symptom_drug_map[symptom_lower]
        
        # Fuzzy search
        results = []
        for effect_name, drugs in self._symptom_drug_map.items():
            if symptom_lower in effect_name or effect_name in symptom_lower:
                results.extend(drugs)
        
        return results
    
    def check_symptom_correlation(
        self,
        drug_name: str,
        symptom: str
    ) -> Optional[SideEffect]:
        """
        Check if a symptom could be a side effect of a drug
        
        Args:
            drug_name: Drug name
            symptom: Symptom to check
            
        Returns:
            Matching SideEffect or None
        """
        drug_effects = self.get_side_effects(drug_name)
        if not drug_effects:
            return None
        
        symptom_lower = symptom.lower()
        
        # Check against synonyms
        check_symptoms = {symptom_lower}
        for key, synonyms in SYMPTOM_SIDE_EFFECT_MAP.items():
            if symptom_lower in key or key in symptom_lower:
                check_symptoms.update(s.lower() for s in synonyms)
        
        # Find matching side effect
        for se in drug_effects.side_effects:
            se_lower = se.side_effect_name.lower()
            for check in check_symptoms:
                if check in se_lower or se_lower in check:
                    return se
        
        return None
    
    def get_side_effects_by_frequency(
        self,
        drug_name: str,
        frequency: str
    ) -> List[SideEffect]:
        """Get side effects by frequency category"""
        drug_effects = self.get_side_effects(drug_name)
        if drug_effects:
            return drug_effects.get_by_frequency(frequency)
        return []
    
    def compare_side_effects(
        self,
        drug1_name: str,
        drug2_name: str
    ) -> Dict[str, Any]:
        """
        Compare side effects between two drugs
        
        Returns:
            Dict with shared and unique side effects
        """
        effects1 = self.get_side_effects(drug1_name)
        effects2 = self.get_side_effects(drug2_name)
        
        if not effects1 or not effects2:
            return {"error": "One or both drugs not found"}
        
        set1 = {se.side_effect_name.lower() for se in effects1.side_effects}
        set2 = {se.side_effect_name.lower() for se in effects2.side_effects}
        
        shared = set1 & set2
        unique_to_drug1 = set1 - set2
        unique_to_drug2 = set2 - set1
        
        return {
            "drug1": drug1_name,
            "drug2": drug2_name,
            "shared_side_effects": list(shared),
            "unique_to_drug1": list(unique_to_drug1),
            "unique_to_drug2": list(unique_to_drug2),
            "total_drug1": len(set1),
            "total_drug2": len(set2)
        }
    
    def get_all_drugs(self) -> List[str]:
        """Get list of all drug names"""
        return [de.drug_name for de in self._side_effects.values()]
    
    def search_side_effects(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search side effects across all drugs
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching results
        """
        query_lower = query.lower()
        results = []
        
        for drug_name, drug_effects in self._side_effects.items():
            for se in drug_effects.side_effects:
                if query_lower in se.side_effect_name.lower():
                    results.append({
                        "drug_name": drug_effects.drug_name,
                        "side_effect": se.to_dict()
                    })
        
        return results[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about loaded data"""
        total_effects = sum(
            len(de.side_effects) for de in self._side_effects.values()
        )
        
        return {
            "total_drugs": len(self._side_effects),
            "total_side_effects": total_effects,
            "unique_symptoms": len(self._symptom_drug_map)
        }


# Singleton instance
sider_loader = SIDERLoader()
