#!/usr/bin/env python
"""
Load Drug Data
Script to load and cache drug data from external sources (RxNorm, DrugBank, SIDER)
"""

import sys
import os
import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base.rxnorm_client import RxNormClient, rxnorm_client
from knowledge_base.drugbank_loader import drugbank_loader, DrugInfo, DrugInteraction
from knowledge_base.sider_loader import sider_loader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Common medications to load data for
COMMON_MEDICATIONS = [
    # Diabetes
    "metformin", "glipizide", "insulin glargine", "sitagliptin", "empagliflozin",
    # Hypertension
    "lisinopril", "amlodipine", "losartan", "hydrochlorothiazide", "metoprolol",
    # Cardiovascular
    "atorvastatin", "simvastatin", "rosuvastatin", "aspirin", "clopidogrel", "warfarin",
    # Mental Health
    "sertraline", "fluoxetine", "escitalopram", "bupropion", "venlafaxine",
    "alprazolam", "lorazepam", "trazodone",
    # Pain/Inflammation
    "gabapentin", "tramadol", "ibuprofen", "naproxen", "celecoxib", "acetaminophen",
    # GI
    "omeprazole", "pantoprazole", "famotidine", "ondansetron",
    # Thyroid
    "levothyroxine",
    # Respiratory
    "albuterol", "fluticasone", "montelukast", "tiotropium",
    # Other common
    "prednisone", "amoxicillin", "azithromycin", "ciprofloxacin"
]


class DrugDataLoader:
    """Load and cache drug data from external sources"""
    
    def __init__(self, cache_dir: str = "./data/drug_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.rxnorm = RxNormClient()
    
    async def load_rxnorm_data(
        self,
        medications: List[str],
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """Load drug data from RxNorm API"""
        logger.info(f"Loading RxNorm data for {len(medications)} medications...")
        
        cache_file = self.cache_dir / "rxnorm_data.json"
        
        # Load existing cache
        cached_data = {}
        if cache_file.exists() and not force_refresh:
            with open(cache_file, 'r') as f:
                cached_data = json.load(f)
            logger.info(f"Loaded {len(cached_data)} medications from cache")
        
        results = {}
        new_count = 0
        
        for med_name in medications:
            med_lower = med_name.lower()
            
            # Check cache first
            if med_lower in cached_data and not force_refresh:
                results[med_lower] = cached_data[med_lower]
                continue
            
            try:
                # Get RxCUI
                rxcui = await self.rxnorm.get_rxcui(med_name)
                
                if rxcui:
                    # Get drug info
                    drug_info = await self.rxnorm.get_drug_info(med_name)
                    
                    # Get drug class
                    drug_classes = await self.rxnorm.get_drug_class(rxcui)
                    
                    # Get interactions
                    interactions = await self.rxnorm.get_drug_interactions(rxcui)
                    
                    results[med_lower] = {
                        "rxcui": rxcui,
                        "name": med_name,
                        "info": drug_info,
                        "classes": drug_classes,
                        "interactions": [i.to_dict() for i in interactions[:10]]  # Limit interactions
                    }
                    new_count += 1
                    logger.info(f"  Loaded: {med_name} (RxCUI: {rxcui})")
                else:
                    logger.warning(f"  Not found: {med_name}")
                    results[med_lower] = {"name": med_name, "error": "RxCUI not found"}
                
            except Exception as e:
                logger.error(f"  Error loading {med_name}: {e}")
                results[med_lower] = {"name": med_name, "error": str(e)}
        
        # Save to cache
        all_data = {**cached_data, **results}
        with open(cache_file, 'w') as f:
            json.dump(all_data, f, indent=2)
        
        logger.info(f"Loaded {new_count} new medications from RxNorm API")
        return results
    
    async def load_drug_interactions(
        self,
        medications: List[str]
    ) -> List[Dict[str, Any]]:
        """Load drug-drug interactions for a list of medications"""
        logger.info("Loading drug interactions...")
        
        # Get RxCUIs for all medications
        rxcuis = []
        rxcui_to_name = {}
        
        for med_name in medications:
            rxcui = await self.rxnorm.get_rxcui(med_name)
            if rxcui:
                rxcuis.append(rxcui)
                rxcui_to_name[rxcui] = med_name
        
        if len(rxcuis) < 2:
            logger.info("Not enough medications with RxCUIs to check interactions")
            return []
        
        # Check interactions between all pairs
        interactions = await self.rxnorm.check_interactions_between(rxcuis)
        
        logger.info(f"Found {len(interactions)} interactions")
        return [i.to_dict() for i in interactions]
    
    def load_drugbank_data(self) -> Dict[str, Any]:
        """Load data from DrugBank (cached/built-in)"""
        logger.info("Loading DrugBank data...")
        
        # Load from cache if available
        drugbank_loader.load_from_cache()
        
        stats = drugbank_loader.get_statistics()
        logger.info(f"DrugBank: {stats['total_drugs']} drugs, {stats['total_interactions']} interactions")
        
        return stats
    
    def load_sider_data(self) -> Dict[str, Any]:
        """Load data from SIDER (side effects)"""
        logger.info("Loading SIDER data...")
        
        # Try to load SIDER files if available
        sider_loader.load_sider_files()
        
        stats = sider_loader.get_statistics()
        logger.info(f"SIDER: {stats['total_drugs']} drugs, {stats['total_side_effects']} side effects")
        
        return stats
    
    def save_combined_data(self, rxnorm_data: Dict[str, Any]):
        """Save combined drug data for application use"""
        logger.info("Saving combined drug data...")
        
        combined_file = self.cache_dir / "combined_drug_data.json"
        
        combined = {
            "rxnorm": rxnorm_data,
            "drugbank_stats": drugbank_loader.get_statistics(),
            "sider_stats": sider_loader.get_statistics(),
            "medications_loaded": list(rxnorm_data.keys())
        }
        
        with open(combined_file, 'w') as f:
            json.dump(combined, f, indent=2)
        
        logger.info(f"Saved combined data to {combined_file}")
    
    async def close(self):
        """Close connections"""
        await self.rxnorm.close()


async def load_interaction_matrix(
    loader: DrugDataLoader,
    medications: List[str]
) -> Dict[str, List[Dict]]:
    """Load interaction matrix for common medication pairs"""
    logger.info("\nLoading drug interaction matrix...")
    
    cache_file = loader.cache_dir / "interaction_matrix.json"
    
    # This can be time-consuming, so we cache aggressively
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            data = json.load(f)
            logger.info(f"Loaded interaction matrix from cache ({len(data)} medications)")
            return data
    
    matrix = {}
    
    for med in medications[:20]:  # Limit to top 20 for API rate limits
        try:
            rxcui = await loader.rxnorm.get_rxcui(med)
            if rxcui:
                interactions = await loader.rxnorm.get_drug_interactions(rxcui)
                if interactions:
                    matrix[med] = [i.to_dict() for i in interactions[:5]]
                    logger.info(f"  {med}: {len(interactions)} interactions")
        except Exception as e:
            logger.error(f"  Error for {med}: {e}")
    
    # Save to cache
    with open(cache_file, 'w') as f:
        json.dump(matrix, f, indent=2)
    
    return matrix


def export_for_vector_store(cache_dir: Path):
    """Export drug data in format suitable for vector store indexing"""
    logger.info("\nExporting data for vector store...")
    
    export_file = cache_dir / "vector_store_export.json"
    
    documents = []
    
    # Export DrugBank data
    for drug_name in drugbank_loader.get_all_drug_names():
        drug = drugbank_loader.get_drug(drug_name)
        if drug:
            doc = {
                "type": "drug_info",
                "drug_name": drug.name,
                "content": f"{drug.name}: {drug.description} Indication: {drug.indication}. {drug.pharmacodynamics}",
                "metadata": {
                    "drug_class": drug.drug_class,
                    "drugbank_id": drug.drugbank_id
                }
            }
            documents.append(doc)
            
            # Food interactions
            if drug.food_interactions:
                doc = {
                    "type": "food_interaction",
                    "drug_name": drug.name,
                    "content": f"Food interactions for {drug.name}: " + " | ".join(drug.food_interactions),
                    "metadata": {"drug_name": drug.name}
                }
                documents.append(doc)
    
    # Export SIDER side effects
    for drug_name in sider_loader.get_all_drugs():
        effects = sider_loader.get_side_effects(drug_name)
        if effects:
            common = [se.side_effect_name for se in effects.side_effects if se.frequency == "common"]
            if common:
                doc = {
                    "type": "side_effects",
                    "drug_name": effects.drug_name,
                    "content": f"Common side effects of {effects.drug_name}: {', '.join(common)}",
                    "metadata": {"frequency": "common"}
                }
                documents.append(doc)
    
    with open(export_file, 'w') as f:
        json.dump(documents, f, indent=2)
    
    logger.info(f"Exported {len(documents)} documents to {export_file}")
    return len(documents)


async def run_data_loading(
    medications: Optional[List[str]] = None,
    force_refresh: bool = False,
    include_interactions: bool = True,
    export_vectors: bool = True
):
    """Run the full data loading process"""
    
    print("\n" + "="*60)
    print("Drug Data Loader")
    print("="*60)
    
    meds_to_load = medications or COMMON_MEDICATIONS
    print(f"Loading data for {len(meds_to_load)} medications")
    
    loader = DrugDataLoader()
    
    try:
        # Load RxNorm data
        print("\n--- RxNorm API ---")
        rxnorm_data = await loader.load_rxnorm_data(meds_to_load, force_refresh)
        
        # Load DrugBank data
        print("\n--- DrugBank ---")
        drugbank_stats = loader.load_drugbank_data()
        
        # Load SIDER data
        print("\n--- SIDER ---")
        sider_stats = loader.load_sider_data()
        
        # Load interaction matrix
        if include_interactions:
            print("\n--- Drug Interactions ---")
            interactions = await load_interaction_matrix(loader, meds_to_load)
        
        # Save combined data
        loader.save_combined_data(rxnorm_data)
        
        # Export for vector store
        if export_vectors:
            export_for_vector_store(loader.cache_dir)
        
        # Print summary
        print("\n" + "="*60)
        print("Data Loading Complete!")
        print("="*60)
        
        successful = sum(1 for v in rxnorm_data.values() if "error" not in v)
        print(f"\nRxNorm:")
        print(f"  Medications loaded: {successful}/{len(rxnorm_data)}")
        
        print(f"\nDrugBank:")
        print(f"  Drugs: {drugbank_stats['total_drugs']}")
        print(f"  Interactions: {drugbank_stats['total_interactions']}")
        
        print(f"\nSIDER:")
        print(f"  Drugs with side effects: {sider_stats['total_drugs']}")
        print(f"  Total side effects: {sider_stats['total_side_effects']}")
        
        print(f"\nCache location: {loader.cache_dir}")
        
    finally:
        await loader.close()


def main():
    parser = argparse.ArgumentParser(
        description="Load drug data from external sources (RxNorm, DrugBank, SIDER)"
    )
    parser.add_argument(
        "--medications",
        nargs="+",
        help="Specific medications to load (default: common medications)"
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force refresh data from APIs (ignore cache)"
    )
    parser.add_argument(
        "--no-interactions",
        action="store_true",
        help="Skip loading drug interaction matrix"
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip exporting data for vector store"
    )
    
    args = parser.parse_args()
    
    asyncio.run(run_data_loading(
        medications=args.medications,
        force_refresh=args.refresh,
        include_interactions=not args.no_interactions,
        export_vectors=not args.no_export
    ))


if __name__ == "__main__":
    main()
