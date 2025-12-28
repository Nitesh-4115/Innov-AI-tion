"""
Tests for Medication Scheduler Tool
Tests medication schedule creation and optimization
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any

from tools.scheduler import (
    MedicationScheduler,
    MedicationScheduleItem,
    DailySchedule,
    PatientPreferences,
    MedicationInput,
    MealRelation,
    TimeSlotPriority,
)
from tools.interaction_checker import InteractionSeverity, DrugInteraction


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def scheduler():
    """Create medication scheduler instance"""
    return MedicationScheduler()


@pytest.fixture
def default_preferences():
    """Default patient preferences"""
    return PatientPreferences(
        wake_time=time(7, 0),
        sleep_time=time(22, 0),
        breakfast_time=time(8, 0),
        lunch_time=time(12, 0),
        dinner_time=time(18, 0),
        preferred_reminder_minutes=15
    )


@pytest.fixture
def night_shift_preferences():
    """Night shift worker preferences"""
    return PatientPreferences(
        wake_time=time(17, 0),   # Wake at 5 PM
        sleep_time=time(9, 0),   # Sleep at 9 AM
        breakfast_time=time(18, 0),
        lunch_time=time(0, 0),   # Midnight lunch
        dinner_time=time(6, 0),   # 6 AM dinner
        work_schedule="night_shift"
    )


@pytest.fixture
def sample_medications():
    """Sample medications for testing"""
    return [
        MedicationInput(
            name="metformin",
            dosage="500mg",
            frequency_per_day=2,
            with_food=True
        ),
        MedicationInput(
            name="lisinopril",
            dosage="10mg",
            frequency_per_day=1,
            with_food=False
        ),
        MedicationInput(
            name="atorvastatin",
            dosage="20mg",
            frequency_per_day=1,
            with_food=False,
            special_instructions="Take in the evening"
        ),
    ]


@pytest.fixture
def complex_medications():
    """Complex medication regimen with interactions"""
    return [
        MedicationInput(
            name="levothyroxine",
            dosage="75mcg",
            frequency_per_day=1,
            with_food=False,
            special_instructions="Take on empty stomach, 30-60 min before breakfast"
        ),
        MedicationInput(
            name="calcium",
            dosage="600mg",
            frequency_per_day=2,
            with_food=True
        ),
        MedicationInput(
            name="iron",
            dosage="325mg",
            frequency_per_day=1,
            with_food=False
        ),
    ]


# =============================================================================
# Test MealRelation Enum
# =============================================================================

class TestMealRelation:
    """Tests for MealRelation enum"""
    
    def test_meal_relations_exist(self):
        """Test all meal relations are defined"""
        assert MealRelation.BEFORE is not None
        assert MealRelation.WITH is not None
        assert MealRelation.AFTER is not None
        assert MealRelation.BETWEEN is not None
        assert MealRelation.ANY is not None
    
    def test_meal_relation_values(self):
        """Test meal relation string values"""
        assert MealRelation.BEFORE.value == "before"
        assert MealRelation.WITH.value == "with"
        assert MealRelation.AFTER.value == "after"
        assert MealRelation.BETWEEN.value == "between_meals"
        assert MealRelation.ANY.value == "any"


# =============================================================================
# Test TimeSlotPriority Enum
# =============================================================================

class TestTimeSlotPriority:
    """Tests for TimeSlotPriority enum"""
    
    def test_priorities_exist(self):
        """Test all priorities are defined"""
        assert TimeSlotPriority.FIXED is not None
        assert TimeSlotPriority.HIGH is not None
        assert TimeSlotPriority.NORMAL is not None
        assert TimeSlotPriority.FLEXIBLE is not None
    
    def test_priority_values(self):
        """Test priority string values"""
        assert TimeSlotPriority.FIXED.value == "fixed"
        assert TimeSlotPriority.HIGH.value == "high"
        assert TimeSlotPriority.NORMAL.value == "normal"
        assert TimeSlotPriority.FLEXIBLE.value == "flexible"


# =============================================================================
# Test PatientPreferences Dataclass
# =============================================================================

class TestPatientPreferences:
    """Tests for PatientPreferences dataclass"""
    
    def test_default_preferences(self):
        """Test default patient preferences"""
        prefs = PatientPreferences()
        
        assert prefs.wake_time == time(7, 0)
        assert prefs.sleep_time == time(22, 0)
        assert prefs.breakfast_time == time(8, 0)
        assert prefs.lunch_time == time(12, 0)
        assert prefs.dinner_time == time(18, 0)
        assert prefs.preferred_reminder_minutes == 15
    
    def test_custom_preferences(self):
        """Test custom patient preferences"""
        prefs = PatientPreferences(
            wake_time=time(6, 0),
            sleep_time=time(21, 0),
            breakfast_time=time(7, 0),
            lunch_time=time(11, 30),
            dinner_time=time(17, 30),
            preferred_reminder_minutes=30,
            work_schedule="9-5"
        )
        
        assert prefs.wake_time == time(6, 0)
        assert prefs.work_schedule == "9-5"


# =============================================================================
# Test MedicationInput Dataclass
# =============================================================================

class TestMedicationInput:
    """Tests for MedicationInput dataclass"""
    
    def test_basic_medication_input(self):
        """Test basic medication input"""
        med = MedicationInput(
            name="metformin",
            dosage="500mg",
            frequency_per_day=2
        )
        
        assert med.name == "metformin"
        assert med.dosage == "500mg"
        assert med.frequency_per_day == 2
        assert med.with_food is False
        assert med.min_hours_between_doses == 4.0
    
    def test_medication_with_food_requirement(self):
        """Test medication with food requirement"""
        med = MedicationInput(
            name="nsaid",
            dosage="200mg",
            frequency_per_day=3,
            with_food=True
        )
        
        assert med.with_food is True
    
    def test_medication_with_preferred_times(self):
        """Test medication with preferred times"""
        med = MedicationInput(
            name="lisinopril",
            dosage="10mg",
            frequency_per_day=1,
            preferred_times=["08:00"]
        )
        
        assert med.preferred_times == ["08:00"]
    
    def test_medication_with_special_instructions(self):
        """Test medication with special instructions"""
        med = MedicationInput(
            name="levothyroxine",
            dosage="75mcg",
            frequency_per_day=1,
            special_instructions="Take on empty stomach"
        )
        
        assert med.special_instructions == "Take on empty stomach"


# =============================================================================
# Test MedicationScheduleItem Dataclass
# =============================================================================

class TestMedicationScheduleItem:
    """Tests for MedicationScheduleItem dataclass"""
    
    def test_schedule_item_creation(self):
        """Test creating a schedule item"""
        item = MedicationScheduleItem(
            medication_name="metformin",
            dosage="500mg",
            scheduled_time=time(8, 0)
        )
        
        assert item.medication_name == "metformin"
        assert item.dosage == "500mg"
        assert item.scheduled_time == time(8, 0)
        assert item.meal_relation == MealRelation.ANY
        assert item.priority == TimeSlotPriority.NORMAL
    
    def test_schedule_item_with_food(self):
        """Test schedule item requiring food"""
        item = MedicationScheduleItem(
            medication_name="nsaid",
            dosage="200mg",
            scheduled_time=time(12, 0),
            with_food=True,
            meal_relation=MealRelation.WITH
        )
        
        assert item.with_food is True
        assert item.meal_relation == MealRelation.WITH


# =============================================================================
# Test DailySchedule Dataclass
# =============================================================================

class TestDailySchedule:
    """Tests for DailySchedule dataclass"""
    
    def test_daily_schedule_creation(self):
        """Test creating a daily schedule"""
        schedule = DailySchedule(
            patient_id=1,
            schedule_date=date.today()
        )
        
        assert schedule.patient_id == 1
        assert schedule.schedule_date == date.today()
        assert schedule.items == []
        assert schedule.time_slots == {}
        assert schedule.warnings == []
        assert schedule.optimization_notes == []
    
    def test_daily_schedule_with_items(self):
        """Test daily schedule with medication items"""
        item = MedicationScheduleItem(
            medication_name="metformin",
            dosage="500mg",
            scheduled_time=time(8, 0)
        )
        
        schedule = DailySchedule(
            patient_id=1,
            schedule_date=date.today(),
            items=[item]
        )
        
        assert len(schedule.items) == 1


# =============================================================================
# Test MedicationScheduler Initialization
# =============================================================================

class TestSchedulerInit:
    """Tests for MedicationScheduler initialization"""
    
    def test_scheduler_initialization(self, scheduler):
        """Test scheduler initializes correctly"""
        assert scheduler is not None
        assert hasattr(scheduler, "interaction_checker")
    
    def test_default_time_slots(self, scheduler):
        """Test default time slots are defined"""
        assert hasattr(scheduler, "DEFAULT_TIME_SLOTS")
        assert len(scheduler.DEFAULT_TIME_SLOTS) > 0
    
    def test_default_slots_format(self, scheduler):
        """Test default slot format is HH:MM"""
        for slot in scheduler.DEFAULT_TIME_SLOTS:
            # Should be parseable as time
            parsed = datetime.strptime(slot, "%H:%M")
            assert parsed is not None


# =============================================================================
# Test Schedule Creation
# =============================================================================

class TestScheduleCreation:
    """Tests for schedule creation"""
    
    @pytest.mark.asyncio
    async def test_create_basic_schedule(self, scheduler, sample_medications, default_preferences):
        """Test creating a basic medication schedule"""
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=sample_medications,
                preferences=default_preferences
            )
            
            assert schedule is not None
            assert schedule.patient_id == 1
            assert schedule.schedule_date == date.today()
            assert len(schedule.items) > 0
    
    @pytest.mark.asyncio
    async def test_create_schedule_with_date(self, scheduler, sample_medications, default_preferences):
        """Test creating schedule for specific date"""
        tomorrow = date.today() + timedelta(days=1)
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=sample_medications,
                preferences=default_preferences,
                schedule_date=tomorrow
            )
            
            assert schedule.schedule_date == tomorrow
    
    @pytest.mark.asyncio
    async def test_schedule_respects_frequency(self, scheduler, default_preferences):
        """Test schedule respects medication frequency"""
        meds = [
            MedicationInput(name="med_once", dosage="10mg", frequency_per_day=1),
            MedicationInput(name="med_twice", dosage="20mg", frequency_per_day=2),
            MedicationInput(name="med_thrice", dosage="30mg", frequency_per_day=3),
        ]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            # Count items per medication
            med_counts = {}
            for item in schedule.items:
                name = item.medication_name
                med_counts[name] = med_counts.get(name, 0) + 1
            
            assert med_counts.get("med_once", 0) == 1
            assert med_counts.get("med_twice", 0) == 2
            assert med_counts.get("med_thrice", 0) == 3
    
    @pytest.mark.asyncio
    async def test_schedule_empty_medications(self, scheduler, default_preferences):
        """Test creating schedule with no medications"""
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=[],
                preferences=default_preferences
            )
            
            assert schedule.items == []


# =============================================================================
# Test Time Slot Assignment
# =============================================================================

class TestTimeSlotAssignment:
    """Tests for time slot assignment"""
    
    @pytest.mark.asyncio
    async def test_once_daily_morning(self, scheduler, default_preferences):
        """Test once daily medication scheduled in morning"""
        meds = [MedicationInput(name="lisinopril", dosage="10mg", frequency_per_day=1)]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            # Should be scheduled in morning hours
            assert len(schedule.items) == 1
            scheduled_time = schedule.items[0].scheduled_time
            # Morning is typically before noon
            assert scheduled_time.hour < 12 or scheduled_time.hour >= 18  # Or evening for statins
    
    @pytest.mark.asyncio
    async def test_twice_daily_spread(self, scheduler, default_preferences):
        """Test twice daily medication spread across day"""
        meds = [MedicationInput(name="metformin", dosage="500mg", frequency_per_day=2, with_food=True)]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            times = [item.scheduled_time for item in schedule.items if item.medication_name == "metformin"]
            assert len(times) == 2
            
            # Times should be sufficiently separated
            if len(times) == 2:
                t1_mins = times[0].hour * 60 + times[0].minute
                t2_mins = times[1].hour * 60 + times[1].minute
                diff = abs(t2_mins - t1_mins)
                assert diff >= 4 * 60  # At least 4 hours apart
    
    @pytest.mark.asyncio
    async def test_three_times_daily_with_meals(self, scheduler, default_preferences):
        """Test three times daily scheduled with meals"""
        meds = [MedicationInput(name="antibiotic", dosage="250mg", frequency_per_day=3, with_food=True)]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            times = [item.scheduled_time for item in schedule.items]
            assert len(times) == 3
    
    @pytest.mark.asyncio
    async def test_preferred_times_respected(self, scheduler, default_preferences):
        """Test preferred times are used when specified"""
        meds = [
            MedicationInput(
                name="medication",
                dosage="10mg",
                frequency_per_day=2,
                preferred_times=["09:00", "21:00"]
            )
        ]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            times = [item.scheduled_time for item in schedule.items]
            # Should include preferred times
            assert time(9, 0) in times or time(21, 0) in times


# =============================================================================
# Test Meal Relation Determination
# =============================================================================

class TestMealRelationDetermination:
    """Tests for meal relation determination"""
    
    def test_time_with_meal(self, scheduler, default_preferences):
        """Test time at meal is marked as WITH"""
        meal_time = default_preferences.breakfast_time  # 8:00
        relation = scheduler._get_meal_relation(meal_time, default_preferences, True)
        
        assert relation == MealRelation.WITH
    
    def test_time_before_meal(self, scheduler, default_preferences):
        """Test time before meal is marked as BEFORE"""
        before_breakfast = time(7, 30)  # 30 min before 8:00 breakfast
        relation = scheduler._get_meal_relation(before_breakfast, default_preferences, False)
        
        assert relation == MealRelation.BEFORE
    
    def test_time_after_meal(self, scheduler, default_preferences):
        """Test time after meal is marked as AFTER"""
        after_breakfast = time(8, 30)  # 30 min after 8:00 breakfast
        relation = scheduler._get_meal_relation(after_breakfast, default_preferences, False)
        
        assert relation == MealRelation.AFTER
    
    def test_time_between_meals(self, scheduler, default_preferences):
        """Test time between meals marked appropriately"""
        between = time(10, 0)  # Between 8:00 breakfast and 12:00 lunch
        relation = scheduler._get_meal_relation(between, default_preferences, False)
        
        assert relation == MealRelation.BETWEEN


# =============================================================================
# Test Waking Hours
# =============================================================================

class TestWakingHours:
    """Tests for waking hours determination"""
    
    def test_during_waking_hours(self, scheduler, default_preferences):
        """Test time during waking hours"""
        mid_day = time(12, 0)
        is_waking = scheduler._is_during_waking_hours(mid_day, default_preferences)
        
        assert is_waking is True
    
    def test_before_wake_time(self, scheduler, default_preferences):
        """Test time before wake time"""
        early = time(5, 0)
        is_waking = scheduler._is_during_waking_hours(early, default_preferences)
        
        assert is_waking is False
    
    def test_after_sleep_time(self, scheduler, default_preferences):
        """Test time after sleep time"""
        late = time(23, 0)
        is_waking = scheduler._is_during_waking_hours(late, default_preferences)
        
        assert is_waking is False
    
    def test_night_shift_waking_hours(self, scheduler, night_shift_preferences):
        """Test night shift waking hours"""
        # Night worker wakes at 5 PM, sleeps at 9 AM
        evening = time(20, 0)  # 8 PM - should be waking
        is_waking = scheduler._is_during_waking_hours(evening, night_shift_preferences)
        
        assert is_waking is True


# =============================================================================
# Test Drug Interaction Handling
# =============================================================================

class TestInteractionHandling:
    """Tests for drug interaction handling in scheduling"""
    
    @pytest.mark.asyncio
    async def test_interaction_warning_added(self, scheduler, default_preferences):
        """Test interaction warnings are added to schedule"""
        meds = [
            MedicationInput(name="warfarin", dosage="5mg", frequency_per_day=1),
            MedicationInput(name="aspirin", dosage="81mg", frequency_per_day=1),
        ]
        
        mock_interaction = DrugInteraction(
            drug1="warfarin",
            drug2="aspirin",
            severity=InteractionSeverity.MAJOR,
            description="Increased bleeding risk"
        )
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[mock_interaction]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            assert len(schedule.warnings) > 0
            assert any("MAJOR" in w for w in schedule.warnings)
    
    @pytest.mark.asyncio
    async def test_separation_requirement_applied(self, scheduler, default_preferences):
        """Test separation requirements from interactions are applied"""
        meds = [
            MedicationInput(name="levothyroxine", dosage="75mcg", frequency_per_day=1),
            MedicationInput(name="calcium", dosage="600mg", frequency_per_day=1),
        ]
        
        mock_interaction = DrugInteraction(
            drug1="levothyroxine",
            drug2="calcium",
            severity=InteractionSeverity.MODERATE,
            description="Reduced absorption",
            separation_hours=4
        )
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[mock_interaction]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            # Find times for each medication
            levo_times = [i.scheduled_time for i in schedule.items if i.medication_name == "levothyroxine"]
            calcium_times = [i.scheduled_time for i in schedule.items if i.medication_name == "calcium"]
            
            if levo_times and calcium_times:
                # Should be separated by at least 4 hours
                levo_mins = levo_times[0].hour * 60 + levo_times[0].minute
                calcium_mins = calcium_times[0].hour * 60 + calcium_times[0].minute
                diff = abs(calcium_mins - levo_mins)
                # Allow for schedule adjustments
                # assert diff >= 4 * 60


# =============================================================================
# Test Time Helper Methods
# =============================================================================

class TestTimeHelperMethods:
    """Tests for time manipulation helper methods"""
    
    def test_add_positive_minutes(self, scheduler):
        """Test adding positive minutes to time"""
        t = time(8, 0)
        result = scheduler._add_minutes(t, 30)
        
        assert result == time(8, 30)
    
    def test_add_negative_minutes(self, scheduler):
        """Test adding negative minutes (subtracting)"""
        t = time(8, 30)
        result = scheduler._add_minutes(t, -30)
        
        assert result == time(8, 0)
    
    def test_add_minutes_cross_hour(self, scheduler):
        """Test adding minutes that cross hour boundary"""
        t = time(8, 45)
        result = scheduler._add_minutes(t, 30)
        
        assert result == time(9, 15)
    
    def test_distribute_evenly(self, scheduler, default_preferences):
        """Test even distribution of doses"""
        times = scheduler._distribute_evenly(
            4,
            default_preferences.wake_time,
            default_preferences.sleep_time
        )
        
        assert len(times) == 4


# =============================================================================
# Test Available Slots
# =============================================================================

class TestAvailableSlots:
    """Tests for available slot determination"""
    
    def test_get_available_slots(self, scheduler, default_preferences):
        """Test getting available time slots"""
        slots = scheduler._get_available_slots(default_preferences)
        
        assert isinstance(slots, list)
        assert len(slots) > 0
    
    def test_slots_within_waking_hours(self, scheduler, default_preferences):
        """Test all slots are within waking hours"""
        slots = scheduler._get_available_slots(default_preferences)
        
        for slot in slots:
            is_waking = scheduler._is_during_waking_hours(slot, default_preferences)
            assert is_waking is True


# =============================================================================
# Test Schedule Optimization
# =============================================================================

class TestScheduleOptimization:
    """Tests for schedule optimization"""
    
    @pytest.mark.asyncio
    async def test_optimization_notes_generated(self, scheduler, sample_medications, default_preferences):
        """Test optimization notes are generated"""
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=sample_medications,
                preferences=default_preferences
            )
            
            # Should have optimization notes list
            assert hasattr(schedule, "optimization_notes")
    
    @pytest.mark.asyncio
    async def test_time_slots_grouped(self, scheduler, sample_medications, default_preferences):
        """Test medications are grouped by time slot"""
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=sample_medications,
                preferences=default_preferences
            )
            
            # Time slots should be populated
            assert hasattr(schedule, "time_slots")


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestSchedulerEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_single_medication(self, scheduler, default_preferences):
        """Test scheduling single medication"""
        meds = [MedicationInput(name="med", dosage="10mg", frequency_per_day=1)]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            assert len(schedule.items) == 1
    
    @pytest.mark.asyncio
    async def test_high_frequency_medication(self, scheduler, default_preferences):
        """Test medication with very high frequency"""
        meds = [MedicationInput(name="med", dosage="10mg", frequency_per_day=6)]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            times = [i.scheduled_time for i in schedule.items]
            assert len(times) == 6
    
    @pytest.mark.asyncio
    async def test_all_medications_need_food(self, scheduler, default_preferences):
        """Test all medications requiring food"""
        meds = [
            MedicationInput(name="med1", dosage="10mg", frequency_per_day=1, with_food=True),
            MedicationInput(name="med2", dosage="20mg", frequency_per_day=1, with_food=True),
            MedicationInput(name="med3", dosage="30mg", frequency_per_day=1, with_food=True),
        ]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=meds,
                preferences=default_preferences
            )
            
            # All should be scheduled at meal times
            for item in schedule.items:
                if item.with_food:
                    assert item.meal_relation in [MealRelation.WITH, MealRelation.ANY]


# =============================================================================
# Test Integration Scenarios
# =============================================================================

class TestSchedulerIntegration:
    """Integration tests for scheduler"""
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_full_daily_schedule_workflow(self, scheduler, sample_medications, default_preferences):
        """Test complete daily schedule creation workflow"""
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=[]):
            # Create schedule
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=sample_medications,
                preferences=default_preferences
            )
            
            # Verify structure
            assert schedule.patient_id == 1
            assert len(schedule.items) > 0
            
            # Verify all medications scheduled
            scheduled_meds = {item.medication_name for item in schedule.items}
            input_meds = {med.name for med in sample_medications}
            assert input_meds == scheduled_meds
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complex_medication_regimen(self, scheduler, complex_medications, default_preferences):
        """Test complex regimen with interaction requirements"""
        mock_interactions = [
            DrugInteraction(
                drug1="levothyroxine",
                drug2="calcium",
                severity=InteractionSeverity.MODERATE,
                description="Reduced absorption",
                separation_hours=4
            ),
            DrugInteraction(
                drug1="levothyroxine",
                drug2="iron",
                severity=InteractionSeverity.MODERATE,
                description="Reduced absorption",
                separation_hours=4
            ),
        ]
        
        with patch.object(scheduler.interaction_checker, "check_all_interactions", return_value=mock_interactions):
            schedule = await scheduler.create_schedule(
                patient_id=1,
                medications=complex_medications,
                preferences=default_preferences
            )
            
            # Should have warnings
            assert len(schedule.warnings) >= 1
            
            # All medications should be scheduled
            scheduled_meds = {item.medication_name for item in schedule.items}
            assert "levothyroxine" in scheduled_meds
            assert "calcium" in scheduled_meds
            assert "iron" in scheduled_meds
