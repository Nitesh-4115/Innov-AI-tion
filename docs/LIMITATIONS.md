# Limitations and Future Improvements

This project is an experimental reference implementation intended for research and prototyping. Below are current limitations and recommended improvements before production use.

Known limitations

- LLM Hallucination: Despite tightened prompts and schema enforcement, the underlying LLM may produce inaccurate or fabricated details. Critical decisions should be validated server-side and through structured outputs.

- Timezone Dependence: Correct patient timezone information is required for accurate schedule calculations and "next dose" reasoning. Missing or incorrect timezones can produce incorrect recommendations.

- UI Dark Mode Styling: Native `<select>` elements render inconsistently across browsers/platforms in dark mode. Consider a custom, accessible dropdown component for consistent styling.

- Audit & Compliance: The current codebase does not implement full prompt/response auditing, encryption-at-rest for logs, or formal retention policies.

- Data Licensing: Some clinical data sources (e.g., DrugBank) have licensing restrictions. Ensure compliance before using or redistributing these datasets.

Future improvements

- Structured LLM Interfaces: Enforce JSON schemas for LLM responses when machine-readable output is required. Validate on the server before taking actions.

- End-to-end tests: Add integration tests that exercise chat quick actions, schedule persistence, timezone edge cases, and adherence logging.

- Monitoring & Observability: Implement prompt/response logging with redaction, request tracing, cost dashboards for LLM usage, and alerting for anomalies.

- Security & Compliance: Harden authentication (OIDC/OAuth), enable RBAC, and prepare HIPAA-compliant hosting (BAA, encryption, access controls).

- UI polish: Replace native selects, add accessibility audits, and add visual tests to avoid regressions across platforms.

Guidance for reviewers

- Treat this repository as a prototype: verify correctness with test data and do not rely on LLM outputs for clinical decisions without human review.
- When evaluating schedule/time bugs, reproduce with patient-local timestamps and confirm stored DB values are UTC-normalized and match the user-provided time converted to UTC.
