## 1. Implementation
- [x] 1.1 Add bounded validated current-session delayed VIX client and additive protected API response.
- [x] 1.2 Update tile/types with timestamp, delay, stale warnings and daily fallback; enable minute refresh.
## 2. Verification
- [x] 2.1 Add and run offline backend fixture tests for malformed data, temporal boundaries, concurrency, cache, outages, and daily independence.
- [x] 2.2 Run frontend tests and static/build checks; inspect integrated diff and independent review.
## 3. Production
- [x] 3.1 Deploy scoped runtime files after backups and verify actual authenticated VIX quote and rollback readiness.
