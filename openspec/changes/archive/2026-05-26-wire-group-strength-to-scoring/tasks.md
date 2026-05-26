## 1. Group strength service module

- [ ] 1.1 Create `backend/app/services/group_strength_service.py` with module docstring referencing this change and the `context_decision_filter` as architectural mirror.
- [ ] 1.2 Define `@dataclass(frozen=True) class GroupMultiplier` with fields `score_multiplier: float`, `badge: str`. Validate `score_multiplier ∈ {0.85, 1.0, 1.15}` in `__post_init__`. Validate `badge ∈ {"leader", "neutral", "weak"}`.
- [ ] 1.3 Define module-level constant `_NEUTRAL = GroupMultiplier(1.0, "neutral")` and `_MIN_GROUP_SIZE = 5` (small-group guard).
- [ ] 1.4 Implement `def compute_group_multiplier(market_group: str | None, group_perfs: dict[str, dict]) -> GroupMultiplier`. Input shape: `{group_name: {"performance_monthly": float, "stock_count": int}}`. Logic: NULL group → neutral; empty perfs → neutral; group not in perfs → neutral; group with stock_count<5 → neutral; else compute percentile rank, return leader/neutral/weak.
- [ ] 1.5 Implement `async def fetch_current_group_strengths(db) -> dict[str, dict]`. Calls `SectorService(db).calculate_sector_performance()`, transforms to dict keyed by group name. Catches exceptions and returns `{}` (cold-start safety).
- [ ] 1.6 Add in-memory cache (module-level dict with TTL 5 min, idéntico al `context_decision_filter`). Cache key: `"current_group_strengths"` (singleton). `clear_cache()` helper for tests.
- [ ] 1.7 Unit tests `backend/tests/test_group_strength_service.py` covering: top-5 leader, bottom-5 weak, middle neutral, NULL group → neutral, empty perfs → neutral, group not in perfs → neutral, small group (n<5) → neutral, composition example (priority 80, ctx 0.5, group 1.15 → 46), cache hit on second call within TTL.

## 2. Actionable endpoint integration

- [ ] 2.1 In `backend/app/api/v1/endpoints/transitions.py`, import `fetch_current_group_strengths` and `compute_group_multiplier` from `group_strength_service`.
- [ ] 2.2 In the `/actionable` handler, after fetching `participation, leadership`, fetch `group_perfs = await fetch_current_group_strengths(db)` once per request.
- [ ] 2.3 For each setup in the loop, fetch `stock.market_group` (add to the query if not already joined). Compute `group_mult = compute_group_multiplier(stock.market_group, group_perfs)`.
- [ ] 2.4 Update the priority calculation: replace `ctx_priority = min(1.0, priority_score * ctx_multiplier.score_multiplier)` with `final_priority = min(100, priority_score * ctx_multiplier.score_multiplier * group_mult.score_multiplier)`. Note: priority_score is on 0-100 scale in this codebase; the existing `min(1.0, ...)` looks like a bug or a unit shift — verify against current behavior before changing.
- [ ] 2.5 Add `"group_strength": {"group": stock.market_group, "badge": group_mult.badge, "multiplier": group_mult.score_multiplier}` to each item in the actionable response.
- [ ] 2.6 Smoke test: `curl localhost:8000/api/v1/transitions/actionable | jq '.[] | {symbol, priority_score, group_strength}'` — verify field present and multiplier reflected in score.

## 3. Queue endpoints integration

- [ ] 3.1 In `backend/app/services/setup_queue_service.py`, update `list_u_and_r`, `list_emerging_leaders`, and `list_building_bases` to include `market_group` in each result dict. Source: join on `Stock.market_group` or read from already-joined `Stock` object.
- [ ] 3.2 In `backend/app/api/v1/endpoints/queue.py`, after fetching results, fetch `group_perfs` once per request (reuse `fetch_current_group_strengths`).
- [ ] 3.3 Enrich each item: `item["group_strength"] = {"group": item["market_group"], "badge": compute_group_multiplier(item["market_group"], group_perfs).badge}` (drop the `multiplier` field — not applicable for queue).
- [ ] 3.4 Apply to all 3 endpoints (`/u-and-r`, `/emerging-leaders`, `/building-bases`). Building-bases included (badge only, no functional effect).
- [ ] 3.5 Verify the sort order of each lens is identical to before — only the per-item shape changed.
- [ ] 3.6 Smoke test: `curl localhost:8000/api/v1/queue/u-and-r | jq '.results[0:3] | .[] | {symbol, group_strength}'` for each endpoint.

## 4. Frontend shared badge component

- [ ] 4.1 Create `frontend/components/shared/GroupStrengthBadge.tsx` accepting props `{group: string | null, badge: "leader" | "neutral" | "weak", rank?: number | null}`. Returns `null` when `badge === "neutral"` or `group === null`.
- [ ] 4.2 Implement leader variant: cyan-400 chip with text `"🔥 Group leader"`, `title` attribute showing `"{group} · #{rank} of 25"` when rank present, else just group name.
- [ ] 4.3 Implement weak variant: amber-400 chip with text `"⚠️ Weak group"`, same tooltip pattern.
- [ ] 4.4 Keep the chip compact (px-2 py-0.5 text-[10px] uppercase tracking-wide) to fit inside CompactSetupCard without disrupting layout.

## 5. Frontend integration — actionable

- [ ] 5.1 In `frontend/components/dashboard/CompactSetupCard.tsx`, add prop `groupStrength?: {group: string | null, badge: string, multiplier?: number} | null`.
- [ ] 5.2 Render `<GroupStrengthBadge>` in an appropriate slot inside the card (near setup_type or near priority_score — choose based on visual density, validate in browser).
- [ ] 5.3 In `frontend/components/dashboard/TopActionableSetups.tsx`, pass `groupStrength={setup.group_strength}` to each `<CompactSetupCard>`.
- [ ] 5.4 Type the new field on the actionable setup type (if a typed interface exists, otherwise inline type).
- [ ] 5.5 Visual check at `/dashboard`: setups in leader groups show cyan chip, weak groups show amber chip, neutral groups show no chip. Hover reveals group name.

## 6. Frontend integration — queue pages

- [ ] 6.1 In `frontend/app/queue/u-and-r/page.tsx`, add the badge to each row using `<GroupStrengthBadge group={item.group_strength?.group} badge={item.group_strength?.badge} />`.
- [ ] 6.2 Same for `frontend/app/queue/emerging-leaders/page.tsx`.
- [ ] 6.3 Same for `frontend/app/queue/building-bases/page.tsx`.
- [ ] 6.4 Verify the badge does NOT alter row order in any of the 3 queues — that's the contract.
- [ ] 6.5 Visual check at each `/queue/<lens>`: badges show inline with each row, no layout shifts when present/absent.

## 7. Verification

- [ ] 7.1 Backend tests: `cd backend && pytest tests/test_group_strength_service.py -v` — all pass.
- [ ] 7.2 Frontend `npx tsc --noEmit` — zero errors.
- [ ] 7.3 Compose check: with backend running, fetch `/actionable` and verify a setup in a leader group has `priority_score = base_priority × ctx_mult × 1.15` (manually compute one example from the response).
- [ ] 7.4 Cold-start safety check: temporarily break `SectorService.calculate_sector_performance` (or run with empty DB), confirm `/actionable` still returns setups with `group_strength: {badge: "neutral"}` and `multiplier=1.0` applied (no error propagation).
- [ ] 7.5 Confirm sort order in queue endpoints is byte-identical (modulo new field) to before the change.
- [ ] 7.6 Open `/dashboard` and each `/queue/<lens>` page; visual smoke test that badges render and don't break layout.

## 8. Cleanup and OpenSpec close

- [ ] 8.1 Run `openspec validate wire-group-strength-to-scoring --strict` — expect clean.
- [ ] 8.2 Confirm no changes to `market_group_mapping.py` were needed (this change is a pure consumer of `market-group-rotation`).
- [ ] 8.3 Update `MEMORY.md` index with a one-line entry pointing to the new memory file `group_strength_wiring_started.md` capturing shipped date, multiplier range, and the "queue badge-only" decision.
