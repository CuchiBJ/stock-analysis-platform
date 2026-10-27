## ADDED Requirements

### Requirement: Market context references are ingested independently of stock universe
The system SHALL include SPY and QQQ in scheduled price downloads and Polygon EOD filtering even if neither appears in active stocks, while preserving sector ETF references and existing stock symbols.

#### Scenario: Scheduled universe excludes QQQ
- **WHEN** the active stock provider returns symbols without QQQ
- **THEN** the scheduler passes QQQ and SPY to its price downloader exactly once, preserving all original and sector ETF symbols without mutating the original list

#### Scenario: Polygon returns QQQ outside stocks
- **WHEN** Polygon supplies valid QQQ bars and QQQ is absent from stocks
- **THEN** the EOD ingestor persists QQQ through its existing upsert path and still filters unrelated instruments

### Requirement: Fresh benchmark evidence follows existing dated pipeline
The system SHALL allow stored QQQ prices to enter the existing SLOW metrics selection regardless of stock-universe membership and SHALL retain actual dated benchmark evidence in overview.

#### Scenario: Current QQQ bar is stored
- **WHEN** QQQ has a price at the latest stored session and no stocks entry
- **THEN** SLOW selects QQQ for metric calculation

#### Scenario: Comparable QQQ evidence exists
- **WHEN** QQQ has closes at both reference sessions and same-session metrics
- **THEN** overview exposes QQQ dates, previous price, daily change and metrics date from those rows

#### Scenario: Provider evidence is missing or stale
- **WHEN** stored QQQ evidence is missing, stale or lacks the immediately preceding SPY session
- **THEN** existing unknown/date behavior remains and no synthetic current price or daily return is supplied

### Requirement: Explicitly authorized QQQ recovery is validated and atomic
The operational tool SHALL default to preparation without database writes, validate a complete260-session adjusted QQQ window against stored SPY references, preserve a QQQ-only backup, and require explicit execute mode plus a matching candidate hash before committing repaired prices and latest QQQ metrics in one transaction.

#### Scenario: Complete and approved candidate
- **WHEN** a frozen QQQ candidate covers every exact reference session with valid OHLCV and its hash matches
- **THEN** execution restores only QQQ prices and latest metrics atomically, after confirming the backup exists and current references are unchanged

#### Scenario: Missing, duplicate or invalid evidence
- **WHEN** candidate dates, symbol, OHLCV or hash are invalid or references have changed
- **THEN** execution aborts before committing any price or metric change

#### Scenario: Metric calculation fails
- **WHEN** the existing calculator raises or produces invalid critical metrics
- **THEN** the price upserts and any metric mutations are rolled back together

#### Scenario: Production verification
- **WHEN** recovery succeeds and the shared benchmark refresh is deployed
- **THEN** actual QQQ evidence is dated to the context session and the automatic update includes QQQ independently of stocks membership
