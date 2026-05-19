# NARRATIVE ENGINE
## Story Construction and Context Compression

**Purpose**: Define how the system constructs narratives from data to compress context and reduce cognitive load. The narrative engine synthesizes information into actionable stories.

---

## CORE NARRATIVE PHILOSOPHY

**Narrative > raw data**. Users should not have to interpret raw metrics. The system must construct stories that explain what's happening, why it matters, and what to do.

**The narrative engine must**:
- Synthesize multiple metrics into a story
- Explain transitions, not just states
- Highlight deterioration immediately
- Provide action-oriented context
- Reduce cognitive load

---

## NARRATIVE STRUCTURE

### Narrative Components

**1. Current State**
- What is the setup doing?
- Current phase of lifecycle
- Key signals

**2. Recent Transitions**
- What changed recently?
- Positive changes
- Negative changes
- Transition velocity

**3. Context**
- Why does this matter?
- Regime context
- Institutional context
- Technical context

**4. Assessment**
- Is the setup strengthening or weakening?
- Quality assessment
- Risk assessment

**5. Recommendation**
- What should the user do?
- Action-oriented
- Specific and clear

---

## NARRATIVE TEMPLATES

### Active Setup Narrative

**Template**:
"{Stock} is in {state} phase. {Positive signals}. {Negative signals if any}. {Context}. {Assessment}. {Recommendation}."

**Example**:
"AAPL is in Active phase. Sponsorship increased from 7 to 8, volume expanded 2.1x average, momentum improving. In bull regime, continuation favored. Setup strengthening. Hold with stops at {stop level}."

### Deteriorating Setup Narrative

**Template**:
"{Stock} is {state}. {Deterioration signals}. {Velocity}. {Context}. {Assessment}. {Recommendation}."

**Example**:
"TSLA is deteriorating. Sponsorship declined from 8 to 6, volume contracted 0.6x average, momentum weakening. Fast deterioration velocity. In bear regime, zero tolerance. Setup weakening significantly. Exit immediately or tighten stops."

### Emerging Setup Narrative

**Template**:
"{Stock} is emerging. {Emergence signals}. {Confirmation status}. {Context}. {Recommendation}."

**Example**:
"NVDA is emerging. Sponsorship increasing (6→7), volume starting to expand, momentum initiating. Awaiting full confirmation. In bull regime, favorable for emergence. Monitor closely for confirmation or deterioration."

---

## NARRATIVE GENERATION RULES

### Rule 1: Always Include Transitions

**Requirement**: Every narrative must mention recent changes

**Why**: Transitions are the signal

**Implementation**:
- Always show "from X to Y"
- Always show velocity
- Always show direction (improving/deteriorating)

**Example**:
✅ "Sponsorship increased from 7 to 8"
❌ "Sponsorship: 8"

### Rule 2: Highlight Deterioration Immediately

**Requirement**: Deterioration must be prominent in narrative

**Why**: Deterioration is first-class information

**Implementation**:
- Deterioration mentioned first if present
- Use strong language ("deteriorating", "declining")
- Include velocity
- Action recommendation urgent

**Example**:
✅ "Setup deteriorating: sponsorship down, volume drying up"
❌ "Sponsorship: 6, Volume: 0.6x"

### Rule 3: Include Regime Context

**Requirement**: Every narrative must mention current regime

**Why**: Regime affects everything

**Implementation**:
- State current regime
- Explain regime impact
- Adjust recommendation based on regime

**Example**:
✅ "In bear regime, zero tolerance for deterioration"
❌ No regime mentioned

### Rule 4: Be Action-Oriented

**Requirement**: Every narrative must include a recommendation

**Why**: Narrative should drive action

**Implementation**:
- Clear recommendation (hold, exit, tighten stops)
- Specific if possible (stop level)
- Urgency level if needed

**Example**:
✅ "Exit immediately or tighten stops"
❌ "Setup is deteriorating"

### Rule 5: Be Concise

**Requirement**: Narratives should be 2-3 sentences maximum

**Why**: Cognitive load reduction

**Implementation**:
- Prioritize critical information
- Remove non-essential details
- Use clear, simple language
- One idea per sentence

**Example**:
✅ "Setup deteriorating: sponsorship down, volume drying up. Fast velocity. Exit immediately."
❌ "The setup is currently experiencing deterioration across multiple metrics including sponsorship which has declined from 8 to 6 and volume which has contracted to 0.6x of average..."

---

## NARRATIVE PRIORITIES

### Information Hierarchy in Narratives

**Priority 1**: Deterioration (if present)
- Must be first
- Must be prominent
- Must include velocity
- Must have urgent recommendation

**Priority 2**: Key positive transitions
- Sponsorship changes
- Volume changes
- Momentum changes

**Priority 3**: Regime context
- Current regime
- Regime impact

**Priority 4**: Assessment
- Strengthening or weakening
- Quality level

**Priority 5**: Recommendation
- Action to take
- Specific if possible

---

## NARRATIVE VARIATIONS

### By Lifecycle State

**Emerging**:
- Focus on confirmation status
- Highlight emergence signals
- Recommendation: monitor

**Active**:
- Focus on continuation signals
- Highlight any deterioration
- Recommendation: hold with stops

**Deteriorating**:
- Focus on deterioration
- Highlight velocity
- Recommendation: exit or tighten stops

**Invalidated**:
- Focus on failure reason
- Recommendation: learn from failure

**Completed**:
- Focus on success
- Recommendation: document success

### By Regime

**Bull regime**:
- More positive language
- Longer holding recommendations
- More tolerance for minor deterioration

**Bear regime**:
- More cautious language
- Shorter holding recommendations
- Zero tolerance for deterioration

**Volatile regime**:
- Very cautious language
- Very short holding recommendations
- Pre-emptive exits

---

## NARRATIVE QUALITY

### Quality Criteria

**Good narrative**:
- ✅ Includes transitions
- ✅ Highlights deterioration
- ✅ Includes regime context
- ✅ Action-oriented
- ✅ Concise (2-3 sentences)
- ✅ Clear and simple language
- ✅ Specific recommendations

**Bad narrative**:
- ❌ Static state only
- ❌ Hides deterioration
- ❌ No regime context
- ❌ No recommendation
- ❌ Too long
- ❌ Complex language
- ❌ Vague recommendations

---

## NARRATIVE DATA MODEL

### State Persistence

**Required fields**:
- Setup ID
- Narrative text
- Narrative timestamp
- Lifecycle state
- Regime at generation
- Key transitions included
- Deterioration flag
- Recommendation type

**Historical tracking**:
- All narratives logged
- Narrative evolution
- Narrative accuracy (post-trade)

---

## NARRATIVE ANTI-PATTERNS

### Anti-Patterns

❌ **Static state narrative**: Only current values, no transitions
❌ **Hidden deterioration**: Deterioration buried or omitted
❌ **No regime context**: Regime not mentioned
❌ **No recommendation**: No action suggested
❌ **Too long**: Paragraphs instead of sentences
❌ **Complex language**: Jargon and complexity
❌ **Vague recommendations**: "Monitor" without specifics

### Correct Patterns

✅ **Transition-focused**: Show changes
✅ **Deterioration prominent**: Negative changes first
✅ **Regime context**: Regime mentioned
✅ **Action-oriented**: Clear recommendation
✅ **Concise**: 2-3 sentences
✅ **Simple language**: Clear and direct
✅ **Specific recommendations**: Specific actions

---

## NARRATIVE IMPLEMENTATION PRINCIPLES

1. **Narrative > raw data**: Synthesize, don't expose
2. **Transitions mandatory**: Show changes
3. **Deterioration prominent**: Negative changes first
4. **Regime context**: Always include
5. **Action-oriented**: Drive decisions
6. **Concise**: 2-3 sentences
7. **Simple language**: Clear and direct
8. **Specific recommendations**: Actionable

---

## NARRATIVE SUMMARY

**Narrative structure**: State, Transitions, Context, Assessment, Recommendation

**Key principles**:
- Narrative > raw data
- Transitions mandatory
- Deterioration prominent
- Regime context
- Action-oriented
- Concise

**Critical rules**:
- Always include transitions
- Highlight deterioration immediately
- Include regime context
- Be action-oriented
- Be concise

**This document defines the narrative engine. All setup displays must include narratives.**
