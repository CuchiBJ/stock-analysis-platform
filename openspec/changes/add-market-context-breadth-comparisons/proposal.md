## Why

Market Context summarizes broad participation through a small set of derived metrics, but it does not show how many qualified stocks are making new extremes, advancing from the open, or moving sharply. These direct counts make current participation easier to inspect while preserving deterministic, interpretable decision support.

## What Changes

- Add three OHLC-based breadth comparisons for the `QUALITY_FILTERS` universe: 52-week highs versus lows, up versus down from the open, and stocks up at least 4% versus down at least 4%.
- Include each count, coverage, and ratio in Market Context and render compact comparison rows in the Participation section.
- Clarify that the existing highs/lows ratio compares stocks near 52-week highs with stocks far from those highs, not new intraday extremes.
- Relax the presentation spec's historical eight-element limit to allow these three rows in Participation.

## Capabilities

### New Capabilities
- `market-context-breadth`: Calculate and present OHLC-based market breadth comparisons.

### Modified Capabilities
- `market-context-presentation`: Update the default Participation content and its element limit.

## Impact

Backend Market Context calculation and endpoint response, frontend Market Context types and drawer, related tests, and OpenSpec requirements. No new dependency, persistence, migration, or provider call is required.

## Non-goals

- These measurements do not alter regime, posture, scoring, or setup eligibility.
- No historical breadth charts, additional comparison types, configuration controls, or intraday provider integration.
- Historical adjusted-price discontinuities are not reconstructed by this change.
