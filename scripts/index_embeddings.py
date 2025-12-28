#!/usr/bin/env python
"""
Index Embeddings
Script to index clinical guidelines and drug information into the vector store
Uses parsed DrugBank and SIDER data for enhanced information
"""

import sys
import os
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from knowledge_base.vector_store import (
    VectorStore, 
    KnowledgeBaseStore, 
    Document,
    knowledge_base
)
from knowledge_base.clinical_guidelines import (
    CLINICAL_GUIDELINES,
    ADHERENCE_BARRIER_TIPS,
    ClinicalGuideline
)
from knowledge_base.drugbank_loader import drugbank_loader, COMMON_DRUGS
from knowledge_base.sider_loader import sider_loader, COMMON_DRUG_SIDE_EFFECTS


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_parsed_drugbank_data() -> Dict:
    """Load parsed DrugBank JSON data"""
    parsed_file = Path("data/drugs/drugbank/parsed/drugbank_parsed.json")
    if parsed_file.exists():
        with open(parsed_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_parsed_sider_data() -> tuple:
    """Load parsed SIDER JSON data"""
    parsed_dir = Path("data/drugs/sider/parsed")
    
    se_data = {}
    guidance_data = {}
    
    se_file = parsed_dir / "side_effects.json"
    guidance_file = parsed_dir / "adherence_guidance.json"
    
    if se_file.exists():
        with open(se_file, 'r', encoding='utf-8') as f:
            se_data = json.load(f)
    
    if guidance_file.exists():
        with open(guidance_file, 'r', encoding='utf-8') as f:
            guidance_data = json.load(f)
    
    return se_data, guidance_data


def index_clinical_guidelines(kb: KnowledgeBaseStore) -> int:
    """Index clinical guidelines into vector store"""
    logger.info("Indexing clinical guidelines...")
    count = 0
    
    for guideline in CLINICAL_GUIDELINES:
        # Index main guideline content
        kb.add_guideline(
            content=f"{guideline.title}\n\n{guideline.content}",
            condition=guideline.condition,
            source=guideline.source,
            year=guideline.year
        )
        count += 1
        
        # Index each recommendation separately for better retrieval
        for i, rec in enumerate(guideline.recommendations):
            kb.add_guideline(
                content=f"Recommendation for {guideline.condition}: {rec}",
                condition=guideline.condition,
                source=guideline.source,
                year=guideline.year
            )
            count += 1
    
    logger.info(f"Indexed {count} clinical guideline documents")
    return count


def index_adherence_tips(kb: KnowledgeBaseStore) -> int:
    """Index adherence tips into vector store"""
    logger.info("Indexing adherence tips...")
    count = 0
    
    for barrier_type, tips in ADHERENCE_BARRIER_TIPS.items():
        for tip in tips:
            kb.add_adherence_tip(
                content=f"For {barrier_type} barrier: {tip}",
                barrier_type=barrier_type,
                effectiveness_score=0.7
            )
            count += 1
    
    logger.info(f"Indexed {count} adherence tip documents")
    return count


def index_drug_information(kb: KnowledgeBaseStore) -> int:
    """Index drug information into vector store using parsed DrugBank data"""
    logger.info("Indexing drug information...")
    count = 0
    
    # First, try to use parsed DrugBank data
    parsed_drugs = load_parsed_drugbank_data()
    
    if parsed_drugs:
        logger.info(f"Using parsed DrugBank data ({len(parsed_drugs)} drugs)")
        
        for drug_name, drug_data in parsed_drugs.items():
            # Main drug information
            categories = drug_data.get('categories', ['Unknown'])
            drug_class = categories[0] if categories else 'Unknown'
            
            content = f"""
Drug: {drug_data.get('name', drug_name)}
DrugBank ID: {drug_data.get('drugbank_id', 'N/A')}
Class: {drug_class}
Description: {drug_data.get('description', 'No description available')[:500]}
Indication: {drug_data.get('indication', 'N/A')[:300]}
Mechanism: {drug_data.get('mechanism_of_action', 'N/A')[:300]}
Half-life: {drug_data.get('half_life', 'Not specified')}
"""
            kb.add_drug_info(
                content=content,
                drug_name=drug_data.get('name', drug_name),
                drug_class=drug_class
            )
            count += 1
            
            # Food interactions from DrugBank
            food_interactions = drug_data.get('food_interactions', [])
            if food_interactions:
                food_content = f"Food interactions for {drug_data.get('name', drug_name)}: " + "; ".join(food_interactions[:5])
                kb.add_drug_info(
                    content=food_content,
                    drug_name=drug_data.get('name', drug_name),
                    drug_class=drug_class
                )
                count += 1
            
            # Pharmacodynamics
            pharma = drug_data.get('pharmacodynamics')
            if pharma:
                kb.add_drug_info(
                    content=f"How {drug_data.get('name', drug_name)} works: {pharma[:500]}",
                    drug_name=drug_data.get('name', drug_name),
                    drug_class=drug_class
                )
                count += 1
    else:
        # Fallback to built-in data
        logger.info("Using built-in drug data")
        
        for drug_name, drug_info in COMMON_DRUGS.items():
            content = f"""
Drug: {drug_info.name}
Class: {drug_info.drug_class}
Description: {drug_info.description}
Indication: {drug_info.indication}
Mechanism: {drug_info.mechanism_of_action}
Half-life: {drug_info.half_life or 'Not specified'}
Route: {drug_info.route_of_administration or 'Not specified'}
"""
            kb.add_drug_info(
                content=content,
                drug_name=drug_info.name,
                drug_class=drug_info.drug_class
            )
            count += 1
            
            if drug_info.food_interactions:
                food_content = f"Food interactions for {drug_info.name}: " + "; ".join(drug_info.food_interactions)
                kb.add_drug_info(
                    content=food_content,
                    drug_name=drug_info.name,
                    drug_class=drug_info.drug_class
                )
                count += 1
            
            if drug_info.pharmacodynamics:
                kb.add_drug_info(
                    content=f"How {drug_info.name} works: {drug_info.pharmacodynamics}",
                    drug_name=drug_info.name,
                    drug_class=drug_info.drug_class
                )
                count += 1
    
    logger.info(f"Indexed {count} drug information documents")
    return count


def index_side_effects(kb: KnowledgeBaseStore) -> int:
    """Index side effect information using parsed SIDER data"""
    logger.info("Indexing side effects...")
    count = 0
    
    # Try to use parsed SIDER data
    se_data, guidance_data = load_parsed_sider_data()
    
    if se_data:
        logger.info(f"Using parsed SIDER data ({len(se_data)} drugs)")
        
        for drug_name, effects in se_data.items():
            # Get unique side effects
            unique_effects = list(set(e.get('side_effect', '') for e in effects if e.get('side_effect')))[:20]
            
            if unique_effects:
                content = f"Side effects of {drug_name.title()}: {', '.join(unique_effects[:10])}"
                kb.add_side_effect_info(
                    content=content,
                    drug_name=drug_name.title(),
                    side_effect=", ".join(unique_effects[:10]),
                    frequency="varies"
                )
                count += 1
            
            # Add adherence guidance if available
            drug_guidance = guidance_data.get(drug_name, {})
            tips = drug_guidance.get('adherence_tips', [])
            if tips:
                tips_content = f"Adherence tips for {drug_name.title()}: " + "; ".join(tips[:3])
                kb.add_adherence_tip(
                    content=tips_content,
                    barrier_type="side_effects",
                    effectiveness_score=0.8
                )
                count += 1
    else:
        # Fallback to built-in data
        logger.info("Using built-in side effect data")
        
        for drug_name, side_effects in COMMON_DRUG_SIDE_EFFECTS.items():
            by_frequency: Dict[str, List[str]] = {}
            for se in side_effects:
                freq = se.frequency
                if freq not in by_frequency:
                    by_frequency[freq] = []
                by_frequency[freq].append(se.side_effect_name)
            
            for frequency, effects in by_frequency.items():
                content = f"{frequency.capitalize()} side effects of {drug_name.title()}: {', '.join(effects)}"
                kb.add_side_effect_info(
                    content=content,
                    drug_name=drug_name.title(),
                    side_effect=", ".join(effects),
                    frequency=frequency
                )
                count += 1
            
            for se in side_effects:
                if se.severity_estimate in ["severe", "moderate"]:
                    content = f"{se.side_effect_name} is a {se.frequency} side effect of {drug_name.title()}. Severity: {se.severity_estimate}."
                    kb.add_side_effect_info(
                        content=content,
                        drug_name=drug_name.title(),
                        side_effect=se.side_effect_name,
                        frequency=se.frequency
                    )
                    count += 1
    
    logger.info(f"Indexed {count} side effect documents")
    return count


def index_medication_timing_guidance() -> int:
    """Index medication timing and administration guidance"""
    logger.info("Indexing medication timing guidance...")
    
    timing_guidance = [
        # General timing
        {
            "content": "Taking medications at the same time each day helps maintain consistent drug levels in your body and makes it easier to remember.",
            "type": "general",
            "topic": "timing"
        },
        {
            "content": "Morning medications are best taken after waking, ideally with breakfast unless the medication requires an empty stomach.",
            "type": "general",
            "topic": "morning"
        },
        {
            "content": "Evening medications should be taken at a consistent time, often with dinner or before bed depending on the medication.",
            "type": "general",
            "topic": "evening"
        },
        
        # Specific drug timing
        {
            "content": "Levothyroxine should be taken on an empty stomach, 30-60 minutes before breakfast. Consistency in timing is crucial for thyroid medications.",
            "type": "specific",
            "topic": "levothyroxine"
        },
        {
            "content": "Statins like simvastatin are more effective when taken in the evening because cholesterol production peaks at night.",
            "type": "specific",
            "topic": "statins"
        },
        {
            "content": "Metformin should be taken with meals to reduce gastrointestinal side effects like nausea and diarrhea.",
            "type": "specific",
            "topic": "metformin"
        },
        {
            "content": "Diuretics (water pills) should be taken in the morning to avoid nighttime urination that disrupts sleep.",
            "type": "specific",
            "topic": "diuretics"
        },
        {
            "content": "Proton pump inhibitors like omeprazole work best when taken 30-60 minutes before the first meal of the day.",
            "type": "specific",
            "topic": "ppi"
        },
        {
            "content": "Blood pressure medications are often taken in the morning, but some may be prescribed for evening to control nighttime blood pressure.",
            "type": "specific",
            "topic": "blood_pressure"
        },
        
        # Missed dose guidance
        {
            "content": "If you miss a dose, take it as soon as you remember unless it's close to your next scheduled dose. Never double up on doses.",
            "type": "missed_dose",
            "topic": "general"
        },
        {
            "content": "For once-daily medications, if you remember within 12 hours of the missed dose, take it. If more than 12 hours have passed, skip to the next scheduled dose.",
            "type": "missed_dose",
            "topic": "once_daily"
        },
        {
            "content": "For twice-daily medications, if you remember within 4-6 hours of the missed dose, take it. Otherwise, wait for the next scheduled dose.",
            "type": "missed_dose",
            "topic": "twice_daily"
        },
        
        # Food interactions
        {
            "content": "Some medications work better on an empty stomach because food can interfere with absorption. Check with your pharmacist if unsure.",
            "type": "food",
            "topic": "empty_stomach"
        },
        {
            "content": "Calcium, iron supplements, and antacids can interfere with many medications. Separate them by at least 2-4 hours.",
            "type": "food",
            "topic": "interactions"
        },
        {
            "content": "Grapefruit and grapefruit juice can interact with many medications including statins, calcium channel blockers, and some psychiatric medications.",
            "type": "food",
            "topic": "grapefruit"
        },
        {
            "content": "Warfarin (blood thinner) requires consistent vitamin K intake. Don't drastically change your consumption of green leafy vegetables.",
            "type": "food",
            "topic": "warfarin"
        }
    ]
    
    count = 0
    for guidance in timing_guidance:
        knowledge_base.add_guideline(
            content=guidance["content"],
            condition="medication_management",
            source="Clinical Best Practices",
            year=2024
        )
        count += 1
    
    logger.info(f"Indexed {count} timing guidance documents")
    return count


def index_adherence_strategies() -> int:
    """Index adherence strategy content"""
    logger.info("Indexing adherence strategies...")
    
    strategies = [
        # Reminder strategies
        {
            "content": "Use smartphone apps with medication reminders. Many apps allow you to set multiple reminders and track your adherence over time.",
            "barrier": "forgetfulness",
            "effectiveness": 0.8
        },
        {
            "content": "Place your medications where you'll see them during your routine - next to your toothbrush, coffee maker, or on the breakfast table.",
            "barrier": "forgetfulness",
            "effectiveness": 0.7
        },
        {
            "content": "Use a weekly pill organizer with compartments for each day and time. This helps you see at a glance if you've taken your medications.",
            "barrier": "forgetfulness",
            "effectiveness": 0.85
        },
        {
            "content": "Link taking your medication to an existing habit like brushing teeth, eating breakfast, or your morning coffee.",
            "barrier": "forgetfulness",
            "effectiveness": 0.75
        },
        
        # Cost strategies
        {
            "content": "Ask your doctor about generic medications. Generics contain the same active ingredients and are FDA-approved but cost significantly less.",
            "barrier": "cost",
            "effectiveness": 0.9
        },
        {
            "content": "Check pharmaceutical manufacturer websites for patient assistance programs. Many offer free or reduced-cost medications for qualifying patients.",
            "barrier": "cost",
            "effectiveness": 0.8
        },
        {
            "content": "Use prescription discount programs like GoodRx, RxSaver, or your pharmacy's discount program to compare prices and find savings.",
            "barrier": "cost",
            "effectiveness": 0.75
        },
        {
            "content": "Ask about 90-day supplies instead of 30-day. Many pharmacies and insurance plans offer lower per-pill costs for larger quantities.",
            "barrier": "cost",
            "effectiveness": 0.7
        },
        
        # Side effect strategies
        {
            "content": "If a medication causes stomach upset, try taking it with food or a small snack unless instructed otherwise.",
            "barrier": "side_effects",
            "effectiveness": 0.7
        },
        {
            "content": "Don't stop your medication due to side effects without talking to your doctor. Many side effects can be managed or may improve over time.",
            "barrier": "side_effects",
            "effectiveness": 0.8
        },
        {
            "content": "Keep a symptom diary to track when side effects occur. This information helps your doctor adjust your treatment if needed.",
            "barrier": "side_effects",
            "effectiveness": 0.75
        },
        {
            "content": "If drowsiness is a side effect, ask your doctor about taking the medication at bedtime instead of during the day.",
            "barrier": "side_effects",
            "effectiveness": 0.8
        },
        
        # Complexity strategies
        {
            "content": "Ask your doctor about combination pills that include multiple medications in one tablet to reduce your pill burden.",
            "barrier": "complexity",
            "effectiveness": 0.85
        },
        {
            "content": "Create a medication chart listing each medication, dose, and time. Keep it visible in your home.",
            "barrier": "complexity",
            "effectiveness": 0.7
        },
        {
            "content": "Use a medication synchronization program at your pharmacy to align all your refills to the same day each month.",
            "barrier": "complexity",
            "effectiveness": 0.75
        },
        
        # Motivation strategies
        {
            "content": "Focus on how your medications help you do the things you love - spending time with family, enjoying hobbies, staying independent.",
            "barrier": "motivation",
            "effectiveness": 0.7
        },
        {
            "content": "Track your health improvements. Seeing lower blood pressure or better blood sugar readings can motivate continued adherence.",
            "barrier": "motivation",
            "effectiveness": 0.75
        },
        {
            "content": "Share your medication goals with a family member or friend who can provide encouragement and accountability.",
            "barrier": "motivation",
            "effectiveness": 0.7
        }
    ]
    
    count = 0
    for strategy in strategies:
        knowledge_base.add_adherence_tip(
            content=strategy["content"],
            barrier_type=strategy["barrier"],
            effectiveness_score=strategy["effectiveness"]
        )
        count += 1
    
    logger.info(f"Indexed {count} adherence strategy documents")
    return count


def clear_vector_store():
    """Clear all data from vector stores"""
    logger.info("Clearing vector stores...")
    
    knowledge_base.guidelines_store.clear()
    knowledge_base.drug_store.clear()
    knowledge_base.tips_store.clear()
    knowledge_base.side_effects_store.clear()
    
    logger.info("Vector stores cleared")


def run_indexing(clear_first: bool = False, verbose: bool = False):
    """Run the full indexing process"""
    
    print("\n" + "="*60)
    print("Vector Store Indexing")
    print("="*60)
    
    if clear_first:
        clear_vector_store()
    
    total_count = 0
    
    # Index all content types
    total_count += index_clinical_guidelines(knowledge_base)
    total_count += index_adherence_tips(knowledge_base)
    total_count += index_drug_information(knowledge_base)
    total_count += index_side_effects(knowledge_base)
    total_count += index_medication_timing_guidance()
    total_count += index_adherence_strategies()
    
    print("\n" + "="*60)
    print("Indexing Complete!")
    print("="*60)
    print(f"Total documents indexed: {total_count}")
    
    # Print store statistics
    print("\nVector Store Statistics:")
    print(f"  Clinical Guidelines: {knowledge_base.guidelines_store.count()}")
    print(f"  Drug Information: {knowledge_base.drug_store.count()}")
    print(f"  Adherence Tips: {knowledge_base.tips_store.count()}")
    print(f"  Side Effects: {knowledge_base.side_effects_store.count()}")
    
    if verbose:
        # Test a search
        print("\nTest Search: 'diabetes medication timing'")
        results = knowledge_base.search_guidelines("diabetes medication timing", n_results=3)
        for i, result in enumerate(results):
            print(f"  {i+1}. Score: {result.score:.3f}")
            print(f"     {result.document.content[:100]}...")
    
    return total_count


def main():
    parser = argparse.ArgumentParser(
        description="Index clinical knowledge into vector store for RAG"
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing vector store data before indexing"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show verbose output including test searches"
    )
    
    args = parser.parse_args()
    
    run_indexing(clear_first=args.clear, verbose=args.verbose)


if __name__ == "__main__":
    main()
