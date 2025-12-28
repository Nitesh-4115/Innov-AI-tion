# Architecture

This file mirrors the higher-level architecture of AdherenceGuardian.

Components

- Frontend (frontend/)
  - React + Vite application. Key UI pieces: Chat, Dashboard, MedicationList, Schedule.
  - Communicates with backend REST endpoints and SSE streams for chat streaming.

# Architecture

This file describes the high-level architecture of AdherenceGuardian.

## Components

- Frontend (`frontend/`)
  - React + Vite application. Key UI pieces: Chat, Dashboard, MedicationList, Schedule.
  - Communicates with backend REST endpoints and SSE streams for chat streaming.

- Backend (FastAPI)
  - Routers in `api/` (chat, patients, medications, schedules, reports, etc.)
  - `services/` layer implements business logic and wraps external systems (LLM provider, schedule/adherence logic).
  - `agents/` encapsulates domain reasoning and coordinates between services and the LLM.
  - `models.py` contains SQLAlchemy models: `Patient`, `Medication`, `Schedule`, `AdherenceLog`, `AgentActivity`, etc.

- LLM Service
  - `services/llm_service.py` wraps the configured LLM provider and injects time context (UTC + patient local) into prompts. It supports single-turn, chat, streaming, and JSON-constrained generation paths.

- Database
  - SQLAlchemy ORM backed by SQLite (development) or another RDBMS in production. All schedules, medications, and adherence logs persist to the DB.

## Deployment and runtime

- Development: Run backend with Uvicorn (`uvicorn app:app --reload`) and frontend with Vite (`npm run dev`).
- Production: Run FastAPI behind a production ASGI server (Uvicorn workers, Gunicorn) and a managed database. Ensure environment secrets and PHI safeguards.

## Interaction flow (high-level)

```mermaid
flowchart LR
  U[User] -->|message| FE[Frontend Chat UI]
  FE -->|POST /chat| API[FastAPI Chat Router]
  API -->|fetch| DB[(Database)]
  API -->|dispatch| ORCH[Orchestrator]
  ORCH --> AGENTS[Agents (Planning, Monitoring, Liaison, Barrier)]
  AGENTS -->|call| LLM[LLM Service]
  LLM --> AGENTS
  AGENTS --> API
  API --> FE
  FE --> U
```

## Safety & privacy notes

- PHI in prompts: prompts may include patient data. Limit prompt content to necessary fields and redact or pseudonymize where possible.
- Audit logs: consider storing prompts+responses for debugging (with retention policies) and ensure they are encrypted at rest.
- Always include "do not change doses" style safety rules in agent system prompts.


