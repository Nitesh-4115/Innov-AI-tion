"""
Planning Agent Prompts
Prompt templates for medication scheduling and optimization
"""

PLANNING_SYSTEM_PROMPT = """You are the Planning Agent in the AdherenceGuardian medication adherence system.

Your responsibilities:
1. Create optimal medication schedules considering:
     - Drug interactions and required separations
     - Food requirements (with/without meals)
     - Patient lifestyle and preferences
     - Sleep/wake cycles
2. Identify and flag potential drug interactions
3. Replan schedules when disruptions occur
4. Provide clear reasoning for scheduling decisions

SAFETY & ACCURACY RULES (Read carefully):
- Use ONLY data provided in the patient context or medication list. Do NOT invent medication names, dosages, adherence events, or dates.
- NEVER recommend changing medication dosages, stopping medications, or providing dosing medical advice. If clinical judgment is needed, instruct to consult a clinician.
- If uncertain about an interaction or data is missing, state the uncertainty and recommend a pharmacist or clinician consult rather than guessing.
- Respect sleep times — avoid scheduling during declared sleep hours unless explicitly requested.

OUTPUT REQUIREMENTS:
- When asked to produce a schedule, RETURN VALID JSON ONLY (no surrounding text). The JSON must follow the structure described in the prompt. Example:
    {
        "schedule": {"08:00": ["Metformin 500mg"], "20:00": ["Metformin 500mg"]},
        "reasoning": "Short, factual explanation of decisions",
        "warnings": ["warning text"],
        "confidence": 0.0
    }
- If you cannot produce a schedule due to missing data, return: {"error": "explain what is missing"}

Output schedules in 24-hour format (e.g., "08:00", "14:00", "20:00").
Be concise, factual, and avoid hallucination."""


SCHEDULE_OPTIMIZATION_PROMPT = """You are a medication scheduling assistant. Create an optimal daily schedule for these medications:

{medication_list}

Constraints:
- Breakfast: {breakfast_time}
- Lunch: {lunch_time}
- Dinner: {dinner_time}
- Sleep: {sleep_time}

Drug Requirements:
{food_requirements}

Known Interactions:
{interactions}

Provide:
1. Optimal schedule (times and medications)
2. Reasoning for each decision
3. Any warnings or considerations

Format as JSON with structure:
{{
  "schedule": {{"08:00": ["Med1 dosage", "Med2 dosage"], "20:00": ["Med1 dosage"]}},
  "reasoning": "explanation",
  "warnings": ["warning1", "warning2"]
}}"""


REPLAN_SCHEDULE_PROMPT = """A patient needs to replan their medication schedule due to a disruption.

Disruption Type: {disruption_type}
Details: {disruption_details}

Current medications:
{medications}

Provide:
1. Adjusted schedule recommendations
2. Reasoning for changes
3. Any precautions

Format as JSON:
{{
    "adjusted_schedule": {{"time": ["medications"]}},
    "reasoning": "...",
    "precautions": ["..."]
}}"""


INTERACTION_CHECK_PROMPT = """Check for potential drug interactions between these medications:
{medications}

Provide any known interactions, severity, and recommendations.

Format as JSON:
{{
    "interactions": [{{"drugs": ["drug1", "drug2"], "severity": "low/moderate/high", "description": "..."}}],
    "recommendations": ["..."]
}}"""


SCHEDULE_QUERY_PROMPT = """Based on this patient's medication information:

Medications:
{medications}

Current Schedule:
{schedule}

Answer this question: {query}

Provide a clear, helpful response."""


# Common drug interaction database
KNOWN_INTERACTIONS = {
    ("metformin", "lisinopril"): {
        "severity": "low",
        "separation_hours": 0,
        "description": "Generally safe. Monitor kidney function."
    },
    ("warfarin", "aspirin"): {
        "severity": "high",
        "separation_hours": 0,
        "description": "Increased bleeding risk. Requires careful monitoring."
    },
    ("atorvastatin", "grapefruit"): {
        "severity": "moderate",
        "separation_hours": 0,
        "description": "Avoid grapefruit. Can increase statin levels."
    },
    ("metformin", "contrast_dye"): {
        "severity": "high",
        "separation_hours": 48,
        "description": "Hold metformin 48 hours before/after contrast procedures."
    },
    ("levothyroxine", "calcium"): {
        "severity": "moderate",
        "separation_hours": 4,
        "description": "Take levothyroxine 4 hours before calcium supplements."
    },
    ("ciprofloxacin", "antacids"): {
        "severity": "moderate",
        "separation_hours": 2,
        "description": "Take ciprofloxacin 2 hours before or 6 hours after antacids."
    }
}


# Food requirement guidelines
FOOD_REQUIREMENTS = {
    "with_food": [
        "metformin",
        "ibuprofen",
        "naproxen",
        "aspirin",
        "prednisone",
        "valproic_acid"
    ],
    "without_food": [
        "levothyroxine",
        "alendronate",
        "omeprazole",
        "pantoprazole",
        "esomeprazole"
    ],
    "either": [
        "lisinopril",
        "atorvastatin",
        "amlodipine",
        "metoprolol",
        "losartan"
    ]
}
