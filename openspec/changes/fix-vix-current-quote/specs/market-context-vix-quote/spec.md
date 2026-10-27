## ADDED Requirements

### Requirement: Current VIX quote SHALL be separate from daily evidence
The authenticated volatility response SHALL retain the existing daily vix unchanged and add optional current_quote with validated official delayed spot price, previous close, computed change, UTC observation and fetch times, actual date, source, delay and freshness. Current quote SHALL only be fetched for today's New York context date. Historical comparisons SHALL continue using daily vix.

#### Scenario: Active current session
- **WHEN** Cboe returns a valid current-session VIX spot observation
- **THEN** the API returns dated current_quote independently of daily vix and the tile shows the delayed spot and change against previous close

#### Scenario: Historical or future context
- **WHEN** as_of is not today's New York date
- **THEN** no spot request occurs and current_quote is null without future evidence leaking into daily comparison

### Requirement: VIX refresh SHALL be bounded and failure transparent
Spot calls SHALL share a 60-second cache, concurrent refresh lock, failure cooldown, response-size limit and total deadline. Invalid symbol, prices or timestamps SHALL not become observations. Failed refresh SHALL retain only correctly dated cached evidence marked stale. Quote older than 60 minutes SHALL be marked stale.

#### Scenario: Provider outage or malformed payload
- **WHEN** spot refresh fails or contains invalid evidence
- **THEN** daily evidence remains usable, no current value is invented, and any retained spot quote is explicitly stale

#### Scenario: Repeated or concurrent updates
- **WHEN** callers refresh within the cooldown
- **THEN** they share the bounded cached result rather than hammering the source

### Requirement: VIX presentation SHALL disclose temporal meaning
The tile SHALL show quote observation time in UTC and at least 20 minutes delay, automatic visible-page refresh every minute and manual refresh. It SHALL label retained stale quotes and daily-close fallback explicitly, preserving earlier server compatibility and other Market context behavior.

#### Scenario: Only daily close available
- **WHEN** spot is unavailable or belongs to an earlier session
- **THEN** the tile shows the actual dated daily close and explains that a current-session quote is unavailable
