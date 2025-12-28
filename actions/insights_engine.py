"""
Insights Engine
Generates insights and analytics from medication adherence data
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics


logger = logging.getLogger(__name__)


class InsightType(str, Enum):
    """Types of insights"""
    ADHERENCE_TREND = "adherence_trend"
    PATTERN_DETECTED = "pattern_detected"
    RISK_ASSESSMENT = "risk_assessment"
    IMPROVEMENT = "improvement"
    CONCERN = "concern"
    RECOMMENDATION = "recommendation"
    MILESTONE = "milestone"
    COMPARISON = "comparison"
    PREDICTION = "prediction"


class InsightPriority(str, Enum):
    """Insight priority levels"""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TrendDirection(str, Enum):
    """Trend direction"""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    FLUCTUATING = "fluctuating"


@dataclass
class Insight:
    """Insight data structure"""
    id: str
    patient_id: int
    insight_type: InsightType
    title: str
    description: str
    priority: InsightPriority = InsightPriority.INFO
    created_at: datetime = field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    is_read: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "insight_type": self.insight_type.value,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "data": self.data,
            "recommendations": self.recommendations,
            "is_read": self.is_read
        }


@dataclass
class AdherenceMetrics:
    """Adherence metrics for analysis"""
    overall_rate: float
    daily_rates: List[float]
    by_medication: Dict[str, float]
    by_time_of_day: Dict[str, float]
    by_day_of_week: Dict[str, float]
    missed_doses: int
    total_doses: int
    streak_current: int
    streak_best: int
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_rate": self.overall_rate,
            "daily_rates": self.daily_rates,
            "by_medication": self.by_medication,
            "by_time_of_day": self.by_time_of_day,
            "by_day_of_week": self.by_day_of_week,
            "missed_doses": self.missed_doses,
            "total_doses": self.total_doses,
            "streak_current": self.streak_current,
            "streak_best": self.streak_best
        }


class InsightsEngine:
    """
    Engine for generating insights from medication adherence data
    
    Responsibilities:
    - Analyze adherence patterns
    - Detect trends and anomalies
    - Generate actionable insights
    - Track progress and milestones
    - Provide risk assessments
    """
    
    def __init__(self):
        self._insights: Dict[str, Insight] = {}
        self._patient_insights: Dict[int, List[str]] = defaultdict(list)
        self._insight_counter = 0
        
        # Thresholds
        self.adherence_thresholds = {
            "excellent": 95,
            "good": 85,
            "fair": 70,
            "poor": 50
        }
        
        # Risk weights
        self.risk_factors = {
            "low_adherence": 3.0,
            "declining_trend": 2.5,
            "multiple_medications": 1.5,
            "missed_critical": 4.0,
            "side_effects": 2.0,
            "cost_barrier": 2.0
        }
    
    def _generate_id(self) -> str:
        """Generate unique insight ID"""
        self._insight_counter += 1
        return f"INS-{self._insight_counter:05d}"
    
    def _add_insight(self, insight: Insight):
        """Add insight to storage"""
        self._insights[insight.id] = insight
        self._patient_insights[insight.patient_id].append(insight.id)
        logger.info(f"Generated insight {insight.id}: {insight.title}")
    
    def calculate_metrics(
        self,
        adherence_records: List[Dict[str, Any]],
        medications: List[Dict[str, Any]]
    ) -> AdherenceMetrics:
        """
        Calculate comprehensive adherence metrics
        
        Args:
            adherence_records: List of adherence records
            medications: List of patient medications
            
        Returns:
            AdherenceMetrics object
        """
        if not adherence_records:
            return AdherenceMetrics(
                overall_rate=0,
                daily_rates=[],
                by_medication={},
                by_time_of_day={},
                by_day_of_week={},
                missed_doses=0,
                total_doses=0,
                streak_current=0,
                streak_best=0
            )
        
        # Calculate overall rate
        taken = sum(1 for r in adherence_records if r.get("taken", False))
        total = len(adherence_records)
        overall_rate = (taken / total * 100) if total > 0 else 0
        
        # Group by date
        by_date = defaultdict(list)
        for record in adherence_records:
            date = record.get("scheduled_date", record.get("date", ""))
            if isinstance(date, datetime):
                date = date.strftime("%Y-%m-%d")
            by_date[date].append(record.get("taken", False))
        
        # Daily rates
        daily_rates = []
        for date in sorted(by_date.keys()):
            records = by_date[date]
            rate = sum(records) / len(records) * 100 if records else 0
            daily_rates.append(rate)
        
        # By medication
        by_medication = defaultdict(lambda: {"taken": 0, "total": 0})
        for record in adherence_records:
            med_name = record.get("medication_name", "Unknown")
            by_medication[med_name]["total"] += 1
            if record.get("taken", False):
                by_medication[med_name]["taken"] += 1
        
        med_rates = {
            name: (data["taken"] / data["total"] * 100) if data["total"] > 0 else 0
            for name, data in by_medication.items()
        }
        
        # By time of day
        time_buckets = {"morning": [], "afternoon": [], "evening": [], "night": []}
        for record in adherence_records:
            time_str = record.get("scheduled_time", "12:00")
            if isinstance(time_str, datetime):
                hour = time_str.hour
            else:
                try:
                    hour = int(time_str.split(":")[0])
                except:
                    hour = 12
            
            if 5 <= hour < 12:
                bucket = "morning"
            elif 12 <= hour < 17:
                bucket = "afternoon"
            elif 17 <= hour < 21:
                bucket = "evening"
            else:
                bucket = "night"
            
            time_buckets[bucket].append(record.get("taken", False))
        
        time_rates = {
            bucket: (sum(records) / len(records) * 100) if records else 0
            for bucket, records in time_buckets.items()
        }
        
        # By day of week
        dow_buckets = {i: [] for i in range(7)}
        for record in adherence_records:
            date = record.get("scheduled_date", record.get("date"))
            if isinstance(date, str):
                try:
                    date = datetime.fromisoformat(date)
                except:
                    continue
            if isinstance(date, datetime):
                dow_buckets[date.weekday()].append(record.get("taken", False))
        
        dow_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_rates = {
            dow_names[i]: (sum(records) / len(records) * 100) if records else 0
            for i, records in dow_buckets.items()
        }
        
        # Calculate streaks
        sorted_dates = sorted(by_date.keys())
        current_streak = 0
        best_streak = 0
        temp_streak = 0
        
        for date in sorted_dates:
            all_taken = all(by_date[date])
            if all_taken:
                temp_streak += 1
                best_streak = max(best_streak, temp_streak)
            else:
                temp_streak = 0
        
        current_streak = temp_streak
        
        return AdherenceMetrics(
            overall_rate=overall_rate,
            daily_rates=daily_rates,
            by_medication=med_rates,
            by_time_of_day=time_rates,
            by_day_of_week=dow_rates,
            missed_doses=total - taken,
            total_doses=total,
            streak_current=current_streak,
            streak_best=best_streak
        )
    
    def analyze_trend(
        self,
        daily_rates: List[float],
        window_size: int = 7
    ) -> Tuple[TrendDirection, float]:
        """
        Analyze adherence trend
        
        Args:
            daily_rates: List of daily adherence rates
            window_size: Window size for trend analysis
            
        Returns:
            Tuple of (trend direction, change rate)
        """
        if len(daily_rates) < window_size * 2:
            return TrendDirection.STABLE, 0.0
        
        recent = daily_rates[-window_size:]
        previous = daily_rates[-window_size*2:-window_size]
        
        recent_avg = statistics.mean(recent)
        previous_avg = statistics.mean(previous)
        
        change = recent_avg - previous_avg
        
        # Check for fluctuation
        if len(daily_rates) >= 7:
            std_dev = statistics.stdev(daily_rates[-7:])
            if std_dev > 20:
                return TrendDirection.FLUCTUATING, change
        
        if change > 5:
            return TrendDirection.IMPROVING, change
        elif change < -5:
            return TrendDirection.DECLINING, change
        else:
            return TrendDirection.STABLE, change
    
    def generate_trend_insight(
        self,
        patient_id: int,
        metrics: AdherenceMetrics
    ) -> Optional[Insight]:
        """Generate insight about adherence trend"""
        if len(metrics.daily_rates) < 7:
            return None
        
        trend, change = self.analyze_trend(metrics.daily_rates)
        
        if trend == TrendDirection.IMPROVING:
            insight = Insight(
                id=self._generate_id(),
                patient_id=patient_id,
                insight_type=InsightType.IMPROVEMENT,
                title="Adherence Improving! 📈",
                description=f"Your medication adherence has improved by {abs(change):.1f}% over the past week. Keep up the great work!",
                priority=InsightPriority.INFO,
                data={"trend": trend.value, "change": change},
                recommendations=[
                    "Continue your current routine",
                    "Consider what's been working well",
                    "Share your success with your healthcare team"
                ]
            )
        elif trend == TrendDirection.DECLINING:
            priority = InsightPriority.HIGH if change < -15 else InsightPriority.MEDIUM
            insight = Insight(
                id=self._generate_id(),
                patient_id=patient_id,
                insight_type=InsightType.CONCERN,
                title="Adherence Declining",
                description=f"Your medication adherence has dropped by {abs(change):.1f}% recently. Let's work on getting back on track.",
                priority=priority,
                data={"trend": trend.value, "change": change},
                recommendations=[
                    "Review your medication schedule",
                    "Check if reminders are working",
                    "Identify any new barriers",
                    "Consider talking to your healthcare provider"
                ]
            )
        elif trend == TrendDirection.FLUCTUATING:
            insight = Insight(
                id=self._generate_id(),
                patient_id=patient_id,
                insight_type=InsightType.PATTERN_DETECTED,
                title="Inconsistent Adherence Pattern",
                description="Your adherence varies significantly day to day. Establishing a consistent routine may help.",
                priority=InsightPriority.MEDIUM,
                data={"trend": trend.value, "change": change},
                recommendations=[
                    "Link medications to daily activities",
                    "Set consistent medication times",
                    "Use a pill organizer"
                ]
            )
        else:
            return None
        
        self._add_insight(insight)
        return insight
    
    def generate_pattern_insights(
        self,
        patient_id: int,
        metrics: AdherenceMetrics
    ) -> List[Insight]:
        """Generate insights about adherence patterns"""
        insights = []
        
        # Time of day patterns
        time_rates = metrics.by_time_of_day
        if time_rates:
            worst_time = min(time_rates, key=time_rates.get)
            best_time = max(time_rates, key=time_rates.get)
            
            if time_rates[worst_time] < 70 and time_rates[best_time] - time_rates[worst_time] > 20:
                insight = Insight(
                    id=self._generate_id(),
                    patient_id=patient_id,
                    insight_type=InsightType.PATTERN_DETECTED,
                    title=f"{worst_time.capitalize()} Doses Often Missed",
                    description=f"You tend to miss more doses in the {worst_time} ({time_rates[worst_time]:.0f}% adherence) compared to {best_time} ({time_rates[best_time]:.0f}%).",
                    priority=InsightPriority.MEDIUM,
                    data={"time_rates": time_rates},
                    recommendations=[
                        f"Set an extra reminder for {worst_time} medications",
                        f"Consider asking your doctor about moving doses to {best_time}",
                        f"Link {worst_time} medication to a specific routine"
                    ]
                )
                self._add_insight(insight)
                insights.append(insight)
        
        # Day of week patterns
        dow_rates = metrics.by_day_of_week
        if dow_rates:
            worst_day = min(dow_rates, key=dow_rates.get)
            
            if dow_rates[worst_day] < 70:
                is_weekend = worst_day in ["Saturday", "Sunday"]
                insight = Insight(
                    id=self._generate_id(),
                    patient_id=patient_id,
                    insight_type=InsightType.PATTERN_DETECTED,
                    title=f"{worst_day}s Are Challenging",
                    description=f"Your adherence drops on {worst_day}s ({dow_rates[worst_day]:.0f}%). {'Weekend routines may be disrupting your schedule.' if is_weekend else 'Consider what makes this day different.'}",
                    priority=InsightPriority.LOW,
                    data={"day_rates": dow_rates},
                    recommendations=[
                        f"Plan ahead for {worst_day}s",
                        "Keep a backup medication supply accessible",
                        "Set extra reminders for that day"
                    ]
                )
                self._add_insight(insight)
                insights.append(insight)
        
        # Medication-specific patterns
        med_rates = metrics.by_medication
        if len(med_rates) > 1:
            worst_med = min(med_rates, key=med_rates.get)
            best_med = max(med_rates, key=med_rates.get)
            
            if med_rates[worst_med] < 70 and med_rates[best_med] - med_rates[worst_med] > 15:
                insight = Insight(
                    id=self._generate_id(),
                    patient_id=patient_id,
                    insight_type=InsightType.PATTERN_DETECTED,
                    title=f"Struggling with {worst_med}",
                    description=f"Your adherence to {worst_med} ({med_rates[worst_med]:.0f}%) is lower than other medications.",
                    priority=InsightPriority.MEDIUM,
                    data={"medication_rates": med_rates},
                    recommendations=[
                        f"Identify what makes {worst_med} harder to take",
                        "Consider if side effects are a factor",
                        "Discuss alternatives with your provider"
                    ]
                )
                self._add_insight(insight)
                insights.append(insight)
        
        return insights
    
    def generate_milestone_insight(
        self,
        patient_id: int,
        metrics: AdherenceMetrics
    ) -> Optional[Insight]:
        """Generate insights for adherence milestones"""
        # Streak milestones
        streak_milestones = [7, 14, 30, 60, 90, 180, 365]
        
        for milestone in streak_milestones:
            if metrics.streak_current == milestone:
                insight = Insight(
                    id=self._generate_id(),
                    patient_id=patient_id,
                    insight_type=InsightType.MILESTONE,
                    title=f"🎉 {milestone}-Day Streak!",
                    description=f"Congratulations! You've taken all your medications for {milestone} days in a row!",
                    priority=InsightPriority.INFO,
                    data={"streak": milestone},
                    recommendations=["Keep up the excellent work!"]
                )
                self._add_insight(insight)
                return insight
        
        # Overall rate milestones
        if metrics.overall_rate >= 95 and metrics.total_doses >= 30:
            insight = Insight(
                id=self._generate_id(),
                patient_id=patient_id,
                insight_type=InsightType.MILESTONE,
                title="⭐ Excellent Adherence!",
                description=f"Your overall adherence rate is {metrics.overall_rate:.1f}%. You're doing an outstanding job!",
                priority=InsightPriority.INFO,
                data={"rate": metrics.overall_rate},
                recommendations=["Share this achievement with your healthcare team"]
            )
            self._add_insight(insight)
            return insight
        
        return None
    
    def assess_risk(
        self,
        patient_id: int,
        metrics: AdherenceMetrics,
        additional_factors: Optional[Dict[str, bool]] = None
    ) -> Insight:
        """
        Assess adherence risk level
        
        Args:
            patient_id: Patient ID
            metrics: Adherence metrics
            additional_factors: Dict of risk factors present
            
        Returns:
            Risk assessment insight
        """
        risk_score = 0
        factors_present = []
        
        # Check adherence level
        if metrics.overall_rate < 70:
            risk_score += self.risk_factors["low_adherence"]
            factors_present.append("Low overall adherence")
        
        # Check trend
        if len(metrics.daily_rates) >= 14:
            trend, _ = self.analyze_trend(metrics.daily_rates)
            if trend == TrendDirection.DECLINING:
                risk_score += self.risk_factors["declining_trend"]
                factors_present.append("Declining adherence trend")
        
        # Check medication count
        if len(metrics.by_medication) > 5:
            risk_score += self.risk_factors["multiple_medications"]
            factors_present.append("Complex medication regimen")
        
        # Check additional factors
        if additional_factors:
            if additional_factors.get("has_side_effects"):
                risk_score += self.risk_factors["side_effects"]
                factors_present.append("Experiencing side effects")
            if additional_factors.get("cost_concern"):
                risk_score += self.risk_factors["cost_barrier"]
                factors_present.append("Cost concerns")
            if additional_factors.get("missed_critical"):
                risk_score += self.risk_factors["missed_critical"]
                factors_present.append("Missed critical medication")
        
        # Determine risk level
        if risk_score >= 8:
            priority = InsightPriority.CRITICAL
            level = "High"
            title = "⚠️ High Adherence Risk"
        elif risk_score >= 5:
            priority = InsightPriority.HIGH
            level = "Moderate"
            title = "Moderate Adherence Risk"
        elif risk_score >= 2:
            priority = InsightPriority.MEDIUM
            level = "Low"
            title = "Low Adherence Risk"
        else:
            priority = InsightPriority.LOW
            level = "Minimal"
            title = "Minimal Adherence Risk"
        
        description = f"Risk Level: {level}. "
        if factors_present:
            description += f"Contributing factors: {', '.join(factors_present)}."
        else:
            description += "Keep up your current adherence habits!"
        
        insight = Insight(
            id=self._generate_id(),
            patient_id=patient_id,
            insight_type=InsightType.RISK_ASSESSMENT,
            title=title,
            description=description,
            priority=priority,
            data={
                "risk_score": risk_score,
                "risk_level": level,
                "factors": factors_present
            },
            recommendations=self._get_risk_recommendations(factors_present)
        )
        
        self._add_insight(insight)
        return insight
    
    def _get_risk_recommendations(self, factors: List[str]) -> List[str]:
        """Get recommendations based on risk factors"""
        recommendations = []
        
        if "Low overall adherence" in factors:
            recommendations.extend([
                "Review your medication schedule",
                "Consider using a pill organizer",
                "Set up medication reminders"
            ])
        
        if "Declining adherence trend" in factors:
            recommendations.extend([
                "Identify recent changes that may be affecting adherence",
                "Talk to your healthcare provider about concerns"
            ])
        
        if "Complex medication regimen" in factors:
            recommendations.extend([
                "Ask about simplifying your regimen",
                "Use a medication management app"
            ])
        
        if "Experiencing side effects" in factors:
            recommendations.extend([
                "Report side effects to your provider",
                "Ask about strategies to manage side effects"
            ])
        
        if "Cost concerns" in factors:
            recommendations.extend([
                "Ask about generic alternatives",
                "Look into patient assistance programs"
            ])
        
        if not recommendations:
            recommendations = ["Continue your current medication routine"]
        
        return recommendations[:5]  # Limit to top 5
    
    def generate_all_insights(
        self,
        patient_id: int,
        adherence_records: List[Dict[str, Any]],
        medications: List[Dict[str, Any]],
        additional_factors: Optional[Dict[str, bool]] = None
    ) -> List[Insight]:
        """Generate all applicable insights for a patient"""
        metrics = self.calculate_metrics(adherence_records, medications)
        insights = []
        
        # Trend insight
        trend_insight = self.generate_trend_insight(patient_id, metrics)
        if trend_insight:
            insights.append(trend_insight)
        
        # Pattern insights
        pattern_insights = self.generate_pattern_insights(patient_id, metrics)
        insights.extend(pattern_insights)
        
        # Milestone insight
        milestone_insight = self.generate_milestone_insight(patient_id, metrics)
        if milestone_insight:
            insights.append(milestone_insight)
        
        # Risk assessment
        risk_insight = self.assess_risk(patient_id, metrics, additional_factors)
        insights.append(risk_insight)
        
        # Sort by priority
        priority_order = {
            InsightPriority.CRITICAL: 0,
            InsightPriority.HIGH: 1,
            InsightPriority.MEDIUM: 2,
            InsightPriority.LOW: 3,
            InsightPriority.INFO: 4
        }
        insights.sort(key=lambda i: priority_order.get(i.priority, 5))
        
        return insights
    
    def get_insight(self, insight_id: str) -> Optional[Insight]:
        """Get insight by ID"""
        return self._insights.get(insight_id)
    
    def get_patient_insights(
        self,
        patient_id: int,
        insight_type: Optional[InsightType] = None,
        unread_only: bool = False
    ) -> List[Insight]:
        """Get insights for a patient"""
        insight_ids = self._patient_insights.get(patient_id, [])
        insights = [self._insights[iid] for iid in insight_ids if iid in self._insights]
        
        if insight_type:
            insights = [i for i in insights if i.insight_type == insight_type]
        if unread_only:
            insights = [i for i in insights if not i.is_read]
        
        insights.sort(key=lambda i: i.created_at, reverse=True)
        return insights
    
    def mark_insight_read(self, insight_id: str) -> bool:
        """Mark insight as read"""
        insight = self.get_insight(insight_id)
        if insight:
            insight.is_read = True
            return True
        return False
    
    def get_insights_summary(self, patient_id: int) -> Dict[str, Any]:
        """Get summary of insights for a patient"""
        insights = self.get_patient_insights(patient_id)
        
        return {
            "total": len(insights),
            "unread": sum(1 for i in insights if not i.is_read),
            "by_type": {
                t.value: sum(1 for i in insights if i.insight_type == t)
                for t in InsightType
            },
            "by_priority": {
                p.value: sum(1 for i in insights if i.priority == p)
                for p in InsightPriority
            }
        }


# Singleton instance
insights_engine = InsightsEngine()
