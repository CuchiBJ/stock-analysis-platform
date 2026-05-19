# SETUP LIFECYCLE
## How Setups Evolve from Detection to Completion

**Purpose**: Define the lifecycle of a momentum setup from initial detection through active trading to completion or invalidation. This ensures the system tracks setup evolution, not just static snapshots.

---

## CORE LIFECYCLE PHILOSOPHY

**Setups are living entities**, not static states. They evolve through distinct phases, each with different characteristics, risks, and operational requirements.

**The lifecycle must**:
- Track state transitions
- Detect deterioration early
- Support decision-making at each phase
- Maintain historical context
- Enable regime-aware adjustments

---

## LIFECYCLE STATES

### 1. NOT DETECTED

**Definition**: No setup conditions met

**Characteristics**:
- Stock not in setup
- No momentum signal
- No institutional sponsorship
- No actionable pattern

**Operational requirements**:
- Monitor for emergence
- No user action required
- Background monitoring only

**Transition triggers**:
- Sponsorship threshold crossed
- Volume expansion detected
- Momentum signal initiated

---

### 2. EMERGING

**Definition**: Setup conditions beginning to form

**Characteristics**:
- Early sponsorship signal
- Volume starting to expand
- Momentum initiating
- Pattern not yet confirmed

**Operational requirements**:
- Monitor closely
- Watch for confirmation
- Prepare for potential entry
- High vigilance for deterioration

**Transition triggers**:
- Full sponsorship confirmation
- Volume sustained above threshold
- Momentum confirmed
- All setup criteria met

**Deterioration triggers**:
- Sponsorship fails to develop
- Volume contracts
- Momentum reverses
- Setup criteria not met within timeframe

---

### 3. ACTIVE

**Definition**: Setup fully confirmed and actionable

**Characteristics**:
- All criteria met
- Strong institutional sponsorship
- Volume expanded and sustained
- Momentum confirmed
- Setup in optimal trading window

**Operational requirements**:
- Primary trading phase
- Entry decisions made here
- Monitor for continuation
- Watch for deterioration signs
- Position management

**Transition triggers**:
- Deterioration detected
- Setup completes (target reached)
- Setup invalidates (stop hit)
- Regime change affects setup

**Deterioration triggers**:
- Sponsorship declining
- Volume contracting
- Momentum weakening
- Technical breakdown

---

### 4. DETERIORATING

**Definition**: Setup showing signs of failure

**Characteristics**:
- Sponsorship declining
- Volume contracting
- Momentum weakening
- Technical breakdown
- Risk of reversal increasing

**Operational requirements**:
- Exit decisions critical
- Tighten stops
- Reduce exposure
- Prepare for exit
- High alert for reversal

**Transition triggers**:
- Deterioration reverses (back to Active)
- Setup invalidates (stop hit)
- Setup completes (target reached)
- Setup abandoned

**Recovery triggers**:
- Sponsorship stabilizes
- Volume re-expands
- Momentum resumes
- Technical recovery

---

### 5. INVALIDATED

**Definition**: Setup failed, stop hit

**Characteristics**:
- Stop loss triggered
- Setup thesis broken
- Momentum reversed
- Sponsorship abandoned

**Operational requirements**:
- Position closed
- Loss realized
- Post-trade analysis
- Learn from failure

**Final state**: No further transitions

---

### 6. COMPLETED

**Definition**: Setup succeeded, target reached

**Characteristics**:
- Price target achieved
- Setup thesis validated
- Momentum sustained
- Profit realized

**Operational requirements**:
- Position closed
- Profit realized
- Post-trade analysis
- Document success pattern

**Final state**: No further transitions

---

## STATE TRANSITIONS

### Valid Transitions

```
Not Detected → Emerging
Emerging → Active
Emerging → Not Detected (failed to emerge)
Active → Deteriorating
Active → Completed
Active → Invalidated
Deteriorating → Active (recovery)
Deteriorating → Invalidated
Deteriorating → Completed (if target reached during deterioration)
```

### Invalid Transitions

```
Not Detected → Active (must go through Emerging)
Not Detected → Deteriorating (no setup to deteriorate)
Not Detected → Completed (no setup to complete)
Not Detected → Invalidated (no setup to invalidate)
Emerging → Completed (must be Active first)
Emerging → Invalidated (must be Active first)
Completed → Any (final state)
Invalidated → Any (final state)
```

---

## DETERIORATION DETECTION

### Deterioration Signals

**Sponsorship deterioration**:
- Institutional ownership declining
- Smart money flow negative
- Sponsorship score dropping
- Rate of decline matters

**Volume deterioration**:
- Volume contracting below threshold
- Volume drying up
- No follow-through
- Volume divergence from price

**Momentum deterioration**:
- RSI weakening
- MACD crossover negative
- Price momentum slowing
- Rate of change negative

**Technical deterioration**:
- Price below key moving average
- Support level broken
- Pattern breakdown
- Negative technical divergence

### Deterioration Velocity

**Slow deterioration**:
- Gradual decline over 5-10 days
- Monitor closely
- May be temporary
- Don't overreact

**Fast deterioration**:
- Rapid decline over 1-3 days
- Immediate action required
- High probability of reversal
- Exit or tighten stops

**Deterioration acceleration**:
- Rate of decline increasing
- Critical situation
- Exit immediately
- No hesitation

---

## REGIME IMPACT ON LIFECYCLE

### Bull Regime

**Lifecycle characteristics**:
- Setups emerge more frequently
- Active phase longer
- Deterioration less frequent
- Completion rate higher

**Adjustments**:
- Lower thresholds for Emerging
- Longer hold times in Active
- More tolerance for minor deterioration
- Higher targets for Completion

### Bear Regime

**Lifecycle characteristics**:
- Setups emerge less frequently
- Active phase shorter
- Deterioration more frequent
- Completion rate lower

**Adjustments**:
- Higher thresholds for Emerging
- Shorter hold times in Active
- Zero tolerance for deterioration
- Lower targets for Completion
- More aggressive stops

### Volatile Regime

**Lifecycle characteristics**:
- Setups emerge unpredictably
- Active phase volatile
- Deterioration frequent and rapid
- Completion rate unpredictable

**Adjustments**:
- Very high thresholds for Emerging
- Very short hold times in Active
- Immediate response to deterioration
- Tight stops
- Reduced position sizes

---

## LIFECYCLE TIMING

### Typical Durations

**Emerging phase**: 3-7 days
- From first signal to full confirmation
- Monitor closely
- High vigilance

**Active phase**: 10-30 days
- Primary trading window
- Depends on regime
- Depends on setup type

**Deteriorating phase**: 1-5 days
- Critical decision window
- Exit or recover
- Short duration

### Timeframe Adjustments

**By regime**:
- Bull: Longer Active phase
- Bear: Shorter Active phase
- Volatile: Very short Active phase

**By setup quality**:
- High quality: Longer Active phase
- Medium quality: Standard Active phase
- Low quality: Short Active phase

---

## LIFECYCLE MONITORING

### Monitoring Frequency

**Emerging**: Daily
- Check confirmation status
- Watch for deterioration
- Prepare for entry

**Active**: Daily
- Monitor continuation
- Watch for deterioration
- Manage position

**Deteriorating**: Intraday
- Immediate action required
- Watch for reversal or failure
- Exit decisions

### Monitoring Checklist

**Emerging phase**:
- [ ] Sponsorship developing?
- [ ] Volume expanding?
- [ ] Momentum confirming?
- [ ] Deterioration signs?

**Active phase**:
- [ ] Sponsorship maintained?
- [ ] Volume sustained?
- [ ] Momentum continuing?
- [ ] Deterioration signs?
- [ ] Regime changed?

**Deteriorating phase**:
- [ ] Deterioration accelerating?
- [ ] Recovery possible?
- [ ] Exit decision made?
- [ ] Position managed?

---

## LIFECYCLE NOTIFICATIONS

### Notification Types

**Emerging confirmation**:
- Setup now Active
- Entry window open
- Action required

**Deterioration alert**:
- Setup deteriorating
- Action required
- Urgency based on velocity

**Setup completion**:
- Target reached
- Position management
- Optional exit

**Setup invalidation**:
- Stop hit
- Position closed
- Loss realized

### Notification Urgency

**Low urgency**: Emerging confirmation
- Can wait for end of day
- Plan entry for next day

**Medium urgency**: Slow deterioration
- Monitor closely
- Plan exit
- Can wait for end of day

**High urgency**: Fast deterioration
- Immediate attention
- Exit or tighten stops
- Don't wait

**Critical urgency**: Deterioration acceleration
- Immediate action
- Exit now
- No hesitation

---

## LIFECYCLE DATA MODEL

### State Persistence

**Required fields**:
- Setup ID
- Current state
- State history (transitions)
- State entry timestamp
- State duration
- Deterioration metrics
- Regime at state entry

**Historical tracking**:
- All state transitions logged
- Transition timestamps
- Transition triggers
- Deterioration events
- Regime changes

---

## LIFECYCLE ANTI-PATTERNS

### Anti-Patterns

❌ **Static state tracking**: Only tracking current state, not transitions
❌ **No deterioration monitoring**: Only watching for continuation
❌ **No regime awareness**: Same lifecycle rules in all regimes
❌ **No historical tracking**: Losing state history
❌ **No notification system**: Manual monitoring only

### Correct Patterns

✅ **State machine**: Clear state transitions
✅ **Deterioration first-class**: Deterioration monitoring is critical
✅ **Regime-aware**: Lifecycle adjusts by regime
✅ **Historical tracking**: Full state history maintained
✅ **Notification system**: Automated alerts for state changes

---

## LIFECYCLE IMPLEMENTATION PRINCIPLES

1. **State machine architecture**: Clear states and transitions
2. **Deterioration detection**: Continuous monitoring
3. **Regime awareness**: Adjustments by market conditions
4. **Historical tracking**: Full lifecycle history
5. **Notification system**: Automated alerts
6. **User control**: Manual state transitions allowed
7. **Interpretability**: Clear rationale for transitions
8. **Observability**: All state changes logged

---

## LIFECYCLE SUMMARY

**States**: Not Detected → Emerging → Active → Deteriorating → Invalidated/Completed

**Key principles**:
- Setups evolve through states
- Deterioration is first-class
- Regime affects lifecycle
- Historical tracking is mandatory
- Notifications are critical

**Critical transitions**:
- Emerging → Active (entry opportunity)
- Active → Deteriorating (exit warning)
- Deteriorating → Invalidated (exit required)

**This document defines the setup lifecycle. All setup tracking must follow this state machine.**
