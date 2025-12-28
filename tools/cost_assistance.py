"""
Cost Assistance Tool
Helps find medication cost assistance programs and alternatives
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import httpx

from config import settings


logger = logging.getLogger(__name__)


class AssistanceType(str, Enum):
    """Types of cost assistance programs"""
    MANUFACTURER_PAP = "manufacturer_pap"       # Patient Assistance Programs
    COPAY_CARD = "copay_card"                   # Manufacturer copay cards
    STATE_PROGRAM = "state_program"             # State pharmaceutical assistance
    FEDERAL_PROGRAM = "federal_program"         # Medicare Extra Help, Medicaid
    DISCOUNT_CARD = "discount_card"             # GoodRx, RxSaver, etc.
    GENERIC_ALTERNATIVE = "generic_alternative" # Generic substitution
    THERAPEUTIC_ALTERNATIVE = "therapeutic_alt" # Different drug, same class
    PILL_SPLITTING = "pill_splitting"           # Where appropriate
    MAIL_ORDER = "mail_order"                   # 90-day supply savings


@dataclass
class AssistanceProgram:
    """Cost assistance program details"""
    name: str
    assistance_type: AssistanceType
    description: str
    eligibility: List[str]
    estimated_savings: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None
    application_process: Optional[str] = None
    requires_income_verification: bool = False
    income_limit: Optional[str] = None
    covers_medications: List[str] = field(default_factory=list)


@dataclass
class CostComparisonResult:
    """Price comparison result"""
    medication: str
    brand_price: Optional[float] = None
    generic_price: Optional[float] = None
    generic_available: bool = False
    generic_name: Optional[str] = None
    discount_prices: Dict[str, float] = field(default_factory=dict)
    lowest_price: Optional[float] = None
    lowest_source: Optional[str] = None
    savings_vs_retail: Optional[float] = None


# Known manufacturer patient assistance programs
MANUFACTURER_PROGRAMS: Dict[str, AssistanceProgram] = {
    "lilly_cares": AssistanceProgram(
        name="Lilly Cares Patient Assistance Program",
        assistance_type=AssistanceType.MANUFACTURER_PAP,
        description="Free medications for eligible patients",
        eligibility=[
            "US resident",
            "No prescription drug coverage",
            "Income at or below 400% FPL"
        ],
        estimated_savings="Up to 100% (free medications)",
        website="https://lillycares.com",
        phone="1-800-545-6962",
        requires_income_verification=True,
        income_limit="400% FPL (~$60,000 single, ~$124,800 family of 4)",
        covers_medications=["insulin lispro", "insulin glargine", "dulaglutide", "tirzepatide"]
    ),
    "pfizer_rxpathways": AssistanceProgram(
        name="Pfizer RxPathways",
        assistance_type=AssistanceType.MANUFACTURER_PAP,
        description="Free or discounted Pfizer medications",
        eligibility=[
            "US resident",
            "Meet income guidelines",
            "No adequate prescription coverage"
        ],
        estimated_savings="Up to 100%",
        website="https://pfizerpatientassistance.com",
        phone="1-844-989-7284",
        requires_income_verification=True,
        covers_medications=["atorvastatin", "amlodipine", "sertraline", "gabapentin"]
    ),
    "merck_helps": AssistanceProgram(
        name="Merck Patient Assistance Program",
        assistance_type=AssistanceType.MANUFACTURER_PAP,
        description="Free Merck medications for eligible patients",
        eligibility=[
            "US resident or US territory",
            "No insurance or inadequate coverage",
            "Income at or below 400% FPL"
        ],
        estimated_savings="Up to 100%",
        website="https://merckhelps.com",
        phone="1-800-727-5400",
        requires_income_verification=True,
        covers_medications=["sitagliptin", "losartan"]
    ),
    "novo_nordisk_pap": AssistanceProgram(
        name="Novo Nordisk Patient Assistance Program",
        assistance_type=AssistanceType.MANUFACTURER_PAP,
        description="Free insulin and diabetes medications",
        eligibility=[
            "US citizen or legal resident",
            "No insurance or Medicare Part D",
            "Household income below 400% FPL"
        ],
        estimated_savings="Up to 100%",
        website="https://novonordisk-us.com/patients/patient-assistance.html",
        phone="1-866-310-7549",
        requires_income_verification=True,
        covers_medications=["insulin aspart", "insulin detemir", "liraglutide", "semaglutide"]
    ),
    "astrazeneca_access360": AssistanceProgram(
        name="AstraZeneca Access 360",
        assistance_type=AssistanceType.MANUFACTURER_PAP,
        description="Assistance for AstraZeneca medications",
        eligibility=[
            "US resident",
            "Income guidelines",
            "Limited or no coverage"
        ],
        estimated_savings="Up to 100%",
        website="https://astrazeneca-us.com/medicines/help-affording-your-medicines.html",
        phone="1-844-275-2360",
        requires_income_verification=True,
        covers_medications=["rosuvastatin", "budesonide", "quetiapine"]
    )
}

# Federal and state programs
GOVERNMENT_PROGRAMS: List[AssistanceProgram] = [
    AssistanceProgram(
        name="Medicare Extra Help (LIS)",
        assistance_type=AssistanceType.FEDERAL_PROGRAM,
        description="Helps pay Part D premiums, deductibles, and copays",
        eligibility=[
            "Medicare Part D enrolled",
            "Limited income (below 150% FPL)",
            "Limited resources"
        ],
        estimated_savings="Save up to $5,000+ per year",
        website="https://ssa.gov/medicare/part-d-extra-help",
        phone="1-800-772-1213",
        requires_income_verification=True,
        income_limit="150% FPL (~$22,000 single, ~$30,000 couple)"
    ),
    AssistanceProgram(
        name="Medicaid Prescription Coverage",
        assistance_type=AssistanceType.FEDERAL_PROGRAM,
        description="Low or no-cost prescriptions through Medicaid",
        eligibility=[
            "Income below Medicaid limits",
            "Varies by state"
        ],
        estimated_savings="Most prescriptions $0-$4",
        website="https://medicaid.gov",
        requires_income_verification=True
    ),
    AssistanceProgram(
        name="State Pharmaceutical Assistance Programs (SPAPs)",
        assistance_type=AssistanceType.STATE_PROGRAM,
        description="State-run programs for residents who need help",
        eligibility=[
            "State resident",
            "Meet state income guidelines",
            "Often for seniors"
        ],
        estimated_savings="Varies by state",
        website="https://medicare.gov/plan-compare/#/pharmaceutical-assistance-program",
        application_process="Apply through your state's program"
    )
]

# Discount programs
DISCOUNT_PROGRAMS: List[AssistanceProgram] = [
    AssistanceProgram(
        name="GoodRx",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Free prescription discount card accepted at most pharmacies",
        eligibility=["Anyone - no eligibility requirements"],
        estimated_savings="Up to 80% off retail prices",
        website="https://goodrx.com",
        application_process="Free - just show card at pharmacy"
    ),
    AssistanceProgram(
        name="RxSaver by RetailMeNot",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Free prescription discounts",
        eligibility=["Anyone"],
        estimated_savings="Up to 80% off",
        website="https://rxsaver.com",
        application_process="Free card"
    ),
    AssistanceProgram(
        name="SingleCare",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Free prescription savings card",
        eligibility=["Anyone - no restrictions"],
        estimated_savings="Up to 80% off",
        website="https://singlecare.com",
        application_process="Free - show card at pharmacy"
    ),
    AssistanceProgram(
        name="Amazon Pharmacy",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Discounted medications, extra savings with Prime",
        eligibility=["Anyone with Amazon account", "Prime for extra savings"],
        estimated_savings="Up to 80% off on generic, 40% on brand",
        website="https://pharmacy.amazon.com"
    ),
    AssistanceProgram(
        name="Cost Plus Drugs",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Mark Cuban's online pharmacy with transparent pricing",
        eligibility=["Anyone"],
        estimated_savings="Significant savings on many generics",
        website="https://costplusdrugs.com",
        application_process="Order online, shipped to you"
    ),
    AssistanceProgram(
        name="Walmart $4 Generics",
        assistance_type=AssistanceType.DISCOUNT_CARD,
        description="Many common generics for $4/30-day or $10/90-day",
        eligibility=["Anyone"],
        estimated_savings="$4 for 30-day supply, $10 for 90-day",
        website="https://walmart.com/cp/4-dollar-prescriptions/1078664"
    )
]

# Generic alternatives database
GENERIC_ALTERNATIVES: Dict[str, Dict[str, Any]] = {
    "lipitor": {
        "generic_name": "atorvastatin",
        "typical_brand_price": 350.00,
        "typical_generic_price": 15.00,
        "savings_percentage": 95
    },
    "norvasc": {
        "generic_name": "amlodipine",
        "typical_brand_price": 150.00,
        "typical_generic_price": 8.00,
        "savings_percentage": 95
    },
    "zoloft": {
        "generic_name": "sertraline",
        "typical_brand_price": 400.00,
        "typical_generic_price": 10.00,
        "savings_percentage": 97
    },
    "glucophage": {
        "generic_name": "metformin",
        "typical_brand_price": 200.00,
        "typical_generic_price": 4.00,
        "savings_percentage": 98
    },
    "prilosec": {
        "generic_name": "omeprazole",
        "typical_brand_price": 250.00,
        "typical_generic_price": 12.00,
        "savings_percentage": 95
    },
    "synthroid": {
        "generic_name": "levothyroxine",
        "typical_brand_price": 150.00,
        "typical_generic_price": 15.00,
        "savings_percentage": 90
    },
    "neurontin": {
        "generic_name": "gabapentin",
        "typical_brand_price": 400.00,
        "typical_generic_price": 15.00,
        "savings_percentage": 96
    },
    "cozaar": {
        "generic_name": "losartan",
        "typical_brand_price": 200.00,
        "typical_generic_price": 10.00,
        "savings_percentage": 95
    },
    "zestril": {
        "generic_name": "lisinopril",
        "typical_brand_price": 150.00,
        "typical_generic_price": 4.00,
        "savings_percentage": 97
    },
    "lopressor": {
        "generic_name": "metoprolol",
        "typical_brand_price": 100.00,
        "typical_generic_price": 8.00,
        "savings_percentage": 92
    }
}


class CostAssistanceFinder:
    """
    Finds cost assistance options for medications
    """
    
    def __init__(self):
        self.manufacturer_programs = MANUFACTURER_PROGRAMS
        self.government_programs = GOVERNMENT_PROGRAMS
        self.discount_programs = DISCOUNT_PROGRAMS
        self.generic_alternatives = GENERIC_ALTERNATIVES
    
    async def find_assistance_options(
        self,
        medication_name: str,
        has_insurance: bool = True,
        insurance_type: Optional[str] = None,  # "commercial", "medicare", "medicaid", "none"
        annual_income: Optional[float] = None,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Find all applicable cost assistance options for a medication
        
        Args:
            medication_name: Name of the medication
            has_insurance: Whether patient has insurance
            insurance_type: Type of insurance coverage
            annual_income: Annual household income
            state: State of residence
            
        Returns:
            Dictionary with all applicable assistance options
        """
        medication_lower = medication_name.lower().strip()
        options = {
            "medication": medication_name,
            "generic_alternative": None,
            "manufacturer_programs": [],
            "government_programs": [],
            "discount_programs": [],
            "additional_strategies": [],
            "estimated_max_savings": None
        }
        
        # Check for generic alternative
        generic_info = await self._find_generic_alternative(medication_lower)
        if generic_info:
            options["generic_alternative"] = generic_info
            options["additional_strategies"].append({
                "strategy": "Switch to generic",
                "description": f"Ask your provider about {generic_info['generic_name']}",
                "estimated_savings": f"~{generic_info['savings_percentage']}%"
            })
        
        # Find manufacturer programs
        for program_id, program in self.manufacturer_programs.items():
            if self._medication_matches_program(medication_lower, program):
                if self._meets_basic_eligibility(program, has_insurance, annual_income):
                    options["manufacturer_programs"].append(self._program_to_dict(program))
        
        # Government programs
        if not has_insurance or insurance_type == "none":
            for program in self.government_programs:
                if program.assistance_type == AssistanceType.FEDERAL_PROGRAM:
                    if self._meets_income_requirements(program, annual_income):
                        options["government_programs"].append(self._program_to_dict(program))
        
        # Medicare Extra Help for Medicare patients
        if insurance_type == "medicare":
            for program in self.government_programs:
                if program.name == "Medicare Extra Help (LIS)":
                    options["government_programs"].append(self._program_to_dict(program))
        
        # Discount programs (always applicable)
        for program in self.discount_programs:
            options["discount_programs"].append(self._program_to_dict(program))
        
        # Additional strategies
        options["additional_strategies"].extend([
            {
                "strategy": "90-day supply",
                "description": "Ask about 90-day supply for maintenance medications",
                "estimated_savings": "~20-30% vs monthly fills"
            },
            {
                "strategy": "Pill splitting",
                "description": "Ask your provider if splitting a higher-strength tablet is appropriate",
                "estimated_savings": "Up to 50%"
            },
            {
                "strategy": "Shop around",
                "description": "Prices vary significantly between pharmacies. Compare prices.",
                "estimated_savings": "Varies"
            }
        ])
        
        # Calculate potential max savings
        options["estimated_max_savings"] = self._calculate_max_savings(options)
        
        return options
    
    async def _find_generic_alternative(self, medication: str) -> Optional[Dict[str, Any]]:
        """Find generic alternative for a brand medication"""
        # Check direct match
        if medication in self.generic_alternatives:
            return self.generic_alternatives[medication]
        
        # Check if it's already a generic (exists as a generic name)
        for brand, info in self.generic_alternatives.items():
            if info["generic_name"].lower() == medication:
                return None  # Already generic
        
        return None
    
    def _medication_matches_program(self, medication: str, program: AssistanceProgram) -> bool:
        """Check if medication is covered by a program"""
        if not program.covers_medications:
            return True  # Program covers all their products
        
        for covered in program.covers_medications:
            if medication in covered.lower() or covered.lower() in medication:
                return True
        
        return False
    
    def _meets_basic_eligibility(
        self, 
        program: AssistanceProgram, 
        has_insurance: bool,
        annual_income: Optional[float]
    ) -> bool:
        """Check basic eligibility for a program"""
        # Most PAPs require no insurance or inadequate coverage
        if program.assistance_type == AssistanceType.MANUFACTURER_PAP:
            if has_insurance:
                return False  # May still qualify if underinsured
        
        # Income check (approximate - 400% FPL ≈ $60,000 single)
        if program.requires_income_verification and annual_income:
            if annual_income > 60000:  # Simplified check
                return False
        
        return True
    
    def _meets_income_requirements(
        self,
        program: AssistanceProgram,
        annual_income: Optional[float]
    ) -> bool:
        """Check income requirements"""
        if not program.requires_income_verification:
            return True
        
        if annual_income is None:
            return True  # Can't verify, include it
        
        # Simplified FPL checks
        if "150%" in (program.income_limit or ""):
            return annual_income <= 22000
        elif "400%" in (program.income_limit or ""):
            return annual_income <= 60000
        
        return True
    
    def _program_to_dict(self, program: AssistanceProgram) -> Dict[str, Any]:
        """Convert program to dictionary"""
        return {
            "name": program.name,
            "type": program.assistance_type.value,
            "description": program.description,
            "eligibility": program.eligibility,
            "estimated_savings": program.estimated_savings,
            "website": program.website,
            "phone": program.phone,
            "application_process": program.application_process,
            "requires_income_verification": program.requires_income_verification
        }
    
    def _calculate_max_savings(self, options: Dict[str, Any]) -> str:
        """Estimate maximum potential savings"""
        if options["generic_alternative"]:
            return f"Up to {options['generic_alternative']['savings_percentage']}% with generic"
        elif options["manufacturer_programs"]:
            return "Up to 100% with patient assistance program"
        elif options["discount_programs"]:
            return "Up to 80% with discount cards"
        return "Savings vary - compare options"
    
    async def compare_prices(
        self,
        medication: str,
        dosage: str,
        quantity: int = 30
    ) -> CostComparisonResult:
        """
        Compare prices across different sources
        
        Note: In production, this would call actual pricing APIs
        """
        medication_lower = medication.lower()
        result = CostComparisonResult(medication=medication)
        
        # Check for generic
        generic_info = await self._find_generic_alternative(medication_lower)
        if generic_info:
            result.generic_available = True
            result.generic_name = generic_info["generic_name"]
            result.brand_price = generic_info["typical_brand_price"]
            result.generic_price = generic_info["typical_generic_price"]
        
        # Simulated discount prices (in production, would call APIs)
        base_price = result.generic_price or result.brand_price or 50.0
        
        result.discount_prices = {
            "GoodRx": round(base_price * 0.4, 2),
            "SingleCare": round(base_price * 0.45, 2),
            "Walmart $4": 4.00 if result.generic_available else None,
            "Cost Plus Drugs": round(base_price * 0.3, 2) if result.generic_available else None,
            "Amazon Pharmacy": round(base_price * 0.35, 2)
        }
        
        # Remove None values
        result.discount_prices = {k: v for k, v in result.discount_prices.items() if v}
        
        # Find lowest
        if result.discount_prices:
            lowest_source = min(result.discount_prices.items(), key=lambda x: x[1])
            result.lowest_price = lowest_source[1]
            result.lowest_source = lowest_source[0]
            
            retail = result.brand_price or base_price * 2
            result.savings_vs_retail = round(retail - result.lowest_price, 2)
        
        return result
    
    def get_all_discount_programs(self) -> List[Dict[str, Any]]:
        """Get list of all discount programs"""
        return [self._program_to_dict(p) for p in self.discount_programs]
    
    def get_eligibility_checklist(self, program_type: AssistanceType) -> List[str]:
        """Get eligibility checklist for a program type"""
        checklists = {
            AssistanceType.MANUFACTURER_PAP: [
                "US citizen or legal resident",
                "No prescription drug coverage OR Medicare without Part D",
                "Household income at or below 400% Federal Poverty Level",
                "Currently prescribed the medication"
            ],
            AssistanceType.FEDERAL_PROGRAM: [
                "Meet program-specific income limits",
                "US citizen or qualified immigrant",
                "Meet age or disability requirements (for some programs)"
            ],
            AssistanceType.DISCOUNT_CARD: [
                "No eligibility requirements",
                "Cannot be used with insurance",
                "Available to anyone"
            ]
        }
        return checklists.get(program_type, ["See program for specific requirements"])


# Singleton instance
cost_assistance_finder = CostAssistanceFinder()


async def find_cost_assistance(
    medication: str,
    has_insurance: bool = True,
    income: Optional[float] = None
) -> Dict[str, Any]:
    """Convenience function to find cost assistance options"""
    return await cost_assistance_finder.find_assistance_options(
        medication, has_insurance, annual_income=income
    )
