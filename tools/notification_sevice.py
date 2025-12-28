"""
Notification Service Tool
Handles multi-channel notifications (SMS, Email, Push)
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from config import settings


logger = logging.getLogger(__name__)


class NotificationChannel(str, Enum):
    """Available notification channels"""
    SMS = "sms"
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    VOICE = "voice"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    CRITICAL = "critical"    # Emergency, immediate delivery
    HIGH = "high"            # Important, deliver ASAP
    NORMAL = "normal"        # Standard delivery
    LOW = "low"              # Can be batched/delayed


class NotificationType(str, Enum):
    """Types of notifications"""
    MEDICATION_REMINDER = "medication_reminder"
    MISSED_DOSE_ALERT = "missed_dose_alert"
    REFILL_REMINDER = "refill_reminder"
    APPOINTMENT_REMINDER = "appointment_reminder"
    SYMPTOM_CHECK_IN = "symptom_check_in"
    ADHERENCE_REPORT = "adherence_report"
    PROVIDER_MESSAGE = "provider_message"
    SYSTEM_ALERT = "system_alert"
    ENCOURAGEMENT = "encouragement"


@dataclass
class NotificationResult:
    """Result of sending a notification"""
    success: bool
    channel: NotificationChannel
    message_id: Optional[str] = None
    delivered_at: Optional[datetime] = None
    error: Optional[str] = None


@dataclass
class NotificationRequest:
    """Notification request details"""
    patient_id: int
    notification_type: NotificationType
    title: str
    message: str
    channels: List[NotificationChannel] = field(default_factory=list)
    priority: NotificationPriority = NotificationPriority.NORMAL
    data: Dict[str, Any] = field(default_factory=dict)
    scheduled_time: Optional[datetime] = None
    expires_at: Optional[datetime] = None


# Notification templates
NOTIFICATION_TEMPLATES: Dict[NotificationType, Dict[str, str]] = {
    NotificationType.MEDICATION_REMINDER: {
        "title": "Medication Reminder",
        "sms": "Time to take your {medication}. {instructions}",
        "email_subject": "Medication Reminder - {medication}",
        "email_body": """
Hi {patient_name},

This is a reminder to take your medication:

💊 **{medication}** - {dosage}
⏰ Scheduled for: {scheduled_time}
{instructions}

{food_note}

Stay healthy!
- Your AdherenceGuardian Team
        """,
        "push": "💊 Time for {medication} ({dosage})"
    },
    NotificationType.MISSED_DOSE_ALERT: {
        "title": "Missed Dose Alert",
        "sms": "You may have missed your {medication} dose scheduled for {scheduled_time}. Please take it if appropriate or skip to next dose.",
        "email_subject": "Missed Medication Alert - {medication}",
        "email_body": """
Hi {patient_name},

We noticed you may have missed a medication dose:

💊 **{medication}** - {dosage}
⏰ Was scheduled for: {scheduled_time}

**What to do:**
- If it's been less than {window_hours} hours, you can still take it
- If it's close to your next dose, skip this one
- Never double up on doses

If you need help, please contact your healthcare provider.

- Your AdherenceGuardian Team
        """,
        "push": "⚠️ Missed {medication} at {scheduled_time}"
    },
    NotificationType.REFILL_REMINDER: {
        "title": "Refill Reminder",
        "sms": "Your {medication} prescription needs refilling. You have approximately {days_remaining} days of supply remaining.",
        "email_subject": "Prescription Refill Needed - {medication}",
        "email_body": """
Hi {patient_name},

Your prescription will need refilling soon:

💊 **{medication}**
📅 Supply remaining: ~{days_remaining} days
🏪 Pharmacy: {pharmacy}

Please request a refill to avoid missing doses.

- Your AdherenceGuardian Team
        """,
        "push": "💊 {medication} refill needed - {days_remaining} days left"
    },
    NotificationType.ENCOURAGEMENT: {
        "title": "Great Job!",
        "sms": "Great job! You've achieved {adherence_rate}% adherence this week. Keep it up! 🌟",
        "email_subject": "You're Doing Great! 🎉",
        "email_body": """
Hi {patient_name},

Congratulations! 🎉

You've achieved **{adherence_rate}% adherence** this week!

{achievement_message}

Keep up the excellent work. Your consistent effort is making a real difference for your health.

- Your AdherenceGuardian Team
        """,
        "push": "🌟 {adherence_rate}% adherence this week! Great job!"
    },
    NotificationType.SYMPTOM_CHECK_IN: {
        "title": "How are you feeling?",
        "sms": "Quick check-in: How are you feeling today? Any side effects to report? Reply GOOD, OK, or NOTGOOD",
        "push": "How are you feeling today? Tap to report any symptoms."
    },
    NotificationType.ADHERENCE_REPORT: {
        "title": "Weekly Adherence Report",
        "email_subject": "Your Weekly Medication Report",
        "email_body": """
Hi {patient_name},

Here's your weekly medication adherence summary:

📊 **Overall Adherence: {adherence_rate}%**

{medication_breakdown}

{recommendations}

Keep up the great work!

- Your AdherenceGuardian Team
        """
    },
    NotificationType.PROVIDER_MESSAGE: {
        "title": "Message from Your Care Team",
        "sms": "You have a new message from your care team. {preview}",
        "email_subject": "Message from Your Healthcare Provider",
        "push": "📩 New message from your care team"
    }
}


class NotificationService:
    """
    Multi-channel notification service for medication reminders and alerts
    """
    
    def __init__(self):
        self.templates = NOTIFICATION_TEMPLATES
        self._sms_enabled = bool(settings.TWILIO_ACCOUNT_SID)
        self._email_enabled = True  # Assume email always available
        self._push_enabled = True   # Assume push available
        
        # Rate limiting
        self._rate_limits: Dict[int, List[datetime]] = {}  # patient_id -> timestamps
        self._max_notifications_per_hour = 10
        
        # Notification queue for scheduling
        self._scheduled_notifications: List[NotificationRequest] = []
    
    async def send_notification(
        self,
        request: NotificationRequest
    ) -> List[NotificationResult]:
        """
        Send a notification through specified channels
        
        Args:
            request: NotificationRequest with details
            
        Returns:
            List of results for each channel attempted
        """
        results = []
        
        # Check rate limiting
        if not self._check_rate_limit(request.patient_id):
            logger.warning(f"Rate limit exceeded for patient {request.patient_id}")
            return [NotificationResult(
                success=False,
                channel=request.channels[0] if request.channels else NotificationChannel.IN_APP,
                error="Rate limit exceeded"
            )]
        
        # If scheduled for future, queue it
        if request.scheduled_time and request.scheduled_time > datetime.utcnow():
            self._scheduled_notifications.append(request)
            return [NotificationResult(
                success=True,
                channel=NotificationChannel.IN_APP,
                message_id=f"scheduled_{len(self._scheduled_notifications)}"
            )]
        
        # Determine channels if not specified
        channels = request.channels or self._get_default_channels(request.priority)
        
        # Send through each channel
        for channel in channels:
            try:
                if channel == NotificationChannel.SMS:
                    result = await self._send_sms(request)
                elif channel == NotificationChannel.EMAIL:
                    result = await self._send_email(request)
                elif channel == NotificationChannel.PUSH:
                    result = await self._send_push(request)
                elif channel == NotificationChannel.IN_APP:
                    result = await self._send_in_app(request)
                else:
                    result = NotificationResult(
                        success=False,
                        channel=channel,
                        error=f"Unsupported channel: {channel}"
                    )
                
                results.append(result)
                
                # For critical, try all channels. For others, stop on success
                if result.success and request.priority != NotificationPriority.CRITICAL:
                    break
                    
            except Exception as e:
                logger.error(f"Error sending {channel.value} notification: {e}")
                results.append(NotificationResult(
                    success=False,
                    channel=channel,
                    error=str(e)
                ))
        
        # Record for rate limiting
        self._record_notification(request.patient_id)
        
        return results
    
    async def _send_sms(self, request: NotificationRequest) -> NotificationResult:
        """Send SMS notification"""
        if not self._sms_enabled:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.SMS,
                error="SMS not configured"
            )
        
        try:
            # In production, this would use Twilio
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            
            message = self._format_message(request, "sms")
            
            # Simulated SMS send
            logger.info(f"[SMS] To patient {request.patient_id}: {message[:50]}...")
            
            # In production:
            # sms = client.messages.create(
            #     body=message,
            #     from_=settings.TWILIO_PHONE_NUMBER,
            #     to=patient_phone
            # )
            
            return NotificationResult(
                success=True,
                channel=NotificationChannel.SMS,
                message_id=f"sms_{datetime.utcnow().timestamp()}",
                delivered_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"SMS send error: {e}")
            return NotificationResult(
                success=False,
                channel=NotificationChannel.SMS,
                error=str(e)
            )
    
    async def _send_email(self, request: NotificationRequest) -> NotificationResult:
        """Send email notification"""
        try:
            # In production, would use SendGrid, AWS SES, etc.
            
            subject = self._get_email_subject(request)
            body = self._format_message(request, "email_body")
            
            logger.info(f"[EMAIL] To patient {request.patient_id}: {subject}")
            
            # Simulated email send
            # In production:
            # await send_email(to=patient_email, subject=subject, body=body)
            
            return NotificationResult(
                success=True,
                channel=NotificationChannel.EMAIL,
                message_id=f"email_{datetime.utcnow().timestamp()}",
                delivered_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Email send error: {e}")
            return NotificationResult(
                success=False,
                channel=NotificationChannel.EMAIL,
                error=str(e)
            )
    
    async def _send_push(self, request: NotificationRequest) -> NotificationResult:
        """Send push notification"""
        try:
            # In production, would use Firebase Cloud Messaging, APNs, etc.
            
            title = request.title
            body = self._format_message(request, "push")
            
            logger.info(f"[PUSH] To patient {request.patient_id}: {title} - {body[:30]}...")
            
            # Simulated push send
            # In production:
            # await firebase_admin.messaging.send(message)
            
            return NotificationResult(
                success=True,
                channel=NotificationChannel.PUSH,
                message_id=f"push_{datetime.utcnow().timestamp()}",
                delivered_at=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Push send error: {e}")
            return NotificationResult(
                success=False,
                channel=NotificationChannel.PUSH,
                error=str(e)
            )
    
    async def _send_in_app(self, request: NotificationRequest) -> NotificationResult:
        """Store in-app notification"""
        try:
            # In production, would store in database for retrieval
            
            logger.info(f"[IN-APP] For patient {request.patient_id}: {request.title}")
            
            return NotificationResult(
                success=True,
                channel=NotificationChannel.IN_APP,
                message_id=f"inapp_{datetime.utcnow().timestamp()}",
                delivered_at=datetime.utcnow()
            )
            
        except Exception as e:
            return NotificationResult(
                success=False,
                channel=NotificationChannel.IN_APP,
                error=str(e)
            )
    
    def _format_message(
        self, 
        request: NotificationRequest, 
        template_key: str
    ) -> str:
        """Format message using template and data"""
        template = self.templates.get(request.notification_type, {})
        message_template = template.get(template_key, request.message)
        
        # Merge request data for formatting
        format_data = {
            "patient_name": request.data.get("patient_name", "there"),
            "medication": request.data.get("medication", "your medication"),
            "dosage": request.data.get("dosage", ""),
            "scheduled_time": request.data.get("scheduled_time", ""),
            "instructions": request.data.get("instructions", ""),
            "food_note": request.data.get("food_note", ""),
            "adherence_rate": request.data.get("adherence_rate", ""),
            "days_remaining": request.data.get("days_remaining", ""),
            "pharmacy": request.data.get("pharmacy", "your pharmacy"),
            "window_hours": request.data.get("window_hours", 4),
            "preview": request.data.get("preview", ""),
            "achievement_message": request.data.get("achievement_message", ""),
            "medication_breakdown": request.data.get("medication_breakdown", ""),
            "recommendations": request.data.get("recommendations", ""),
            **request.data
        }
        
        try:
            return message_template.format(**format_data)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            return request.message
    
    def _get_email_subject(self, request: NotificationRequest) -> str:
        """Get email subject from template"""
        template = self.templates.get(request.notification_type, {})
        subject_template = template.get("email_subject", request.title)
        
        try:
            return subject_template.format(**request.data)
        except KeyError:
            return request.title
    
    def _get_default_channels(
        self, 
        priority: NotificationPriority
    ) -> List[NotificationChannel]:
        """Get default channels based on priority"""
        if priority == NotificationPriority.CRITICAL:
            return [NotificationChannel.SMS, NotificationChannel.PUSH, NotificationChannel.EMAIL]
        elif priority == NotificationPriority.HIGH:
            return [NotificationChannel.PUSH, NotificationChannel.SMS]
        elif priority == NotificationPriority.NORMAL:
            return [NotificationChannel.PUSH, NotificationChannel.IN_APP]
        else:
            return [NotificationChannel.IN_APP]
    
    def _check_rate_limit(self, patient_id: int) -> bool:
        """Check if patient has exceeded rate limit"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        if patient_id not in self._rate_limits:
            return True
        
        # Clean old entries
        self._rate_limits[patient_id] = [
            ts for ts in self._rate_limits[patient_id]
            if ts > hour_ago
        ]
        
        return len(self._rate_limits[patient_id]) < self._max_notifications_per_hour
    
    def _record_notification(self, patient_id: int):
        """Record notification for rate limiting"""
        if patient_id not in self._rate_limits:
            self._rate_limits[patient_id] = []
        self._rate_limits[patient_id].append(datetime.utcnow())
    
    async def send_medication_reminder(
        self,
        patient_id: int,
        medication_name: str,
        dosage: str,
        scheduled_time: str,
        instructions: Optional[str] = None,
        with_food: bool = False,
        patient_name: Optional[str] = None
    ) -> List[NotificationResult]:
        """Convenience method to send medication reminder"""
        food_note = "Take with food." if with_food else ""
        
        request = NotificationRequest(
            patient_id=patient_id,
            notification_type=NotificationType.MEDICATION_REMINDER,
            title="Medication Reminder",
            message=f"Time to take {medication_name} {dosage}",
            priority=NotificationPriority.NORMAL,
            data={
                "patient_name": patient_name or "there",
                "medication": medication_name,
                "dosage": dosage,
                "scheduled_time": scheduled_time,
                "instructions": instructions or "",
                "food_note": food_note
            }
        )
        
        return await self.send_notification(request)
    
    async def send_missed_dose_alert(
        self,
        patient_id: int,
        medication_name: str,
        scheduled_time: str,
        patient_name: Optional[str] = None
    ) -> List[NotificationResult]:
        """Convenience method to send missed dose alert"""
        request = NotificationRequest(
            patient_id=patient_id,
            notification_type=NotificationType.MISSED_DOSE_ALERT,
            title="Missed Dose Alert",
            message=f"You may have missed your {medication_name}",
            priority=NotificationPriority.HIGH,
            data={
                "patient_name": patient_name or "there",
                "medication": medication_name,
                "scheduled_time": scheduled_time,
                "window_hours": 4
            }
        )
        
        return await self.send_notification(request)
    
    async def send_encouragement(
        self,
        patient_id: int,
        adherence_rate: float,
        patient_name: Optional[str] = None
    ) -> List[NotificationResult]:
        """Send positive reinforcement notification"""
        # Generate achievement message based on rate
        if adherence_rate >= 95:
            achievement = "Outstanding! You're a medication adherence champion! 🏆"
        elif adherence_rate >= 90:
            achievement = "Excellent work! You've hit your adherence target! 🎯"
        elif adherence_rate >= 80:
            achievement = "Great progress! Keep building that healthy habit! 💪"
        else:
            achievement = "Every dose counts! You're making progress! 🌱"
        
        request = NotificationRequest(
            patient_id=patient_id,
            notification_type=NotificationType.ENCOURAGEMENT,
            title="Great Job!",
            message=f"You achieved {adherence_rate:.0f}% adherence!",
            priority=NotificationPriority.LOW,
            data={
                "patient_name": patient_name or "there",
                "adherence_rate": f"{adherence_rate:.0f}",
                "achievement_message": achievement
            }
        )
        
        return await self.send_notification(request)


# Singleton instance
notification_service = NotificationService()


async def send_reminder(
    patient_id: int,
    medication: str,
    dosage: str,
    time: str
) -> List[NotificationResult]:
    """Convenience function to send a reminder"""
    return await notification_service.send_medication_reminder(
        patient_id, medication, dosage, time
    )
