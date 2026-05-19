# DECISION FILTER
## Feature Evaluation Criteria to Prevent Feature Creep

**Purpose**: Provide a decision filter for evaluating every feature suggestion. This prevents feature creep and maintains product focus.

---

## CORE DECISION PHILOSOPHY

**Every feature must**:
- Improve operational speed
- Improve context compression
- Improve setup quality
- Reduce cognitive load
- Help detect transitions
- Help detect deterioration
- Help discretionary workflow
- Add institutional edge

**If a feature doesn't meet these criteria, it should be rejected.**

---

## DECISION FILTER QUESTIONS

Before adding any feature, ask these 8 questions:

### 1. DOES IT IMPROVE OPERATIONAL SPEED?

**What this means**:
- Does it make the workflow faster?
- Does it reduce steps in the workflow?
- Does it reduce time to decision?
- Does it enable faster scanning?

**Why it matters**:
- Speed is critical in trading
- Operational speed is the metric
- Professional tools optimize for speed
- Slow tools kill edge

**Examples**:
✅ Pre-computed setup narratives (faster decision)
✅ Keyboard shortcuts (faster navigation)
❌ More drill-down panels (slower workflow)
❌ Complex configuration (slower setup)

---

### 2. DOES IT IMPROVE CONTEXT COMPRESSION?

**What this means**:
- Does it synthesize information?
- Does it reduce information overload?
- Does it construct narrative?
- Does it reduce cognitive load?

**Why it matters**:
- Information overload kills performance
- Professional tools synthesize, don't expose
- Context enables faster decisions
- Compression is the product's value

**Examples**:
✅ Automatic narrative generation (compresses context)
✅ Signal grouping (reduces cognitive load)
❌ Raw data tables (no compression)
❌ More metrics (more overload)

---

### 3. DOES IT IMPROVE SETUP QUALITY?

**What this means**:
- Does it detect better setups?
- Does it filter out noise?
- Does it improve signal-to-noise ratio?
- Does it maintain scarcity?

**Why it matters**:
- Quality > quantity
- Scarcity is signal
- Professional tools are selective
- Bad setups waste time

**Examples**:
✅ Better deterioration detection (better quality)
✅ Improved regime awareness (better filtering)
❌ More results (lower quality)
❌ Lowering thresholds (worse quality)

---

### 4. DOES IT REDUCE COGNITIVE LOAD?

**What this means**:
- Does it simplify the interface?
- Does it reduce mental effort?
- Does it support mental models?
- Does it reduce confusion?

**Why it matters**:
- Cognitive load reduces decision quality
- Traders make mistakes when overloaded
- Professional tools reduce complexity
- Mental energy should go to trading

**Examples**:
✅ Progressive disclosure (reduces load)
✅ Clear hierarchy (reduces confusion)
❌ Everything visible at once (high load)
❌ Complex interfaces (high confusion)

---

### 5. DOES IT HELP DETECT TRANSITIONS?

**What this means**:
- Does it highlight changes?
- Does it show rate of change?
- Does it detect momentum shifts?
- Does it support transition detection?

**Why it matters**:
- Transitions are the signal
- Static states are noise
- Momentum is about change
- Transitions > Static States

**Examples**:
✅ Change indicators for metrics (detects transitions)
✅ Rate of change calculations (detects transitions)
❌ Only showing current values (no transitions)
❌ Static snapshots (no transitions)

---

### 6. DOES IT HELP DETECT DETERIORATION?

**What this means**:
- Does it highlight decay?
- Does it show negative changes?
- Does it detect early warning signs?
- Does it make deterioration visible?

**Why it matters**:
- Loss prevention is critical
- Early exit signals preserve capital
- Deterioration precedes reversal
- Deterioration is first-class

**Examples**:
✅ Deterioration alerts (detects decay)
✅ Negative transition highlighting (detects decay)
❌ Only showing positive signals (misses deterioration)
❌ Hiding deterioration (ignores decay)

---

### 7. DOES IT HELP DISCRETIONARY WORKFLOW?

**What this means**:
- Does it support human judgment?
- Does it provide context for decisions?
- Does it enable user control?
- Does it not replace the trader?

**Why it matters**:
- Trading is discretionary
- Human judgment is the edge
- Professional tools empower, don't replace
- Automation must be transparent

**Examples**:
✅ Explainable signals (supports judgment)
✅ User-adjustable filters (enables control)
❌ "Trust the system" (replaces judgment)
❌ Black-box automation (no control)

---

### 8. DOES IT ADD INSTITUTIONAL EDGE?

**What this means**:
- Does it track institutional activity?
- Does it follow smart money?
- Does it provide institutional data?
- Does it avoid retail noise?

**Why it matters**:
- Institutions move markets
- Retail follows, doesn't lead
- Sponsorship indicates conviction
- Smart money flow is the signal

**Examples**:
✅ Institutional sponsorship tracking (institutional edge)
✅ Smart money flow analysis (institutional edge)
❌ Retail sentiment (retail noise)
❌ Social media indicators (retail noise)

---

## DECISION FILTER PROCESS

### For Every Feature Suggestion

1. **Ask all 8 questions**
2. **Score each question (Yes/No)**
3. **Count Yes responses**
4. **Apply scoring rules**
5. **Document the decision**

### Scoring Rules

- **8/8 Yes**: Implement immediately
- **6-7/8 Yes**: Strong consideration
- **4-5/8 Yes**: Weak consideration, needs refinement
- **0-3/8 Yes**: Reject

### Required Yes Responses

At minimum, a feature must be **Yes** on:
- Question 1 (Operational Speed) OR Question 2 (Context Compression)
- Question 5 (Detect Transitions) OR Question 6 (Detect Deterioration)
- Question 8 (Institutional Edge)

If any of these are **No**, the feature is **automatically rejected**.

---

## DECISION FILTER EXAMPLES

### Example 1: Social Sentiment Feature

**Questions**:
1. Improve operational speed? No (adds noise)
2. Improve context compression? No (adds information)
3. Improve setup quality? No (retail noise)
4. Reduce cognitive load? No (adds complexity)
5. Help detect transitions? No (retail signal)
6. Help detect deterioration? No (retail signal)
7. Help discretionary workflow? No (adds noise)
8. Add institutional edge? No (retail sentiment)

**Score**: 0/8 Yes
**Decision**: REJECT
**Rationale**: Violates WHAT_THIS_PRODUCT_IS_NOT.md (social trading platform)

---

### Example 2: Deterioration Alert Enhancement

**Questions**:
1. Improve operational speed? Yes (faster detection)
2. Improve context compression? Yes (clear alert)
3. Improve setup quality? Yes (better exit signals)
4. Reduce cognitive load? Yes (prominent alert)
5. Help detect transitions? Yes (negative transition)
6. Help detect deterioration? Yes (explicit purpose)
7. Help discretionary workflow? Yes (supports judgment)
8. Add institutional edge? Yes (institutions monitor decay)

**Score**: 8/8 Yes
**Decision**: IMPLEMENT
**Rationale**: Aligns with all principles, especially Principle 4 (Deterioration is First-Class)

---

### Example 3: More Metrics Dashboard

**Questions**:
1. Improve operational speed? No (slower scanning)
2. Improve context compression? No (more information)
3. Improve setup quality? No (quantity over quality)
4. Reduce cognitive load? No (more complexity)
5. Help detect transitions? No (static metrics)
6. Help detect deterioration? No (static metrics)
7. Help discretionary workflow? No (analysis paralysis)
8. Add institutional edge? No (generic metrics)

**Score**: 0/8 Yes
**Decision**: REJECT
**Rationale**: Violates Principle 2 (Scarcity is Signal) and WHAT_THIS_PRODUCT_IS_NOT.md (analytics dashboard)

---

### Example 4: Improved Sponsorship Tracking

**Questions**:
1. Improve operational speed? Yes (faster sponsorship analysis)
2. Improve context compression? Yes (clearer sponsorship narrative)
3. Improve setup quality? Yes (better sponsorship signals)
4. Reduce cognitive load? Yes (clearer presentation)
5. Help detect transitions? Yes (sponsorship transitions)
6. Help detect deterioration? Yes (sponsorship decay)
7. Help discretionary workflow? Yes (supports judgment)
8. Add institutional edge? Yes (institutional sponsorship)

**Score**: 8/8 Yes
**Decision**: IMPLEMENT
**Rationale**: Aligns with Principle 9 (Institutional Sponsorship is Primary Signal)

---

## DECISION FILTER ANTI-PATTERNS

**Never**:
- ❌ Bypass the decision filter
- ❌ Answer questions dishonestly
- ❌ Assume "maybe later" is Yes
- ❌ Use "users want it" as justification
- ❌ Use "competitors have it" as justification
- ❌ Use "it's cool" as justification

**Always**:
- ✅ Answer questions honestly
- ✅ Apply scoring rules strictly
- ✅ Document the rationale
- ✅ Cite relevant principles
- ✅ Check against WHAT_THIS_PRODUCT_IS_NOT.md
- ✅ Check against ANTI_PATTERNS.md

---

## DECISION FILTER IN PRACTICE

### For Developers

1. Before coding, apply decision filter
2. Document the decision
3. Get approval if score is 4-5/8
4. Reject if score is 0-3/8

### For Product Managers

1. Before prioritizing, apply decision filter
2. Use decision filter for backlog grooming
3. Reject features that don't pass
4. Prioritize features that score 8/8

### For LLMs

1. Before suggesting, apply decision filter
2. Show the decision filter results
3. Explain the rationale
4. Reject if score is 0-3/8

---

## DECISION FILTER MAINTENANCE

**Review the decision filter**:
- Quarterly
- When philosophy evolves
- When anti-patterns are discovered
- When market conditions change

**Update the decision filter**:
- If new criteria emerge
- If existing criteria prove inadequate
- If scoring rules need adjustment
- Document the rationale for changes

**Current version**: v1.0.0
**Last review**: [Date]
**Next review**: [Date]

---

## DECISION FILTER EMERGENCY

**If decision filter is being bypassed**:
1. Stop all feature work
2. Re-read NON_NEGOTIABLE_PRINCIPLES.md
3. Re-read WHAT_THIS_PRODUCT_IS_NOT.md
4. Re-apply decision filter to all pending features
5. Reject features that don't pass
6. Document the bypass incident

---

## DECISION FILTER SUMMARY

**The decision filter has 8 questions**:
1. Improve operational speed?
2. Improve context compression?
3. Improve setup quality?
4. Reduce cognitive load?
5. Help detect transitions?
6. Help detect deterioration?
7. Help discretionary workflow?
8. Add institutional edge?

**Scoring**:
- 8/8 Yes: Implement
- 6-7/8 Yes: Strong consideration
- 4-5/8 Yes: Weak consideration
- 0-3/8 Yes: Reject

**Required Yes**:
- Operational speed OR context compression
- Detect transitions OR detect deterioration
- Institutional edge

**This document is the decision filter. All features must pass.**
