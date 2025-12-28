"""
Reminder Engine
Generates and manages medication reminders and notifications
"""

import logging
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time
from enum import Enum
import uuid
from collections import defaultdict


logger = logging.getLogger(__name__)


class ReminderType(str, Enum):
    """Types of reminders"""
    MEDICATION_DUE = "medication_due"
    MEDICATION_UPCOMING = "medication_upcoming"
    REFILL_REMINDER = "refill_reminder"
    APPOINTMENT = "appointment"
    CHECK_IN = "check_in"
    FOLLOW_UP = "follow_up"
    CUSTOM = "custom"


class ReminderChannel(str, Enum):
    """Reminder delivery channels"""
    PUSH = "push"
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"
    VOICE = "voice"


class ReminderStatus(str, Enum):
    """Reminder status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    SNOOZED = "snoozed"
    DISMISSED = "dismissed"
    FAILED = "failed"


class ReminderPriority(str, Enum):
    """Reminder priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class ReminderPreferences:
    """User reminder preferences"""
    patient_id: int
    enabled: bool = True
    channels: List[ReminderChannel] = field(default_factory=lambda: [ReminderChannel.PUSH])
    quiet_hours_start: Optional[time] = None  # e.g., 22:00
    quiet_hours_end: Optional[time] = None    # e.g., 07:00
    advance_notice_minutes: int = 15
    snooze_duration_minutes: int = 10
    max_reminders_per_dose: int = 3
    language: str = "en"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "patient_id": self.patient_id,
            "enabled": self.enabled,
            "channels": [c.value for c in self.channels],
            "quiet_hours_start": self.quiet_hours_start.isoformat() if self.quiet_hours_start else None,
            "quiet_hours_end": self.quiet_hours_end.isoformat() if self.quiet_hours_end else None,
            "advance_notice_minutes": self.advance_notice_minutes,
            "snooze_duration_minutes": self.snooze_duration_minutes,
            "max_reminders_per_dose": self.max_reminders_per_dose,
            "language": self.language
        }
    
    def is_quiet_time(self, check_time: Optional[datetime] = None) -> bool:
        """Check if current time is within quiet hours"""
        if not self.quiet_hours_start or not self.quiet_hours_end:
            return False
        
        current = (check_time or datetime.now()).time()
        
        # Handle overnight quiet hours (e.g., 22:00 to 07:00)
        if self.quiet_hours_start > self.quiet_hours_end:
            return current >= self.quiet_hours_start or current <= self.quiet_hours_end
        else:
            return self.quiet_hours_start <= current <= self.quiet_hours_end


@dataclass
class Reminder:
    """Reminder data structure"""
    id: str
    patient_id: int
    reminder_type: ReminderType
    title: str
    message: str
    scheduled_time: datetime
    status: ReminderStatus = ReminderStatus.PENDING
    priority: ReminderPriority = ReminderPriority.NORMAL
    channels: List[ReminderChannel] = field(default_factory=lambda: [ReminderChannel.PUSH])
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    snooze_until: Optional[datetime] = None
    attempt_count: int = 0
    max_attempts: int = 3
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "reminder_type": self.reminder_type.value,
            "title": self.title,
            "message": self.message,
            "scheduled_time": self.scheduled_time.isoformat(),
            "status": self.status.value,
            "priority": self.priority.value,
            "channels": [c.value for c in self.channels],
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "snooze_until": self.snooze_until.isoformat() if self.snooze_until else None,
            "attempt_count": self.attempt_count,
            "metadata": self.metadata
        }
    
    def is_due(self, current_time: Optional[datetime] = None) -> bool:
        """Check if reminder is due"""
        now = current_time or datetime.utcnow()
        
        if self.status != ReminderStatus.PENDING:
            return False
        
        if self.snooze_until and now < self.snooze_until:
            return False
        
        return now >= self.scheduled_time
    
    def snooze(self, minutes: int):
        """Snooze the reminder"""
        self.snooze_until = datetime.utcnow() + timedelta(minutes=minutes)
        self.status = ReminderStatus.SNOOZED
    
    def mark_sent(self):
        """Mark reminder as sent"""
        self.status = ReminderStatus.SENT
        self.sent_at = datetime.utcnow()
        self.attempt_count += 1
    
    def acknowledge(self):
        """Acknowledge the reminder"""
        self.status = ReminderStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
    
    def dismiss(self):
        """Dismiss the reminder"""
        self.status = ReminderStatus.DISMISSED


class ReminderEngine:
    """
    Engine for generating and managing medication reminders
    
    Responsibilities:
    - Schedule reminders for medications
    - Handle reminder delivery
    - Manage reminder lifecycle
    - Support snoozing and dismissing
    - Track reminder effectiveness
    """
    
    def __init__(self):
        self._reminders: Dict[str, Reminder] = {}
        self._patient_reminders: Dict[int, List[str]] = defaultdict(list)
        self._preferences: Dict[int, ReminderPreferences] = {}
        self._delivery_handlers: Dict[ReminderChannel, Callable] = {}
        
        # Message templates
        self._templates = {
            ReminderType.MEDICATION_DUE: {
                "title": "Time for {medication_name}",
                "message": "It's time to take your {medication_name} ({dosage}). {instructions}"
            },
            ReminderType.MEDICATION_UPCOMING: {
                "title": "Upcoming: {medication_name}",
                "message": "Reminder: Take {medication_name} in {minutes} minutes."
            },
            ReminderType.REFILL_REMINDER: {
                "title": "Refill Needed: {medication_name}",
                "message": "Your {medication_name} supply is running low ({days_remaining} days left). Please arrange a refill."
            },
            ReminderType.CHECK_IN: {
                "title": "How are you feeling?",
                "message": "Time for your daily check-in. How are your medications working for you?"
            },
            ReminderType.FOLLOW_UP: {
                "title": "Follow-up Reminder",
                "message": "{message}"
            }
        }
    
    def _generate_id(self) -> str:
        """Generate unique reminder ID"""
        return str(uuid.uuid4())[:8]
    
    def set_preferences(
        self,
        patient_id: int,
        preferences: ReminderPreferences
    ):
        """Set reminder preferences for a patient"""
        self._preferences[patient_id] = preferences
        logger.info(f"Set reminder preferences for patient {patient_id}")
    
    def get_preferences(self, patient_id: int) -> ReminderPreferences:
        """Get reminder preferences for a patient"""
        if patient_id not in self._preferences:
            self._preferences[patient_id] = ReminderPreferences(patient_id=patient_id)
        return self._preferences[patient_id]
    
    def register_delivery_handler(
        self,
        channel: ReminderChannel,
        handler: Callable[[Reminder], bool]
    ):
        """Register a delivery handler for a channel"""
        self._delivery_handlers[channel] = handler
        logger.info(f"Registered delivery handler for {channel.value}")
    
    def _format_message(
        self,
        template_type: ReminderType,
        **kwargs
    ) -> tuple:
        """Format reminder message from template"""
        template = self._templates.get(template_type, {})
        title = template.get("title", "Medication Reminder")
        message = template.get("message", "")
        
        try:
            title = title.format(**kwargs)
            message = message.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
        
        return title, message
    
    def create_medication_reminder(
        self,
        patient_id: int,
        medication_name: str,
        dosage: str,
        scheduled_time: datetime,
        instructions: str = "",
        is_critical: bool = False
    ) -> Reminder:
        """Create a medication due reminder"""
        prefs = self.get_preferences(patient_id)
        
        title, message = self._format_message(
            ReminderType.MEDICATION_DUE,
            medication_name=medication_name,
            dosage=dosage,
            instructions=instructions
        )
        
        priority = ReminderPriority.HIGH if is_critical else ReminderPriority.NORMAL
        
        reminder = Reminder(
            id=self._generate_id(),
            patient_id=patient_id,
            reminder_type=ReminderType.MEDICATION_DUE,
            title=title,
            message=message,
            scheduled_time=scheduled_time,
            priority=priority,
            channels=prefs.channels.copy(),
            max_attempts=prefs.max_reminders_per_dose,
            metadata={
                "medication_name": medication_name,
                "dosage": dosage,
                "is_critical": is_critical
            }
        )
        
        self._add_reminder(reminder)
        return reminder
    
    def create_advance_reminder(
        self,
        patient_id: int,
        medication_name: str,
        dose_time: datetime,
        advance_minutes: Optional[int] = None
    ) -> Reminder:
        """Create an advance reminder before medication is due"""
        prefs = self.get_preferences(patient_id)
        minutes = advance_minutes or prefs.advance_notice_minutes
        
        title, message = self._format_message(
            ReminderType.MEDICATION_UPCOMING,
            medication_name=medication_name,
            minutes=minutes
        )
        
        reminder = Reminder(
            id=self._generate_id(),
            patient_id=patient_id,
            reminder_type=ReminderType.MEDICATION_UPCOMING,
            title=title,
            message=message,
            scheduled_time=dose_time - timedelta(minutes=minutes),
            priority=ReminderPriority.LOW,
            channels=prefs.channels.copy(),
            max_attempts=1,
            metadata={
                "medication_name": medication_name,
                "dose_time": dose_time.isoformat()
            }
        )
        
        self._add_reminder(reminder)
        return reminder
    
    def create_refill_reminder(
        self,
        patient_id: int,
        medication_name: str,
        days_remaining: int
    ) -> Reminder:
        """Create a refill reminder"""
        prefs = self.get_preferences(patient_id)
        
        title, message = self._format_message(
            ReminderType.REFILL_REMINDER,
            medication_name=medication_name,
            days_remaining=days_remaining
        )
        
        # Schedule for morning
        scheduled = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        if scheduled < datetime.now():
            scheduled += timedelta(days=1)
        
        priority = ReminderPriority.HIGH if days_remaining <= 3 else ReminderPriority.NORMAL
        
        reminder = Reminder(
            id=self._generate_id(),
            patient_id=patient_id,
            reminder_type=ReminderType.REFILL_REMINDER,
            title=title,
            message=message,
            scheduled_time=scheduled,
            priority=priority,
            channels=prefs.channels.copy(),
            metadata={
                "medication_name": medication_name,
                "days_remaining": days_remaining
            }
        )
        
        self._add_reminder(reminder)
        return reminder
    
    def create_check_in_reminder(
        self,
        patient_id: int,
        scheduled_time: datetime
    ) -> Reminder:
        """Create a daily check-in reminder"""
        prefs = self.get_preferences(patient_id)
        
        title, message = self._format_message(ReminderType.CHECK_IN)
        
        reminder = Reminder(
            id=self._generate_id(),
            patient_id=patient_id,
            reminder_type=ReminderType.CHECK_IN,
            title=title,
            message=message,
            scheduled_time=scheduled_time,
            priority=ReminderPriority.LOW,
            channels=prefs.channels.copy()
        )
        
        self._add_reminder(reminder)
        return reminder
    
    def create_custom_reminder(
        self,
        patient_id: int,
        title: str,
        message: str,
        scheduled_time: datetime,
        priority: ReminderPriority = ReminderPriority.NORMAL
    ) -> Reminder:
        """Create a custom reminder"""
        prefs = self.get_preferences(patient_id)
        
        reminder = Reminder(
            id=self._generate_id(),
            patient_id=patient_id,
            reminder_type=ReminderType.CUSTOM,
            title=title,
            message=message,
            scheduled_time=scheduled_time,
            priority=priority,
            channels=prefs.channels.copy()
        )
        
        self._add_reminder(reminder)
        return reminder
    
    def _add_reminder(self, reminder: Reminder):
        """Add reminder to storage"""
        self._reminders[reminder.id] = reminder
        self._patient_reminders[reminder.patient_id].append(reminder.id)
        logger.info(f"Created reminder {reminder.id}: {reminder.title}")
    
    def get_reminder(self, reminder_id: str) -> Optional[Reminder]:
        """Get reminder by ID"""
        return self._reminders.get(reminder_id)
    
    def get_patient_reminders(
        self,
        patient_id: int,
        status: Optional[ReminderStatus] = None,
        reminder_type: Optional[ReminderType] = None
    ) -> List[Reminder]:
        """Get reminders for a patient"""
        reminder_ids = self._patient_reminders.get(patient_id, [])
        reminders = [self._reminders[rid] for rid in reminder_ids if rid in self._reminders]
        
        if status:
            reminders = [r for r in reminders if r.status == status]
        if reminder_type:
            reminders = [r for r in reminders if r.reminder_type == reminder_type]
        
        reminders.sort(key=lambda r: r.scheduled_time)
        return reminders
    
    def get_due_reminders(
        self,
        patient_id: Optional[int] = None
    ) -> List[Reminder]:
        """Get all due reminders"""
        now = datetime.utcnow()
        
        if patient_id:
            reminders = self.get_patient_reminders(patient_id)
        else:
            reminders = list(self._reminders.values())
        
        due = []
        for reminder in reminders:
            if reminder.is_due(now):
                # Check quiet hours
                prefs = self.get_preferences(reminder.patient_id)
                if not prefs.is_quiet_time():
                    due.append(reminder)
        
        return due
    
    def get_upcoming_reminders(
        self,
        patient_id: int,
        hours: int = 24
    ) -> List[Reminder]:
        """Get upcoming reminders within specified hours"""
        now = datetime.utcnow()
        cutoff = now + timedelta(hours=hours)
        
        reminders = self.get_patient_reminders(patient_id, status=ReminderStatus.PENDING)
        return [r for r in reminders if now <= r.scheduled_time <= cutoff]
    
    def snooze_reminder(
        self,
        reminder_id: str,
        minutes: Optional[int] = None
    ) -> bool:
        """Snooze a reminder"""
        reminder = self.get_reminder(reminder_id)
        if not reminder:
            return False
        
        prefs = self.get_preferences(reminder.patient_id)
        snooze_minutes = minutes or prefs.snooze_duration_minutes
        
        reminder.snooze(snooze_minutes)
        logger.info(f"Reminder {reminder_id} snoozed for {snooze_minutes} minutes")
        return True
    
    def acknowledge_reminder(self, reminder_id: str) -> bool:
        """Acknowledge a reminder"""
        reminder = self.get_reminder(reminder_id)
        if reminder:
            reminder.acknowledge()
            logger.info(f"Reminder {reminder_id} acknowledged")
            return True
        return False
    
    def dismiss_reminder(self, reminder_id: str) -> bool:
        """Dismiss a reminder"""
        reminder = self.get_reminder(reminder_id)
        if reminder:
            reminder.dismiss()
            logger.info(f"Reminder {reminder_id} dismissed")
            return True
        return False
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a reminder"""
        if reminder_id in self._reminders:
            reminder = self._reminders[reminder_id]
            del self._reminders[reminder_id]
            
            if reminder.patient_id in self._patient_reminders:
                self._patient_reminders[reminder.patient_id].remove(reminder_id)
            
            logger.info(f"Reminder {reminder_id} cancelled")
            return True
        return False
    
    def send_reminder(self, reminder: Reminder) -> bool:
        """Send a reminder through registered channels"""
        prefs = self.get_preferences(reminder.patient_id)
        
        if not prefs.enabled:
            logger.info(f"Reminders disabled for patient {reminder.patient_id}")
            return False
        
        if prefs.is_quiet_time():
            logger.info(f"Quiet hours active for patient {reminder.patient_id}")
            return False
        
        if reminder.attempt_count >= reminder.max_attempts:
            reminder.status = ReminderStatus.FAILED
            logger.warning(f"Max attempts reached for reminder {reminder.id}")
            return False
        
        success = False
        
        for channel in reminder.channels:
            handler = self._delivery_handlers.get(channel)
            if handler:
                try:
                    if handler(reminder):
                        success = True
                        logger.info(f"Reminder {reminder.id} sent via {channel.value}")
                except Exception as e:
                    logger.error(f"Failed to send via {channel.value}: {e}")
        
        if success:
            reminder.mark_sent()
        else:
            reminder.attempt_count += 1
            if reminder.attempt_count >= reminder.max_attempts:
                reminder.status = ReminderStatus.FAILED
        
        return success
    
    def process_due_reminders(self) -> int:
        """Process all due reminders"""
        due_reminders = self.get_due_reminders()
        sent_count = 0
        
        for reminder in due_reminders:
            if self.send_reminder(reminder):
                sent_count += 1
        
        return sent_count
    
    def get_reminder_stats(self, patient_id: int) -> Dict[str, Any]:
        """Get reminder statistics for a patient"""
        reminders = self.get_patient_reminders(patient_id)
        
        stats = {
            "total": len(reminders),
            "by_status": {},
            "by_type": {},
            "acknowledged_rate": 0.0
        }
        
        acknowledged = 0
        sent = 0
        
        for reminder in reminders:
            # By status
            status = reminder.status.value
            stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
            
            # By type
            rtype = reminder.reminder_type.value
            stats["by_type"][rtype] = stats["by_type"].get(rtype, 0) + 1
            
            # Track acknowledgment rate
            if reminder.status in [ReminderStatus.SENT, ReminderStatus.DELIVERED, 
                                   ReminderStatus.ACKNOWLEDGED, ReminderStatus.DISMISSED]:
                sent += 1
                if reminder.status == ReminderStatus.ACKNOWLEDGED:
                    acknowledged += 1
        
        if sent > 0:
            stats["acknowledged_rate"] = (acknowledged / sent) * 100
        
        return stats
    
    def clear_old_reminders(self, days: int = 30):
        """Clear reminders older than specified days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        to_remove = []
        
        for reminder_id, reminder in self._reminders.items():
            if reminder.created_at < cutoff and reminder.status in [
                ReminderStatus.ACKNOWLEDGED, 
                ReminderStatus.DISMISSED, 
                ReminderStatus.FAILED
            ]:
                to_remove.append(reminder_id)
        
        for reminder_id in to_remove:
            reminder = self._reminders[reminder_id]
            del self._reminders[reminder_id]
            if reminder.patient_id in self._patient_reminders:
                self._patient_reminders[reminder.patient_id].remove(reminder_id)
        
        logger.info(f"Cleared {len(to_remove)} old reminders")


# Singleton instance
reminder_engine = ReminderEngine()
