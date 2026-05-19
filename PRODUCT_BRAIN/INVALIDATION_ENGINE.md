# INVALIDATION ENGINE
## Setup Failure Detection and Management

**Purpose**: Define how the system detects setup failures (invalidation) and manages the invalidation process. Early failure detection preserves capital.

---

## CORE INVALIDATION PHILOSOPHY

**Deterioration precedes reversal**. Early detection of setup failure is critical for capital preservation. The invalidation engine detects failure signals and triggers exit decisions.

**The invalidation engine must**:
- Detect setup failure early
- Distinguish temporary pullback from failure
- Trigger appropriate alerts
- Support exit decisions
- Learn from failures

---

## INVALIDATION TRIGGERS

### Primary Invalidation Triggers

#### 1. Sponsorship Failure

**Definition**: Institutional sponsorship abandons the setup

**Triggers**:
- Sponsorship score drops below threshold
- Sponsorship score drops by 3+ points
- Smart money flow turns strongly negative
- Institutional ownership declines significantly

**Thresholds**:
- Bull Regime: Sponsorship < 5
- Bear Regime: Sponsorship < 6
- Volatile Regime: Sponsorship < 7

**Velocity matters**:
- Fast drop (1-3 days): Immediate invalidation
- Slow drop (5-10 days): Monitor, may invalidate

---

#### 2. Volume Failure

**Definition**: Volume dries up, indicating lack of interest

**Triggers**:
- Volume drops below 0.5x average for 3+ days
- Volume drops below 0.3x average for 1 day
- Volume pattern breaks (no follow-through)

**Thresholds**:
- Bull Regime: Volume < 0.8x average
- Bear Regime: Volume < 1.0x average
- Volatile Regime: Volume < 1.2x average

**Velocity matters**:
- Fast drop (1-2 days): Immediate invalidation
- Slow drop (3-5 days): Monitor, may invalidate

---

#### 3. Momentum Failure

**Definition**: Momentum reverses, indicating trend change

**Triggers**:
- RSI drops below 40
- RSI drops by 15+ points
- MACD crosses negative
- Rate of change turns negative

**Thresholds**:
- Bull Regime: RSI < 45
- Bear Regime: RSI < 50
- Volatile Regime: RSI < 55

**Velocity matters**:
- Fast drop (1-3 days): Immediate invalidation
- Slow drop (5-10 days): Monitor, may invalidate

---

#### 4. Technical Failure

**Definition**: Technical breakdown, indicating pattern failure

**Triggers**:
- Price breaks below key support
- Price breaks below 50-day MA (bull regime)
- Price breaks below 200-day MA (bear regime)
- Pattern breakdown confirmed

**Thresholds**:
- Bull Regime: Price < 50-day MA
- Bear Regime: Price < 200-day MA
- Volatile Regime: Price < 50-day MA or pattern breakdown

**Velocity matters**:
- Fast breakdown (1-2 days): Immediate invalidation
- Slow breakdown (3-5 days): Monitor, may invalidate

---

### Secondary Invalidation Triggers

#### 1. Multi-Metric Failure

**Definition**: Multiple metrics failing simultaneously

**Triggers**:
- 2+ metrics failing simultaneously
- 3+ metrics failing within 3 days

**Action**: Immediate invalidation (higher confidence)

---

#### 2. Regime Change Impact

**Definition**: Regime change invalidates setup thesis

**Triggers**:
- Bull → Bear regime change
- Any → Volatile regime change (if setup quality < 9)

**Action**: Reassess setup, may invalidate

---

#### 3. Stop Loss Hit

**Definition**: Price hits predetermined stop loss

**Triggers**:
- Price hits stop loss level
- Stop loss based on technical level
- Stop loss based on volatility

**Action**: Immediate invalidation

---

## INVALIDATION DETECTION

### Detection Frequency

**Daily detection**:
- Check all invalidation triggers
- Calculate deterioration velocity
- Assess multi-metric failure
- Log invalidation signals

**Intraday detection** (critical only):
- Sponsorship drops (if available intraday)
- Volume spikes (if available intraday)
- Technical breakdown (if available intraday)
- Stop loss hit

---

### Detection Logic

**Single trigger**:
- Assess velocity
- Check regime context
- Determine if temporary or permanent
- Trigger alert if invalidation likely

**Multi-trigger**:
- Higher confidence
- Immediate invalidation
- No waiting for confirmation

**Regime context**:
- Bear/volatile: Lower threshold for invalidation
- Bull: Higher threshold, more tolerance

---

## INVALIDATION CLASSIFICATION

### Invalidation Types

#### 1. Fast Invalidation

**Definition**: Setup fails rapidly (1-3 days)

**Characteristics**:
- Fast deterioration velocity
- Multiple metrics failing
- Strong failure signals

**Action**: Immediate exit, no hesitation

**Examples**:
- Sponsorship drops 3 points in 2 days
- Volume drops to 0.3x average in 1 day
- Technical breakdown in 1 day

---

#### 2. Slow Invalidation

**Definition**: Setup fails gradually (5-10 days)

**Characteristics**:
- Slow deterioration velocity
- Single metric failing
- Weak failure signals

**Action**: Monitor closely, exit if continues

**Examples**:
- Sponsorship drops 2 points over 7 days
- Volume declines to 0.8x average over 5 days
- Momentum weakens over 7 days

---

#### 3. Regime Invalidation

**Definition**: Regime change invalidates setup

**Characteristics**:
- Regime change (bull → bear)
- Regime change (any → volatile)
- Setup thesis broken by regime

**Action**: Reassess, may exit

**Examples**:
- Bull → bear regime change
- Setup quality < 9 in volatile regime

---

#### 4. Stop Invalidation

**Definition**: Stop loss hit

**Characteristics**:
- Price hits stop level
- Predetermined exit point

**Action**: Immediate exit

**Examples**:
- Price hits support level
- Price hits volatility-based stop

---

## INVALIDATION ALERTS

### Alert Types

#### Fast Invalidation Alert

**Urgency**: Critical
**Message**: "Setup invalidating rapidly. Exit immediately."
**Action**: Exit now

#### Slow Invalidation Alert

**Urgency**: High
**Message**: "Setup deteriorating. Monitor closely or exit."
**Action**: Exit if continues

#### Regime Invalidation Alert

**Urgency**: High
**Message**: "Regime change affects setup. Reassess or exit."
**Action**: Reassess, may exit

#### Stop Invalidation Alert

**Urgency**: Critical
**Message**: "Stop loss hit. Position closed."
**Action**: Position closed

---

### Alert Content

**Every invalidation alert must include**:
- Setup ID and ticker
- Invalidation type
- Trigger metrics
- Velocity (if applicable)
- Regime context
- Recommended action
- Urgency level

---

## INVALIDATION RESPONSE

### Response Strategies

#### Fast Invalidation

**Response**: Immediate exit
- No hesitation
- No waiting for confirmation
- Close position immediately

**Rationale**: Fast deterioration indicates reversal, not pullback

---

#### Slow Invalidation

**Response**: Monitor or exit
- Monitor for 1-2 days
- Exit if deterioration continues
- Exit if deterioration accelerates

**Rationale**: Slow deterioration may be temporary

---

#### Regime Invalidation

**Response**: Reassess
- Reassess setup quality
- Reassess setup thesis
- Exit if quality < threshold
- Hold if quality remains high

**Rationale**: Regime change affects all setups differently

---

#### Stop Invalidation

**Response**: Exit immediately
- Position already closed (automated)
- Or close position manually
- No decision needed

**Rationale**: Stop loss is predetermined exit point

---

## INVALIDATION DATA MODEL

### State Persistence

**Required fields**:
- Setup ID
- Invalidation type
- Invalidation timestamp
- Trigger metrics
- Velocity (if applicable)
- Regime at invalidation
- Response taken
- Outcome (exit result)

**Historical tracking**:
- All invalidations logged
- Invalidation patterns
- Invalidation accuracy
- Learning from failures

---

## INVALIDATION LEARNING

### Failure Analysis

**For every invalidation**:
- Document the trigger
- Document the velocity
- Document the regime
- Document the response
- Document the outcome
- Analyze the pattern

**Pattern recognition**:
- Identify common failure triggers
- Identify regime-specific failure patterns
- Identify velocity thresholds
- Improve detection rules

---

### Rule Adjustment

**Based on learning**:
- Adjust invalidation thresholds
- Adjust velocity sensitivity
- Adjust regime-specific rules
- Improve detection accuracy

**Process**:
1. Analyze failure patterns
2. Identify improvement opportunities
3. Propose rule changes
4. Test in staging
5. Deploy to production
6. Monitor impact

---

## INVALIDATION ANTI-PATTERNS

### Anti-Patterns

❌ **No invalidation detection**: No failure detection
❌ **Late detection**: Detect failure too late
❌ **No velocity consideration**: Treat all deterioration equally
❌ **No regime context**: Same rules in all regimes
❌ **No learning**: Don't learn from failures

### Correct Patterns

✅ **Early detection**: Detect failure early
✅ **Velocity consideration**: Speed matters
✅ **Regime context**: Different rules by regime
✅ **Learning**: Learn from failures
✅ **Alerts**: Automated notifications

---

## INVALIDATION IMPLEMENTATION PRINCIPLES

1. **Early detection**: Detect failure before reversal
2. **Velocity matters**: Speed of deterioration critical
3. **Regime-aware**: Different rules by regime
4. **Multi-trigger**: Multiple triggers = higher confidence
5. **Clear alerts**: Automated notifications
6. **Action-oriented**: Clear response guidance
7. **Learning**: Learn from failures
8. **Observable**: All invalidations logged

---

## INVALIDATION SUMMARY

**Triggers**: Sponsorship, volume, momentum, technical failure
**Classification**: Fast, slow, regime, stop invalidation
**Response**: Immediate exit, monitor, reassess
**Alerts**: Critical/high urgency notifications
**Learning**: Pattern recognition and rule adjustment

**Key principles**:
- Early detection
- Velocity matters
- Regime-aware
- Multi-trigger
- Learning

**This document defines the invalidation engine. All setup failure detection must follow these rules.**
