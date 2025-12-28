"""
Barrier Resolution Agent Prompts
Prompt templates for identifying and resolving adherence barriers
"""

BARRIER_SYSTEM_PROMPT = """You are the Barrier Resolution Agent in the AdherenceGuardian medication adherence system.

Your responsibilities:
1. Identify root causes of medication adherence barriers
2. Generate personalized intervention strategies
3. Connect patients with cost assistance programs
4. Recommend schedule modifications
5. Provide practical, actionable solutions

BARRIER CATEGORIES:
- COST: Financial difficulties affording medications
- SIDE_EFFECTS: Adverse reactions affecting willingness to take
- FORGETFULNESS: Memory-related missed doses
- COMPLEXITY: Too many medications or complex timing
- BELIEFS: Doubts about medication necessity or safety
- ACCESS: Difficulty obtaining medications
- LIFESTYLE: Schedule conflicts with medication timing

IMPORTANT RULES:
- Be empathetic and non-judgmental
- Provide practical, actionable solutions
- NEVER change medication dosing without provider approval
- Always recommend provider consultation for medical decisions
- Prioritize safety in all recommendations

Focus on removing barriers while maintaining medication safety."""


BARRIER_PRIORITIZATION_PROMPT = """Prioritize these medication adherence barriers and recommend strategies:

Patient Context:
- Age: {age}
- Medications: {medication_count}
- Work Schedule: {work_schedule}

Identified Barriers:
{barriers}

Provide:
1. Brief summary (2-3 sentences)
2. Priority order for addressing barriers
3. Top 3 actionable recommendations

Format as JSON:
{{
    "summary": "...",
    "priority_order": ["barrier1", "barrier2", ...],
    "recommendations": ["...", "...", "..."],
    "reasoning": "..."
}}"""


COST_ASSISTANCE_PROMPT = """Summarize these medication cost assistance options:

{cost_options}

Provide:
1. Brief summary
2. Primary recommendation
3. Estimated potential savings
4. Next steps

Format as JSON:
{{
    "summary": "...",
    "primary_recommendation": "...",
    "estimated_savings": "...",
    "recommendations": ["...", "..."]
}}"""


SIDE_EFFECT_ANALYSIS_PROMPT = """Analyze these medication side effects and strategies:

Symptoms:
{symptoms}

Medications involved: {medications}

Provide:
1. Summary of the situation
2. Primary management strategy
3. Recommendations
4. Whether provider consultation is needed

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "recommendations": ["...", "..."],
    "requires_provider_consultation": false,
    "reasoning": "..."
}}"""


FORGETFULNESS_STRATEGY_PROMPT = """Personalize reminder strategies for this patient:

Patient Info:
- Work schedule: {work_schedule}
- Lifestyle preferences: {lifestyle_preferences}

Forgetfulness Patterns:
- Worst time: {worst_time}
- Worst day: {worst_day}
- Pattern type: {pattern_type}

Available Strategies:
{strategies}

Provide:
1. Summary of approach
2. Primary strategy
3. Personalized recommendations
4. Implementation steps

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "strategies": [...],
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""


COMPLEXITY_SIMPLIFICATION_PROMPT = """Provide regimen simplification advice:

Current Regimen:
- Medications: {medication_count}
- Daily dose times: {daily_doses}
- Complexity score: {complexity_score}/10

Available Strategies:
{strategies}

Provide:
1. Summary assessment
2. Primary simplification strategy
3. Actionable recommendations

Format as JSON:
{{
    "summary": "...",
    "primary_strategy": "...",
    "strategies": [...],
    "recommendations": ["...", "..."],
    "reasoning": "..."
}}"""


# Barrier intervention templates
INTERVENTION_TEMPLATES = {
    "cost": {
        "strategies": [
            "Generic medication alternatives",
            "Manufacturer patient assistance programs",
            "Pharmacy discount programs (GoodRx, RxSaver)",
            "Medicare/Medicaid enrollment assistance",
            "Pill splitting (where appropriate)",
            "90-day supply for cost savings"
        ],
        "resources": [
            "NeedyMeds.org",
            "RxAssist.org",
            "Medicare.gov Extra Help",
            "State pharmaceutical assistance programs"
        ]
    },
    "forgetfulness": {
        "strategies": [
            "Smartphone alarms and reminders",
            "Weekly pill organizers",
            "Habit stacking with daily routines",
            "Visual cues and placement",
            "Family/caregiver reminders",
            "Smart pill bottles"
        ]
    },
    "side_effects": {
        "strategies": [
            "Take with food (if appropriate)",
            "Timing adjustments",
            "Hydration increase",
            "Gradual dose titration discussion",
            "Alternative formulation discussion"
        ]
    },
    "complexity": {
        "strategies": [
            "Medication synchronization",
            "Combination medications",
            "AM/PM pill organizers",
            "Simplified dosing discussions",
            "Pharmacy medication therapy management"
        ]
    }
}
