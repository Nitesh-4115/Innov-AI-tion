# API Reference

This file documents the primary API endpoints used by the frontend and integrations.

**Base path:** `/api/v1`

## Chat

### POST `/chat`
- Description: Main chat endpoint. Routes user message to the appropriate agent and returns an AI response.
- Body: `{ "patient_id": int, "message": string, "conversation_history": [ {role, content} ], "include_context": bool }`
- Response: `{ patient_id, response, agent_used, actions_taken, suggestions, timestamp }`

### POST `/chat/stream`
- Description: Server-sent events streaming response. Useful for UI streaming chat.
- Body: same as `/chat`.

### POST `/chat/quick-action`
- Description: Perform small actions (log dose, get_schedule, get_adherence, report_symptom).
- Body: `{ action: string, patient_id: int, parameters?: {} }`
- Response: `{ success: bool, action: string, result: {}, message: string }`

### GET `/chat/suggestions/{patient_id}`
- Description: Return contextual quick suggestions for the UI based on patient state (overdue doses, upcoming doses, low adherence).
- Response: `{ patient_id: int, suggestions: [ {text, action, priority} ] }`

### POST `/chat/analyze`
- Description: Lightweight NLP analysis for intent/entity extraction. Returns JSON from LLM via `generate_json`.
- Body: same as `/chat` request schema

## Patients, Medications, Schedules

Refer to `api/patients.py`, `api/medications.py`, `api/schedules.py` for CRUD and list endpoints. Common behaviors:
- `GET /patients/{id}`: returns patient profile
- `GET /patients/{id}/schedule/today`: returns today's schedule rows for patient
- `POST /patients/{id}/medications`: create medication (persists recurring template where appropriate)
- `POST /patients/{id}/schedule/regenerate`: generate schedule rows based on recurring templates

## Adherence endpoints
- `POST /adherence/log`: Log adherence events (body includes `medication_id`, `schedule_id`, `scheduled_time`, `actual_time`, `taken`)
- `GET /patients/{patient_id}/adherence/stats?days=N`: Combined stats (rate, streak, trend)
- `GET /patients/{patient_id}/adherence/daily?days=N`: Per-day adherence metrics for charting

## Notes
- Many endpoints accept/return fields that include time strings and dates; the API attempts to be timezone-aware but relies on `Patient.timezone` when present.
- Quick-action endpoints are intentionally small and synchronous; heavy operations should be routed through agents and orchestrator.
