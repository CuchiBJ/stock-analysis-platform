# MARKET REGIME ENGINE
## Market Regime Detection and Regime-Aware Logic

**Purpose**: Define how the system detects market regimes (bull, bear, volatile) and how regime affects all setup logic, filtering, and decision-making.

---

## CORE REGIME PHILOSOPHY

**Regime is the master context**. What works in a bull market fails in a bear market. Setup effectiveness varies by regime. Ignoring regime is fatal.

**The regime engine must**:
- Detect current market regime
- Adjust setup rules by regime
- Modify thresholds by regime
- Change filtering by regime
- Adapt recommendations by regime

---

## REGIME DEFINITIONS

### 1. BULL REGIME

**Definition**: Market in uptrend, risk-on environment

**Characteristics**:
- Index above 200-day moving average
- Index above 50-day moving average
- 50-day above 200-day (golden cross)
- Breadth positive
- Volatility normal to low
- Momentum positive

**Setup behavior**:
- Setups emerge more frequently
- Continuation setups work well
- Deterioration less frequent
- Hold times can be longer
- Targets can be higher

**Operational adjustments**:
- Lower thresholds for setup detection
- More setups shown
- Longer holding periods
- Higher price targets
- More tolerance for minor deterioration

---

### 2. BEAR REGIME

**Definition**: Market in downtrend, risk-off environment

**Characteristics**:
- Index below 200-day moving average
- Index below 50-day moving average
- 50-day below 200-day (death cross)
- Breadth negative
- Volatility elevated
- Momentum negative

**Setup behavior**:
- Setups emerge less frequently
- Continuation setups fail more often
- Deterioration more frequent
- Hold times must be shorter
- Targets must be lower

**Operational adjustments**:
- Higher thresholds for setup detection
- Fewer setups shown (scarcity enforced)
- Shorter holding periods
- Lower price targets
- Zero tolerance for deterioration
- Tighter stops

---

### 3. VOLATILE REGIME

**Definition**: High volatility, choppy, unclear direction

**Characteristics**:
- VIX elevated (> 25)
- Large daily index moves (> 2%)
- Index whipsawing around moving averages
- Breadth inconsistent
- Momentum unclear
- High uncertainty

**Setup behavior**:
- Setups emerge unpredictably
- Continuation setups unreliable
- Deterioration frequent and rapid
- Hold times very short
- Targets uncertain

**Operational adjustments**:
- Very high thresholds for setup detection
- Very few setups shown (extreme scarcity)
- Very short holding periods
- Conservative targets
- Immediate response to deterioration
- Very tight stops
- Reduced position sizes

---

## REGIME DETECTION

### Primary Indicators

**Trend indicators**:
- Index vs 200-day MA
- Index vs 50-day MA
- 50-day vs 200-day relationship
- Slope of moving averages

**Momentum indicators**:
- Index rate of change
- Index RSI
- Index MACD
- Breadth momentum

**Volatility indicators**:
- VIX level
- VIX rate of change
- Index daily range
- ATR (average true range)

**Breadth indicators**:
- Advance/decline ratio
- New highs/new lows
- Percentage of stocks above MA
- Breadth momentum

### Detection Logic

**Bull regime** (must meet ALL):
- Index > 200-day MA
- Index > 50-day MA
- 50-day MA > 200-day MA
- VIX < 20
- Breadth positive

**Bear regime** (must meet ALL):
- Index < 200-day MA
- Index < 50-day MA
- 50-day MA < 200-day MA
- Breadth negative
- Momentum negative

**Volatile regime** (meets ANY):
- VIX > 25
- Daily index move > 2%
- Index whipsawing (crossing MAs frequently)
- Unclear trend signals

### Detection Frequency

**Daily regime assessment**:
- Calculate all indicators
- Determine regime
- Log regime change if any
- Apply regime adjustments

**Intraday regime check**:
- If VIX spikes > 30
- If index moves > 3%
- Reassess regime immediately

---

## REGIME TRANSITIONS

### Transition Detection

**Bull → Bear transition**:
- Index breaks below 200-day MA
- Breadth turns negative
- Momentum turns negative
- Regime change logged

**Bear → Bull transition**:
- Index breaks above 200-day MA
- Breadth turns positive
- Momentum turns positive
- Regime change logged

**Any → Volatile transition**:
- VIX spikes > 25
- Large index moves
- Regime change logged

**Volatile → Bull/Bear transition**:
- VIX drops < 20
- Trend clarifies
- Regime reassessed

### Transition Handling

**On regime change**:
1. Log the transition
2. Reassess all active setups
3. Apply new regime rules
4. Send regime change notification
5. Adjust recommendations

**Setup reassessment**:
- Active setups may need tighter stops in bear
- Active setups may need longer holds in bull
- Deteriorating setups may need immediate exit in bear
- Emerging setups may be invalidated in volatile

---

## REGIME-AWARE SETUP RULES

### Setup Detection Thresholds

**Bull regime**:
- Sponsorship threshold: 6/10
- Volume threshold: 1.5x average
- Momentum threshold: RSI > 50
- Technical threshold: Price > 50-day MA

**Bear regime**:
- Sponsorship threshold: 8/10 (stricter)
- Volume threshold: 2.0x average (stricter)
- Momentum threshold: RSI > 60 (stricter)
- Technical threshold: Price > 200-day MA (stricter)

**Volatile regime**:
- Sponsorship threshold: 9/10 (very strict)
- Volume threshold: 2.5x average (very strict)
- Momentum threshold: RSI > 65 (very strict)
- Technical threshold: Strong trend (very strict)

### Setup Filtering

**Bull regime**:
- Show top 20% of setups
- More setups shown
- Lower quality threshold

**Bear regime**:
- Show top 5% of setups
- Fewer setups shown
- Higher quality threshold
- Extreme scarcity

**Volatile regime**:
- Show top 2% of setups
- Very few setups shown
- Highest quality threshold
- Extreme scarcity enforced

### Setup Scoring

**Bull regime**:
- Standard scoring weights
- Continuation favored
- Deterioration less penalized

**Bear regime**:
- Stricter scoring weights
- Quality favored
- Deterioration heavily penalized

**Volatile regime**:
- Very strict scoring weights
- Quality only
- Deterioration = immediate rejection

---

## REGIME-AWARE LIFECYCLE

### Active Phase Duration

**Bull regime**: 20-30 days
- Longer holding periods
- More patience for continuation
- Targets can be higher

**Bear regime**: 7-14 days
- Shorter holding periods
- Quick exits
- Conservative targets

**Volatile regime**: 3-7 days
- Very short holding periods
- Immediate exits
- Conservative targets

### Deterioration Response

**Bull regime**:
- Monitor slow deterioration
- May give 2-3 days
- Recovery possible

**Bear regime**:
- Immediate response to any deterioration
- Exit on first sign
- No tolerance

**Volatile regime**:
- Pre-emptive response
- Exit before deterioration
- Zero tolerance

---

## REGIME NOTIFICATIONS

### Notification Types

**Regime change detected**:
- New regime announced
- Setup rules changed
- Recommendations adjusted
- Action required

**Regime-specific setup alert**:
- Setup meets regime-specific criteria
- Higher quality in bear/volatile
- Action recommended

**Regime-specific deterioration alert**:
- Deterioration in current regime context
- Different urgency by regime
- Action required

### Notification Content

**Regime change notification**:
- Old regime → New regime
- Reason for change
- Impact on setups
- Recommended adjustments
- Action items

---

## REGIME DATA MODEL

### State Persistence

**Required fields**:
- Current regime
- Regime history (transitions)
- Regime entry timestamp
- Regime duration
- Regime indicators (current values)
- Regime confidence score

**Historical tracking**:
- All regime transitions logged
- Transition timestamps
- Transition triggers
- Indicator values at transition
- Setup impact assessment

---

## REGIME ANTI-PATTERNS

### Anti-Patterns

❌ **No regime detection**: Same rules in all markets
❌ **Static thresholds**: No adjustment by regime
❌ **No regime notifications**: Users unaware of regime
❌ **No regime history**: Losing regime context
❌ **No setup reassessment**: Regime change doesn't affect setups

### Correct Patterns

✅ **Regime detection**: Continuous regime assessment
✅ **Regime-aware thresholds**: Adjustments by regime
✅ **Regime notifications**: Users informed of regime
✅ **Regime history**: Full regime tracking
✅ **Setup reassessment**: Regime changes affect setups

---

## REGIME IMPLEMENTATION PRINCIPLES

1. **Regime is master context**: Regime affects everything
2. **Continuous detection**: Daily regime assessment
3. **Regime-aware rules**: All rules adjust by regime
4. **Regime transitions**: Logged and handled
5. **Setup reassessment**: Regime changes affect setups
6. **Regime notifications**: Users informed
7. **Regime history**: Full tracking
8. **Regime confidence**: Uncertainty acknowledged

---

## REGIME SUMMARY

**Regimes**: Bull, Bear, Volatile

**Detection**: Trend, momentum, volatility, breadth indicators

**Key principles**:
- Regime is master context
- Setup rules adjust by regime
- Thresholds vary by regime
- Regime changes trigger reassessment
- Regime history is tracked

**Critical transitions**:
- Bull → Bear: Tighten everything
- Bear → Bull: Loosen rules
- Any → Volatile: Extreme caution

**This document defines the regime engine. All logic must be regime-aware.**
