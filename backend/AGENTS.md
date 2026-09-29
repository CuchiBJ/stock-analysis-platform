# Backend

## Conventions

- Keep the backend a modular monolith. Prefer explicit, rule-based, testable business logic over opaque prediction systems.
- Keep HTTP transport in endpoints, domain/application logic in services, persistence in repositories, and request/response contracts in schemas where the existing architecture supports that separation.
- Register new API routers in `app/api/v1/api.py`.
- Private endpoints must remain behind `require_protected_request`. Public endpoints must be explicit and justified.
- Preserve user ownership boundaries, CSRF protections, secure cookie behavior, CORS restrictions, and fail-closed security behavior.
- Treat UTC as the canonical timezone for persisted and operational timestamps.
- Schema changes require an Alembic migration. Do not rewrite a migration that may already have been applied unless explicitly requested.

## Verification

- From `backend/`, run `venv/bin/python -m pytest tests/<relevant_test>.py` for targeted tests and `venv/bin/python -m pytest` for the broader suite.
- When relevant, run `venv/bin/python -m ruff check app tests` and `venv/bin/python -m mypy app`.
- For migrations, inspect Alembic heads and validate upgrades against a disposable database when practical.
