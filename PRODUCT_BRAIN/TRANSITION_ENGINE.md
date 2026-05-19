# TRANSITION ENGINE
## State Transition Detection and Management

**Purpose**: Define how the system detects and manages transitions between states. Transitions are the signal, not static states. The transition engine is the core of the product.

---

## CORE TRANSITION PHILOSOPHY

**Transitions dominate over static metrics**. Change is more important than state. Momentum shifts are more valuable than absolute levels. The transition engine detects these changes.

**The transition engine must**:
- Detect all state transitions
- Calculate transition velocity
- Detect deterioration transitions
- Detect improvement transitions
- Provide transition context

---

## TRANSITION TYPES

### 1. POSITIVE TRANSITIONS

**Definition**: Improvement in key metrics

**Types**:
- Sponsorship increase
- Volume expansion
- Momentum improvement
- Technical breakout

**Detection**:
- Current value > previous value
- Rate of change positive
- Threshold crossed
- Sustained improvement

**Significance**:
- Indicates setup strengthening
- May trigger state transition
- Increases setup quality score
- May extend holding period

---

### 2. NEGATIVE TRANSITIONS

**Definition**: Deterioration in key metrics

**Types**:
- Sponsorship decline
- Volume contraction
- Momentum weakening
- Technical breakdown

**Detection**:
- Current value < previous value
- Rate of change negative
- Threshold broken
- Sustained deterioration

**Significance**:
- Indicates setup weakening
- May trigger state transition
- Decreases setup quality score
- May trigger exit

---

### 3. TRANSITION VELOCITY

**Definition**: Speed of change

**Types**:
- Fast transition (1-3 days)
- Moderate transition (4-7 days)
- Slow transition (8+ days)

**Calculation**:
- Rate of change per day
- Acceleration (change in rate)
- Velocity classification

**Significance**:
- Fast positive = strong signal
- Fast negative = urgent deterioration
- Slow = monitor, don't overreact

---

## TRANSITION DETECTION

### Metric Transitions

**Sponsorship transitions**:
- Institutional ownership change
- Smart money flow change
- Sponsorship score change
- Detection: Compare current to previous

**Volume transitions**:
- Volume vs average change
- Volume trend change
- Volume pattern change
- Detection: Compare current to average

**Momentum transitions**:
- RSI change
- MACD crossover
- Rate of change
- Detection: Compare current to previous

**Technical transitions**:
- Price vs MA change
- Support/resistance break
- Pattern completion
- Detection: Compare current to threshold

### Detection Frequency

**Daily transitions**:
- Compare end-of-day values
- Calculate rate of change
- Classify velocity
- Log transition

**Intraday transitions** (critical only):
- Sponsorship changes (if available)
- Volume spikes
- Technical breakdowns
- Immediate notification

---

## TRANSITION CONTEXT

### Transition Context Requirements

Every transition must include:
- What changed (metric)
- How much it changed (magnitude)
- How fast it changed (velocity)
- What it means (interpretation)
- What to do (action)

### Transition Interpretation

**Positive transition interpretation**:
- Setup strengthening
- May extend holding period
- May increase position size
- Continue monitoring

**Negative transition interpretation**:
- Setup weakening
- May shorten holding period
- May reduce position size
- Prepare for exit

**Fast negative transition interpretation**:
- Setup deteriorating rapidly
- Immediate action required
- Exit or tighten stops
- No hesitation

---

## TRANSITION ALERTS

### Alert Types

**Positive transition alert**:
- Metric improved
- Velocity: slow/moderate/fast
- Interpretation
- Recommendation

**Negative transition alert**:
- Metric deteriorated
- Velocity: slow/moderate/fast
- Interpretation
- Recommendation (action required)

**Critical deterioration alert**:
- Fast negative transition
- Multiple metrics deteriorating
- Immediate action required
- Exit recommendation

### Alert Urgency

**Low urgency**: Slow positive transition
- Informational
- No action required
- Continue monitoring

**Medium urgency**: Moderate positive/negative transition
- Monitor closely
- Consider adjustment
- Can wait for end of day

**High urgency**: Fast negative transition
- Immediate attention
- Action required
- Don't wait

**Critical urgency**: Critical deterioration
- Immediate action
- Exit now
- No hesitation

---

## TRANSITION AGGREGATION

### Multi-Metric Transitions

**All positive transitions**:
- Setup strengthening
- Increase quality score
- Extend holding period
- Consider increasing position

**Mixed transitions**:
- Some improving, some deteriorating
- Assess net effect
- Monitor closely
- May need adjustment

**All negative transitions**:
- Setup deteriorating
- Decrease quality score
- Shorten holding period
- Consider exit

**Fast negative on multiple metrics**:
- Critical deterioration
- Immediate exit
- No hesitation

---

## TRANSITION DATA MODEL

### State Persistence

**Required fields**:
- Metric ID
- Previous value
- Current value
- Change magnitude
- Rate of change
- Velocity classification
- Transition timestamp
- Transition type (positive/negative)

**Historical tracking**:
- All transitions logged
- Transition history per metric
- Transition history per setup
- Aggregate transition patterns

---

## TRANSITION ANTI-PATTERNS

### Anti-Patterns

❌ **Static state only**: Only showing current values, no transitions
❌ **No velocity**: Not calculating speed of change
❌ **No context**: Transitions without interpretation
❌ **No aggregation**: Not seeing multi-metric transitions
❌ **No history**: Losing transition context

### Correct Patterns

✅ **Transition-focused**: Show changes, not just states
✅ **Velocity calculation**: Speed of change matters
✅ **Transition context**: Interpretation provided
✅ **Transition aggregation**: Multi-metric view
✅ **Transition history**: Full tracking

---

## TRANSITION IMPLEMENTATION PRINCIPLES

1. **Transitions > states**: Show changes, not snapshots
2. **Velocity matters**: Speed of change is critical
3. **Context mandatory**: Every transition interpreted
4. **Aggregation important**: Multi-metric view
5. **History tracked**: Full transition history
6. **Alerts generated**: Automated notifications
7. **Action-oriented**: Transitions drive decisions
8. **Deterioration first-class**: Negative transitions critical

---

## TRANSITION SUMMARY

**Transition types**: Positive, Negative

**Velocity**: Fast, Moderate, Slow

**Key principles**:
- Transitions > static states
- Velocity matters
- Context mandatory
- Deterioration first-class
- History tracked

**Critical transitions**:
- Fast negative: Immediate action
- Multi-metric negative: Exit
- Fast positive: Strong signal

**This document defines the transition engine. All metric tracking must be transition-focused.**
