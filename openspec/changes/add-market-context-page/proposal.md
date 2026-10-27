## Why

Operators need a dedicated market-context page with prominent benchmark evidence and inspectable breadth constituents. Preserve the existing Dashboard context bar and drawer exactly while adding the approved page, supporting context compression and deterioration visibility.

## What Changes

- Add authenticated `/market-context` and a navigation link immediately after Dashboard.
- Organize existing context dimensions, highlight SPY/QQQ, and show dated VIX daily-close evidence.
- Expand new 52-week extremes into constituent lists grouped by sector with consistent coverage and session semantics.
- Preserve all Dashboard rendering, interactions, current API contract, and decision policies.

## Capabilities

### New Capabilities
- `market-context-page`: Dedicated presentation and additive evidence endpoints.

### Modified Capabilities
None. Existing Dashboard and breadth definitions remain unchanged.

## Non-goals

No weighting or posture/regime changes, trading recommendations, deployment, production backfills, or replacement of the Dashboard drawer. VIX is informational, not a new risk threshold.

## Impact

Frontend navigation and new page/components; additive backend endpoints and small services reusing breadth eligibility. No production dependency or database migration anticipated. Existing large MarketContext engine and drawer remain untouched.
