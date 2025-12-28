"""
DrugBank Data Loader
Loader for DrugBank drug database information
"""

import logging
import os
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class DrugInfo:
    """Drug information from DrugBank"""
    drugbank_id: str
    name: str
    description: str
    indication: str
    pharmacodynamics: str
    mechanism_of_action: str
    drug_class: str
    categories: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    food_interactions: List[str] = field(default_factory=list)
    half_life: Optional[str] = None
    route_of_administration: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drugbank_id": self.drugbank_id,
            "name": self.name,
            "description": self.description,
            "indication": self.indication,
            "pharmacodynamics": self.pharmacodynamics,
            "mechanism_of_action": self.mechanism_of_action,
            "drug_class": self.drug_class,
            "categories": self.categories,
            "synonyms": self.synonyms,
            "food_interactions": self.food_interactions,
            "half_life": self.half_life,
            "route_of_administration": self.route_of_administration
        }


@dataclass
class DrugInteraction:
    """Drug-drug interaction from DrugBank"""
    drug1_id: str
    drug1_name: str
    drug2_id: str
    drug2_name: str
    description: str
    severity: str = "moderate"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "drug1_id": self.drug1_id,
            "drug1_name": self.drug1_name,
            "drug2_id": self.drug2_id,
            "drug2_name": self.drug2_name,
            "description": self.description,
            "severity": self.severity
        }


# Built-in common drug data (fallback when API unavailable)
COMMON_DRUGS: Dict[str, DrugInfo] = {
    "metformin": DrugInfo(
        drugbank_id="DB00331",
        name="Metformin",
        description="Metformin is a biguanide antidiabetic agent used for managing type 2 diabetes mellitus.",
        indication="Type 2 diabetes mellitus, Polycystic ovary syndrome (off-label)",
        pharmacodynamics="Metformin decreases hepatic glucose production, decreases intestinal absorption of glucose, and improves insulin sensitivity by increasing peripheral glucose uptake and utilization.",
        mechanism_of_action="Metformin activates AMP-activated protein kinase (AMPK), reducing hepatic gluconeogenesis and lipogenesis while increasing insulin-mediated glucose uptake in skeletal muscle.",
        drug_class="Biguanide antidiabetic",
        categories=["Antidiabetic Agents", "Biguanides", "Hypoglycemic Agents"],
        synonyms=["Glucophage", "Fortamet", "Glumetza", "Riomet"],
        food_interactions=[
            "Take with meals to reduce GI side effects",
            "Avoid excessive alcohol consumption (risk of lactic acidosis)",
            "High-fiber meals may reduce absorption"
        ],
        half_life="4-8.7 hours",
        route_of_administration="Oral"
    ),
    
    "lisinopril": DrugInfo(
        drugbank_id="DB00722",
        name="Lisinopril",
        description="Lisinopril is an ACE inhibitor used to treat hypertension, heart failure, and improve survival after heart attack.",
        indication="Hypertension, Heart failure, Post-myocardial infarction, Diabetic nephropathy",
        pharmacodynamics="Lisinopril inhibits ACE, preventing conversion of angiotensin I to angiotensin II, resulting in decreased vasoconstriction and aldosterone secretion.",
        mechanism_of_action="Competitive inhibition of angiotensin-converting enzyme (ACE), preventing the formation of vasoconstrictor angiotensin II.",
        drug_class="ACE Inhibitor",
        categories=["Antihypertensive Agents", "ACE Inhibitors", "Cardiovascular Agents"],
        synonyms=["Zestril", "Prinivil", "Qbrelis"],
        food_interactions=[
            "Can be taken with or without food",
            "Avoid potassium-rich foods and salt substitutes",
            "Avoid alcohol (enhances hypotensive effect)"
        ],
        half_life="12 hours",
        route_of_administration="Oral"
    ),
    
    "atorvastatin": DrugInfo(
        drugbank_id="DB01076",
        name="Atorvastatin",
        description="Atorvastatin is a statin medication used to prevent cardiovascular disease and treat abnormal lipid levels.",
        indication="Hyperlipidemia, Prevention of cardiovascular disease, Reduction of cardiovascular risk",
        pharmacodynamics="Atorvastatin reduces LDL cholesterol, total cholesterol, triglycerides, and apolipoprotein B while increasing HDL cholesterol.",
        mechanism_of_action="Selectively inhibits HMG-CoA reductase, the rate-limiting enzyme in cholesterol biosynthesis, leading to upregulation of LDL receptors and increased LDL clearance.",
        drug_class="HMG-CoA Reductase Inhibitor (Statin)",
        categories=["Anticholesteremic Agents", "Statins", "Lipid-lowering Agents"],
        synonyms=["Lipitor", "Torvast"],
        food_interactions=[
            "Can be taken with or without food",
            "Avoid grapefruit juice (increases drug levels)",
            "Avoid excessive alcohol consumption"
        ],
        half_life="14 hours",
        route_of_administration="Oral"
    ),
    
    "amlodipine": DrugInfo(
        drugbank_id="DB00381",
        name="Amlodipine",
        description="Amlodipine is a calcium channel blocker used to treat hypertension and coronary artery disease.",
        indication="Hypertension, Chronic stable angina, Vasospastic angina, Coronary artery disease",
        pharmacodynamics="Amlodipine inhibits calcium influx into vascular smooth muscle and cardiac muscle, causing vasodilation and reduced blood pressure.",
        mechanism_of_action="Blocks L-type calcium channels in vascular smooth muscle, causing relaxation and vasodilation, leading to reduced peripheral resistance.",
        drug_class="Calcium Channel Blocker",
        categories=["Antihypertensive Agents", "Calcium Channel Blockers", "Antianginal Agents"],
        synonyms=["Norvasc", "Amvaz"],
        food_interactions=[
            "Can be taken with or without food",
            "Grapefruit may increase drug levels",
            "Avoid excessive alcohol"
        ],
        half_life="30-50 hours",
        route_of_administration="Oral"
    ),
    
    "omeprazole": DrugInfo(
        drugbank_id="DB00338",
        name="Omeprazole",
        description="Omeprazole is a proton pump inhibitor used to treat GERD, peptic ulcers, and Zollinger-Ellison syndrome.",
        indication="GERD, Peptic ulcer disease, H. pylori eradication, Zollinger-Ellison syndrome",
        pharmacodynamics="Omeprazole suppresses gastric acid secretion by inhibiting the H+/K+-ATPase enzyme system at the secretory surface of gastric parietal cells.",
        mechanism_of_action="Irreversible inhibition of the gastric proton pump (H+/K+-ATPase), blocking the final step of acid production in parietal cells.",
        drug_class="Proton Pump Inhibitor",
        categories=["Anti-Ulcer Agents", "Proton Pump Inhibitors", "Gastrointestinal Agents"],
        synonyms=["Prilosec", "Losec", "Omesec"],
        food_interactions=[
            "Take before meals (30-60 minutes before eating)",
            "Avoid alcohol",
            "May affect absorption of vitamin B12 with long-term use"
        ],
        half_life="0.5-1 hour",
        route_of_administration="Oral"
    ),
    
    "sertraline": DrugInfo(
        drugbank_id="DB01104",
        name="Sertraline",
        description="Sertraline is an SSRI antidepressant used to treat depression, anxiety disorders, OCD, PTSD, and premenstrual dysphoric disorder.",
        indication="Major depressive disorder, Panic disorder, OCD, PTSD, Social anxiety disorder, PMDD",
        pharmacodynamics="Sertraline enhances serotonergic neurotransmission by inhibiting serotonin reuptake, leading to increased serotonin levels in the synaptic cleft.",
        mechanism_of_action="Potent and selective inhibition of the serotonin reuptake transporter (SERT), preventing reuptake of serotonin into presynaptic neurons.",
        drug_class="Selective Serotonin Reuptake Inhibitor (SSRI)",
        categories=["Antidepressive Agents", "SSRIs", "Anti-Anxiety Agents"],
        synonyms=["Zoloft", "Lustral"],
        food_interactions=[
            "Can be taken with or without food",
            "Avoid alcohol",
            "Avoid grapefruit juice"
        ],
        half_life="26 hours",
        route_of_administration="Oral"
    ),
    
    "levothyroxine": DrugInfo(
        drugbank_id="DB00451",
        name="Levothyroxine",
        description="Levothyroxine is a synthetic thyroid hormone used to treat hypothyroidism and thyroid cancer.",
        indication="Hypothyroidism, Myxedema coma, TSH suppression in thyroid cancer",
        pharmacodynamics="Levothyroxine increases metabolic rate, protein synthesis, and sensitivity to catecholamines. It promotes growth and development in children.",
        mechanism_of_action="Synthetic T4 is converted to T3 in peripheral tissues. T3 binds to thyroid receptors in the nucleus, regulating gene expression for metabolism.",
        drug_class="Thyroid Hormone",
        categories=["Thyroid Agents", "Hormones"],
        synonyms=["Synthroid", "Levoxyl", "Tirosint", "Unithroid"],
        food_interactions=[
            "Take on empty stomach, 30-60 minutes before breakfast",
            "Separate from calcium, iron, and antacids by 4 hours",
            "Coffee can decrease absorption",
            "Soy products may decrease absorption",
            "High-fiber foods may decrease absorption"
        ],
        half_life="6-7 days",
        route_of_administration="Oral"
    ),
    
    "gabapentin": DrugInfo(
        drugbank_id="DB00996",
        name="Gabapentin",
        description="Gabapentin is an anticonvulsant and analgesic used for epilepsy, neuropathic pain, and restless legs syndrome.",
        indication="Epilepsy (partial seizures), Postherpetic neuralgia, Neuropathic pain, Restless legs syndrome",
        pharmacodynamics="Gabapentin modulates neurotransmitter release and neuronal excitability by binding to voltage-gated calcium channels.",
        mechanism_of_action="Binds to the alpha-2-delta subunit of voltage-gated calcium channels, reducing calcium influx and excitatory neurotransmitter release.",
        drug_class="Anticonvulsant/Analgesic",
        categories=["Anticonvulsants", "Analgesics", "Neuropathic Pain Agents"],
        synonyms=["Neurontin", "Gralise", "Horizant"],
        food_interactions=[
            "Can be taken with or without food",
            "Antacids may reduce absorption - separate by 2 hours",
            "Avoid alcohol"
        ],
        half_life="5-7 hours",
        route_of_administration="Oral"
    ),
    
    "warfarin": DrugInfo(
        drugbank_id="DB00682",
        name="Warfarin",
        description="Warfarin is an anticoagulant used to prevent and treat thromboembolic disorders.",
        indication="Venous thromboembolism, Atrial fibrillation, Mechanical heart valves, Stroke prevention",
        pharmacodynamics="Warfarin reduces blood clot formation by inhibiting vitamin K-dependent synthesis of clotting factors II, VII, IX, and X.",
        mechanism_of_action="Inhibits vitamin K epoxide reductase (VKORC1), preventing regeneration of active vitamin K needed for synthesis of functional clotting factors.",
        drug_class="Vitamin K Antagonist Anticoagulant",
        categories=["Anticoagulants", "Vitamin K Antagonists"],
        synonyms=["Coumadin", "Jantoven"],
        food_interactions=[
            "Maintain consistent vitamin K intake",
            "Avoid drastic changes in green leafy vegetable consumption",
            "Avoid alcohol",
            "Cranberry juice may increase anticoagulant effect",
            "Many drug interactions - always check before adding medications"
        ],
        half_life="20-60 hours",
        route_of_administration="Oral"
    ),
    
    "metoprolol": DrugInfo(
        drugbank_id="DB00264",
        name="Metoprolol",
        description="Metoprolol is a beta-blocker used to treat hypertension, angina, heart failure, and arrhythmias.",
        indication="Hypertension, Angina pectoris, Heart failure, Arrhythmias, Post-MI cardioprotection",
        pharmacodynamics="Metoprolol reduces heart rate, myocardial contractility, and blood pressure by blocking beta-1 adrenergic receptors in the heart.",
        mechanism_of_action="Selective beta-1 adrenergic receptor antagonist, reducing the effects of catecholamines on the heart.",
        drug_class="Beta-1 Selective Blocker",
        categories=["Antihypertensive Agents", "Beta-Blockers", "Antianginal Agents"],
        synonyms=["Lopressor", "Toprol-XL", "Metoprolol Succinate", "Metoprolol Tartrate"],
        food_interactions=[
            "Take with food (tartrate) for better absorption",
            "Succinate extended-release can be taken with or without food",
            "Avoid alcohol"
        ],
        half_life="3-7 hours",
        route_of_administration="Oral"
    )
}

# Common drug-drug interactions
DRUG_INTERACTIONS: List[DrugInteraction] = [
    DrugInteraction(
        drug1_id="DB00682",
        drug1_name="Warfarin",
        drug2_id="DB00945",
        drug2_name="Aspirin",
        description="Increased risk of bleeding. Aspirin inhibits platelet aggregation while warfarin inhibits clotting factors. Monitor closely if combination is necessary.",
        severity="major"
    ),
    DrugInteraction(
        drug1_id="DB00331",
        drug1_name="Metformin",
        drug2_id="DB00091",
        drug2_name="Contrast Media (Iodinated)",
        description="Risk of lactic acidosis. Hold metformin before and 48 hours after iodinated contrast procedures in patients with renal impairment.",
        severity="major"
    ),
    DrugInteraction(
        drug1_id="DB00722",
        drug1_name="Lisinopril",
        drug2_id="DB00421",
        drug2_name="Spironolactone",
        description="Increased risk of hyperkalemia. Both drugs can raise potassium levels. Monitor potassium closely.",
        severity="moderate"
    ),
    DrugInteraction(
        drug1_id="DB01104",
        drug1_name="Sertraline",
        drug2_id="DB01247",
        drug2_name="Tramadol",
        description="Risk of serotonin syndrome. Both drugs increase serotonin levels. Monitor for symptoms: agitation, tremor, hyperthermia.",
        severity="major"
    ),
    DrugInteraction(
        drug1_id="DB01076",
        drug1_name="Atorvastatin",
        drug2_id="DB01167",
        drug2_name="Itraconazole",
        description="Increased statin levels and risk of myopathy/rhabdomyolysis. CYP3A4 inhibition by itraconazole increases atorvastatin exposure.",
        severity="major"
    ),
    DrugInteraction(
        drug1_id="DB00338",
        drug1_name="Omeprazole",
        drug2_id="DB00758",
        drug2_name="Clopidogrel",
        description="Reduced antiplatelet effect. Omeprazole inhibits CYP2C19, reducing clopidogrel activation. Consider alternative PPI like pantoprazole.",
        severity="major"
    ),
    DrugInteraction(
        drug1_id="DB00451",
        drug1_name="Levothyroxine",
        drug2_id="DB00258",
        drug2_name="Calcium Carbonate",
        description="Reduced levothyroxine absorption. Calcium binds levothyroxine in the GI tract. Separate administration by at least 4 hours.",
        severity="moderate"
    ),
    DrugInteraction(
        drug1_id="DB00381",
        drug1_name="Amlodipine",
        drug2_id="DB01183",
        drug2_name="Simvastatin",
        description="Increased simvastatin levels. Amlodipine inhibits CYP3A4. Limit simvastatin dose to 20mg daily when combined.",
        severity="moderate"
    ),
    DrugInteraction(
        drug1_id="DB00264",
        drug1_name="Metoprolol",
        drug2_id="DB00604",
        drug2_name="Fluoxetine",
        description="Increased metoprolol levels. Fluoxetine inhibits CYP2D6, which metabolizes metoprolol. Monitor for bradycardia and hypotension.",
        severity="moderate"
    ),
    DrugInteraction(
        drug1_id="DB00996",
        drug1_name="Gabapentin",
        drug2_id="DB00252",
        drug2_name="Morphine",
        description="Increased CNS depression. Risk of respiratory depression is increased. Use lower gabapentin doses when combined with opioids.",
        severity="moderate"
    )
]


class DrugBankLoader:
    """
    Loader for DrugBank drug database
    
    Can use:
    1. DrugBank API (if API key available)
    2. Local cached data
    3. Built-in common drug data as fallback
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Optional[str] = None,
        parsed_data_dir: Optional[str] = None
    ):
        self.api_key = api_key or settings.DRUGBANK_API_KEY
        self.cache_dir = cache_dir or "./data/drugbank_cache"
        self.parsed_data_dir = parsed_data_dir or "./data/drugs/drugbank/parsed"
        self._drugs_cache: Dict[str, DrugInfo] = {}
        self._interactions_cache: List[DrugInteraction] = []
        
        # Load built-in data first
        self._load_builtin_data()
        
        # Then try to load parsed DrugBank data
        self._load_parsed_drugbank_data()
    
    def _load_builtin_data(self):
        """Load built-in drug data"""
        self._drugs_cache = COMMON_DRUGS.copy()
        self._interactions_cache = DRUG_INTERACTIONS.copy()
        logger.info(f"Loaded {len(self._drugs_cache)} built-in drugs")
    
    def _load_parsed_drugbank_data(self):
        """Load parsed DrugBank data from JSON files"""
        parsed_dir = Path(self.parsed_data_dir)
        
        # Load main drug data
        drugs_file = parsed_dir / "drugbank_parsed.json"
        if drugs_file.exists():
            try:
                with open(drugs_file, 'r', encoding='utf-8') as f:
                    drugs_data = json.load(f)
                
                count = 0
                for name, data in drugs_data.items():
                    # Convert parsed data to DrugInfo format
                    drug_info = DrugInfo(
                        drugbank_id=data.get('drugbank_id', ''),
                        name=data.get('name', name),
                        description=data.get('description', ''),
                        indication=data.get('indication', ''),
                        pharmacodynamics=data.get('pharmacodynamics', ''),
                        mechanism_of_action=data.get('mechanism_of_action', ''),
                        drug_class=data.get('categories', ['Unknown'])[0] if data.get('categories') else 'Unknown',
                        categories=data.get('categories', []),
                        synonyms=data.get('synonyms', []),
                        food_interactions=data.get('food_interactions', []),
                        half_life=data.get('half_life'),
                        route_of_administration=None
                    )
                    self._drugs_cache[name.lower()] = drug_info
                    count += 1
                
                logger.info(f"Loaded {count} drugs from parsed DrugBank data")
            except Exception as e:
                logger.warning(f"Failed to load parsed DrugBank data: {e}")
        
        # Load drug interactions
        interactions_file = parsed_dir / "drug_interactions.json"
        if interactions_file.exists():
            try:
                with open(interactions_file, 'r', encoding='utf-8') as f:
                    interactions_data = json.load(f)
                
                count = 0
                for drug_name, interactions in interactions_data.items():
                    drug = self._drugs_cache.get(drug_name.lower())
                    if not drug:
                        continue
                    
                    for interaction in interactions:
                        interaction_obj = DrugInteraction(
                            drug1_id=drug.drugbank_id,
                            drug1_name=drug.name,
                            drug2_id=interaction.get('drugbank_id', ''),
                            drug2_name=interaction.get('name', ''),
                            description=interaction.get('description', ''),
                            severity=self._infer_severity(interaction.get('description', ''))
                        )
                        self._interactions_cache.append(interaction_obj)
                        count += 1
                
                logger.info(f"Loaded {count} drug interactions from parsed DrugBank data")
            except Exception as e:
                logger.warning(f"Failed to load parsed drug interactions: {e}")
        
        # Load food interactions
        food_file = parsed_dir / "food_interactions.json"
        if food_file.exists():
            try:
                with open(food_file, 'r', encoding='utf-8') as f:
                    food_data = json.load(f)
                
                count = 0
                for drug_name, food_interactions in food_data.items():
                    drug = self._drugs_cache.get(drug_name.lower())
                    if drug and food_interactions:
                        drug.food_interactions = food_interactions
                        count += 1
                
                logger.info(f"Updated food interactions for {count} drugs")
            except Exception as e:
                logger.warning(f"Failed to load food interactions: {e}")
    
    def _infer_severity(self, description: str) -> str:
        """Infer interaction severity from description text"""
        desc_lower = description.lower()
        
        # Keywords indicating severe interactions
        if any(word in desc_lower for word in [
            'life-threatening', 'fatal', 'death', 'contraindicated',
            'avoid', 'do not use', 'serious', 'severe'
        ]):
            return 'severe'
        
        # Keywords indicating major interactions
        if any(word in desc_lower for word in [
            'significantly', 'major', 'substantial', 'marked',
            'dangerous', 'monitoring required'
        ]):
            return 'major'
        
        # Keywords indicating minor interactions
        if any(word in desc_lower for word in [
            'minor', 'slight', 'minimal', 'small'
        ]):
            return 'minor'
        
        return 'moderate'
    
    def _ensure_cache_dir(self):
        """Ensure cache directory exists"""
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)
    
    def load_from_cache(self) -> bool:
        """Load drug data from local cache"""
        self._ensure_cache_dir()
        
        drugs_file = Path(self.cache_dir) / "drugs.json"
        interactions_file = Path(self.cache_dir) / "interactions.json"
        
        try:
            if drugs_file.exists():
                with open(drugs_file, 'r') as f:
                    drugs_data = json.load(f)
                    for key, data in drugs_data.items():
                        self._drugs_cache[key] = DrugInfo(**data)
                    logger.info(f"Loaded {len(drugs_data)} drugs from cache")
            
            if interactions_file.exists():
                with open(interactions_file, 'r') as f:
                    interactions_data = json.load(f)
                    for data in interactions_data:
                        self._interactions_cache.append(DrugInteraction(**data))
                    logger.info(f"Loaded {len(interactions_data)} interactions from cache")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to load from cache: {e}")
            return False
    
    def save_to_cache(self):
        """Save drug data to local cache"""
        self._ensure_cache_dir()
        
        drugs_file = Path(self.cache_dir) / "drugs.json"
        interactions_file = Path(self.cache_dir) / "interactions.json"
        
        try:
            # Save drugs
            drugs_data = {
                key: drug.to_dict()
                for key, drug in self._drugs_cache.items()
            }
            with open(drugs_file, 'w') as f:
                json.dump(drugs_data, f, indent=2)
            
            # Save interactions
            interactions_data = [
                interaction.to_dict()
                for interaction in self._interactions_cache
            ]
            with open(interactions_file, 'w') as f:
                json.dump(interactions_data, f, indent=2)
            
            logger.info("Saved drug data to cache")
            
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")
    
    def get_drug(self, name: str) -> Optional[DrugInfo]:
        """
        Get drug information by name
        
        Args:
            name: Drug name (generic or brand)
            
        Returns:
            DrugInfo or None if not found
        """
        name_lower = name.lower().strip()
        
        # Direct lookup
        if name_lower in self._drugs_cache:
            return self._drugs_cache[name_lower]
        
        # Search by name field
        for drug in self._drugs_cache.values():
            if drug.name.lower() == name_lower:
                return drug
            
            # Check synonyms
            if name_lower in [s.lower() for s in drug.synonyms]:
                return drug
        
        return None
    
    def search_drugs(
        self,
        query: str,
        limit: int = 10
    ) -> List[DrugInfo]:
        """
        Search drugs by name or description
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of matching drugs
        """
        query_lower = query.lower()
        results = []
        
        for drug in self._drugs_cache.values():
            score = 0
            
            # Name match
            if query_lower in drug.name.lower():
                score += 10
                if drug.name.lower() == query_lower:
                    score += 10
            
            # Synonym match
            for synonym in drug.synonyms:
                if query_lower in synonym.lower():
                    score += 5
            
            # Description match
            if query_lower in drug.description.lower():
                score += 2
            
            # Indication match
            if query_lower in drug.indication.lower():
                score += 3
            
            if score > 0:
                results.append((score, drug))
        
        # Sort by score
        results.sort(key=lambda x: x[0], reverse=True)
        
        return [drug for _, drug in results[:limit]]
    
    def get_drug_by_id(self, drugbank_id: str) -> Optional[DrugInfo]:
        """Get drug by DrugBank ID"""
        for drug in self._drugs_cache.values():
            if drug.drugbank_id == drugbank_id:
                return drug
        return None
    
    def get_interactions(
        self,
        drug_name: str
    ) -> List[DrugInteraction]:
        """
        Get all interactions for a drug
        
        Args:
            drug_name: Drug name
            
        Returns:
            List of interactions
        """
        drug = self.get_drug(drug_name)
        if not drug:
            return []
        
        interactions = []
        
        for interaction in self._interactions_cache:
            if (interaction.drug1_name.lower() == drug.name.lower() or
                interaction.drug2_name.lower() == drug.name.lower() or
                interaction.drug1_id == drug.drugbank_id or
                interaction.drug2_id == drug.drugbank_id):
                interactions.append(interaction)
        
        return interactions
    
    def check_interaction(
        self,
        drug1_name: str,
        drug2_name: str
    ) -> Optional[DrugInteraction]:
        """
        Check for interaction between two specific drugs
        
        Args:
            drug1_name: First drug name
            drug2_name: Second drug name
            
        Returns:
            DrugInteraction if exists, None otherwise
        """
        drug1 = self.get_drug(drug1_name)
        drug2 = self.get_drug(drug2_name)
        
        if not drug1 or not drug2:
            return None
        
        for interaction in self._interactions_cache:
            names = {
                interaction.drug1_name.lower(),
                interaction.drug2_name.lower()
            }
            ids = {interaction.drug1_id, interaction.drug2_id}
            
            if ({drug1.name.lower(), drug2.name.lower()} == names or
                {drug1.drugbank_id, drug2.drugbank_id} == ids):
                return interaction
        
        return None
    
    def get_drugs_by_class(self, drug_class: str) -> List[DrugInfo]:
        """Get all drugs of a specific class"""
        class_lower = drug_class.lower()
        
        return [
            drug for drug in self._drugs_cache.values()
            if class_lower in drug.drug_class.lower() or
               any(class_lower in cat.lower() for cat in drug.categories)
        ]
    
    def get_food_interactions(self, drug_name: str) -> List[str]:
        """Get food interactions for a drug"""
        drug = self.get_drug(drug_name)
        if drug:
            return drug.food_interactions
        return []
    
    def add_drug(self, drug: DrugInfo):
        """Add a drug to the cache"""
        key = drug.name.lower()
        self._drugs_cache[key] = drug
    
    def add_interaction(self, interaction: DrugInteraction):
        """Add an interaction to the cache"""
        self._interactions_cache.append(interaction)
    
    def get_all_drug_names(self) -> List[str]:
        """Get list of all drug names"""
        return [drug.name for drug in self._drugs_cache.values()]
    
    def get_statistics(self) -> Dict[str, int]:
        """Get statistics about loaded data"""
        return {
            "total_drugs": len(self._drugs_cache),
            "total_interactions": len(self._interactions_cache),
            "drug_classes": len(set(d.drug_class for d in self._drugs_cache.values()))
        }


# Singleton instance
drugbank_loader = DrugBankLoader()
