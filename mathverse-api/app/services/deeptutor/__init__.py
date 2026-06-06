"""DeepTutor full-capability client package.

The original single-file client (`app.services.deeptutor_ws` + `agent_client`)
covers only the lightweight `/api/v1/chat` + vision/judge WS. This package adds
clients for the rest of DeepTutor's surface:

- `transport`  — shared REST helper toward the DeepTutor backend.
- `turn`       — the unified_ws turn runtime (DeepTutor's agentic core).
- `tenancy`    — per-user namespacing over DeepTutor's single-tenant data space.

Domain REST clients (knowledge / sessions / notebook / book / memory / ...) are
added in `rest.py` by the phases that consume them, to avoid speculative code.
"""
