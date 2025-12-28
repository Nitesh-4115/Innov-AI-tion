"""
Alert Engine
Generates and manages alerts for medication adherence issues
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid


logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts"""
    MISSED_DOSE = "missed_dose"
    MULTIPLE_MISSED = "multiple_missed"
    ADHERENCE_DROP = "adherence_drop"
    INTERACTION_WARNING = "interaction_warning"
    SIDE_EFFECT_REPORTED = "side_effect_reported"
    REFILL_NEEDED = "refill_needed"
    CRITICAL_MEDICATION = "critical_medication"
    PATTERN_DETECTED = "pattern_detected"
    PROVIDER_NOTIFICATION = "provider_notification"
    SCHEDULE_CONFLICT = "schedule_conflict"


class AlertStatus(str, Enum):
    """Alert status"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    EXPIRED = "expired"


@dataclass
class Alert:
    """Alert data structure"""
    id: str
    patient_id: int
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    status: AlertStatus = AlertStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    actions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "alert_type": self.alert_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "metadata": self.metadata,
            "actions": self.actions
        }
    
    def acknowledge(self):
        """Mark alert as acknowledged"""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.utcnow()
    
    def resolve(self):
        """Mark alert as resolved"""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.utcnow()
    
    def escalate(self):
        """Escalate the alert"""
        self.status = AlertStatus.ESCALATED
        # Increase severity if not already critical
        if self.severity == AlertSeverity.LOW:
            self.severity = AlertSeverity.MEDIUM
        elif self.severity == AlertSeverity.MEDIUM:
            self.severity = AlertSeverity.HIGH
        elif self.severity == AlertSeverity.HIGH:
            self.severity = AlertSeverity.CRITICAL


class AlertEngine:
    """
    Engine for generating and managing medication adherence alerts
    
    Responsibilities:
    - Generate alerts based on adherence events
    - Manage alert lifecycle
    - Determine alert severity
    - Track alert history
    """
    
    def __init__(self):
        self._alerts: Dict[str, Alert] = {}
        self._patient_alerts: Dict[int, List[str]] = {}
        
        # Severity thresholds
        self.adherence_thresholds = {
            "critical": 50,  # Below 50% is critical
            "high": 70,      # Below 70% is high
            "medium": 85,    # Below 85% is medium
            "low": 95        # Below 95% is low
        }
        
        # Alert expiration times (hours)
        self.expiration_times = {
            AlertSeverity.LOW: 24,
            AlertSeverity.MEDIUM: 48,
            AlertSeverity.HIGH: 72,
            AlertSeverity.CRITICAL: 168  # 1 week
        }
    
    def _generate_id(self) -> str:
        """Generate unique alert ID"""
        return str(uuid.uuid4())[:8]
    
    def _add_alert(self, alert: Alert):
        """Add alert to storage"""
        self._alerts[alert.id] = alert
        
        if alert.patient_id not in self._patient_alerts:
            self._patient_alerts[alert.patient_id] = []
        self._patient_alerts[alert.patient_id].append(alert.id)
        
        logger.info(f"Created alert {alert.id}: {alert.title} for patient {alert.patient_id}")
    
    def create_missed_dose_alert(
        self,
        patient_id: int,
        medication_name: str,
        scheduled_time: datetime,
        is_critical: bool = False
    ) -> Alert:
        """Create alert for a missed dose"""
        severity = AlertSeverity.HIGH if is_critical else AlertSeverity.MEDIUM
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.MISSED_DOSE,
            severity=severity,
            title=f"Missed Dose: {medication_name}",
            message=f"A scheduled dose of {medication_name} was missed at {scheduled_time.strftime('%I:%M %p')}.",
            metadata={
                "medication_name": medication_name,
                "scheduled_time": scheduled_time.isoformat(),
                "is_critical": is_critical
            },
            actions=[
                "Take the dose if within the safe window",
                "Skip if close to next scheduled dose",
                "Contact provider if unsure"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_multiple_missed_alert(
        self,
        patient_id: int,
        medication_name: str,
        missed_count: int,
        time_period: str = "week"
    ) -> Alert:
        """Create alert for multiple missed doses"""
        if missed_count >= 5:
            severity = AlertSeverity.CRITICAL
        elif missed_count >= 3:
            severity = AlertSeverity.HIGH
        else:
            severity = AlertSeverity.MEDIUM
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.MULTIPLE_MISSED,
            severity=severity,
            title=f"Multiple Missed Doses: {medication_name}",
            message=f"{missed_count} doses of {medication_name} have been missed this {time_period}.",
            metadata={
                "medication_name": medication_name,
                "missed_count": missed_count,
                "time_period": time_period
            },
            actions=[
                "Review medication schedule",
                "Identify barriers to adherence",
                "Consider provider consultation"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_adherence_drop_alert(
        self,
        patient_id: int,
        current_rate: float,
        previous_rate: float,
        medication_name: Optional[str] = None
    ) -> Alert:
        """Create alert for significant adherence rate drop"""
        drop = previous_rate - current_rate
        
        if current_rate < self.adherence_thresholds["critical"]:
            severity = AlertSeverity.CRITICAL
        elif current_rate < self.adherence_thresholds["high"]:
            severity = AlertSeverity.HIGH
        elif drop > 20:
            severity = AlertSeverity.HIGH
        else:
            severity = AlertSeverity.MEDIUM
        
        target = medication_name or "overall medications"
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.ADHERENCE_DROP,
            severity=severity,
            title=f"Adherence Rate Dropped",
            message=f"Adherence rate for {target} dropped from {previous_rate:.1f}% to {current_rate:.1f}%.",
            metadata={
                "current_rate": current_rate,
                "previous_rate": previous_rate,
                "drop_amount": drop,
                "medication_name": medication_name
            },
            actions=[
                "Investigate recent changes",
                "Check for new barriers",
                "Schedule follow-up"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_interaction_alert(
        self,
        patient_id: int,
        drug1: str,
        drug2: str,
        interaction_description: str,
        severity_level: str = "moderate"
    ) -> Alert:
        """Create alert for drug interaction"""
        severity_map = {
            "minor": AlertSeverity.LOW,
            "moderate": AlertSeverity.MEDIUM,
            "major": AlertSeverity.HIGH,
            "severe": AlertSeverity.CRITICAL
        }
        severity = severity_map.get(severity_level.lower(), AlertSeverity.MEDIUM)
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.INTERACTION_WARNING,
            severity=severity,
            title=f"Drug Interaction: {drug1} & {drug2}",
            message=interaction_description,
            metadata={
                "drug1": drug1,
                "drug2": drug2,
                "severity_level": severity_level
            },
            actions=[
                "Review with healthcare provider",
                "Do not stop medications without guidance",
                "Monitor for symptoms"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_side_effect_alert(
        self,
        patient_id: int,
        medication_name: str,
        side_effect: str,
        severity_level: str = "moderate"
    ) -> Alert:
        """Create alert for reported side effect"""
        severity_map = {
            "mild": AlertSeverity.LOW,
            "moderate": AlertSeverity.MEDIUM,
            "severe": AlertSeverity.HIGH,
            "emergency": AlertSeverity.CRITICAL
        }
        severity = severity_map.get(severity_level.lower(), AlertSeverity.MEDIUM)
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.SIDE_EFFECT_REPORTED,
            severity=severity,
            title=f"Side Effect Reported: {side_effect}",
            message=f"Patient reported {side_effect} possibly related to {medication_name}.",
            metadata={
                "medication_name": medication_name,
                "side_effect": side_effect,
                "severity_level": severity_level
            },
            actions=[
                "Document symptom details",
                "Assess symptom severity",
                "Consider provider notification"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_refill_alert(
        self,
        patient_id: int,
        medication_name: str,
        days_remaining: int
    ) -> Alert:
        """Create alert for medication refill needed"""
        if days_remaining <= 3:
            severity = AlertSeverity.HIGH
        elif days_remaining <= 7:
            severity = AlertSeverity.MEDIUM
        else:
            severity = AlertSeverity.LOW
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.REFILL_NEEDED,
            severity=severity,
            title=f"Refill Needed: {medication_name}",
            message=f"{medication_name} supply will run out in {days_remaining} days. Please arrange a refill.",
            metadata={
                "medication_name": medication_name,
                "days_remaining": days_remaining
            },
            actions=[
                "Contact pharmacy for refill",
                "Check prescription status",
                "Request provider authorization if needed"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_critical_medication_alert(
        self,
        patient_id: int,
        medication_name: str,
        reason: str
    ) -> Alert:
        """Create alert for critical medication issue"""
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.CRITICAL_MEDICATION,
            severity=AlertSeverity.CRITICAL,
            title=f"Critical Alert: {medication_name}",
            message=f"Critical issue with {medication_name}: {reason}",
            metadata={
                "medication_name": medication_name,
                "reason": reason
            },
            actions=[
                "Contact healthcare provider immediately",
                "Do not make changes without guidance",
                "Seek emergency care if symptoms severe"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def create_pattern_alert(
        self,
        patient_id: int,
        pattern_description: str,
        recommendations: List[str]
    ) -> Alert:
        """Create alert for detected adherence pattern"""
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.PATTERN_DETECTED,
            severity=AlertSeverity.MEDIUM,
            title="Adherence Pattern Detected",
            message=pattern_description,
            metadata={
                "pattern": pattern_description
            },
            actions=recommendations
        )
        
        self._add_alert(alert)
        return alert
    
    def create_provider_notification(
        self,
        patient_id: int,
        subject: str,
        details: str,
        urgency: str = "routine"
    ) -> Alert:
        """Create alert for provider notification"""
        severity_map = {
            "routine": AlertSeverity.LOW,
            "soon": AlertSeverity.MEDIUM,
            "urgent": AlertSeverity.HIGH,
            "emergency": AlertSeverity.CRITICAL
        }
        severity = severity_map.get(urgency.lower(), AlertSeverity.MEDIUM)
        
        alert = Alert(
            id=self._generate_id(),
            patient_id=patient_id,
            alert_type=AlertType.PROVIDER_NOTIFICATION,
            severity=severity,
            title=f"Provider Notification: {subject}",
            message=details,
            metadata={
                "subject": subject,
                "urgency": urgency
            },
            actions=[
                "Forward to healthcare provider",
                "Document in patient record",
                "Schedule follow-up as needed"
            ]
        )
        
        self._add_alert(alert)
        return alert
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """Get alert by ID"""
        return self._alerts.get(alert_id)
    
    def get_patient_alerts(
        self,
        patient_id: int,
        status: Optional[AlertStatus] = None,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None
    ) -> List[Alert]:
        """Get alerts for a patient with optional filters"""
        alert_ids = self._patient_alerts.get(patient_id, [])
        alerts = [self._alerts[aid] for aid in alert_ids if aid in self._alerts]
        
        # Apply filters
        if status:
            alerts = [a for a in alerts if a.status == status]
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]
        
        # Sort by severity (critical first) then by creation time
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3
        }
        alerts.sort(key=lambda a: (severity_order.get(a.severity, 4), a.created_at), reverse=True)
        
        return alerts
    
    def get_active_alerts(self, patient_id: int) -> List[Alert]:
        """Get active alerts for a patient"""
        return self.get_patient_alerts(patient_id, status=AlertStatus.ACTIVE)
    
    def get_critical_alerts(self, patient_id: int) -> List[Alert]:
        """Get critical alerts for a patient"""
        return self.get_patient_alerts(patient_id, severity=AlertSeverity.CRITICAL)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert"""
        alert = self.get_alert(alert_id)
        if alert:
            alert.acknowledge()
            logger.info(f"Alert {alert_id} acknowledged")
            return True
        return False
    
    def resolve_alert(self, alert_id: str) -> bool:
        """Resolve an alert"""
        alert = self.get_alert(alert_id)
        if alert:
            alert.resolve()
            logger.info(f"Alert {alert_id} resolved")
            return True
        return False
    
    def escalate_alert(self, alert_id: str) -> bool:
        """Escalate an alert"""
        alert = self.get_alert(alert_id)
        if alert:
            alert.escalate()
            logger.info(f"Alert {alert_id} escalated to {alert.severity.value}")
            return True
        return False
    
    def expire_old_alerts(self):
        """Mark old alerts as expired"""
        now = datetime.utcnow()
        
        for alert in self._alerts.values():
            if alert.status == AlertStatus.ACTIVE:
                expiration_hours = self.expiration_times.get(alert.severity, 72)
                if now - alert.created_at > timedelta(hours=expiration_hours):
                    alert.status = AlertStatus.EXPIRED
                    logger.info(f"Alert {alert.id} expired")
    
    def get_alert_summary(self, patient_id: int) -> Dict[str, Any]:
        """Get summary of alerts for a patient"""
        alerts = self.get_patient_alerts(patient_id)
        
        summary = {
            "total": len(alerts),
            "by_status": {},
            "by_severity": {},
            "by_type": {},
            "active_critical": 0
        }
        
        for alert in alerts:
            # By status
            status = alert.status.value
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # By severity
            severity = alert.severity.value
            summary["by_severity"][severity] = summary["by_severity"].get(severity, 0) + 1
            
            # By type
            alert_type = alert.alert_type.value
            summary["by_type"][alert_type] = summary["by_type"].get(alert_type, 0) + 1
            
            # Active critical count
            if alert.status == AlertStatus.ACTIVE and alert.severity == AlertSeverity.CRITICAL:
                summary["active_critical"] += 1
        
        return summary
    
    def clear_patient_alerts(self, patient_id: int):
        """Clear all alerts for a patient"""
        if patient_id in self._patient_alerts:
            for alert_id in self._patient_alerts[patient_id]:
                if alert_id in self._alerts:
                    del self._alerts[alert_id]
            del self._patient_alerts[patient_id]
            logger.info(f"Cleared all alerts for patient {patient_id}")


# Singleton instance
alert_engine = AlertEngine()
