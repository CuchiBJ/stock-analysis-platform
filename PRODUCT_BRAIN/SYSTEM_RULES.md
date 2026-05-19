# SYSTEM RULES
## Concrete System Rules and Thresholds

**Purpose**: Document the concrete rules and thresholds that the system uses. These are the implementation details of the philosophical principles.

---

## CORE RULES

### Setup Detection Rules

#### Rule 1: Sponsorship Threshold

**Bull Regime**: Sponsorship score ≥ 6/10
**Bear Regime**: Sponsorship score ≥ 8/10
**Volatile Regime**: Sponsorship score ≥ 9/10

**Sponsorship score components**:
- Institutional ownership trend (40%)
- Smart money flow (30%)
- Institutional concentration (20%)
- Sponsorship consistency (10%)

**Calculation**:
```
Sponsorship Score = (Ownership Trend × 0.4) + (Smart Money Flow × 0.3) + (Concentration × 0.2) + (Consistency × 0.1)
```

---

#### Rule 2: Volume Threshold

**Bull Regime**: Volume ≥ 1.5x 50-day average
**Bear Regime**: Volume ≥ 2.0x 50-day average
**Volatile Regime**: Volume ≥ 2.5x 50-day average

**Volume calculation**:
- Compare current day volume to 50-day average
- Volume must be sustained for 2+ days
- Volume must be expanding (not just spike)

---

#### Rule 3: Momentum Threshold

**Bull Regime**: RSI > 50
**Bear Regime**: RSI > 60
**Volatile Regime**: RSI > 65

**Momentum components**:
- RSI (50%)
- Rate of change (30%)
- MACD signal (20%)

**Calculation**:
```
Momentum Score = (RSI × 0.5) + (Rate of Change × 0.3) + (MACD × 0.2)
```

---

#### Rule 4: Technical Threshold

**Bull Regime**: Price > 50-day MA
**Bear Regime**: Price > 200-day MA
**Volatile Regime**: Strong trend (price > 50-day MA and 50-day MA > 200-day MA)

**Technical components**:
- Price vs moving average (50%)
- Moving average slope (30%)
- Support/resistance (20%)

---

### Setup Quality Scoring

#### Quality Score Components

**Sponsorship quality** (30%):
- Sponsorship score
- Sponsorship trend
- Sponsorship stability

**Volume quality** (25%):
- Volume expansion
- Volume sustainability
- Volume pattern

**Momentum quality** (25%):
- Momentum strength
- Momentum consistency
- Momentum trend

**Technical quality** (20%):
- Technical position
- Trend strength
- Pattern quality

**Calculation**:
```
Quality Score = (Sponsorship × 0.3) + (Volume × 0.25) + (Momentum × 0.25) + (Technical × 0.2)
```

**Score ranges**:
- 8-10: High quality
- 6-7: Medium quality
- 4-5: Low quality
- 0-3: Reject

---

### Deterioration Detection Rules

#### Rule 1: Sponsorship Deterioration

**Slow deterioration**: Sponsorship score decline of 1-2 points over 5-10 days
**Fast deterioration**: Sponsorship score decline of 1-2 points over 1-3 days
**Critical deterioration**: Sponsorship score decline of 3+ points over 1-3 days

**Actions**:
- Slow: Monitor closely
- Fast: Prepare to exit
- Critical: Exit immediately

---

#### Rule 2: Volume Deterioration

**Slow deterioration**: Volume < 1.0x average for 3-5 days
**Fast deterioration**: Volume < 0.8x average for 1-2 days
**Critical deterioration**: Volume < 0.5x average for 1 day

**Actions**:
- Slow: Monitor closely
- Fast: Prepare to exit
- Critical: Exit immediately

---

#### Rule 3: Momentum Deterioration

**Slow deterioration**: RSI decline of 5-10 points over 5-10 days
**Fast deterioration**: RSI decline of 5-10 points over 1-3 days
**Critical deterioration**: RSI decline of 15+ points over 1-3 days

**Actions**:
- Slow: Monitor closely
- Fast: Prepare to exit
- Critical: Exit immediately

---

### Regime Detection Rules

#### Bull Regime Detection

**Must meet ALL**:
- Index > 200-day MA
- Index > 50-day MA
- 50-day MA > 200-day MA
- VIX < 20
- Breadth positive (advance/decline > 1.0)

---

#### Bear Regime Detection

**Must meet ALL**:
- Index < 200-day MA
- Index < 50-day MA
- 50-day MA < 200-day MA
- Breadth negative (advance/decline < 1.0)
- Index momentum negative

---

#### Volatile Regime Detection

**Meets ANY**:
- VIX > 25
- Daily index move > 2%
- Index whipsawing (crossing MAs frequently)
- Unclear trend signals

---

### Setup Filtering Rules

#### Scarcity Rules

**Bull Regime**: Show top 20% of setups by quality score
**Bear Regime**: Show top 5% of setups by quality score
**Volatile Regime**: Show top 2% of setups by quality score

**Minimum quality thresholds**:
- Bull Regime: Quality score ≥ 6
- Bear Regime: Quality score ≥ 8
- Volatile Regime: Quality score ≥ 9

---

### Lifecycle Rules

#### Emerging Phase Duration

**Maximum duration**: 7 days
- If setup doesn't confirm in 7 days → Revert to Not Detected
- If setup confirms → Transition to Active
- If setup deteriorates → Transition to Not Detected

---

#### Active Phase Duration

**Bull Regime**: 20-30 days
**Bear Regime**: 7-14 days
**Volatile Regime**: 3-7 days

**Extension conditions**:
- Setup quality score ≥ 8
- No deterioration
- Strong continuation signals

**Early exit conditions**:
- Any deterioration in bear/volatile regime
- Fast deterioration in any regime
- Target reached

---

#### Deteriorating Phase Duration

**Maximum duration**: 5 days
- If setup recovers → Transition back to Active
- If setup continues deteriorating → Transition to Invalidated
- If target reached during deterioration → Transition to Completed

---

### Alert Rules

#### Alert Triggers

**Setup emerging**:
- Trigger: Setup state changes to Emerging
- Urgency: Low
- Action: Monitor for confirmation

**Setup active**:
- Trigger: Setup state changes to Active
- Urgency: Medium
- Action: Entry opportunity

**Setup deteriorating (slow)**:
- Trigger: Slow deterioration detected
- Urgency: Medium
- Action: Monitor closely, prepare to exit

**Setup deteriorating (fast)**:
- Trigger: Fast deterioration detected
- Urgency: High
- Action: Exit or tighten stops

**Setup deteriorating (critical)**:
- Trigger: Critical deterioration detected
- Urgency: Critical
- Action: Exit immediately

**Setup completed**:
- Trigger: Setup state changes to Completed
- Urgency: Low
- Action: Position management

**Setup invalidated**:
- Trigger: Setup state changes to Invalidated
- Urgency: Low
- Action: Loss realized

**Regime change**:
- Trigger: Regime state changes
- Urgency: High
- Action: Reassess all setups

---

### Notification Rules

#### Notification Frequency

**Real-time notifications**:
- Critical deterioration
- Regime change

**Daily notifications**:
- Setup emerging
- Setup active
- Slow deterioration
- Setup completed
- Setup invalidated

**Weekly notifications**:
- Setup quality summary
- Regime summary

---

### Data Freshness Rules

#### Market Data

**Update frequency**: Daily (end-of-day)
**Data availability**: By 6:00 PM EST
**Data retention**: 10 years

---

#### Institutional Data

**Update frequency**: Daily (end-of-day)
**Data availability**: By 8:00 PM EST
**Data retention**: 5 years

---

#### Technical Indicators

**Update frequency**: Daily (end-of-day)
**Calculation**: After market data available
**Data retention**: 5 years

---

### Performance Rules

#### API Performance

**Target response time**: < 100ms (p95)
**Target uptime**: 99.9%
**Target error rate**: < 0.1%

---

#### Calculation Performance

**Setup calculation**: < 5s per setup
**Regime calculation**: < 10s
**Narrative generation**: < 1s per setup

---

#### Data Ingestion Performance

**Market data ingestion**: < 10min for full market
**Institutional data ingestion**: < 30min
**Indicator calculation**: < 20min for full market

---

## RULE CONFIGURATION

### Configuration Storage

**Location**: Database configuration table
**Format**: JSON
**Versioning**: Rule version tracking
**Audit**: All rule changes logged

### Rule Updates

**Process**:
1. Propose rule change
2. Document rationale
3. Test in staging
4. Review and approve
5. Deploy to production
6. Monitor impact

---

## RULE ANTI-PATTERNS

### Anti-Patterns

❌ **Hard-coded values**: Rules should be configurable
❌ **No rule versioning**: Can't track changes
❌ **No rule documentation**: Rules unclear
❌ **No rule testing**: Rules may be wrong
❌ **No rule audit**: Can't track who changed what

### Correct Patterns

✅ **Configurable rules**: Rules in database
✅ **Rule versioning**: Track all changes
✅ **Rule documentation**: All rules documented
✅ **Rule testing**: Rules tested before deployment
✅ **Rule audit**: All changes logged

---

## RULE SUMMARY

**Setup detection**: Sponsorship, volume, momentum, technical thresholds
**Quality scoring**: Multi-component weighted score
**Deterioration detection**: Velocity-based rules
**Regime detection**: Trend, volatility, breadth rules
**Setup filtering**: Scarcity rules by regime
**Lifecycle rules**: Duration limits by regime
**Alert rules**: Trigger-based notifications
**Performance rules**: Response time targets

**This document defines the concrete system rules. All rule changes must follow the configuration process.**
