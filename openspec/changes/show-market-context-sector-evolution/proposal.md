## Why
A single sector extreme snapshot cannot reveal whether events are spreading across sectors or concentrating over multiple sessions. Dated rates and denominators make deterioration and changes inspectable without inventing persistent trends.
## What Changes
- Add five stored-session history of 52-week high/low counts, eligible/excluded coverage by sector.
- Compare exact window endpoints with intermediate session evidence, sector incidence and separate event concentration.
- Expose current-metadata attribution and variable-population limitations.
## Capabilities
### New Capabilities
- `market-context-sector-evolution`: bounded sector extreme history and interpretable change.
### Modified Capabilities
None.
## Non-goals
No sector predictions, ETF rankings, policy/scoring/dashboard changes, deployment, backfills or historical metadata reconstruction.
## Impact
New protected dated endpoint and cached bulk-query service, shared annual-extreme calculation, dedicated page component/helper/tests. No migrations or dependencies. No large service is extended.
