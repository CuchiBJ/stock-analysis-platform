## ADDED Requirements

### Requirement: Market Context SHALL expose daily OHLC breadth comparisons
The Market Context response SHALL expose `participation.breadth_comparisons` for its resolved `as_of` date. It SHALL include new 52-week highs versus lows, advancing versus declining from open, and stocks up at least 4% versus down at least 4%. For each measure it SHALL include positive and negative counts, eligible and excluded symbol counts, and a nullable positive ratio. The service SHALL use only symbols satisfying `QUALITY_FILTERS` on `as_of`, exact-date OHLC for that session, finite positive price inputs, and no price rows after `as_of`. SPY price dates SHALL define market sessions. The annual comparison SHALL use the 252 distinct SPY price dates immediately preceding `as_of`, requiring valid high and low (high ≥ low) on every date for eligibility. The daily ±4% comparison SHALL use the latest SPY price date before `as_of` and require the symbol's close on that exact date. The service SHALL NOT fall back to price dates from other symbols if the SPY calendar is missing. Ratios SHALL be positive / (positive + negative), and SHALL be null when there are no events.

#### Scenario: Strict 52-week intraday extremes
- **WHEN** a qualified symbol has valid high and low on all 252 globally preceding price dates and its session high exceeds every prior high or its session low is below every prior low
- **THEN** count each qualifying extreme; equal highs and lows are not new extremes and both sides may count on one session

#### Scenario: Annual history incomplete
- **WHEN** a qualified symbol is missing a valid high or low on any of the 252 preceding SPY price dates
- **THEN** exclude that symbol from the annual-extreme eligible count

#### Scenario: Opening direction and neutral ties
- **WHEN** exact-session open and close are finite and positive
- **THEN** count close above open as advancing, close below open as declining, and equality as neutral while retaining the symbol in eligible coverage

#### Scenario: Daily move thresholds
- **WHEN** exact-session close and prior-session close are valid and positive
- **THEN** count a gain of at least 4% as positive and a loss of at least 4% as negative, with exact ±4% included

#### Scenario: Missing inputs and zero events
- **WHEN** a symbol lacks required valid inputs or a comparison has no positive and negative events
- **THEN** exclude the symbol only from the affected measure and return a null ratio when its event denominator is zero

#### Scenario: Historical analysis
- **WHEN** Market Context is reconstructed for a historical `as_of`
- **THEN** every breadth comparison uses only data dated at or before that `as_of` and reports that resolved date

#### Scenario: SPY session calendar is absent
- **WHEN** other symbols have price rows before `as_of` but SPY has no preceding price date
- **THEN** annual and daily-move coverage is zero while exact-date open-versus-close participation remains available

### Requirement: Breadth calculation SHALL not affect market decisions
The new comparison counts SHALL remain informational and SHALL NOT change participation descriptors, regime, posture, scoring, or setup filters.

#### Scenario: Breadth changes without decision inputs changing
- **WHEN** OHLC breadth inputs change while the existing participation and leadership inputs remain unchanged
- **THEN** the new comparison values may change but descriptor, regime, posture, and setup eligibility remain unchanged
