#!/usr/bin/env python
"""
Parse SIDER Data
Script to parse SIDER (Side Effect Resource) data files and create
a clean side effects database for the AdherenceGuardian system.
"""

import sys
import os
import csv
import json
import logging
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Target medications to focus on
TARGET_MEDICATIONS = {
    "metformin", "glipizide", "glyburide", "glimepiride", "sitagliptin", 
    "empagliflozin", "dapagliflozin", "canagliflozin", "liraglutide", 
    "semaglutide", "lisinopril", "enalapril", "ramipril", "losartan", 
    "valsartan", "olmesartan", "amlodipine", "nifedipine", "diltiazem", 
    "verapamil", "hydrochlorothiazide", "chlorthalidone", "furosemide", 
    "metoprolol", "atenolol", "carvedilol", "propranolol", "clonidine",
    "atorvastatin", "simvastatin", "rosuvastatin", "pravastatin",
    "aspirin", "clopidogrel", "warfarin", "apixaban", "rivaroxaban",
    "dabigatran", "sertraline", "fluoxetine", "paroxetine", "escitalopram", 
    "citalopram", "venlafaxine", "duloxetine", "bupropion", "mirtazapine", 
    "trazodone", "alprazolam", "lorazepam", "clonazepam", "diazepam",
    "lithium", "quetiapine", "aripiprazole", "olanzapine", "risperidone",
    "gabapentin", "pregabalin", "tramadol", "ibuprofen", "naproxen",
    "celecoxib", "acetaminophen", "meloxicam", "omeprazole", "pantoprazole", 
    "esomeprazole", "famotidine", "ranitidine", "ondansetron", "metoclopramide",
    "levothyroxine", "liothyronine", "methimazole", "albuterol", "fluticasone", 
    "budesonide", "montelukast", "tiotropium", "ipratropium", "theophylline",
    "prednisone", "methylprednisolone", "amoxicillin", "azithromycin",
    "ciprofloxacin", "metronidazole", "doxycycline", "cyclobenzaprine"
}


def load_drug_names(file_path: str) -> Dict[str, str]:
    """
    Load SIDER drug names mapping
    Format: CID\tname
    """
    drug_map = {}
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) >= 2:
                cid = row[0].strip()
                name = row[1].strip().lower()
                drug_map[cid] = name
    
    logger.info(f"Loaded {len(drug_map)} drug names from SIDER")
    return drug_map


def load_side_effects(file_path: str, drug_map: Dict[str, str]) -> Dict[str, List[Dict]]:
    """
    Load SIDER side effects
    Format: cid, umls_cui_from_label, method_of_detection, 
            umls_cui_from_meddra, meddra_type, umls_concept_name
    """
    side_effects = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) >= 6:
                cid = row[0].strip()
                drug_name = drug_map.get(cid, cid)
                
                # Only include target medications
                if drug_name.lower() not in TARGET_MEDICATIONS:
                    continue
                
                side_effect = {
                    'meddra_concept': row[4].strip(),
                    'side_effect': row[5].strip(),
                    'detection_method': row[2].strip() if len(row) > 2 else ''
                }
                
                # Avoid duplicates
                if side_effect not in side_effects[drug_name]:
                    side_effects[drug_name].append(side_effect)
    
    logger.info(f"Loaded side effects for {len(side_effects)} drugs")
    return dict(side_effects)


def load_side_effect_frequencies(file_path: str, drug_map: Dict[str, str]) -> Dict[str, List[Dict]]:
    """
    Load SIDER side effect frequencies
    Format: cid, umls_cui_from_label, placebo, freq, freq_lower, freq_upper, 
            umls_cui_from_meddra, meddra_type, meddra_concept
    """
    frequencies = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) >= 9:
                cid = row[0].strip()
                drug_name = drug_map.get(cid, cid)
                
                # Only include target medications
                if drug_name.lower() not in TARGET_MEDICATIONS:
                    continue
                
                freq_entry = {
                    'side_effect': row[8].strip(),
                    'frequency': row[3].strip(),
                    'frequency_lower': row[4].strip() if len(row) > 4 else '',
                    'frequency_upper': row[5].strip() if len(row) > 5 else '',
                    'placebo': row[2].strip() if len(row) > 2 else ''
                }
                
                frequencies[drug_name].append(freq_entry)
    
    logger.info(f"Loaded frequencies for {len(frequencies)} drugs")
    return dict(frequencies)


def load_indications(file_path: str, drug_map: Dict[str, str]) -> Dict[str, List[Dict]]:
    """
    Load SIDER drug indications
    Format: cid, umls_cui_from_label, method_of_detection, concept_name, 
            meddra_type, umls_cui_from_meddra, meddra_concept_name
    """
    indications = defaultdict(list)
    
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f, delimiter='\t')
        for row in reader:
            if len(row) >= 4:
                cid = row[0].strip()
                drug_name = drug_map.get(cid, cid)
                
                # Only include target medications
                if drug_name.lower() not in TARGET_MEDICATIONS:
                    continue
                
                indication = {
                    'concept_name': row[3].strip(),
                    'meddra_concept': row[6].strip() if len(row) > 6 else row[3].strip(),
                    'detection_method': row[2].strip() if len(row) > 2 else ''
                }
                
                # Avoid duplicates
                if indication not in indications[drug_name]:
                    indications[drug_name].append(indication)
    
    logger.info(f"Loaded indications for {len(indications)} drugs")
    return dict(indications)


def create_adherence_guidance(side_effects: Dict, frequencies: Dict, indications: Dict) -> Dict:
    """
    Create adherence guidance based on side effect data
    """
    guidance = {}
    
    for drug_name in set(list(side_effects.keys()) + list(indications.keys())):
        drug_se = side_effects.get(drug_name, [])
        drug_freq = frequencies.get(drug_name, [])
        drug_ind = indications.get(drug_name, [])
        
        # Get common side effects (those with frequency data)
        common_se = []
        for freq_entry in drug_freq:
            if freq_entry.get('frequency'):
                common_se.append({
                    'effect': freq_entry['side_effect'],
                    'frequency': freq_entry['frequency']
                })
        
        # Get unique side effects
        all_se = list(set(se['side_effect'] for se in drug_se))[:20]  # Limit to 20
        
        # Get indications
        all_ind = list(set(ind['concept_name'] for ind in drug_ind))[:10]  # Limit to 10
        
        guidance[drug_name] = {
            'side_effects': all_se,
            'common_side_effects': common_se[:10],  # Top 10 with frequencies
            'indications': all_ind,
            'adherence_tips': generate_adherence_tips(drug_name, all_se)
        }
    
    return guidance


def generate_adherence_tips(drug_name: str, side_effects: List[str]) -> List[str]:
    """Generate adherence tips based on common side effects"""
    tips = []
    
    # Check for GI side effects
    gi_terms = ['nausea', 'vomiting', 'diarrh', 'constipation', 'stomach', 'abdominal']
    if any(term in se.lower() for se in side_effects for term in gi_terms):
        tips.append(f"Take {drug_name} with food to minimize stomach upset")
    
    # Check for dizziness/drowsiness
    drowsy_terms = ['dizziness', 'drowsiness', 'somnolence', 'fatigue', 'sedation']
    if any(term in se.lower() for se in side_effects for term in drowsy_terms):
        tips.append(f"Take {drug_name} at bedtime if it causes drowsiness")
        tips.append("Avoid driving or operating machinery until you know how this medication affects you")
    
    # Check for headache
    if any('headache' in se.lower() for se in side_effects):
        tips.append("Stay well hydrated to help prevent headaches")
    
    # Check for dry mouth
    if any('dry mouth' in se.lower() or 'xerostomia' in se.lower() for se in side_effects):
        tips.append("Keep water handy and consider sugar-free gum for dry mouth")
    
    # Generic tips
    tips.extend([
        "Set a daily reminder to take your medication at the same time each day",
        "Do not stop taking this medication without consulting your healthcare provider",
        "Report any unusual or severe side effects to your doctor"
    ])
    
    return tips[:5]  # Return max 5 tips


def save_parsed_data(
    side_effects: Dict,
    frequencies: Dict,
    indications: Dict,
    guidance: Dict,
    output_dir: str
):
    """Save all parsed data to JSON files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Save side effects
    se_file = output_path / "side_effects.json"
    with open(se_file, 'w', encoding='utf-8') as f:
        json.dump(side_effects, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved side effects to {se_file}")
    
    # Save frequencies
    freq_file = output_path / "side_effect_frequencies.json"
    with open(freq_file, 'w', encoding='utf-8') as f:
        json.dump(frequencies, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved frequencies to {freq_file}")
    
    # Save indications
    ind_file = output_path / "indications.json"
    with open(ind_file, 'w', encoding='utf-8') as f:
        json.dump(indications, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved indications to {ind_file}")
    
    # Save adherence guidance
    guidance_file = output_path / "adherence_guidance.json"
    with open(guidance_file, 'w', encoding='utf-8') as f:
        json.dump(guidance, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved adherence guidance to {guidance_file}")


def main():
    print("\n" + "="*60)
    print("SIDER Side Effects Parser")
    print("="*60)
    
    sider_dir = Path("data/drugs/sider")
    output_dir = Path("data/drugs/sider/parsed")
    
    # Check if files exist
    drug_names_file = sider_dir / "drug_names.tsv"
    se_file = sider_dir / "meddra_all_se.tsv"
    freq_file = sider_dir / "meddra_freq.tsv"
    ind_file = sider_dir / "meddra_all_indications.tsv"
    
    if not drug_names_file.exists():
        logger.error(f"Drug names file not found: {drug_names_file}")
        logger.info("Downloading SIDER data...")
        # Download SIDER data
        import urllib.request
        
        sider_dir.mkdir(parents=True, exist_ok=True)
        
        base_url = "http://sideeffects.embl.de/media/download/"
        files_to_download = [
            ("drug_names.tsv", "drug_names.tsv"),
            ("meddra_all_se.tsv.gz", "meddra_all_se.tsv.gz"),
            ("meddra_freq.tsv.gz", "meddra_freq.tsv.gz"),
            ("meddra_all_indications.tsv.gz", "meddra_all_indications.tsv.gz"),
        ]
        
        for remote_file, local_file in files_to_download:
            local_path = sider_dir / local_file
            if not local_path.exists():
                logger.info(f"Downloading {remote_file}...")
                try:
                    urllib.request.urlretrieve(f"{base_url}{remote_file}", local_path)
                except Exception as e:
                    logger.error(f"Failed to download {remote_file}: {e}")
        
        # Decompress gzip files
        import gzip
        import shutil
        
        for gz_file in sider_dir.glob("*.gz"):
            out_file = sider_dir / gz_file.stem
            if not out_file.exists():
                logger.info(f"Decompressing {gz_file.name}...")
                with gzip.open(gz_file, 'rb') as f_in:
                    with open(out_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
    
    # Load drug names
    logger.info("Loading drug names...")
    drug_map = load_drug_names(drug_names_file)
    
    # Load side effects
    logger.info("Loading side effects...")
    side_effects = {}
    if se_file.exists():
        side_effects = load_side_effects(se_file, drug_map)
    
    # Load frequencies
    logger.info("Loading frequencies...")
    frequencies = {}
    if freq_file.exists():
        frequencies = load_side_effect_frequencies(freq_file, drug_map)
    
    # Load indications
    logger.info("Loading indications...")
    indications = {}
    if ind_file.exists():
        indications = load_indications(ind_file, drug_map)
    
    # Create adherence guidance
    logger.info("Creating adherence guidance...")
    guidance = create_adherence_guidance(side_effects, frequencies, indications)
    
    # Save parsed data
    logger.info("Saving parsed data...")
    save_parsed_data(side_effects, frequencies, indications, guidance, output_dir)
    
    # Print summary
    print("\n" + "="*60)
    print("Parsing Complete!")
    print("="*60)
    print(f"\nDrugs with side effects: {len(side_effects)}")
    print(f"Drugs with frequency data: {len(frequencies)}")
    print(f"Drugs with indications: {len(indications)}")
    print(f"Adherence guidance entries: {len(guidance)}")
    print(f"\nOutput directory: {output_dir}")


if __name__ == "__main__":
    main()
