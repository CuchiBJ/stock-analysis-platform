# ANTI-PATTERNS
## Common Traps and Patterns to Avoid

**Purpose**: Document known anti-patterns that LLMs and developers tend to suggest. These patterns violate product philosophy and must be explicitly avoided.

---

## CORE ANTI-PATTERN PHILOSOPHY

**Anti-patterns are**:
- Known traps that violate philosophy
- Patterns that drift toward retail/SaaS
- Suggestions that seem reasonable but are wrong
- Patterns that kill institutional edge

**Anti-patterns must be**:
- Explicitly documented
- Checked before any suggestion
- Rejected immediately
- Learned from and avoided

---

## UI ANTI-PATTERNS

### GIANT TABLES

**The anti-pattern**:
- Dense spreadsheet-like tables
- 50+ columns of data
- No visual hierarchy
- Requires careful reading

**Why it's wrong**:
- Violates context compression
- Increases cognitive load
- Doesn't support operational scanning
- Not transition-focused
- Retail screener pattern

**Instead**:
- Card-based layout
- Key metrics only
- Visual hierarchy
- Narrative summaries

**Example**:
❌ Table with ticker, price, volume, RSI, MACD, P/E, PEG, 52-week high, 52-week low, beta, market cap, float, institutional ownership, short interest, etc.
✅ Setup cards with key metrics and narrative

---

### ANALYTICS OVERLOAD

**The anti-pattern**:
- Multiple panels with charts
- Endless metrics and KPIs
- Drill-down interfaces
- "Explore the data" workflows

**Why it's wrong**:
- Violates context compression
- Increases cognitive load
- Not operationally focused
- Analytics dashboard pattern
- Analysis paralysis

**Instead**:
- Single, focused view
- Pre-computed signals
- Narrative-driven
- Action-oriented

**Example**:
❌ Dashboard with 10 charts, 20 metrics, drill-down panels
✅ Setup cards with narrative and key signals

---

### TOO MANY PANELS

**The anti-pattern**:
- Multiple panels competing for attention
- No clear hierarchy
- Information scattered
- Confusing layout

**Why it's wrong**:
- Violates cognitive load reduction
- No clear workflow
- Not operationally focused
- SaaS dashboard pattern
- Confusing navigation

**Instead**:
- Single column layout
- Clear hierarchy
- Linear workflow
- Focused information

**Example**:
❌ 3-column layout with 6 panels
✅ Single column with setup cards

---

### EQUAL VISUAL WEIGHT

**The anti-pattern**:
- All information same size
- No visual hierarchy
- Everything looks equally important
- No guidance for attention

**Why it's wrong**:
- Violates visual hierarchy principle
- Increases cognitive load
- Doesn't guide attention
- Not professional
- No urgency indication

**Instead**:
- Size indicates importance
- Color indicates urgency
- Position indicates hierarchy
- Clear visual guidance

**Example**:
❌ All metrics same size and color
✅ Critical signals large and prominent

---

### EXCESSIVE DECORATION

**The anti-pattern**:
- Gradients, shadows, rounded corners
- Decorative icons and illustrations
- Marketing-style design
- Startup aesthetics

**Why it's wrong**:
- Violates institutional feel
- Distracts from signal
- SaaS startup pattern
- Not professional
- Reduces credibility

**Instead**:
- Minimal decoration
- Flat design
- Professional typography
- Information-focused

**Example**:
❌ Gradient buttons, shadows everywhere, playful icons
✅ Flat buttons, no shadows, functional icons

---

## FEATURE ANTI-PATTERNS

### FAKE AI INSIGHTS

**The anti-pattern**:
- "AI predicts X will go up"
- "AI says buy now"
- "Confidence score: 87%"
- Black-box recommendations

**Why it's wrong**:
- Violates interpretability principle
- Not explainable
- Prediction theater
- Retail gimmick
- Not institutional

**Instead**:
- Rule-based signals
- Explainable rationale
- No predictions
- Context for decisions

**Example**:
❌ "AI predicts AAPL will rise 5%"
✅ "Setup flagged: sponsorship up, volume expanding, momentum improving"

---

### PREDICTION THEATER

**The anti-pattern**:
- Price targets
- "Will go up X%"
- Probability scores
- Forecasting features

**Why it's wrong**:
- Violates interpretability
- Not actionable
- False precision
- Retail gimmick
- Not institutional

**Instead**:
- Transition detection
- Deterioration detection
- Contextual signals
- No predictions

**Example**:
❌ "Price target: $250 (probability: 73%)"
✅ "Setup deteriorating: sponsorship down, volume drying up"

---

### NOISY DASHBOARDS

**The anti-pattern**:
- Everything visible at once
- No filtering
- No hierarchy
- Information overload

**Why it's wrong**:
- Violates context compression
- Increases cognitive load
- Not operationally focused
- Retail screener pattern
- Analysis paralysis

**Instead**:
- Filtered, quality setups
- Clear hierarchy
- Progressive disclosure
- Scarcity

**Example**:
❌ 100 stocks with all metrics visible
✅ 3 quality setups with key signals

---

### STARTUP SAAS AESTHETICS

**The anti-pattern**:
- Bright, saturated colors
- Gradients and shadows
- Playful illustrations
- Marketing copy
- Feature highlights

**Why it's wrong**:
- Violates institutional feel
- Not professional
- SaaS startup pattern
- Reduces credibility
- Not operationally focused

**Instead**:
- Low saturation
- Minimal decoration
- Professional typography
- Functional design
- Institutional feel

**Example**:
❌ Bright purple gradients, playful icons, "Get Started" tours
✅ Dark background, minimal decoration, functional design

---

### FEATURE ACCUMULATION

**The anti-pattern**:
- Adding features for completeness
- "Me too" features
- Feature lists as selling points
- Constant feature additions

**Why it's wrong**:
- Violates operational clarity principle
- Increases complexity
- Feature bloat
- Not focused
- Maintenance burden

**Instead**:
- Surgical features
- Each feature earns its place
- Quality over quantity
- Decision filter

**Example**:
❌ "We have 50+ features!"
✅ "We have 3 critical features that work perfectly"

---

## DATA ANTI-PATTERNS

### RETAIL SENTIMENT METRICS

**The anti-pattern**:
- Social media sentiment
- "Most popular" rankings
- Retail interest indicators
- Social trading features

**Why it's wrong**:
- Violates institutional edge principle
- Retail follows, doesn't lead
- Not institutional
- Retail noise
- Violates WHAT_THIS_PRODUCT_IS_NOT.md

**Instead**:
- Institutional sponsorship
- Smart money flow
- Institutional activity
- Professional data

**Example**:
❌ "Social sentiment: Bullish"
✅ "Institutional sponsorship: Increasing"

---

### STATIC METRICS WITHOUT CONTEXT

**The anti-pattern**:
- Showing RSI=50 without change
- Showing P/E without trend
- Static filters without time
- Snapshot-only displays

**Why it's wrong**:
- Violates transitions > static states
- No temporal context
- Not transition-focused
- Retail screener pattern
- No narrative

**Instead**:
- Show rate of change
- Show transitions
- Show deterioration
- Provide context

**Example**:
❌ "RSI: 50"
✅ "RSI: 50 (↓ from 70 in 5 days)"

---

### QUANTITY OVER QUALITY

**The anti-pattern**:
- Showing many results
- Lowering thresholds to show more
- "Expand your search" suggestions
- Celebrating result quantity

**Why it's wrong**:
- Violates scarcity principle
- Quality > quantity
- Retail screener pattern
- Not institutional
- Reduces confidence

**Instead**:
- Maintain scarcity
- High thresholds
- Quality setups only
- "No setups" is valid

**Example**:
❌ "50 stocks matching your criteria"
✅ "3 high-quality setups today"

---

## WORKFLOW ANTI-PATTERNS

### ANALYSIS PARALYSIS

**The anti-pattern**:
- Endless drill-down interfaces
- Multiple parallel workflows
- "Explore the data" design
- No clear path to action

**Why it's wrong**:
- Violates workflow > analytics
- Increases cognitive load
- Not operationally focused
- Analytics dashboard pattern
- Kills speed

**Instead**:
- Clear linear workflow
- Single path to action
- Pre-computed signals
- Action-oriented

**Example**:
❌ "Explore all metrics, drill down, analyze, then decide"
✅ "Scan setups → Analyze → Decide"

---

### COMPLEX CONFIGURATION

**The anti-pattern**:
- Many options and settings
- Customizable everything
- Configuration complexity
- User-driven filtering

**Why it's wrong**:
- Violates operational clarity
- Increases cognitive load
- Not professional
- Retail pattern
- Maintenance burden

**Instead**:
- Sensible defaults
- Minimal configuration
- Opinionated system
- Professional defaults

**Example**:
❌ 20 filter options, customizable everything
✅ 3 key filters with professional defaults

---

## ARCHITECTURAL ANTI-PATTERNS

### PREMATURE MICROSERVICES

**The anti-pattern**:
- Microservices for small features
- Distributed system complexity
- Service mesh
- Event sourcing for everything

**Why it's wrong**:
- Unnecessary complexity
- Operational burden
- Not needed for scale
- Architecture for architecture's sake
- Following trends

**Instead**:
- Modular monolith
- Clear module boundaries
- Extract services when needed
- Simple architecture

**Example**:
❌ 10 microservices for a small product
✅ Modular monolith with clear boundaries

---

### BLACK-BOX ML FOR CORE LOGIC

**The anti-pattern**:
- ML for setup detection
- Neural networks for scoring
- "AI-powered" as selling point
- Opaque decision logic

**Why it's wrong**:
- Violates interpretability
- Not explainable
- Not debuggable
- Retail gimmick
- Not institutional

**Instead**:
- Rule-based logic
- Explicit rules
- Explainable signals
- Transparent scoring

**Example**:
❌ "Neural network detects setups"
✅ "Setup flagged because: sponsorship > 7 AND volume > 2x"

---

## ANTI-PATTERN CHECKLIST

Before any suggestion, check if it matches:

**UI Anti-Patterns**:
- [ ] Giant tables
- [ ] Analytics overload
- [ ] Too many panels
- [ ] Equal visual weight
- [ ] Excessive decoration

**Feature Anti-Patterns**:
- [ ] Fake AI insights
- [ ] Prediction theater
- [ ] Noisy dashboards
- [ ] Startup SaaS aesthetics
- [ ] Feature accumulation

**Data Anti-Patterns**:
- [ ] Retail sentiment metrics
- [ ] Static metrics without context
- [ ] Quantity over quality

**Workflow Anti-Patterns**:
- [ ] Analysis paralysis
- [ ] Complex configuration

**Architectural Anti-Patterns**:
- [ ] Premature microservices
- [ ] Black-box ML for core logic

**If any checkbox is checked, REJECT the suggestion.**

---

## ANTI-PATTERN DETECTION

**When LLMs suggest anti-patterns**:
1. Cite the specific anti-pattern
2. Explain why it's wrong
3. Cite the violated principle
4. Suggest aligned alternative
5. Update LLM context if needed

**When developers suggest anti-patterns**:
1. Cite the specific anti-pattern
2. Explain why it's wrong
3. Cite the violated principle
4. Suggest aligned alternative
5. Document the rejection

---

## ANTI-PATTERN MAINTENANCE

**Review anti-patterns**:
- Quarterly
- When new patterns emerge
- When LLMs suggest new anti-patterns
- When philosophy evolves

**Update anti-patterns**:
- Add new anti-patterns as discovered
- Document the rationale
- Cite violated principles
- Keep examples current

**Current version**: v1.0.0
**Last review**: [Date]
**Next review**: [Date]

---

## ANTI-PATTERN SUMMARY

**UI Anti-Patterns**:
- Giant tables
- Analytics overload
- Too many panels
- Equal visual weight
- Excessive decoration

**Feature Anti-Patterns**:
- Fake AI insights
- Prediction theater
- Noisy dashboards
- Startup SaaS aesthetics
- Feature accumulation

**Data Anti-Patterns**:
- Retail sentiment metrics
- Static metrics without context
- Quantity over quality

**Workflow Anti-Patterns**:
- Analysis paralysis
- Complex configuration

**Architectural Anti-Patterns**:
- Premature microservices
- Black-box ML for core logic

**This document is the anti-pattern guide. All suggestions must avoid these patterns.**
