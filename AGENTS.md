# Repository Instructions

## Product identity

- This product is an institutional momentum operating system for swing trading, not a generic stock screener or analytics dashboard.
- Preserve transition-first, regime-aware, deterioration-aware, scarce, and interpretable decision support.
- Do not introduce black-box predictions, automated trading recommendations, retail-trading gimmicks, or decorative SaaS patterns.

## Sources of truth

- Use `PRODUCT_BRAIN/` for product intent and philosophy. Read only the documents relevant to the task.
- For an active OpenSpec change, use its `proposal.md`, `design.md`, `specs/`, and `tasks.md` as the intended behavior for that change.
- Use executable code, tests, migrations, and runtime configuration as the source of truth for current behavior.
- Use `backend/pyproject.toml`, `backend/requirements.txt`, and `frontend/package.json` for tool and dependency versions; do not rely on versions copied into narrative documentation.
- If product documents, OpenSpec artifacts, tests, and implementation disagree, surface the conflict instead of resolving it silently.

Read documentation contextually:

- Product or feature decisions: `PRODUCT_BRAIN/PRODUCT_BRAIN.md`, `PRODUCT_BRAIN/DECISION_FILTER.md`, and the relevant operational document.
- UI or interaction work: `PRODUCT_BRAIN/UX_PHILOSOPHY.md`, `PRODUCT_BRAIN/VISUAL_LANGUAGE.md`, and `PRODUCT_BRAIN/ANTI_PATTERNS.md`.
- Architectural changes: `PRODUCT_BRAIN/ARCHITECTURAL_PHILOSOPHY.md` and `PRODUCT_BRAIN/ARCHITECTURE.md`.
- Do not require a full Product Brain review for a trivial, behavior-preserving edit.

## Repository map

- `backend/`: FastAPI, async SQLAlchemy, PostgreSQL, Alembic, data pipelines, and scheduler.
- `frontend/`: Next.js App Router, React, TypeScript, Tailwind CSS, and TanStack Query.
- `PRODUCT_BRAIN/`: product principles, domain behavior, UX, and visual language.
- `openspec/`: proposed changes, specifications, designs, and implementation tasks.
- `infra/oci/`, `compose.production.yml`, and `docs/ORACLE_DEPLOY.md`: production infrastructure and operations.

## Scoped instructions

- For tasks affecting `backend/` or `frontend/`, read that directory's `AGENTS.md`; read both for cross-layer work.

## Working style

- Own requested work end to end: inspect, implement, verify, review the diff, and report the result.
- Prefer small, coherent changes. Preserve existing interfaces and unrelated behavior unless the request explicitly changes them.
- Preserve user-owned changes in a dirty worktree. Never discard, overwrite, or reformat unrelated work.
- Do not expand a scoped task into a broad refactor. When a large file must be touched, keep the edit local and mention meaningful decomposition opportunities separately.
- Make reasonable, low-risk assumptions and continue. Ask only when a missing decision would materially change behavior or scope.
- Do not add dependencies unless the existing stack cannot reasonably support the requirement; explain any new production dependency.

## Agent delegation

- The primary agent owns scope, decisions, integration, verification, and the final report.
- For complex work, delegate independent, clearly bounded subtasks to specialized subagents when doing so materially improves speed or quality.
- Useful delegated tasks include codebase exploration, independent backend/frontend investigation, documentation research, test-gap analysis, and focused security or correctness review.
- Do not spawn subagents for trivial, tightly coupled, or strictly sequential work.
- Give each subagent a concrete question, explicit scope, relevant paths, and a required deliverable. Avoid vague assignments such as "review the repository."
- Prefer read-only exploration and review agents. Delegate edits only when file ownership is non-overlapping and integration boundaries are clear.
- Never assign concurrent agents to edit the same files. Keep parallelism small and useful; normally use two or three focused subagents.
- When backend and frontend work can proceed independently, define their shared contract before delegating implementation.
- Wait for delegated work that affects the result. Reconcile conflicting findings and inspect evidence rather than copying recommendations blindly.
- The primary agent must inspect the integrated diff and run relevant verification. A subagent reporting success is not final verification.
- For changes with meaningful security, data, migration, concurrency, or cross-layer risk, use an independent review agent when practical.
- Briefly report what was delegated and how it influenced the result.

## Product invariants

- Transitions are more important than static snapshots.
- Deterioration and invalidation are first-class and should be evaluated before positive scoring.
- Market regime changes how signals are interpreted.
- Scarcity is valid: returning no qualifying setup is preferable to lowering quality thresholds.
- Core decisions must be deterministic, explainable, and inspectable.
- Compress raw metrics into operational context without hiding the evidence needed to understand a conclusion.

## OpenSpec workflow

- Use the repository OpenSpec workflow when the user asks to propose, implement, continue, or archive a change, or when work belongs to an existing active change.
- Keep implementation, tests, and the relevant OpenSpec task checklist synchronized.
- Do not create a new OpenSpec change for a trivial fix unless requested or the fix changes a meaningful contract.
- Do not mix unrelated active changes in one implementation.

## Verification

- Start with the narrowest reliable verification for the changed behavior, then broaden according to risk.
- Do not claim a check passed unless it was run. Report skipped or blocked verification and the reason.

## Safety and production boundaries

- Never read, expose, or commit secrets from `.env` files. Use example environment files for documentation.
- Do not use production services or production data for tests.
- Do not deploy, restore databases, reset credentials, run production backfills, or apply production migrations without an explicit request.
- Treat `start.sh`, administrative scripts, infrastructure scripts, and production Compose commands as state-changing operations, not routine verification.
- Do not weaken authentication, authorization, ownership isolation, CSRF, CORS, or transport security to make a test pass.

## Definition of done

- The requested behavior is complete across every affected layer.
- Relevant verification passes, or remaining gaps are stated explicitly.
- The final diff contains no accidental or unrelated changes.
- API contracts, migrations, tests, and affected documentation or OpenSpec artifacts are synchronized.
- The final report lists changed files, checks run, and any residual risk or follow-up.
