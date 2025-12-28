#!/usr/bin/env python
"""
Fetch RxNorm Data via Public API
Script to fetch drug data from the RxNav public API and save locally
"""

import sys
import os
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# RxNav API (public, no auth required)
RXNORM_API_URL = "https://rxnav.nlm.nih.gov/REST"

# Target medications for adherence system
TARGET_MEDICATIONS = [
    # Diabetes
    "metformin", "glipizide", "glyburide", "glimepiride", "sitagliptin",
    "empagliflozin", "dapagliflozin", "canagliflozin", "liraglutide",
    "semaglutide", "pioglitazone",
    
    # Hypertension  
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan",
    "olmesartan", "amlodipine", "nifedipine", "diltiazem", "verapamil",
    "hydrochlorothiazide", "chlorthalidone", "furosemide", "metoprolol",
    "atenolol", "carvedilol", "propranolol", "clonidine",
    
    # Cardiovascular
    "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    "aspirin", "clopidogrel", "warfarin", "apixaban", "rivaroxaban",
    
    # Mental Health
    "sertraline", "fluoxetine", "paroxetine", "escitalopram", "citalopram",
    "venlafaxine", "duloxetine", "bupropion", "mirtazapine", "trazodone",
    "alprazolam", "lorazepam", "clonazepam", "diazepam",
    "quetiapine", "aripiprazole", "olanzapine", "risperidone",
    
    # Pain/Inflammation
    "gabapentin", "pregabalin", "tramadol", "ibuprofen", "naproxen",
    "celecoxib", "acetaminophen", "meloxicam",
    
    # GI
    "omeprazole", "pantoprazole", "esomeprazole", "famotidine",
    "ondansetron", "metoclopramide",
    
    # Thyroid
    "levothyroxine", "methimazole",
    
    # Respiratory
    "albuterol", "fluticasone", "budesonide", "montelukast", "tiotropium",
    
    # Other
    "prednisone", "amoxicillin", "azithromycin", "ciprofloxacin",
    "metronidazole", "doxycycline", "cyclobenzaprine"
]


@dataclass
class RxNormDrug:
    """Drug information from RxNorm"""
    rxcui: str
    name: str
    tty: str  # Term type
    synonym: str = ""
    drug_class: str = ""
    strengths: List[str] = field(default_factory=list)
    dose_forms: List[str] = field(default_factory=list)
    interactions: List[Dict] = field(default_factory=list)
    ndc_codes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class RxNormDataLoader:
    """Load RxNorm data from the public RxNav API"""
    
    def __init__(self):
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required. Install with: pip install requests")
        
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "AdherenceGuardian/1.0"
        })
    
    def get_rxcui(self, drug_name: str) -> Optional[str]:
        """Get RxCUI for a drug name using RxNav API"""
        url = f"{RXNORM_API_URL}/rxcui.json"
        params = {"name": drug_name, "search": 2}  # Approximate match
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "idGroup" in data and "rxnormId" in data["idGroup"]:
                rxcui_list = data["idGroup"]["rxnormId"]
                if rxcui_list:
                    return rxcui_list[0]
        except Exception as e:
            logger.warning(f"Error getting RxCUI for {drug_name}: {e}")
        
        return None
    
    def get_drug_info(self, rxcui: str) -> Optional[Dict]:
        """Get drug information by RxCUI"""
        url = f"{RXNORM_API_URL}/rxcui/{rxcui}/properties.json"
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "properties" in data:
                return data["properties"]
        except Exception as e:
            logger.warning(f"Error getting drug info for RxCUI {rxcui}: {e}")
        
        return None
    
    def get_drug_class(self, rxcui: str) -> List[str]:
        """Get drug class information"""
        url = f"{RXNORM_API_URL}/rxclass/class/byRxcui.json"
        params = {"rxcui": rxcui}
        
        classes = []
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "rxclassMinConceptList" in data:
                for concept in data["rxclassMinConceptList"].get("rxclassMinConcept", []):
                    class_name = concept.get("className", "")
                    if class_name and class_name not in classes:
                        classes.append(class_name)
        except Exception as e:
            logger.debug(f"Error getting drug class for RxCUI {rxcui}: {e}")
        
        return classes[:5]  # Limit to 5 classes
    
    def get_related_drugs(self, rxcui: str) -> Dict[str, List]:
        """Get related drug concepts (strengths, dose forms)"""
        url = f"{RXNORM_API_URL}/rxcui/{rxcui}/related.json"
        params = {"tty": "SCD+SBD"}  # Semantic clinical drug forms
        
        related = {"strengths": [], "dose_forms": []}
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "relatedGroup" in data and "conceptGroup" in data["relatedGroup"]:
                for group in data["relatedGroup"]["conceptGroup"]:
                    if "conceptProperties" in group:
                        for prop in group["conceptProperties"]:
                            name = prop.get("name", "")
                            if name:
                                related["dose_forms"].append(name)
                                # Extract strength patterns
                                if any(unit in name.lower() for unit in ["mg", "mcg", "ml", "unit", "%"]):
                                    related["strengths"].append(name)
        except Exception as e:
            logger.debug(f"Error getting related drugs for RxCUI {rxcui}: {e}")
        
        return {
            "strengths": related["strengths"][:15],
            "dose_forms": related["dose_forms"][:15]
        }
    
    def get_drug_interactions(self, rxcui: str) -> List[Dict]:
        """Get drug-drug interactions"""
        url = f"{RXNORM_API_URL}/interaction/interaction.json"
        params = {"rxcui": rxcui}
        
        interactions = []
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "interactionTypeGroup" in data:
                for group in data["interactionTypeGroup"]:
                    for itype in group.get("interactionType", []):
                        for pair in itype.get("interactionPair", []):
                            interaction = {
                                "severity": pair.get("severity", "N/A"),
                                "description": pair.get("description", ""),
                                "interacting_drug": "",
                                "interacting_rxcui": ""
                            }
                            
                            # Get interacting drug name
                            concepts = pair.get("interactionConcept", [])
                            for concept in concepts:
                                concept_rxcui = concept.get("minConceptItem", {}).get("rxcui")
                                if concept_rxcui and concept_rxcui != rxcui:
                                    interaction["interacting_drug"] = concept.get("minConceptItem", {}).get("name", "")
                                    interaction["interacting_rxcui"] = concept_rxcui
                            
                            if interaction["interacting_drug"]:
                                interactions.append(interaction)
        except Exception as e:
            logger.debug(f"Error getting interactions for RxCUI {rxcui}: {e}")
        
        return interactions[:25]  # Limit to top 25
    
    def get_ndcs(self, rxcui: str) -> List[str]:
        """Get NDC codes for a drug"""
        url = f"{RXNORM_API_URL}/rxcui/{rxcui}/ndcs.json"
        
        ndcs = []
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "ndcGroup" in data and "ndcList" in data["ndcGroup"]:
                ndcs = data["ndcGroup"]["ndcList"].get("ndc", [])[:10]
        except Exception as e:
            logger.debug(f"Error getting NDCs for RxCUI {rxcui}: {e}")
        
        return ndcs
    
    def fetch_drug_data(self, drug_name: str) -> Optional[RxNormDrug]:
        """Fetch complete drug data for a medication"""
        logger.info(f"  Fetching: {drug_name}")
        
        # Get RxCUI
        rxcui = self.get_rxcui(drug_name)
        if not rxcui:
            logger.warning(f"    No RxCUI found for {drug_name}")
            return None
        
        # Get basic info
        info = self.get_drug_info(rxcui)
        if not info:
            return None
        
        # Get drug class
        drug_classes = self.get_drug_class(rxcui)
        
        # Get related drugs (strengths, forms)
        related = self.get_related_drugs(rxcui)
        
        # Get interactions
        interactions = self.get_drug_interactions(rxcui)
        
        # Get NDC codes
        ndcs = self.get_ndcs(rxcui)
        
        drug = RxNormDrug(
            rxcui=rxcui,
            name=info.get("name", drug_name),
            tty=info.get("tty", ""),
            synonym=info.get("synonym", ""),
            drug_class=drug_classes[0] if drug_classes else "",
            strengths=related["strengths"],
            dose_forms=related["dose_forms"],
            interactions=interactions,
            ndc_codes=ndcs
        )
        
        logger.info(f"    RxCUI: {rxcui} | Class: {drug.drug_class or 'N/A'} | Interactions: {len(drug.interactions)}")
        
        return drug
    
    def fetch_all_target_drugs(self, rate_limit: float = 0.3) -> Dict[str, RxNormDrug]:
        """Fetch data for all target medications"""
        drugs = {}
        
        for i, drug_name in enumerate(TARGET_MEDICATIONS):
            logger.info(f"[{i+1}/{len(TARGET_MEDICATIONS)}] {drug_name}")
            
            drug = self.fetch_drug_data(drug_name)
            if drug:
                drugs[drug_name.lower()] = drug
            
            # Rate limiting
            time.sleep(rate_limit)
        
        return drugs


def save_rxnorm_data(drugs: Dict[str, RxNormDrug], output_dir: str):
    """Save RxNorm data to JSON files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save all drugs
    drugs_file = output_path / "rxnorm_drugs.json"
    drugs_dict = {name: drug.to_dict() for name, drug in drugs.items()}
    
    with open(drugs_file, 'w', encoding='utf-8') as f:
        json.dump(drugs_dict, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(drugs)} drugs to {drugs_file}")
    
    # Save interactions separately
    interactions_file = output_path / "rxnorm_interactions.json"
    interactions = {}
    for name, drug in drugs.items():
        if drug.interactions:
            interactions[name] = drug.interactions
    
    with open(interactions_file, 'w', encoding='utf-8') as f:
        json.dump(interactions, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved interactions for {len(interactions)} drugs")
    
    # Save drug classes
    classes_file = output_path / "drug_classes.json"
    classes = {}
    for name, drug in drugs.items():
        if drug.drug_class:
            if drug.drug_class not in classes:
                classes[drug.drug_class] = []
            classes[drug.drug_class].append(name)
    
    with open(classes_file, 'w', encoding='utf-8') as f:
        json.dump(classes, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(classes)} drug classes")
    
    # Save RxCUI mapping
    rxcui_file = output_path / "rxcui_mapping.json"
    rxcui_map = {name: drug.rxcui for name, drug in drugs.items()}
    
    with open(rxcui_file, 'w', encoding='utf-8') as f:
        json.dump(rxcui_map, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved RxCUI mappings")
    
    # Save dose forms for scheduling
    forms_file = output_path / "dose_forms.json"
    forms = {name: drug.dose_forms for name, drug in drugs.items() if drug.dose_forms}
    
    with open(forms_file, 'w', encoding='utf-8') as f:
        json.dump(forms, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved dose forms for {len(forms)} drugs")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch RxNorm drug data from the public RxNav API"
    )
    parser.add_argument(
        "--output",
        default="data/drugs/rxnorm/parsed",
        help="Output directory for RxNorm data"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=0.3,
        help="Delay between API calls (seconds)"
    )
    parser.add_argument(
        "--drug",
        type=str,
        help="Fetch data for a specific drug only"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("RxNorm Data Loader (RxNav Public API)")
    print("="*60)
    print(f"API: {RXNORM_API_URL}")
    
    loader = RxNormDataLoader()
    
    if args.drug:
        # Fetch single drug
        drug = loader.fetch_drug_data(args.drug)
        if drug:
            print(f"\nDrug: {drug.name}")
            print(f"RxCUI: {drug.rxcui}")
            print(f"Class: {drug.drug_class}")
            print(f"Dose Forms: {len(drug.dose_forms)}")
            print(f"Interactions: {len(drug.interactions)}")
            
            # Save single drug
            save_rxnorm_data({args.drug.lower(): drug}, args.output)
        else:
            print(f"\nCould not find drug: {args.drug}")
    else:
        # Fetch all target drugs
        print(f"\nFetching data for {len(TARGET_MEDICATIONS)} medications...")
        print(f"Rate limit: {args.rate_limit}s between API calls\n")
        
        drugs = loader.fetch_all_target_drugs(rate_limit=args.rate_limit)
        
        # Save data
        save_rxnorm_data(drugs, args.output)
        
        # Print summary
        print("\n" + "="*60)
        print("Fetch Complete!")
        print("="*60)
        print(f"\nDrugs fetched: {len(drugs)} / {len(TARGET_MEDICATIONS)}")
        print(f"Output directory: {args.output}")
        
        # Statistics
        with_interactions = sum(1 for d in drugs.values() if d.interactions)
        with_class = sum(1 for d in drugs.values() if d.drug_class)
        total_interactions = sum(len(d.interactions) for d in drugs.values())
        
        print(f"\nDrugs with interactions: {with_interactions}")
        print(f"Total interaction pairs: {total_interactions}")
        print(f"Drugs with drug class: {with_class}")


if __name__ == "__main__":
    main()
