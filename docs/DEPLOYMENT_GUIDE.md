# Deployment Guide

This guide summarizes deployment considerations for production environments.

Environment and secrets

- Store secrets in a secret manager (AWS Secrets Manager, Vault, Azure Key Vault).
- Required variables include:
  - `DATABASE_URL` — connection string for production DB
  - `LLM_API_KEY` / `LLM_BASE_URL` — credentials for the LLM provider
  - `SECRET_KEY` — application signing secret

Recommended architecture

- Backend: FastAPI served by Uvicorn with Gunicorn or another process manager; run multiple worker processes behind a load balancer.
- Database: Use a managed Postgres for production; enable daily backups and point-in-time recovery.
- Vector store: Use a managed vector database or dedicated service for embeddings (Pinecone, Milvus, Weaviate) for scale and reliability.
- Frontend: Serve the built static assets from a CDN or object storage (S3 + CloudFront).

Operational concerns

- Observability: Collect application logs, metrics (Prometheus), and tracing (OpenTelemetry) for LLM calls and user actions.
- Cost Controls: Monitor LLM token usage and apply rate limits, caching, and batching for high-volume flows.
- Security: Enforce HTTPS, use CSP, and validate inputs server-side.

Compliance

- For PHI workloads, ensure a BAA with cloud providers and LLM vendors, use encrypted storage, and implement least-privilege access controls.

CI/CD

- Build pipelines should run linters and tests, build the frontend, and run integration tests against a staging environment before deploying.
- Use immutable deployment artifacts (container images) and tag releases semantically.

Rollout

- Start with a small canary deployment, monitor errors and costs, then gradually increase traffic.
- Feature flags can be used to gate risky LLM-driven features until validated.

Maintenance

- Rebuild embeddings when source data changes; automate with scheduled jobs.
- Rotate secrets periodically and enforce key expiry for third-party credentials.
