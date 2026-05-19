# PRIORITY ENGINE
## Setup Ranking and Filtering Logic

**Purpose**: Define how setups are ranked and filtered to maintain scarcity and quality. The priority engine ensures only the best setups are shown.

---

## CORE PRIORITY PHILOSOPHY

**Scarcity is signal**. Quality > quantity. If everything looks good, nothing is. The priority engine enforces scarcity by ranking and filtering setups.

**The priority engine must**:
- Rank setups by quality
- Filter by regime-specific thresholds
- Enforce scarcity rules
- Maintain quality standards
- Support regime-aware filtering

---

## PRIORITY CALCULATION

### Quality Score Components

#### 1. Sponsorship Quality (30%)

**Components**:
- Sponsorship score (40%)
- Sponsorship trend (30%)
- Sponsorship stability (30%)

**Calculation**:
```
Sponsorship Quality = (Score × 0.4) + (Trend × 0.3) + (Stability × 0.3)
```

**Scoring**:
- Score: 0-10 (from sponsorship calculation)
- Trend: -1 to +1 (negative to positive trend)
- Stability: 0-1 (0 = volatile, 1 = stable)

---

#### 2. Volume Quality (25%)

**Components**:
- Volume expansion (40%)
- Volume sustainability (30%)
- Volume pattern (30%)

**Calculation**:
```
Volume Quality = (Expansion × 0.4) + (Sustainability × 0.3) + (Pattern × 0.3)
```

**Scoring**:
- Expansion: 0-10 (volume vs average)
- Sustainability: 0-10 (days above threshold)
- Pattern: 0-10 (pattern quality)

---

#### 3. Momentum Quality (25%)

**Components**:
- Momentum strength (40%)
- Momentum consistency (30%)
- Momentum trend (30%)

**Calculation**:
```
Momentum Quality = (Strength × 0.4) + (Consistency × 0.3) + (Trend × 0.3)
```

**Scoring**:
- Strength: 0-10 (RSI, rate of change)
- Consistency: 0-10 (days with positive momentum)
- Trend: 0-10 (momentum trend)

---

#### 4. Technical Quality (20%)

**Components**:
- Technical position (40%)
- Trend strength (30%)
- Pattern quality (30%)

**Calculation**:
```
Technical Quality = (Position × 0.4) + (Trend Strength × 0.3) + (Pattern × 0.3)
```

**Scoring**:
- Position: 0-10 (price vs MA, support/resistance)
- Trend Strength: 0-10 (MA slope, trend duration)
- Pattern: 0-10 (pattern recognition score)

---

### Overall Quality Score

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

## PRIORITY ADJUSTMENTS

### Regime Adjustments

#### Bull Regime Adjustments

**Sponsorship weight**: +10% (more important in bull)
**Volume weight**: -5% (less critical in bull)
**Momentum weight**: -5% (less critical in bull)
**Technical weight**: 0% (no change)

**Adjusted weights**:
- Sponsorship: 40%
- Volume: 20%
- Momentum: 20%
- Technical: 20%

---

#### Bear Regime Adjustments

**Sponsorship weight**: +15% (critical in bear)
**Volume weight**: +10% (critical in bear)
**Momentum weight**: +5% (important in bear)
**Technical weight**: -30% (less important in bear)

**Adjusted weights**:
- Sponsorship: 45%
- Volume: 35%
- Momentum: 30%
- Technical: -10% (clamped to 0%)

---

#### Volatile Regime Adjustments

**Sponsorship weight**: +20% (most critical in volatile)
**Volume weight**: +15% (critical in volatile)
**Momentum weight**: +15% (critical in volatile)
**Technical weight**: -50% (least important in volatile)

**Adjusted weights**:
- Sponsorship: 50%
- Volume: 40%
- Momentum: 40%
- Technical: -30% (clamped to 0%)

---

### Deterioration Penalty

**Slow deterioration**: -1 point
**Fast deterioration**: -3 points
**Critical deterioration**: -5 points

**Multi-metric deterioration**: Additional -2 points

**Deterioration recovery**: +1 point (if recovered)

---

## FILTERING RULES

### Scarcity Rules

#### Bull Regime

**Filter**: Top 20% of setups by quality score
**Minimum threshold**: Quality score ≥ 6
**Maximum setups**: 20 (if more than 20 pass, take top 20)

---

#### Bear Regime

**Filter**: Top 5% of setups by quality score
**Minimum threshold**: Quality score ≥ 8
**Maximum setups**: 5 (if more than 5 pass, take top 5)

---

#### Volatile Regime

**Filter**: Top 2% of setups by quality score
**Minimum threshold**: Quality score ≥ 9
**Maximum setups**: 2 (if more than 2 pass, take top 2)

---

### Quality Thresholds

#### Absolute Thresholds

**Minimum quality score**:
- Bull Regime: 6
- Bear Regime: 8
- Volatile Regime: 9

**Below threshold**: Automatically rejected

---

#### Component Thresholds

**Sponsorship minimum**:
- Bull Regime: 6/10
- Bear Regime: 8/10
- Volatile Regime: 9/10

**Volume minimum**:
- Bull Regime: 1.5x average
- Bear Regime: 2.0x average
- Volatile Regime: 2.5x average

**Momentum minimum**:
- Bull Regime: RSI > 50
- Bear Regime: RSI > 60
- Volatile Regime: RSI > 65

**Below component threshold**: Automatically rejected

---

## RANKING ALGORITHM

### Ranking Process

1. **Calculate base quality score**: Using standard weights
2. **Apply regime adjustments**: Adjust weights by regime
3. **Apply deterioration penalty**: Subtract for deterioration
4. **Apply component thresholds**: Filter below thresholds
5. **Apply quality threshold**: Filter below minimum
6. **Apply scarcity filter**: Take top percentage
7. **Apply maximum limit**: Cap at maximum number
8. **Sort by final score**: Highest score first

---

### Ranking Example

**Setup A**:
- Sponsorship: 8/10
- Volume: 7/10
- Momentum: 7/10
- Technical: 6/10
- Regime: Bull
- Deterioration: None

**Calculation**:
```
Base Score = (8 × 0.3) + (7 × 0.25) + (7 × 0.25) + (6 × 0.2) = 7.05
Bull Adjustment = No penalty
Deterioration Penalty = 0
Final Score = 7.05
```

**Setup B**:
- Sponsorship: 9/10
- Volume: 8/10
- Momentum: 8/10
- Technical: 7/10
- Regime: Bear
- Deterioration: Slow (-1)

**Calculation**:
```
Base Score = (9 × 0.3) + (8 × 0.25) + (8 × 0.25) + (7 × 0.2) = 8.0
Bear Adjustment = Higher sponsorship/volume weight
Deterioration Penalty = -1
Final Score = 7.0 (adjusted for bear regime)
```

---

## PRIORITY DATA MODEL

### State Persistence

**Required fields**:
- Setup ID
- Base quality score
- Regime-adjusted score
- Deterioration penalty
- Final score
- Component scores (sponsorship, volume, momentum, technical)
- Ranking position
- Filter status (passed/rejected)
- Rejection reason (if rejected)

**Historical tracking**:
- All score changes logged
- Ranking history
- Filter history
- Rejection reasons

---

## PRIORITY ANTI-PATTERNS

### Anti-Patterns

❌ **No scarcity rules**: Show all setups
❌ **No regime adjustments**: Same rules in all markets
❌ **No deterioration penalty**: Ignore deterioration
❌ **No component thresholds**: Accept low component scores
❌ **No maximum limits**: Show too many setups

### Correct Patterns

✅ **Scarcity rules**: Top percentage only
✅ **Regime adjustments**: Different rules by regime
✅ **Deterioration penalty**: Penalize deterioration
✅ **Component thresholds**: Minimum component scores
✅ **Maximum limits**: Cap number of setups

---

## PRIORITY IMPLEMENTATION PRINCIPLES

1. **Scarcity enforced**: Top percentage only
2. **Regime-aware**: Adjustments by regime
3. **Deterioration penalized**: Negative transitions hurt score
4. **Component thresholds**: Minimum quality per component
5. **Quality thresholds**: Minimum overall quality
6. **Maximum limits**: Cap number of setups
7. **Transparent**: Scoring is explainable
8. **Observable**: All scoring logged

---

## PRIORITY SUMMARY

**Quality score**: Multi-component weighted score
**Regime adjustments**: Different weights by regime
**Deterioration penalty**: Negative transitions penalized
**Scarcity rules**: Top percentage by regime
**Quality thresholds**: Minimum scores by regime
**Maximum limits**: Cap number of setups

**Key principles**:
- Scarcity enforced
- Regime-aware
- Deterioration penalized
- Transparent scoring
- Observable

**This document defines the priority engine. All setup ranking must follow these rules.**
