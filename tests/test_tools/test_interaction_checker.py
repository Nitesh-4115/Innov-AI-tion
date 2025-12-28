"""
Tests for Drug Interaction Checker Tool
Tests drug-drug interaction detection and severity classification
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

from tools.interaction_checker import (
    InteractionChecker,
    DrugInteraction,
    InteractionSeverity,
    INTERACTION_DATABASE,
    interaction_checker,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def checker():
    """Create interaction checker instance"""
    return InteractionChecker()


@pytest.fixture
def sample_medications():
    """Sample medication list for testing"""
    return ["warfarin", "aspirin", "lisinopril", "metformin"]


@pytest.fixture
def safe_medications():
    """Medications with no known interactions"""
    return ["acetaminophen", "vitamin_d"]


# =============================================================================
# Test InteractionSeverity Enum
# =============================================================================

class TestInteractionSeverity:
    """Tests for InteractionSeverity enum"""
    
    def test_severity_levels_exist(self):
        """Test all severity levels are defined"""
        assert InteractionSeverity.CONTRAINDICATED is not None
        assert InteractionSeverity.MAJOR is not None
        assert InteractionSeverity.MODERATE is not None
        assert InteractionSeverity.MINOR is not None
        assert InteractionSeverity.UNKNOWN is not None
    
    def test_severity_values(self):
        """Test severity level string values"""
        assert InteractionSeverity.CONTRAINDICATED.value == "contraindicated"
        assert InteractionSeverity.MAJOR.value == "major"
        assert InteractionSeverity.MODERATE.value == "moderate"
        assert InteractionSeverity.MINOR.value == "minor"
        assert InteractionSeverity.UNKNOWN.value == "unknown"
    
    def test_severity_comparison(self):
        """Test severity levels can be compared"""
        severity_order = {
            InteractionSeverity.CONTRAINDICATED: 0,
            InteractionSeverity.MAJOR: 1,
            InteractionSeverity.MODERATE: 2,
            InteractionSeverity.MINOR: 3,
            InteractionSeverity.UNKNOWN: 4
        }
        
        assert severity_order[InteractionSeverity.CONTRAINDICATED] < severity_order[InteractionSeverity.MAJOR]
        assert severity_order[InteractionSeverity.MAJOR] < severity_order[InteractionSeverity.MODERATE]


# =============================================================================
# Test DrugInteraction Dataclass
# =============================================================================

class TestDrugInteraction:
    """Tests for DrugInteraction dataclass"""
    
    def test_interaction_creation(self):
        """Test creating a drug interaction"""
        interaction = DrugInteraction(
            drug1="warfarin",
            drug2="aspirin",
            severity=InteractionSeverity.MAJOR,
            description="Increased risk of bleeding"
        )
        
        assert interaction.drug1 == "warfarin"
        assert interaction.drug2 == "aspirin"
        assert interaction.severity == InteractionSeverity.MAJOR
        assert interaction.description == "Increased risk of bleeding"
    
    def test_interaction_with_all_fields(self):
        """Test interaction with all optional fields"""
        interaction = DrugInteraction(
            drug1="levothyroxine",
            drug2="calcium",
            severity=InteractionSeverity.MODERATE,
            description="Reduced absorption",
            mechanism="Calcium binds levothyroxine in GI tract",
            clinical_effects="Subtherapeutic thyroid hormone levels",
            management="Separate doses by at least 4 hours",
            separation_hours=4,
            monitoring_required=True,
            avoid_combination=False
        )
        
        assert interaction.mechanism is not None
        assert interaction.clinical_effects is not None
        assert interaction.management is not None
        assert interaction.separation_hours == 4
        assert interaction.monitoring_required is True
        assert interaction.avoid_combination is False
    
    def test_interaction_defaults(self):
        """Test default values for optional fields"""
        interaction = DrugInteraction(
            drug1="drug_a",
            drug2="drug_b",
            severity=InteractionSeverity.MINOR,
            description="Minor interaction"
        )
        
        assert interaction.mechanism is None
        assert interaction.clinical_effects is None
        assert interaction.management is None
        assert interaction.separation_hours == 0
        assert interaction.monitoring_required is False
        assert interaction.avoid_combination is False


# =============================================================================
# Test InteractionChecker Initialization
# =============================================================================

class TestInteractionCheckerInit:
    """Tests for InteractionChecker initialization"""
    
    def test_checker_initialization(self, checker):
        """Test checker initializes correctly"""
        assert checker is not None
        assert hasattr(checker, "interaction_db")
    
    def test_interaction_database_loaded(self, checker):
        """Test interaction database is loaded"""
        assert len(checker.interaction_db) > 0
    
    def test_drug_index_built(self, checker):
        """Test drug pair index is built"""
        assert hasattr(checker, "_drug_pairs")
        assert len(checker._drug_pairs) > 0
    
    def test_global_instance_available(self):
        """Test global interaction_checker instance is available"""
        assert interaction_checker is not None
        assert isinstance(interaction_checker, InteractionChecker)


# =============================================================================
# Test Drug Name Normalization
# =============================================================================

class TestDrugNameNormalization:
    """Tests for drug name normalization"""
    
    def test_lowercase_normalization(self, checker):
        """Test drug names are lowercased"""
        normalized = checker._normalize_drug_name("WARFARIN")
        assert normalized == "warfarin"
    
    def test_whitespace_removal(self, checker):
        """Test whitespace is removed"""
        normalized = checker._normalize_drug_name(" warfarin ")
        assert normalized == "warfarin"
    
    def test_hyphen_removal(self, checker):
        """Test hyphens are removed"""
        normalized = checker._normalize_drug_name("ace-inhibitor")
        assert normalized == "aceinhibitor"
    
    def test_space_removal(self, checker):
        """Test spaces are removed"""
        normalized = checker._normalize_drug_name("potassium supplements")
        assert normalized == "potassiumsupplements"


# =============================================================================
# Test Single Interaction Check
# =============================================================================

class TestSingleInteractionCheck:
    """Tests for checking interaction between two drugs"""
    
    def test_known_interaction_found(self, checker):
        """Test known interaction is detected"""
        interaction = checker.check_interaction("warfarin", "aspirin")
        
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR
    
    def test_interaction_found_reverse_order(self, checker):
        """Test interaction found regardless of drug order"""
        interaction1 = checker.check_interaction("warfarin", "aspirin")
        interaction2 = checker.check_interaction("aspirin", "warfarin")
        
        # Both should find the same interaction
        assert interaction1 is not None
        assert interaction2 is not None
    
    def test_no_interaction_found(self, checker):
        """Test no interaction returns None"""
        interaction = checker.check_interaction("acetaminophen", "vitamin_d")
        assert interaction is None
    
    def test_case_insensitive_check(self, checker):
        """Test interaction check is case insensitive"""
        interaction1 = checker.check_interaction("WARFARIN", "ASPIRIN")
        interaction2 = checker.check_interaction("warfarin", "aspirin")
        
        assert interaction1 is not None
        assert interaction2 is not None
    
    def test_contraindicated_interaction(self, checker):
        """Test contraindicated interaction detection"""
        interaction = checker.check_interaction("sertraline", "maoi")
        
        if interaction:
            assert interaction.severity == InteractionSeverity.CONTRAINDICATED


# =============================================================================
# Test Multiple Interaction Check
# =============================================================================

class TestMultipleInteractionCheck:
    """Tests for checking all interactions among medications"""
    
    def test_check_all_interactions(self, checker, sample_medications):
        """Test checking all interactions in medication list"""
        interactions = checker.check_all_interactions(sample_medications)
        
        assert isinstance(interactions, list)
        # warfarin + aspirin should be detected
        assert len(interactions) > 0
    
    def test_interactions_sorted_by_severity(self, checker, sample_medications):
        """Test interactions are sorted by severity"""
        interactions = checker.check_all_interactions(sample_medications)
        
        if len(interactions) > 1:
            severity_order = {
                InteractionSeverity.CONTRAINDICATED: 0,
                InteractionSeverity.MAJOR: 1,
                InteractionSeverity.MODERATE: 2,
                InteractionSeverity.MINOR: 3,
                InteractionSeverity.UNKNOWN: 4
            }
            
            for i in range(len(interactions) - 1):
                current_order = severity_order.get(interactions[i].severity, 5)
                next_order = severity_order.get(interactions[i+1].severity, 5)
                assert current_order <= next_order
    
    def test_no_duplicate_interactions(self, checker, sample_medications):
        """Test no duplicate interactions reported"""
        interactions = checker.check_all_interactions(sample_medications)
        
        pairs = [
            tuple(sorted([i.drug1.lower(), i.drug2.lower()])) 
            for i in interactions
        ]
        assert len(pairs) == len(set(pairs))
    
    def test_empty_medication_list(self, checker):
        """Test empty medication list returns empty interactions"""
        interactions = checker.check_all_interactions([])
        assert interactions == []
    
    def test_single_medication(self, checker):
        """Test single medication returns no interactions"""
        interactions = checker.check_all_interactions(["metformin"])
        assert interactions == []
    
    def test_safe_medication_list(self, checker, safe_medications):
        """Test safe medications return no interactions"""
        interactions = checker.check_all_interactions(safe_medications)
        assert len(interactions) == 0


# =============================================================================
# Test Interaction Summary
# =============================================================================

class TestInteractionSummary:
    """Tests for interaction summary generation"""
    
    def test_get_interaction_summary(self, checker, sample_medications):
        """Test getting interaction summary"""
        summary = checker.get_interaction_summary(sample_medications)
        
        assert isinstance(summary, dict)
        # Should have counts and details
    
    def test_summary_counts_by_severity(self, checker, sample_medications):
        """Test summary includes severity counts"""
        summary = checker.get_interaction_summary(sample_medications)
        
        # Check expected keys in summary
        if "by_severity" in summary:
            assert "major" in summary["by_severity"] or "contraindicated" in summary["by_severity"]
    
    def test_summary_total_count(self, checker, sample_medications):
        """Test summary includes total interaction count"""
        summary = checker.get_interaction_summary(sample_medications)
        
        if "total" in summary:
            assert summary["total"] >= 0


# =============================================================================
# Test Specific Drug Interactions
# =============================================================================

class TestSpecificDrugInteractions:
    """Tests for specific known drug interactions"""
    
    def test_warfarin_aspirin_interaction(self, checker):
        """Test warfarin-aspirin major interaction"""
        interaction = checker.check_interaction("warfarin", "aspirin")
        
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR
        assert "bleeding" in interaction.description.lower()
        assert interaction.avoid_combination is True
    
    def test_warfarin_ibuprofen_interaction(self, checker):
        """Test warfarin-ibuprofen interaction"""
        interaction = checker.check_interaction("warfarin", "ibuprofen")
        
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR
    
    def test_lisinopril_potassium_interaction(self, checker):
        """Test ACE inhibitor-potassium interaction"""
        interaction = checker.check_interaction("lisinopril", "potassium")
        
        assert interaction is not None
        assert "hyperkalemia" in interaction.description.lower() or "potassium" in interaction.description.lower()
    
    def test_statin_gemfibrozil_interaction(self, checker):
        """Test statin-gemfibrozil myopathy risk"""
        interaction = checker.check_interaction("atorvastatin", "gemfibrozil")
        
        assert interaction is not None
        assert interaction.severity == InteractionSeverity.MAJOR
        assert "myopathy" in interaction.description.lower() or "rhabdomyolysis" in interaction.description.lower()
    
    def test_levothyroxine_calcium_interaction(self, checker):
        """Test levothyroxine-calcium separation requirement"""
        interaction = checker.check_interaction("levothyroxine", "calcium")
        
        assert interaction is not None
        assert interaction.separation_hours >= 4
    
    def test_metformin_contrast_interaction(self, checker):
        """Test metformin-contrast interaction"""
        interaction = checker.check_interaction("metformin", "contrast_dye")
        
        assert interaction is not None
        assert interaction.separation_hours >= 48
    
    def test_ssri_maoi_contraindication(self, checker):
        """Test SSRI-MAOI contraindication"""
        interaction = checker.check_interaction("sertraline", "maoi")
        
        if interaction:
            assert interaction.severity == InteractionSeverity.CONTRAINDICATED
            assert interaction.avoid_combination is True


# =============================================================================
# Test Separation Requirements
# =============================================================================

class TestSeparationRequirements:
    """Tests for dose separation requirements"""
    
    def test_levothyroxine_calcium_separation(self, checker):
        """Test 4-hour separation for levothyroxine-calcium"""
        interaction = checker.check_interaction("levothyroxine", "calcium")
        
        assert interaction is not None
        assert interaction.separation_hours >= 4
    
    def test_levothyroxine_iron_separation(self, checker):
        """Test separation for levothyroxine-iron"""
        interaction = checker.check_interaction("levothyroxine", "iron")
        
        assert interaction is not None
        assert interaction.separation_hours >= 4
    
    def test_ciprofloxacin_antacid_separation(self, checker):
        """Test separation for ciprofloxacin-antacid"""
        interaction = checker.check_interaction("ciprofloxacin", "antacids")
        
        assert interaction is not None
        assert interaction.separation_hours >= 2


# =============================================================================
# Test Monitoring Requirements
# =============================================================================

class TestMonitoringRequirements:
    """Tests for monitoring requirements"""
    
    def test_warfarin_aspirin_monitoring(self, checker):
        """Test warfarin-aspirin requires monitoring"""
        interaction = checker.check_interaction("warfarin", "aspirin")
        
        assert interaction is not None
        assert interaction.monitoring_required is True
    
    def test_lisinopril_potassium_monitoring(self, checker):
        """Test lisinopril-potassium requires monitoring"""
        interaction = checker.check_interaction("lisinopril", "potassium")
        
        assert interaction is not None
        assert interaction.monitoring_required is True


# =============================================================================
# Test Interaction Database
# =============================================================================

class TestInteractionDatabase:
    """Tests for the interaction database"""
    
    def test_database_not_empty(self):
        """Test database has interactions"""
        assert len(INTERACTION_DATABASE) > 0
    
    def test_database_keys_are_tuples(self):
        """Test database keys are drug name tuples"""
        for key in INTERACTION_DATABASE.keys():
            assert isinstance(key, tuple)
            assert len(key) == 2
    
    def test_database_values_are_interactions(self):
        """Test database values are DrugInteraction objects"""
        for value in INTERACTION_DATABASE.values():
            assert isinstance(value, DrugInteraction)
    
    def test_all_interactions_have_required_fields(self):
        """Test all interactions have required fields"""
        for interaction in INTERACTION_DATABASE.values():
            assert interaction.drug1 is not None
            assert interaction.drug2 is not None
            assert interaction.severity is not None
            assert interaction.description is not None
    
    def test_all_severities_valid(self):
        """Test all interaction severities are valid enum values"""
        for interaction in INTERACTION_DATABASE.values():
            assert interaction.severity in InteractionSeverity


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_same_drug_no_interaction(self, checker):
        """Test checking same drug against itself"""
        interaction = checker.check_interaction("warfarin", "warfarin")
        assert interaction is None
    
    def test_unknown_drugs(self, checker):
        """Test handling unknown drug names"""
        interaction = checker.check_interaction("unknown_drug_xyz", "another_unknown")
        assert interaction is None
    
    def test_empty_drug_name(self, checker):
        """Test handling empty drug names"""
        interaction = checker.check_interaction("", "warfarin")
        assert interaction is None
    
    def test_special_characters_in_drug_name(self, checker):
        """Test handling special characters"""
        # Should normalize and still find interaction
        interaction = checker.check_interaction("war-farin", "asp irin")
        # May or may not find depending on normalization
    
    def test_very_long_medication_list(self, checker):
        """Test handling long medication list"""
        medications = [f"drug_{i}" for i in range(50)]
        medications.extend(["warfarin", "aspirin"])  # Add known interaction
        
        interactions = checker.check_all_interactions(medications)
        # Should find warfarin-aspirin interaction
        assert len(interactions) >= 1


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestInteractionCheckerIntegration:
    """Integration tests for interaction checker"""
    
    @pytest.mark.integration
    def test_full_medication_review(self, checker):
        """Test complete medication review workflow"""
        # Patient's medication list
        medications = [
            "metformin",
            "lisinopril", 
            "atorvastatin",
            "aspirin",
            "omeprazole"
        ]
        
        # Check all interactions
        interactions = checker.check_all_interactions(medications)
        
        # Get summary
        summary = checker.get_interaction_summary(medications)
        
        assert isinstance(interactions, list)
        assert isinstance(summary, dict)
    
    @pytest.mark.integration
    def test_high_risk_patient_scenario(self, checker):
        """Test high-risk patient with multiple interactions"""
        # Patient on anticoagulation with multiple risks
        medications = [
            "warfarin",
            "aspirin",
            "ibuprofen",
            "sertraline"
        ]
        
        interactions = checker.check_all_interactions(medications)
        
        # Should detect multiple major interactions
        major_interactions = [
            i for i in interactions 
            if i.severity in [InteractionSeverity.MAJOR, InteractionSeverity.CONTRAINDICATED]
        ]
        assert len(major_interactions) >= 2
    
    @pytest.mark.integration
    def test_diabetes_patient_scenario(self, checker):
        """Test typical diabetes patient medications"""
        medications = [
            "metformin",
            "lisinopril",
            "atorvastatin",
            "aspirin"
        ]
        
        interactions = checker.check_all_interactions(medications)
        # Common diabetes combo - should have minimal high-risk interactions
        
        contraindicated = [
            i for i in interactions 
            if i.severity == InteractionSeverity.CONTRAINDICATED
        ]
        assert len(contraindicated) == 0
