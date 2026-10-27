## Context

The approved visual is additive. Existing Dashboard MarketContextBar and MarketContextDrawer must remain byte-for-byte unchanged. Current data combines a cached context and a latest SPY tile. Existing breadth uses strict OHLC extremes over the preceding 252 SPY sessions; only aggregate counts are exposed. Stock sector/name and QQQ prices already exist. VIX is not ingested.

## Goals / Non-Goals

**Goals:** An authenticated page with progressive disclosure, prominently dated SPY/QQQ, VIX, and sector constituents. Preserve current context policy and Dashboard behavior.

**Non-Goals:** No new score, weighting, thresholds, production data changes, migrations, or live VIX feed.

## Decisions

- Keep `/current` and its consumers unchanged. Add protected `/overview` returning `{context, indices, extremes}` and protected `/volatility?as_of=YYYY-MM-DD` returning `{vix}`. Fetch volatility independently so external latency/failure cannot hide internal context.
- `context` preserves the current response shape. `indices` contains SPY and QQQ entries: `{symbol, price, change_pct, date, metrics_date, trend, above_ema50, above_ema200, new_high_52w}`; unavailable price/trend/flags are null. Prices and metrics cannot be after context `as_of`; metrics cannot be after the price date. Show differing dates visibly, never imply synchronous live quotes. Daily change requires the prior SPY session close; a gap is unknown rather than a multi-session daily change. Benchmark high flags compare price to the stored closing-price high (ties qualify), so labels distinguish them from strict intraday breadth extremes.
- `extremes` contains `{date, up_count, down_count, eligible_symbols, excluded_symbols, up_ratio, sectors:[{sector,highs:[{symbol,name}],lows:[{symbol,name}]}]}`. Reuse the existing breadth loop with opt-in constituents so predicates never diverge; preserve its default exact shape. Group missing sectors as `Sin sector`, sort sectors and symbols deterministically. A symbol can appear on both sides. Cache page calculations for five minutes with bounded storage; keep counts and detail from the same computation.
- Source VIX daily closes from the official Cboe historical CSV using existing httpx. Return `{symbol:'VIX',price,change_points,change_pct,date,source:'Cboe',source_url,status:'current'|'stale'}` for the latest valid close at/before requested date, or null if unavailable. Compare to previous valid close; no synthetic zeros. Cache successful downloads for one hour and failed attempts briefly; bound network timeout/response size and coalesce concurrent refreshes. Never call external sources in tests.
- Frontend uses api-client, protected layout, independent pending/error/empty states, accessible native disclosures, and links to existing symbol pages. Preserve all existing context evidence behind concise summaries and additional metrics. Retry should work without remounting the app; abort requests on unmount and session loss.

## Risks / Trade-offs

- Daily VIX is not intraday → label daily close, source and actual date; explicitly show older data.
- Provider unavailable → show unavailable or dated cached data without blocking context.
- Breadth scan cost → reuse batched queries and bounded page cache; do not expand Dashboard requests.
- Sector metadata is current rather than historically versioned → disclose this in methodology.
- Corporate actions remain a limitation of stored OHLC, consistent with current breadth.
- Product narrative describes VIX regime rules that executable code does not use → do not implement those rules; this feature is informational only.

## Migration Plan

No schema changes. Ship additive backend endpoints and frontend together. Rollback removes the route/link and additive services. No deployment is performed in this task.
