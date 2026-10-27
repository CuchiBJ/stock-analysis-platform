## 1. Automatic capture

- [x] 1.1 [market-posture-pipeline-capture] Add focused current-session capture with uncached calculation, exact-date/nonempty-universe validation and complete payload using existing durable observation.
- [x] 1.2 [market-posture-pipeline-capture] Integrate awaited capture after qualified post-close metrics; distinguish skipped/partial SLOW runs, isolate failures, report heartbeat and retry after 300 seconds without marking failed sessions complete.

## 2. Regression coverage

- [x] 2.1 [market-posture-pipeline-capture] Add offline tests for no-visit capture, exact dates, fresh calculation, invalid/empty inputs, idempotency, coverage and overlap, persistence/calculation failure, retry cadence and session boundaries; preserve endpoint contracts.

## 3. Verification

- [x] 3.1 [market-posture-pipeline-capture] Independently review integration, concurrency and failure behavior; resolve actionable findings.
- [x] 3.2 [market-posture-pipeline-capture] Run targeted backend and frontend comparison regression checks, static checks on changed code and OpenSpec validation; inspect integrated diff and document rollout prerequisites and verification limits.

## 4. Authorized production activation

- [x] 4.1 [market-posture-pipeline-capture] Identify the explicitly authorized production target, verify existing schema and exact baseline source hashes, and isolate the six runtime files from unrelated worktree changes.
- [x] 4.2 [market-posture-pipeline-capture] Preserve previous sources/images, build and inspect the release in an isolated Python 3.11 container, and recreate only API and scheduler without migrations or backfills.
- [x] 4.3 [market-posture-pipeline-capture] Verify active source hashes, service health, scheduler startup, HTTPS/authentication and unchanged supporting containers; document recovery assets and the first eligible capture window.
