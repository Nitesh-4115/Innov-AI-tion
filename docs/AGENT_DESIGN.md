# Agent Design

This document describes each agent's responsibilities, expected inputs/outputs, and interaction patterns with the LLM.

Agents

# Agent Design

This document describes each agent's responsibilities, expected inputs/outputs, and interaction patterns with the LLM.

## Agents

### Planning Agent
- Purpose: Create or re-plan optimal medication schedules that respect interactions, food requirements, and user preferences.
- Input: Patient meds list, constraints (interactions, food requirements, preferences), optional new medication.
- Output: Structured JSON schedule, reasoning, and warnings. System prompt enforces JSON-only for schedule outputs.
- Safety: Always include "do not change doses" instruction; return an error JSON when data is missing.

### Monitoring Agent
- Purpose: Interpret adherence logs, summarize recent adherence, identify missed/overdue doses, and suggest quick actions.
- Input: Recent `AdherenceLog` rows, upcoming schedule.
- Output: Human-friendly summary and optional quick action suggestions.

### Liaison Agent
- Purpose: Assist with adding medications, preparing structured messages for clinicians, and handling user-/provider-facing requests.
- Input: Free-text requests to add or update medications.
- Output: Confirmation of CRUD actions, or clarifying questions.

### Barrier Agent
- Purpose: Recommend non-clinical interventions (cost assistance, pickup options, adherence strategies).
- Input: Social determinants, cost/adherence cues.
- Output: Practical recommendations and resources.

## LLM interactions

- All agents use `BaseAgent.call_llm` which appends a Time Context block (UTC + local) to system prompts.
- Structured tasks use `LLMService.generate_json` or clearly-requested JSON-only system prompts to reduce hallucination and make outputs machine-parseable.
- Agents should defensively validate LLM outputs before persisting anything to the DB.

## Prompt hygiene

- Include explicit safety constraints in system prompts (no dosing advice, do not invent data).
- Ask clarifying follow-up questions when required fields are missing.
- For planning, return JSON-only. For conversational answers, cite context lines used if assertions are made.
