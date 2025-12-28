#!/usr/bin/env python
"""
Parse DrugBank XML
Script to parse the full DrugBank XML database and extract relevant drug information
for the AdherenceGuardian system.
"""

import sys
import os
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# DrugBank XML namespace
NS = {'db': 'http://www.drugbank.ca'}

# Medications commonly used for chronic conditions (focus on adherence)
TARGET_MEDICATIONS = {
    # Diabetes
    "metformin", "glipizide", "glyburide", "glimepiride", "sitagliptin", 
    "empagliflozin", "dapagliflozin", "canagliflozin", "liraglutide", 
    "semaglutide", "insulin glargine", "insulin lispro", "pioglitazone",
    
    # Hypertension
    "lisinopril", "enalapril", "ramipril", "losartan", "valsartan", 
    "olmesartan", "amlodipine", "nifedipine", "diltiazem", "verapamil",
    "hydrochlorothiazide", "chlorthalidone", "furosemide", "metoprolol",
    "atenolol", "carvedilol", "propranolol", "clonidine",
    
    # Cardiovascular
    "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    "aspirin", "clopidogrel", "warfarin", "apixaban", "rivaroxaban",
    "dabigatran",
    
    # Mental Health
    "sertraline", "fluoxetine", "paroxetine", "escitalopram", "citalopram",
    "venlafaxine", "duloxetine", "bupropion", "mirtazapine", "trazodone",
    "alprazolam", "lorazepam", "clonazepam", "diazepam",
    "lithium", "quetiapine", "aripiprazole", "olanzapine", "risperidone",
    
    # Pain/Inflammation
    "gabapentin", "pregabalin", "tramadol", "ibuprofen", "naproxen",
    "celecoxib", "acetaminophen", "meloxicam",
    
    # GI
    "omeprazole", "pantoprazole", "esomeprazole", "famotidine", "ranitidine",
    "ondansetron", "metoclopramide",
    
    # Thyroid
    "levothyroxine", "liothyronine", "methimazole",
    
    # Respiratory
    "albuterol", "fluticasone", "budesonide", "montelukast", "tiotropium",
    "ipratropium", "theophylline",
    
    # Other common
    "prednisone", "methylprednisolone", "amoxicillin", "azithromycin",
    "ciprofloxacin", "metronidazole", "doxycycline", "cyclobenzaprine"
}


@dataclass
class DrugData:
    """Parsed drug data from DrugBank"""
    drugbank_id: str
    name: str
    description: str
    indication: str
    pharmacodynamics: str
    mechanism_of_action: str
    toxicity: str
    metabolism: str
    absorption: str
    half_life: str
    protein_binding: str
    route_of_elimination: str
    food_interactions: List[str]
    drug_interactions: List[Dict[str, str]]
    categories: List[str]
    synonyms: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def parse_drug_element(drug_elem) -> Optional[DrugData]:
    """Parse a single drug element from the XML"""
    
    def get_text(elem, path: str, default: str = "") -> str:
        """Get text from an element path"""
        found = elem.find(path, NS)
        return found.text.strip() if found is not None and found.text else default
    
    def get_list(elem, path: str, item_tag: str) -> List[str]:
        """Get a list of items from an element path"""
        container = elem.find(path, NS)
        if container is None:
            return []
        items = []
        for item in container.findall(item_tag, NS):
            if item.text:
                items.append(item.text.strip())
        return items
    
    try:
        # Get basic info
        drugbank_id = get_text(drug_elem, 'db:drugbank-id[@primary="true"]')
        name = get_text(drug_elem, 'db:name')
        
        if not name:
            return None
        
        # Get detailed information
        description = get_text(drug_elem, 'db:description')
        indication = get_text(drug_elem, 'db:indication')
        pharmacodynamics = get_text(drug_elem, 'db:pharmacodynamics')
        mechanism = get_text(drug_elem, 'db:mechanism-of-action')
        toxicity = get_text(drug_elem, 'db:toxicity')
        metabolism = get_text(drug_elem, 'db:metabolism')
        absorption = get_text(drug_elem, 'db:absorption')
        half_life = get_text(drug_elem, 'db:half-life')
        protein_binding = get_text(drug_elem, 'db:protein-binding')
        route_elimination = get_text(drug_elem, 'db:route-of-elimination')
        
        # Food interactions
        food_interactions = []
        food_elem = drug_elem.find('db:food-interactions', NS)
        if food_elem is not None:
            for fi in food_elem.findall('db:food-interaction', NS):
                if fi.text:
                    food_interactions.append(fi.text.strip())
        
        # Drug interactions
        drug_interactions = []
        di_elem = drug_elem.find('db:drug-interactions', NS)
        if di_elem is not None:
            for di in di_elem.findall('db:drug-interaction', NS):
                interaction = {
                    'drugbank_id': get_text(di, 'db:drugbank-id'),
                    'name': get_text(di, 'db:name'),
                    'description': get_text(di, 'db:description')
                }
                if interaction['name']:
                    drug_interactions.append(interaction)
        
        # Categories
        categories = []
        cat_elem = drug_elem.find('db:categories', NS)
        if cat_elem is not None:
            for cat in cat_elem.findall('db:category', NS):
                cat_name = get_text(cat, 'db:category')
                if cat_name:
                    categories.append(cat_name)
        
        # Synonyms
        synonyms = []
        syn_elem = drug_elem.find('db:synonyms', NS)
        if syn_elem is not None:
            for syn in syn_elem.findall('db:synonym', NS):
                if syn.text:
                    synonyms.append(syn.text.strip())
        
        return DrugData(
            drugbank_id=drugbank_id,
            name=name,
            description=description[:2000] if description else "",  # Truncate long descriptions
            indication=indication[:1000] if indication else "",
            pharmacodynamics=pharmacodynamics[:1000] if pharmacodynamics else "",
            mechanism_of_action=mechanism[:1000] if mechanism else "",
            toxicity=toxicity[:500] if toxicity else "",
            metabolism=metabolism[:500] if metabolism else "",
            absorption=absorption[:500] if absorption else "",
            half_life=half_life,
            protein_binding=protein_binding,
            route_of_elimination=route_elimination[:300] if route_elimination else "",
            food_interactions=food_interactions[:10],  # Limit to 10
            drug_interactions=drug_interactions[:50],  # Limit to 50 most relevant
            categories=categories,
            synonyms=synonyms[:10]  # Limit synonyms
        )
        
    except Exception as e:
        logger.error(f"Error parsing drug element: {e}")
        return None


def parse_drugbank_xml(xml_path: str, target_only: bool = True) -> Dict[str, DrugData]:
    """
    Parse the DrugBank XML file
    
    Args:
        xml_path: Path to the DrugBank XML file
        target_only: If True, only parse target medications
        
    Returns:
        Dictionary of drug name -> DrugData
    """
    logger.info(f"Parsing DrugBank XML: {xml_path}")
    
    drugs = {}
    count = 0
    matched = 0
    
    # Use iterparse for memory efficiency with large XML
    context = ET.iterparse(xml_path, events=('end',))
    
    for event, elem in context:
        # Look for drug elements
        if elem.tag == '{http://www.drugbank.ca}drug':
            count += 1
            
            # Get drug name
            name_elem = elem.find('{http://www.drugbank.ca}name')
            if name_elem is not None and name_elem.text:
                name_lower = name_elem.text.strip().lower()
                
                # Check if it's a target medication
                if target_only and name_lower not in TARGET_MEDICATIONS:
                    # Also check synonyms
                    syn_elem = elem.find('{http://www.drugbank.ca}synonyms')
                    is_target = False
                    if syn_elem is not None:
                        for syn in syn_elem.findall('{http://www.drugbank.ca}synonym'):
                            if syn.text and syn.text.strip().lower() in TARGET_MEDICATIONS:
                                is_target = True
                                break
                    
                    if not is_target:
                        elem.clear()
                        continue
                
                # Parse the drug
                # Need to re-add namespace for parsing
                drug_data = parse_drug_element(elem)
                if drug_data:
                    drugs[drug_data.name.lower()] = drug_data
                    matched += 1
                    logger.info(f"  Parsed: {drug_data.name} ({drug_data.drugbank_id})")
            
            # Clear element to save memory
            elem.clear()
            
            if count % 1000 == 0:
                logger.info(f"  Processed {count} drugs, matched {matched}...")
    
    logger.info(f"Parsing complete: {count} total drugs, {matched} matched")
    return drugs


def save_parsed_data(drugs: Dict[str, DrugData], output_dir: str):
    """Save parsed drug data to JSON files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save all drugs to a single JSON
    all_drugs_file = output_path / "drugbank_parsed.json"
    drugs_dict = {name: drug.to_dict() for name, drug in drugs.items()}
    
    with open(all_drugs_file, 'w', encoding='utf-8') as f:
        json.dump(drugs_dict, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved {len(drugs)} drugs to {all_drugs_file}")
    
    # Save drug interactions separately for quick lookup
    interactions_file = output_path / "drug_interactions.json"
    interactions = {}
    for name, drug in drugs.items():
        if drug.drug_interactions:
            interactions[name] = drug.drug_interactions
    
    with open(interactions_file, 'w', encoding='utf-8') as f:
        json.dump(interactions, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved interactions for {len(interactions)} drugs to {interactions_file}")
    
    # Save food interactions
    food_file = output_path / "food_interactions.json"
    food = {}
    for name, drug in drugs.items():
        if drug.food_interactions:
            food[name] = drug.food_interactions
    
    with open(food_file, 'w', encoding='utf-8') as f:
        json.dump(food, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved food interactions for {len(food)} drugs to {food_file}")


def update_vector_store(drugs: Dict[str, DrugData]):
    """Update the vector store with parsed drug data"""
    try:
        from knowledge_base import knowledge_base
        
        logger.info("Updating vector store with DrugBank data...")
        
        # Clear existing drug info
        knowledge_base.drug_info_store.clear()
        
        count = 0
        for name, drug in drugs.items():
            # Add main drug info
            content = f"""
Drug: {drug.name}
DrugBank ID: {drug.drugbank_id}
Description: {drug.description[:500] if drug.description else 'N/A'}
Indication: {drug.indication[:300] if drug.indication else 'N/A'}
Mechanism: {drug.mechanism_of_action[:300] if drug.mechanism_of_action else 'N/A'}
Half-life: {drug.half_life or 'N/A'}
"""
            knowledge_base.add_drug_info(
                content=content,
                drug_name=drug.name,
                drug_class=drug.categories[0] if drug.categories else "Unknown"
            )
            count += 1
            
            # Add food interactions
            if drug.food_interactions:
                food_content = f"Food interactions for {drug.name}: " + "; ".join(drug.food_interactions[:5])
                knowledge_base.add_drug_info(
                    content=food_content,
                    drug_name=drug.name,
                    drug_class="food_interaction"
                )
                count += 1
        
        logger.info(f"Added {count} documents to vector store")
        return count
        
    except Exception as e:
        logger.error(f"Failed to update vector store: {e}")
        return 0


def main():
    parser = argparse.ArgumentParser(
        description="Parse DrugBank XML and extract drug data"
    )
    parser.add_argument(
        "--xml",
        default="data/drugs/drugbank/full database.xml",
        help="Path to DrugBank XML file"
    )
    parser.add_argument(
        "--output",
        default="data/drugs/drugbank/parsed",
        help="Output directory for parsed data"
    )
    parser.add_argument(
        "--all-drugs",
        action="store_true",
        help="Parse all drugs (not just target medications)"
    )
    parser.add_argument(
        "--update-vectors",
        action="store_true",
        help="Update the vector store with parsed data"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("DrugBank XML Parser")
    print("="*60)
    
    # Parse XML
    drugs = parse_drugbank_xml(args.xml, target_only=not args.all_drugs)
    
    if not drugs:
        logger.error("No drugs parsed!")
        return
    
    # Save parsed data
    save_parsed_data(drugs, args.output)
    
    # Update vector store if requested
    if args.update_vectors:
        update_vector_store(drugs)
    
    # Print summary
    print("\n" + "="*60)
    print("Parsing Complete!")
    print("="*60)
    print(f"\nDrugs parsed: {len(drugs)}")
    print(f"Output directory: {args.output}")
    
    # Show some stats
    with_interactions = sum(1 for d in drugs.values() if d.drug_interactions)
    with_food = sum(1 for d in drugs.values() if d.food_interactions)
    print(f"\nDrugs with drug interactions: {with_interactions}")
    print(f"Drugs with food interactions: {with_food}")


if __name__ == "__main__":
    main()
