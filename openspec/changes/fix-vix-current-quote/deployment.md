# Deployment

## Scope
Five runtime files: backend volatility service and existing endpoint; frontend MarketContextPage, ContextEvidence and market-context types/helper. No database changes, migration, scheduler or trading-policy changes.

## Safety
Before deployment, source hashes matched production. The scoped release saves source-before.tar.gz, before/after SHA-256 manifests and previous API/frontend image IDs in a dated directory under /opt/stock-analysis/backups/vix-current-*. Previous images are tagged stock-analysis-api:rollback-vix-20261026 and stock-analysis-frontend:rollback-vix-20261026. Only API and frontend are rebuilt/recreated with --no-deps. Existing authentication protections stay in place.

## Rollback
Restore the five source files from source-before.tar.gz. Retag the saved API/frontend images to the Compose image names and recreate only API/frontend using --no-build --no-deps, then check their health. No database rollback is necessary.

## Result
Deployed 2026-10-26. Backup: /opt/stock-analysis/backups/vix-current-20261026T183541Z. Final server production build passed; API/frontend healthy.

Authenticated UI and service verified current_quote 18.31, -1.14 pts / -5.86%, observed_at 2026-10-26T18:21:31+00:00, actual session 2026-10-26, refresh_failed=false. Daily vix remains 19.45 dated 2026-10-23. Historical context 2026-10-23 returns current_quote=null. Unauthenticated volatility request returns 401. Manual refresh works and respects server cooldown.

Screenshot: /tmp/vix-current-production-20261026.jpg. Existing Dashboard and decision policy untouched.
