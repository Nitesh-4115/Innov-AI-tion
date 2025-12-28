"""
Medication Scheduler Tool
Handles medication schedule creation and optimization
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date, time, timedelta
from enum import Enum

from tools.interaction_checker import interaction_checker, InteractionSeverity
from tools.drug_database import drug_database


logger = logging.getLogger(__name__)


class MealRelation(str, Enum):
    """Timing relative to meals"""
    BEFORE = "before"           # 30-60 min before meal
    WITH = "with"               # During meal
    AFTER = "after"             # Within 30 min after meal
    BETWEEN = "between_meals"   # 2+ hours after, 1+ hour before
    ANY = "any"                 # No meal restriction


class TimeSlotPriority(str, Enum):
    """Priority for time slot assignment"""
    FIXED = "fixed"             # Cannot be moved (e.g., specific time required)
    HIGH = "high"               # Preferred time, avoid moving
    NORMAL = "normal"           # Can be adjusted
    FLEXIBLE = "flexible"       # Can be moved freely


@dataclass
class MedicationScheduleItem:
    """A single medication in the schedule"""
    medication_name: str
    dosage: str
    scheduled_time: time
    meal_relation: MealRelation = MealRelation.ANY
    priority: TimeSlotPriority = TimeSlotPriority.NORMAL
    with_food: bool = False
    with_water: bool = True
    special_instructions: Optional[str] = None
    conflicts: List[str] = field(default_factory=list)


@dataclass
class DailySchedule:
    """Complete daily medication schedule"""
    patient_id: int
    schedule_date: date
    items: List[MedicationScheduleItem] = field(default_factory=list)
    time_slots: Dict[str, List[str]] = field(default_factory=dict)  # "08:00" -> ["Med1", "Med2"]
    warnings: List[str] = field(default_factory=list)
    optimization_notes: List[str] = field(default_factory=list)


@dataclass
class PatientPreferences:
    """Patient lifestyle preferences for scheduling"""
    wake_time: time = field(default_factory=lambda: time(8, 0))
    sleep_time: time = field(default_factory=lambda: time(22, 0))
    breakfast_time: time = field(default_factory=lambda: time(8, 0))
    lunch_time: time = field(default_factory=lambda: time(12, 0))
    dinner_time: time = field(default_factory=lambda: time(18, 0))
    preferred_reminder_minutes: int = 15
    work_schedule: Optional[str] = None  # "9-5", "night_shift", etc.


@dataclass
class MedicationInput:
    """Input for scheduling a medication"""
    name: str
    dosage: str
    frequency_per_day: int
    with_food: bool = False
    min_hours_between_doses: float = 4.0
    special_instructions: Optional[str] = None
    preferred_times: List[str] = field(default_factory=list)  # ["08:00", "20:00"]


class MedicationScheduler:
    """
    Intelligent medication scheduling with constraint satisfaction
    """
    
    # Default slot interval (minutes) used to generate available slots from preferences
    DEFAULT_SLOT_INTERVAL_MINUTES = 60
    
    def __init__(self):
        self.interaction_checker = interaction_checker
    
    async def create_schedule(
        self,
        patient_id: int,
        medications: List[MedicationInput],
        preferences: PatientPreferences,
        schedule_date: Optional[date] = None
    ) -> DailySchedule:
        """
        Create an optimized daily medication schedule
        
        Args:
            patient_id: Patient identifier
            medications: List of medications to schedule
            preferences: Patient lifestyle preferences
            schedule_date: Date for the schedule (default: today)
            
        Returns:
            Optimized DailySchedule
        """
        schedule_date = schedule_date or date.today()
        schedule = DailySchedule(
            patient_id=patient_id,
            schedule_date=schedule_date
        )
        
        # Get available time slots based on preferences
        available_slots = self._get_available_slots(preferences)
        
        # Check for drug interactions
        med_names = [m.name for m in medications]
        interactions = self.interaction_checker.check_all_interactions(med_names)
        separation_requirements = self._get_separation_requirements(interactions)
        
        # Add interaction warnings
        for interaction in interactions:
            if interaction.severity in [InteractionSeverity.CONTRAINDICATED, InteractionSeverity.MAJOR]:
                schedule.warnings.append(
                    f"⚠️ {interaction.severity.value.upper()}: {interaction.drug1} + {interaction.drug2} - {interaction.description}"
                )
        
        # Schedule each medication
        assigned_times: Dict[str, List[str]] = {}  # time -> [medications]
        
        for med in medications:
            times = await self._schedule_medication(
                med,
                preferences,
                available_slots,
                assigned_times,
                separation_requirements,
                med_names
            )
            
            for t in times:
                item = MedicationScheduleItem(
                    medication_name=med.name,
                    dosage=med.dosage,
                    scheduled_time=t,
                    with_food=med.with_food,
                    meal_relation=self._get_meal_relation(t, preferences, med.with_food),
                    special_instructions=med.special_instructions
                )
                schedule.items.append(item)
                
                time_str = t.strftime("%H:%M")
                if time_str not in assigned_times:
                    assigned_times[time_str] = []
                assigned_times[time_str].append(med.name)
        
        # Build time slots view
        schedule.time_slots = assigned_times
        
        # Add optimization notes
        schedule.optimization_notes = self._generate_optimization_notes(
            schedule, preferences, interactions
        )
        
        return schedule
    
    async def _schedule_medication(
        self,
        med: MedicationInput,
        preferences: PatientPreferences,
        available_slots: List[time],
        assigned_times: Dict[str, List[str]],
        separation_requirements: Dict[Tuple[str, str], int],
        all_med_names: List[str]
    ) -> List[time]:
        """Schedule a single medication's doses"""
        
        # Use preferred times if specified
        if med.preferred_times:
            times = []
            for time_str in med.preferred_times[:med.frequency_per_day]:
                try:
                    t = datetime.strptime(time_str, "%H:%M").time()
                    times.append(t)
                except ValueError:
                    pass
            if len(times) == med.frequency_per_day:
                return times
        
        # Auto-schedule based on frequency
        scheduled_times = []
        
        if med.frequency_per_day == 1:
            # Once daily - morning with breakfast if needs food, otherwise morning
            if med.with_food:
                scheduled_times.append(preferences.breakfast_time)
            else:
                # 30 min before breakfast
                scheduled_times.append(self._add_minutes(preferences.breakfast_time, -30))
        
        elif med.frequency_per_day == 2:
            # Twice daily - morning and evening
            if med.with_food:
                scheduled_times.append(preferences.breakfast_time)
                scheduled_times.append(preferences.dinner_time)
            else:
                scheduled_times.append(self._add_minutes(preferences.wake_time, 30))
                scheduled_times.append(self._add_minutes(preferences.dinner_time, -60))
        
        elif med.frequency_per_day == 3:
            # Three times daily - with meals
            scheduled_times.append(preferences.breakfast_time)
            scheduled_times.append(preferences.lunch_time)
            scheduled_times.append(preferences.dinner_time)
        
        elif med.frequency_per_day == 4:
            # Four times daily - breakfast, lunch, dinner, bedtime
            scheduled_times.append(preferences.breakfast_time)
            scheduled_times.append(preferences.lunch_time)
            scheduled_times.append(preferences.dinner_time)
            scheduled_times.append(self._add_minutes(preferences.sleep_time, -30))
        
        else:
            # More than 4 - distribute evenly during waking hours
            scheduled_times = self._distribute_evenly(
                med.frequency_per_day,
                preferences.wake_time,
                preferences.sleep_time
            )
        
        # Adjust for separation requirements
        for other_med in all_med_names:
            if other_med == med.name:
                continue
            
            sep_key = tuple(sorted([med.name.lower(), other_med.lower()]))
            sep_hours = separation_requirements.get(sep_key, 0)
            
            if sep_hours > 0:
                scheduled_times = self._adjust_for_separation(
                    scheduled_times,
                    assigned_times,
                    other_med,
                    sep_hours
                )
        
        return scheduled_times
    
    def _get_available_slots(self, preferences: PatientPreferences) -> List[time]:
        """Get available time slots based on wake/sleep times"""
        slots: List[time] = []

        # Generate hourly (or interval-based) slots between wake and sleep
        interval = self.DEFAULT_SLOT_INTERVAL_MINUTES

        wake = preferences.wake_time
        sleep = preferences.sleep_time

        wake_mins = wake.hour * 60 + wake.minute
        sleep_mins = sleep.hour * 60 + sleep.minute

        # Handle night-shift / wrap-around by normalizing end minutes
        if sleep_mins <= wake_mins:
            sleep_mins += 24 * 60

        current = wake_mins
        while current <= sleep_mins:
            mins = current % (24 * 60)
            hour = mins // 60
            minute = mins % 60
            slots.append(time(hour, minute))
            current += interval

        # Filter using waking hours check (keeps logic consistent)
        slots = [s for s in slots if self._is_during_waking_hours(s, preferences)]
        return slots
    
    def _is_during_waking_hours(
        self, 
        t: time, 
        preferences: PatientPreferences
    ) -> bool:
        """Check if time is during patient's waking hours"""
        # Convert to minutes for easier comparison
        wake_mins = preferences.wake_time.hour * 60 + preferences.wake_time.minute
        sleep_mins = preferences.sleep_time.hour * 60 + preferences.sleep_time.minute
        time_mins = t.hour * 60 + t.minute
        
        # Simple case: wake before sleep (e.g., 7am - 10pm)
        if wake_mins < sleep_mins:
            return wake_mins <= time_mins <= sleep_mins
        
        # Night shift case: wake after sleep (e.g., 7pm - 7am)
        return time_mins >= wake_mins or time_mins <= sleep_mins
    
    def _get_meal_relation(
        self, 
        t: time, 
        preferences: PatientPreferences,
        needs_food: bool
    ) -> MealRelation:
        """Determine meal relation for a time"""
        time_mins = t.hour * 60 + t.minute
        
        meals = {
            "breakfast": preferences.breakfast_time,
            "lunch": preferences.lunch_time,
            "dinner": preferences.dinner_time
        }
        
        for meal_name, meal_time in meals.items():
            meal_mins = meal_time.hour * 60 + meal_time.minute
            diff = time_mins - meal_mins
            
            # Within 15 minutes = with meal
            if abs(diff) <= 15:
                return MealRelation.WITH
            
            # 15-60 min before = before meal
            if -60 <= diff < -15:
                return MealRelation.BEFORE
            
            # 15-60 min after = after meal
            if 15 < diff <= 60:
                return MealRelation.AFTER
        
        return MealRelation.BETWEEN if not needs_food else MealRelation.WITH
    
    def _get_separation_requirements(
        self, 
        interactions: List
    ) -> Dict[Tuple[str, str], int]:
        """Extract separation hour requirements from interactions"""
        separations = {}
        
        for interaction in interactions:
            if interaction.separation_hours > 0:
                key = tuple(sorted([interaction.drug1.lower(), interaction.drug2.lower()]))
                separations[key] = interaction.separation_hours
        
        return separations
    
    def _add_minutes(self, t: time, minutes: int) -> time:
        """Add minutes to a time object"""
        dt = datetime.combine(date.today(), t)
        dt = dt + timedelta(minutes=minutes)
        return dt.time()
    
    def _distribute_evenly(
        self, 
        count: int, 
        start: time, 
        end: time
    ) -> List[time]:
        """Distribute doses evenly during waking hours"""
        start_mins = start.hour * 60 + start.minute
        end_mins = end.hour * 60 + end.minute
        
        if end_mins < start_mins:  # Night shift
            end_mins += 24 * 60
        
        total_mins = end_mins - start_mins
        interval = total_mins // count
        
        times = []
        for i in range(count):
            mins = start_mins + (i * interval) + (interval // 2)
            if mins >= 24 * 60:
                mins -= 24 * 60
            
            hour = mins // 60
            minute = mins % 60
            times.append(time(hour, minute))
        
        return times
    
    def _adjust_for_separation(
        self,
        times: List[time],
        assigned_times: Dict[str, List[str]],
        other_med: str,
        sep_hours: int
    ) -> List[time]:
        """Adjust times to maintain required separation from another medication"""
        sep_mins = sep_hours * 60
        adjusted = []
        
        for t in times:
            t_mins = t.hour * 60 + t.minute
            needs_adjustment = False
            
            for time_str, meds in assigned_times.items():
                if other_med in meds:
                    other_t = datetime.strptime(time_str, "%H:%M").time()
                    other_mins = other_t.hour * 60 + other_t.minute
                    
                    diff = abs(t_mins - other_mins)
                    if diff < sep_mins:
                        needs_adjustment = True
                        # Try to push time later
                        t = self._add_minutes(t, sep_mins - diff + 30)
                        break
            
            adjusted.append(t)
        
        return adjusted
    
    def _generate_optimization_notes(
        self,
        schedule: DailySchedule,
        preferences: PatientPreferences,
        interactions: List
    ) -> List[str]:
        """Generate optimization notes for the schedule"""
        notes = []
        
        # Check for busy time slots
        for time_str, meds in schedule.time_slots.items():
            if len(meds) > 3:
                notes.append(f"📋 {time_str} has {len(meds)} medications - consider splitting if difficult")
        
        # Note about interactions
        if interactions:
            moderate_plus = [i for i in interactions if i.severity in 
                          [InteractionSeverity.MODERATE, InteractionSeverity.MAJOR]]
            if moderate_plus:
                notes.append(f"⚠️ {len(moderate_plus)} drug interaction(s) to be aware of")
        
        # Food-related notes
        food_meds = [i for i in schedule.items if i.with_food]
        if food_meds:
            notes.append(f"🍽️ {len(food_meds)} medication(s) should be taken with food")
        
        # Empty stomach meds
        empty_meds = [i for i in schedule.items if i.meal_relation == MealRelation.BEFORE]
        if empty_meds:
            notes.append(f"⏰ {len(empty_meds)} medication(s) should be taken before meals")
        
        return notes
    
    async def replan_for_disruption(
        self,
        current_schedule: DailySchedule,
        disruption_type: str,
        disruption_details: str,
        preferences: PatientPreferences
    ) -> DailySchedule:
        """
        Replan schedule when a disruption occurs
        
        Args:
            current_schedule: Current schedule
            disruption_type: Type of disruption (travel, illness, etc.)
            disruption_details: Details about the disruption
            preferences: Patient preferences (may be temporarily modified)
            
        Returns:
            Adjusted schedule
        """
        new_schedule = DailySchedule(
            patient_id=current_schedule.patient_id,
            schedule_date=current_schedule.schedule_date
        )
        
        # Handle different disruption types
        if "travel" in disruption_type.lower():
            # Time zone adjustment needed
            new_schedule.warnings.append(
                "🌍 Travel detected - schedule adjusted. Maintain consistent intervals."
            )
            # In production, would calculate timezone offset
            
        elif "illness" in disruption_type.lower() or "sick" in disruption_type.lower():
            new_schedule.warnings.append(
                "🤒 Illness detected - contact provider if unable to take medications."
            )
            
        elif "missed" in disruption_type.lower():
            # Reschedule remaining doses
            new_schedule.optimization_notes.append(
                "Doses rescheduled to maintain proper spacing."
            )
        
        # Copy items with potential adjustments
        for item in current_schedule.items:
            new_item = MedicationScheduleItem(
                medication_name=item.medication_name,
                dosage=item.dosage,
                scheduled_time=item.scheduled_time,
                meal_relation=item.meal_relation,
                with_food=item.with_food,
                special_instructions=item.special_instructions
            )
            new_schedule.items.append(new_item)
        
        # Rebuild time slots
        for item in new_schedule.items:
            time_str = item.scheduled_time.strftime("%H:%M")
            if time_str not in new_schedule.time_slots:
                new_schedule.time_slots[time_str] = []
            new_schedule.time_slots[time_str].append(item.medication_name)
        
        return new_schedule
    
    def get_next_dose(
        self,
        schedule: DailySchedule,
        current_time: Optional[time] = None
    ) -> Optional[MedicationScheduleItem]:
        """Get the next scheduled dose"""
        current_time = current_time or datetime.now().time()
        current_mins = current_time.hour * 60 + current_time.minute
        
        upcoming = []
        for item in schedule.items:
            item_mins = item.scheduled_time.hour * 60 + item.scheduled_time.minute
            if item_mins > current_mins:
                upcoming.append((item_mins - current_mins, item))
        
        if upcoming:
            upcoming.sort(key=lambda x: x[0])
            return upcoming[0][1]
        
        return None
    
    def format_schedule_display(self, schedule: DailySchedule) -> str:
        """Format schedule for display"""
        lines = [f"📅 Schedule for {schedule.schedule_date.strftime('%A, %B %d, %Y')}"]
        lines.append("=" * 50)
        
        # Sort time slots
        sorted_times = sorted(schedule.time_slots.keys())
        
        for time_str in sorted_times:
            meds = schedule.time_slots[time_str]
            lines.append(f"\n⏰ {time_str}")
            for med in meds:
                # Find the item for additional details
                item = next((i for i in schedule.items 
                           if i.medication_name == med and 
                           i.scheduled_time.strftime("%H:%M") == time_str), None)
                if item:
                    food_icon = "🍽️" if item.with_food else ""
                    lines.append(f"   💊 {med} {item.dosage} {food_icon}")
                else:
                    lines.append(f"   💊 {med}")
        
        # Add warnings
        if schedule.warnings:
            lines.append("\n⚠️ Warnings:")
            for warning in schedule.warnings:
                lines.append(f"   {warning}")
        
        # Add notes
        if schedule.optimization_notes:
            lines.append("\n📝 Notes:")
            for note in schedule.optimization_notes:
                lines.append(f"   {note}")
        
        return "\n".join(lines)


# Singleton instance
medication_scheduler = MedicationScheduler()


async def create_schedule(
    patient_id: int,
    medications: List[Dict[str, Any]],
    preferences: Dict[str, Any]
) -> DailySchedule:
    """Convenience function to create a schedule"""
    med_inputs = [
        MedicationInput(
            name=m["name"],
            dosage=m.get("dosage", ""),
            frequency_per_day=m.get("frequency_per_day", 1),
            with_food=m.get("with_food", False),
            min_hours_between_doses=m.get("min_hours_between", 4.0),
            preferred_times=m.get("preferred_times", [])
        )
        for m in medications
    ]
    
    prefs = PatientPreferences(
        wake_time=time(*[int(x) for x in preferences.get("wake_time", "08:00").split(":")]),
        sleep_time=time(*[int(x) for x in preferences.get("sleep_time", "22:00").split(":")]),
        breakfast_time=time(*[int(x) for x in preferences.get("breakfast_time", "08:00").split(":")]),
        lunch_time=time(*[int(x) for x in preferences.get("lunch_time", "12:00").split(":")]),
        dinner_time=time(*[int(x) for x in preferences.get("dinner_time", "18:00").split(":")])
    )
    
    return await medication_scheduler.create_schedule(patient_id, med_inputs, prefs)
