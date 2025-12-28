"""
Drug Database Tool
Interface for drug information lookup via RxNorm and local cache
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import httpx
from functools import lru_cache

from config import settings


logger = logging.getLogger(__name__)


@dataclass
class DrugInfo:
    """Drug information structure"""
    name: str
    generic_name: Optional[str] = None
    rxnorm_id: Optional[str] = None
    drug_class: Optional[str] = None
    dosage_forms: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    common_doses: List[str] = field(default_factory=list)
    with_food: bool = False
    with_water: bool = True
    common_side_effects: List[str] = field(default_factory=list)
    serious_side_effects: List[str] = field(default_factory=list)
    contraindications: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pregnancy_category: Optional[str] = None
    storage_instructions: Optional[str] = None


# Local drug database (fallback when API unavailable)
LOCAL_DRUG_DATABASE: Dict[str, DrugInfo] = {
    "metformin": DrugInfo(
        name="Metformin",
        generic_name="metformin hydrochloride",
        rxnorm_id="6809",
        drug_class="Biguanide",
        dosage_forms=["tablet", "extended-release tablet", "oral solution"],
        strengths=["500mg", "850mg", "1000mg"],
        common_doses=["500mg twice daily", "1000mg twice daily"],
        with_food=True,
        common_side_effects=["nausea", "diarrhea", "stomach upset", "metallic taste", "loss of appetite"],
        serious_side_effects=["lactic acidosis", "vitamin B12 deficiency"],
        contraindications=["severe kidney disease", "metabolic acidosis", "diabetic ketoacidosis"],
        warnings=["Hold before contrast procedures", "Monitor kidney function"]
    ),
    "lisinopril": DrugInfo(
        name="Lisinopril",
        generic_name="lisinopril",
        rxnorm_id="29046",
        drug_class="ACE Inhibitor",
        dosage_forms=["tablet"],
        strengths=["2.5mg", "5mg", "10mg", "20mg", "40mg"],
        common_doses=["10mg once daily", "20mg once daily"],
        with_food=False,
        common_side_effects=["dry cough", "dizziness", "headache", "fatigue"],
        serious_side_effects=["angioedema", "hyperkalemia", "acute kidney injury"],
        contraindications=["history of angioedema", "pregnancy"],
        pregnancy_category="D"
    ),
    "atorvastatin": DrugInfo(
        name="Atorvastatin",
        generic_name="atorvastatin calcium",
        rxnorm_id="83367",
        drug_class="HMG-CoA Reductase Inhibitor (Statin)",
        dosage_forms=["tablet"],
        strengths=["10mg", "20mg", "40mg", "80mg"],
        common_doses=["20mg once daily", "40mg once daily"],
        with_food=False,
        common_side_effects=["muscle pain", "joint pain", "nausea", "diarrhea"],
        serious_side_effects=["rhabdomyolysis", "liver damage", "memory issues"],
        contraindications=["active liver disease", "pregnancy", "breastfeeding"],
        warnings=["Avoid grapefruit juice", "Monitor liver function"]
    ),
    "amlodipine": DrugInfo(
        name="Amlodipine",
        generic_name="amlodipine besylate",
        rxnorm_id="17767",
        drug_class="Calcium Channel Blocker",
        dosage_forms=["tablet"],
        strengths=["2.5mg", "5mg", "10mg"],
        common_doses=["5mg once daily", "10mg once daily"],
        with_food=False,
        common_side_effects=["swelling", "dizziness", "flushing", "fatigue", "palpitations"],
        serious_side_effects=["severe hypotension", "worsening angina"],
        contraindications=["severe aortic stenosis", "cardiogenic shock"]
    ),
    "omeprazole": DrugInfo(
        name="Omeprazole",
        generic_name="omeprazole",
        rxnorm_id="7646",
        drug_class="Proton Pump Inhibitor",
        dosage_forms=["capsule", "tablet"],
        strengths=["10mg", "20mg", "40mg"],
        common_doses=["20mg once daily", "40mg once daily"],
        with_food=False,
        common_side_effects=["headache", "nausea", "diarrhea", "stomach pain", "gas"],
        serious_side_effects=["C. diff infection", "bone fractures", "magnesium deficiency"],
        contraindications=["known hypersensitivity"],
        warnings=["Take 30-60 minutes before meals", "Long-term use concerns"]
    ),
    "metoprolol": DrugInfo(
        name="Metoprolol",
        generic_name="metoprolol succinate",
        rxnorm_id="6918",
        drug_class="Beta Blocker",
        dosage_forms=["tablet", "extended-release tablet"],
        strengths=["25mg", "50mg", "100mg", "200mg"],
        common_doses=["50mg twice daily", "100mg once daily (ER)"],
        with_food=True,
        common_side_effects=["fatigue", "dizziness", "slow heartbeat", "cold hands/feet"],
        serious_side_effects=["severe bradycardia", "heart failure worsening", "bronchospasm"],
        contraindications=["severe bradycardia", "heart block", "decompensated heart failure"],
        warnings=["Do not stop abruptly", "May mask hypoglycemia symptoms"]
    ),
    "levothyroxine": DrugInfo(
        name="Levothyroxine",
        generic_name="levothyroxine sodium",
        rxnorm_id="10582",
        drug_class="Thyroid Hormone",
        dosage_forms=["tablet", "capsule"],
        strengths=["25mcg", "50mcg", "75mcg", "100mcg", "125mcg", "150mcg"],
        common_doses=["50mcg once daily", "100mcg once daily"],
        with_food=False,
        common_side_effects=["weight changes", "anxiety", "tremor", "insomnia"],
        serious_side_effects=["arrhythmias", "chest pain", "thyroid storm"],
        contraindications=["untreated adrenal insufficiency", "acute MI"],
        warnings=["Take on empty stomach", "Wait 4 hours before calcium/iron"]
    ),
    "gabapentin": DrugInfo(
        name="Gabapentin",
        generic_name="gabapentin",
        rxnorm_id="25480",
        drug_class="Anticonvulsant/Analgesic",
        dosage_forms=["capsule", "tablet", "oral solution"],
        strengths=["100mg", "300mg", "400mg", "600mg", "800mg"],
        common_doses=["300mg three times daily", "600mg three times daily"],
        with_food=False,
        common_side_effects=["drowsiness", "dizziness", "fatigue", "weight gain"],
        serious_side_effects=["suicidal thoughts", "severe allergic reaction", "respiratory depression"],
        contraindications=["known hypersensitivity"],
        warnings=["Taper gradually to discontinue", "May cause sedation"]
    ),
    "sertraline": DrugInfo(
        name="Sertraline",
        generic_name="sertraline hydrochloride",
        rxnorm_id="36437",
        drug_class="SSRI Antidepressant",
        dosage_forms=["tablet", "oral solution"],
        strengths=["25mg", "50mg", "100mg"],
        common_doses=["50mg once daily", "100mg once daily"],
        with_food=False,
        common_side_effects=["nausea", "diarrhea", "insomnia", "dry mouth", "dizziness"],
        serious_side_effects=["serotonin syndrome", "suicidal thoughts", "bleeding risk"],
        contraindications=["MAO inhibitor use", "pimozide use"],
        warnings=["Black box warning for suicidal thoughts in youth"]
    ),
    "losartan": DrugInfo(
        name="Losartan",
        generic_name="losartan potassium",
        rxnorm_id="52175",
        drug_class="Angiotensin II Receptor Blocker (ARB)",
        dosage_forms=["tablet"],
        strengths=["25mg", "50mg", "100mg"],
        common_doses=["50mg once daily", "100mg once daily"],
        with_food=False,
        common_side_effects=["dizziness", "fatigue", "nasal congestion", "back pain"],
        serious_side_effects=["hyperkalemia", "acute kidney injury", "fetal toxicity"],
        contraindications=["pregnancy", "bilateral renal artery stenosis"],
        pregnancy_category="D"
    ),
    "aspirin": DrugInfo(
        name="Aspirin",
        generic_name="acetylsalicylic acid",
        rxnorm_id="1191",
        drug_class="NSAID/Antiplatelet",
        dosage_forms=["tablet", "enteric-coated tablet", "chewable tablet"],
        strengths=["81mg", "325mg", "500mg"],
        common_doses=["81mg once daily", "325mg once daily"],
        with_food=True,
        common_side_effects=["stomach upset", "heartburn", "nausea"],
        serious_side_effects=["GI bleeding", "allergic reaction", "tinnitus"],
        contraindications=["bleeding disorders", "aspirin allergy", "active GI bleeding"]
    ),
    "warfarin": DrugInfo(
        name="Warfarin",
        generic_name="warfarin sodium",
        rxnorm_id="11289",
        drug_class="Anticoagulant",
        dosage_forms=["tablet"],
        strengths=["1mg", "2mg", "2.5mg", "3mg", "4mg", "5mg", "6mg", "7.5mg", "10mg"],
        common_doses=["5mg once daily", "Variable based on INR"],
        with_food=False,
        common_side_effects=["bruising", "bleeding gums"],
        serious_side_effects=["major bleeding", "skin necrosis", "purple toe syndrome"],
        contraindications=["active bleeding", "pregnancy"],
        warnings=["Many drug and food interactions", "Regular INR monitoring required"]
    )
}


class DrugDatabase:
    """
    Drug information database with RxNorm API integration
    and local cache fallback
    """
    
    def __init__(self):
        self.rxnorm_base_url = settings.RXNORM_API_URL
        self.local_db = LOCAL_DRUG_DATABASE
        self._cache: Dict[str, tuple[DrugInfo, datetime]] = {}
        self._cache_ttl = timedelta(hours=24)
    
    async def get_drug_info(self, drug_name: str) -> Optional[DrugInfo]:
        """
        Get comprehensive drug information
        
        Args:
            drug_name: Name of the drug to look up
            
        Returns:
            DrugInfo object or None if not found
        """
        normalized_name = drug_name.lower().strip()
        
        # Check cache first
        if normalized_name in self._cache:
            cached_info, cached_time = self._cache[normalized_name]
            if datetime.utcnow() - cached_time < self._cache_ttl:
                return cached_info
        
        # Check local database
        if normalized_name in self.local_db:
            drug_info = self.local_db[normalized_name]
            self._cache[normalized_name] = (drug_info, datetime.utcnow())
            return drug_info
        
        # Try RxNorm API
        try:
            drug_info = await self._fetch_from_rxnorm(drug_name)
            if drug_info:
                self._cache[normalized_name] = (drug_info, datetime.utcnow())
                return drug_info
        except Exception as e:
            logger.warning(f"RxNorm API error for {drug_name}: {e}")
        
        return None
    
    async def _fetch_from_rxnorm(self, drug_name: str) -> Optional[DrugInfo]:
        """Fetch drug info from RxNorm API"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Get RxCUI (RxNorm Concept Unique Identifier)
                response = await client.get(
                    f"{self.rxnorm_base_url}/rxcui.json",
                    params={"name": drug_name}
                )
                
                if response.status_code != 200:
                    return None
                
                data = response.json()
                rxcui = data.get("idGroup", {}).get("rxnormId", [None])[0]
                
                if not rxcui:
                    return None
                
                # Get drug properties
                props_response = await client.get(
                    f"{self.rxnorm_base_url}/rxcui/{rxcui}/properties.json"
                )
                
                if props_response.status_code != 200:
                    return None
                
                props = props_response.json().get("properties", {})
                
                return DrugInfo(
                    name=props.get("name", drug_name),
                    generic_name=props.get("name"),
                    rxnorm_id=rxcui,
                    drug_class=props.get("tty"),
                )
                
        except httpx.TimeoutException:
            logger.warning(f"RxNorm API timeout for {drug_name}")
            return None
        except Exception as e:
            logger.error(f"RxNorm API error: {e}")
            return None
    
    async def get_side_effects(self, drug_name: str) -> Dict[str, List[str]]:
        """
        Get side effects for a drug
        
        Returns:
            Dictionary with 'common' and 'serious' side effects
        """
        drug_info = await self.get_drug_info(drug_name)
        
        if drug_info:
            return {
                "common": drug_info.common_side_effects,
                "serious": drug_info.serious_side_effects
            }
        
        return {"common": [], "serious": []}
    
    async def get_food_requirements(self, drug_name: str) -> Dict[str, Any]:
        """Get food/water requirements for a drug"""
        drug_info = await self.get_drug_info(drug_name)
        
        if drug_info:
            return {
                "with_food": drug_info.with_food,
                "with_water": drug_info.with_water,
                "recommendation": self._get_food_recommendation(drug_info)
            }
        
        return {
            "with_food": False,
            "with_water": True,
            "recommendation": "Take as directed"
        }
    
    def _get_food_recommendation(self, drug_info: DrugInfo) -> str:
        """Generate food recommendation text"""
        if drug_info.with_food:
            return "Take with food to reduce stomach upset"
        elif drug_info.name.lower() == "levothyroxine":
            return "Take on empty stomach, 30-60 minutes before breakfast"
        elif drug_info.name.lower() == "omeprazole":
            return "Take 30-60 minutes before a meal"
        else:
            return "Can be taken with or without food"
    
    async def search_drugs(self, query: str, limit: int = 10) -> List[Dict[str, str]]:
        """
        Search for drugs by name
        
        Args:
            query: Search term
            limit: Maximum results
            
        Returns:
            List of matching drug names with RxNorm IDs
        """
        results = []
        query_lower = query.lower()
        
        # Search local database first
        for name, info in self.local_db.items():
            if query_lower in name or query_lower in (info.generic_name or "").lower():
                results.append({
                    "name": info.name,
                    "generic_name": info.generic_name,
                    "rxnorm_id": info.rxnorm_id
                })
                
                if len(results) >= limit:
                    return results
        
        # Supplement with RxNorm API if needed
        if len(results) < limit:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(
                        f"{self.rxnorm_base_url}/drugs.json",
                        params={"name": query}
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        concepts = data.get("drugGroup", {}).get("conceptGroup", [])
                        
                        for group in concepts:
                            for concept in group.get("conceptProperties", []):
                                if len(results) >= limit:
                                    break
                                    
                                results.append({
                                    "name": concept.get("name"),
                                    "generic_name": concept.get("synonym"),
                                    "rxnorm_id": concept.get("rxcui")
                                })
                                
            except Exception as e:
                logger.warning(f"RxNorm search error: {e}")
        
        return results
    
    async def get_contraindications(self, drug_name: str) -> List[str]:
        """Get contraindications for a drug"""
        drug_info = await self.get_drug_info(drug_name)
        return drug_info.contraindications if drug_info else []
    
    async def get_warnings(self, drug_name: str) -> List[str]:
        """Get warnings for a drug"""
        drug_info = await self.get_drug_info(drug_name)
        return drug_info.warnings if drug_info else []
    
    def get_drug_class(self, drug_name: str) -> Optional[str]:
        """Get the drug class (synchronous for quick lookups)"""
        normalized = drug_name.lower().strip()
        if normalized in self.local_db:
            return self.local_db[normalized].drug_class
        return None


# Singleton instance
drug_database = DrugDatabase()


async def get_drug_info(drug_name: str) -> Optional[DrugInfo]:
    """Convenience function for getting drug info"""
    return await drug_database.get_drug_info(drug_name)


async def get_side_effects(drug_name: str) -> Dict[str, List[str]]:
    """Convenience function for getting side effects"""
    return await drug_database.get_side_effects(drug_name)
