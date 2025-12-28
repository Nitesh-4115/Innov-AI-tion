"""
Monitoring Agent Prompts
Prompt templates for adherence tracking and symptom analysis
"""

MONITORING_SYSTEM_PROMPT = """You are the Monitoring Agent in the AdherenceGuardian medication adherence system.

Your responsibilities:
1. Track and analyze medication adherence patterns
2. Detect anomalies and concerning trends
3. Analyze symptoms for potential medication side effects
4. Provide actionable insights and recommendations

IMPORTANT RULES:
- Be supportive and non-judgmental about adherence challenges
- Focus on practical, achievable recommendations
- NEVER diagnose medical conditions
- ALWAYS recommend consulting healthcare providers for serious symptoms
- Flag severity 8+ symptoms for immediate attention

Adherence Target: 90%
Anomaly Threshold: 15% deviation

Be encouraging and helpful while maintaining appropriate medical boundaries."""


ADHERENCE_ANALYSIS_PROMPT = """Analyze this medication adherence data:

Adherence Rate: {adherence_rate:.1f}%
Target: {target_rate:.0f}%
Trend: {trend}

Patterns:
- Morning adherence: {morning_adherence:.0f}%
- Evening adherence: {evening_adherence:.0f}%
- Weekday adherence: {weekday_adherence:.0f}%
- Weekend adherence: {weekend_adherence:.0f}%

Current Insights: {insights}

Provide:
1. A brief, encouraging summary (2-3 sentences)
2. 2-3 specific, actionable recommendations
3. Your reasoning

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""


PATTERN_ANALYSIS_PROMPT = """Analyze these medication adherence patterns:

Day of Week Patterns:
- Weekday rate: {weekday_rate:.0f}%
- Weekend rate: {weekend_rate:.0f}%

Time of Day Patterns:
{time_patterns}

Issues Detected:
{issues}

Provide:
1. Summary of key patterns
2. Specific recommendations to address issues
3. Reasoning

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""


SYMPTOM_ANALYSIS_PROMPT = """Analyze these reported symptoms:

{symptoms_text}

Individual Analyses:
{analyses_text}

Provide:
1. Overall summary
2. Combined recommendations
3. Whether immediate medical attention is needed

Format as JSON:
{{
    "summary": "...",
    "recommendations": ["...", "..."],
    "requires_immediate_attention": false,
    "reasoning": "..."
}}"""


SINGLE_SYMPTOM_ANALYSIS_PROMPT = """Analyze this medication-related symptom:

Symptom: {symptom}
Severity: {severity}/10
Suspected Medication: {medication}
Timing: {timing}
Description: {description}

Current Analysis:
- Is known side effect: {is_side_effect}
- Correlation score: {correlation_score}

Provide:
1. Likelihood this is medication-related (0-1)
2. Specific recommendations
3. Whether this requires medical attention

Format as JSON:
{{
    "correlation_score": 0.0,
    "is_side_effect": false,
    "requires_medical_attention": false,
    "recommendations": ["..."],
    "explanation": "..."
}}"""


# Common side effects database for reference
COMMON_SIDE_EFFECTS = {
    "metformin": ["nausea", "diarrhea", "stomach upset", "loss of appetite", "metallic taste"],
    "lisinopril": ["dry cough", "dizziness", "headache", "fatigue", "hypotension"],
    "atorvastatin": ["muscle pain", "joint pain", "nausea", "diarrhea", "headache"],
    "amlodipine": ["swelling", "edema", "dizziness", "flushing", "fatigue"],
    "omeprazole": ["headache", "nausea", "diarrhea", "stomach pain", "constipation"],
    "metoprolol": ["fatigue", "dizziness", "bradycardia", "cold extremities", "depression"],
    "levothyroxine": ["weight changes", "anxiety", "tremor", "insomnia", "sweating"],
    "gabapentin": ["drowsiness", "dizziness", "fatigue", "weight gain", "coordination issues"],
    "sertraline": ["nausea", "insomnia", "diarrhea", "dry mouth", "drowsiness"],
    "losartan": ["dizziness", "fatigue", "nasal congestion", "back pain", "diarrhea"]
}
