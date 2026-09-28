## Why

The dashboard's Top Actionable Setups panel competes with the Setup Feed instead of supporting the operator's actual workflow: trades originate from fresh transitions in the feed, while the separate actionable ranking can bury a newly operable pullback because it scores the age of a broad lifecycle state. BE on 2026-09-24 exposed the mismatch: it generated an `entering_pullback` transition near EMA9, yet stale structural-state age pushed it far down the actionable ranking.

This change defends transition-first workflow, context compression, and scarcity by turning that redundant panel into a small pre-signal workbench: the few structurally sound names most likely to produce the next useful Setup Feed transition.

## What Changes

- Replace the Top Actionable Setups dashboard panel with **Setups Forming**, a maximum-six candidate list that answers “what should I prepare before it reaches the Setup Feed?”.
- Select candidates from the institutional-quality universe only after deterioration and structural invalidation checks; broken, distribution-heavy, or structurally failed names never reach ranking.
- Admit intact pullbacks and contractions without a hard proximity gate to the 52-week high. Distance from the high remains explainable ranking context, so candidates such as BE or DOCN can surface before a textbook near-high setup without lowering structural quality.
- Rank formation readiness using deterministic evidence: proximity and direction toward an operational EMA trigger, pullback orderliness, volume/volatility contraction, weekly structure, relative-strength direction, market regime, and group context.
- Separate **structural age** from **opportunity age**. Setups Forming reports maturity as context, while the Setup Feed owns executable transition freshness; a long-lived structure does not automatically bury a newly developing opportunity.
- Make the two dashboard sections mutually exclusive by lifecycle: a symbol leaves Setups Forming when it has a current qualifying non-stable transition in the Setup Feed, and can return only after that transition episode ends without structural invalidation.
- Preserve the Setup Feed's current transition detection, ordering, and execution role.
- Replace actionable-specific diagnostic, chat-tool, guide, and card language with formation-stage eligibility, score breakdown, and promotion-to-feed explanations.
- **BREAKING**: retire the protected `/api/v1/transitions/actionable` contract after migrating its in-repository consumers to a formation-stage endpoint and service.

## Capabilities

### New Capabilities

- `forming-setups`: Defines pre-signal candidate eligibility, invalidation-first ranking, scarcity, lifecycle handoff to the Setup Feed, and the dashboard presentation contract.

### Modified Capabilities

- `priority-engine`: Replaces the dashboard-specific actionable score with an explainable formation-readiness ranking and separates structural maturity from operational signal freshness.
- `symbol-diagnostic`: Replaces actionable-list diagnosis with Setups Forming eligibility, exclusion, rank, and promotion-state explanations.
- `setup-card-presentation`: Adapts the compact dashboard card to show preparation-stage evidence without presenting a buy recommendation or duplicating the Setup Feed.

## Impact

- Backend: extract formation eligibility and ranking from the oversized transitions endpoint into a focused service; add the formation-stage API; update diagnostics and chat-tool routing; retire actionable-only scoring code after migration.
- Frontend: replace `TopActionableSetups` with a Setups Forming component above the Setup Feed, while preserving the Setup Feed as the execution surface, and update dashboard keyboard/navigation labels and the operator guide.
- Tests: add focused eligibility, invalidation, ranking, lifecycle handoff, historical BE-like fixture, diagnostic parity, and frontend rendering/empty/error-state coverage.
- Data model and dependencies: no new provider or production dependency is expected. Existing metrics and transition observations are sufficient; a migration is required only if implementation proves that transition episodes cannot be derived reliably from current history.
- Operations: no change to trading automation, notifications, order execution, or production scheduling cadence.

## Non-goals

- Do not change the Setup Feed's role, transition taxonomy, or current execution workflow.
- Do not guarantee that BE, DOCN, or any named ticker always appears; examples define the desired setup shape, not an allowlist.
- Do not loosen institutional structure, liquidity, tradability, or deterioration protections to increase result count.
- Do not turn the panel into a generic screener, raw table, prediction, buy list, or configurable retail filter builder.
- Do not add fundamental proxies, machine-learning ranking, alerts, broker execution, or new market-data providers.
