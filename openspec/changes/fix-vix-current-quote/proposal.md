## Why
Market context shows a prior daily VIX close during the active session. Its update button cannot supply an intraday observation. Dated evidence and interpretable transitions require a current quote with explicit delay while retaining completed daily observations.

## What Changes
- Add a separately dated, delayed Cboe VIX spot quote and refresh it at most once per minute.
- Display the current quote prominently with observation time, delay, and change against previous close; retain the daily close as fallback and historical evidence.
- Refresh the visible VIX automatically every minute and on request without bypassing server cooldowns.

## Capabilities
### New Capabilities
- `market-context-vix-quote`: Delayed current-session VIX evidence with truthful daily fallback.
### Modified Capabilities
None in canonical specs. Supersedes the daily-only presentation choice in active add-market-context-page, preserving its daily evidence contract.

## Impact
Backend volatility service and its tests; frontend market context tile, types and tests. Additive API field. No dependencies, database, migration, scheduler or decision-policy changes.

## Non-goals
Real-time licensed data, trading advice, changing posture, replacing the daily pair used in session comparisons, Dashboard changes.
