"""
Healthcare Liaison Agent Prompts
Prompt templates for provider communication and FHIR report generation
"""

LIAISON_SYSTEM_PROMPT = """You are the Healthcare Liaison Agent in the AdherenceGuardian medication adherence system.

Your responsibilities:
1. Generate FHIR-compatible provider reports
2. Format clinical summaries for healthcare teams
3. Handle urgent escalations appropriately
4. Facilitate patient-provider communication
5. Coordinate care across the healthcare team

CLINICAL COMMUNICATION GUIDELINES:
- Use professional, clinical language
- Be concise and factual
- Prioritize actionable information
- Include relevant context without overwhelming detail
- Follow HIPAA-compliant communication practices

ESCALATION SEVERITY LEVELS:
- CRITICAL (9-10): Immediate provider contact required
- HIGH (7-8): Same-day communication recommended
- MODERATE (5-6): Within 48 hours
- LOW (1-4): Include in routine reports

FHIR COMPLIANCE:
- Generate valid FHIR R4 resources
- Use standard coding systems (LOINC, SNOMED CT)
- Include proper resource references

IMPORTANT:
- NEVER provide medical diagnoses
- ALWAYS recommend provider consultation for medical decisions
- Maintain patient privacy in all communications
- Clearly indicate urgency levels in escalations"""


CLINICAL_NARRATIVE_PROMPT = """Generate a clinical narrative for a medication adherence report.

Report Type: {report_type}
Period: {period_start} to {period_end}

Adherence Data:
- Rate: {adherence_rate}%
- Target: {target_rate}%
- Total doses: {total_doses}
- Doses taken: {taken_doses}

Medications: {medication_count}

Symptoms Reported: {symptom_count}
{symptoms_detail}

Barriers Identified: {barrier_count}
{barriers_detail}

Generate:
1. A concise summary (1-2 sentences)
2. A clinical narrative (2-3 paragraphs) suitable for a healthcare provider
3. Key findings list

Format as JSON:
{{
    "summary": "...",
    "narrative": "...",
    "key_findings": ["...", "..."]
}}"""


ESCALATION_MESSAGE_PROMPT = """Generate an escalation message for a healthcare provider.

Severity: {severity}
Reason: {reason}

Context:
- Recent adherence: {adherence_rate}%
- Recent symptoms: {symptoms}

Additional Details: {details}

Generate:
1. A clear, professional message for the provider
2. Recommended action
3. Patient guidance to provide

Format as JSON:
{{
    "message": "...",
    "recommended_action": "...",
    "patient_guidance": "..."
}}"""


CARE_COORDINATION_PROMPT = """Generate a care coordination summary for a healthcare team.

Patient Overview:
- Medications: {medication_count}
- Active Barriers: {active_barriers}
- Active Interventions: {active_interventions}

Recent Agent Activities: {activity_count}

Barrier Resolutions: {resolution_count}

Active Interventions: {intervention_count}

Generate:
1. Brief summary
2. Care coordination narrative
3. Recommendations for the care team

Format as JSON:
{{
    "summary": "...",
    "narrative": "...",
    "recommendations": ["...", "..."]
}}"""


# FHIR coding systems
FHIR_CODING_SYSTEMS = {
    "loinc": "http://loinc.org",
    "snomed": "http://snomed.info/sct",
    "rxnorm": "http://www.nlm.nih.gov/research/umls/rxnorm",
    "icd10": "http://hl7.org/fhir/sid/icd-10-cm",
    "observation_category": "http://terminology.hl7.org/CodeSystem/observation-category",
    "condition_clinical": "http://terminology.hl7.org/CodeSystem/condition-clinical",
    "interpretation": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation"
}


# Common LOINC codes for adherence
ADHERENCE_LOINC_CODES = {
    "medication_adherence": "LA14080-8",
    "adherence_assessment": "71942-6",
    "medication_taking_behavior": "10165-0"
}


# Severity to SNOMED mapping
SEVERITY_SNOMED_CODES = {
    "mild": {"code": "255604002", "display": "Mild"},
    "moderate": {"code": "6736007", "display": "Moderate"},
    "severe": {"code": "24484000", "display": "Severe"}
}


# Report templates
REPORT_SECTIONS = {
    "executive_summary": {
        "title": "Executive Summary",
        "required_fields": ["period", "adherence_status", "adherence_rate", "medication_count"]
    },
    "adherence": {
        "title": "Medication Adherence",
        "required_fields": ["current_rate", "target_rate", "status", "doses_tracked"]
    },
    "medications": {
        "title": "Current Medications",
        "required_fields": ["name", "dosage", "frequency"]
    },
    "symptoms": {
        "title": "Reported Symptoms",
        "required_fields": ["count", "unresolved", "high_severity"]
    },
    "barriers": {
        "title": "Identified Barriers",
        "required_fields": ["category", "description", "status"]
    },
    "interventions": {
        "title": "Active Interventions",
        "required_fields": ["type", "description", "status"]
    }
}


# Escalation response timeframes
ESCALATION_TIMEFRAMES = {
    "critical": "Immediate attention required",
    "high": "Same-day response recommended",
    "moderate": "Within 48 hours",
    "low": "At next scheduled visit"
}
