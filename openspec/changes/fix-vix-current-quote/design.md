## Context
Production Cboe CSV correctly returns 2026-10-23 close 19.45 during 2026-10-26. The official delayed spot endpoint https://cdn-api.cboe.com/api/global/delayed_quotes/quotes/_VIX.json returns data.symbol ^VIX, current_price, prev_day_close and last_trade_time (US Eastern naive ISO); top-level timestamp is publication time. Verified from production without writes. Spot on verification was 18.33. Public Cboe market-data page discloses at least 20 minutes delay.

## Goals / Non-Goals
Show latest available delayed quote with timestamp and truthful fallback; preserve daily VIX comparison semantics and protected API. No changes to posture or Dashboard.

## Decisions
- Keep existing `vix` daily payload unchanged. Add `current_quote` separately to volatility response. Existing SessionChanges remains a completed-daily comparison; never pass intraday as a daily close.
- Fixed HTTPS Cboe URL, no redirects, bounded streaming, total timeout, lock, 60-second cache and failure cooldown, injectable clocks and transport. Separate client prevents spot failure losing daily evidence. Fetch daily and spot concurrently under their own timeouts.
- Current quote fields: symbol VIX, price, previous_close, change_points, change_pct calculated from validated prices, date, observed_at UTC ISO, fetched_at UTC ISO, source Cboe, source_url official VIX page, delay_minutes 20, refresh_failed and status current/stale. Reject non-VIX symbol, non-finite/nonpositive/bool prices, malformed/future timestamps, impossible times. Interpret last_trade_time with America/New_York zone, not publication timestamp. No invented observation date.
- Request spot only when as_of equals today's New York date. Accept observations no later than as_of; older quote may be returned only marked stale. Cached quote becomes stale when over 60 minutes old or source refresh fails, regardless of cache validity. No intraday quote for historical/future context dates.
- UI promotes usable current-session current_quote, labels Cotización demorada · al menos 20 min and exact observed UTC time. Stale spot retained with warning and real timestamp; prefer available daily close when spot from another session. Explicit source failure/unavailability when spot absent, keep daily fallback. Never label spot Cierre diario. Auto refetch every 60 seconds while visible; manual button respects bounded server cache.
- Backward compatibility: current_quote optional; older server still displays daily close. No new production dependency.

## Risks / Trade-offs
- Public provider can fail or change format → strict validation, truthful fallback, focused fixture tests.
- Data are delayed, not real time → label delay and observation time explicitly.
- Daily-only original spec conflicts with current-session requirement → retain daily API/evidence and explicitly supersede presentation here.

## Migration Plan
Test offline, review integrated diff, deploy only changed runtime files after source/image backup. Build API/frontend, verify authenticated tile and protected API; rollback saved sources/images if needed. No database changes.

## Open Questions
None.
