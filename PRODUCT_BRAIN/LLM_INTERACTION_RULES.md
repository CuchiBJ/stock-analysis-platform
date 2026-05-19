# LLM INTERACTION RULES
## How to Work with AI Models to Maintain Product Coherence

**Purpose**: Define how LLMs should interact with this product to prevent conceptual drift and maintain operational philosophy. LLMs tend to drift toward generic patterns; these rules prevent that.

---

## CORE LLM INTERACTION PHILOSOPHY

**LLMs must**:
- Read PRODUCT_BRAIN before suggesting features
- Apply NON_NEGOTIABLE_PRINCIPLES as constraints
- Use DECISION_FILTER for feature evaluation
- Follow VISUAL_LANGUAGE for design
- Maintain institutional identity
- Avoid retail/SaaS drift

**LLMs must NOT**:
- Redesign the whole system at once
- Suggest features without context
- Ignore WHAT_THIS_PRODUCT_IS_NOT boundaries
- Violate NON_NEGOTIABLE_PRINCIPLES
- Suggest retail/SaaS patterns
- Add unnecessary complexity

---

## RULE 1: ALWAYS READ PRODUCT_BRAIN FIRST

**The rule**:
- Before any suggestion, read PRODUCT_BRAIN.md
- Before any design, read VISUAL_LANGUAGE.md
- Before any feature, read WHAT_THIS_PRODUCT_IS_NOT.md
- Before any change, read NON_NEGOTIABLE_PRINCIPLES.md

**Why it matters**:
- LLMs lack persistent context
- Product philosophy is complex
- Boundaries are critical
- Principles are immutable

**Implementation**:
- LLM must explicitly reference documents
- LLM must cite relevant principles
- LLM must check boundaries before suggesting
- LLM must apply decision filter

**Anti-patterns**:
❌ Suggesting features without reading documentation
❌ Ignoring boundaries
❌ Violating principles
❌ Not citing sources

**Examples**:
✅ "Per WHAT_THIS_PRODUCT_IS_NOT.md, this is a retail pattern. Instead, consider..."
✅ "This aligns with Principle 1: Transitions > Static States"
❌ "Let's add a social sentiment feature"
❌ "Users want more charts"

---

## RULE 2: WORK IN SURGICAL ITERATIONS

**The rule**:
- Never redesign whole system at once
- Make small, focused changes
- Each change must be justified
- Each change must be tested

**Why it matters**:
- Large changes introduce risk
- Small changes are easier to review
- Surgical iterations maintain coherence
- Incremental evolution is safer

**Implementation**:
- One feature/change per interaction
- Clear rationale for each change
- Test each change independently
- Document the impact

**Anti-patterns**:
❌ "Let's redesign the entire UI"
❌ "Let's rewrite the architecture"
❌ Multiple unrelated changes in one suggestion
❌ No rationale for changes

**Examples**:
✅ "Add deterioration alert to setup card"
✅ "Improve narrative generation for emerging setups"
❌ "Redesign the entire dashboard"
❌ "Rewrite the backend in Go"

---

## RULE 3: PRESERVE OPERATIONAL PHILOSOPHY

**The rule**:
- Maintain transition-first thinking
- Preserve scarcity
- Keep context compression
- Support discretionary trading
- Don't add retail features

**Why it matters**:
- Operational philosophy is the edge
- Drift kills the product identity
- Retail features dilute the product
- Philosophy is non-negotiable

**Implementation**:
- Check every suggestion against philosophy
- Reject retail/SaaS patterns
- Maintain institutional feel
- Preserve workflow continuity

**Anti-patterns**:
❌ Suggesting retail features
❌ Adding complexity for complexity
❌ Violating scarcity principle
❌ Breaking workflow continuity

**Examples**:
✅ "This maintains transition-first thinking by..."
✅ "This preserves scarcity by..."
❌ "Let's add a social feed"
❌ "Let's show more results"

---

## RULE 4: AVOID ADDING UNNECESSARY METRICS

**The rule**:
- Every metric must earn its place
- Metrics must support transitions
- Metrics must be interpretable
- Metrics must be actionable

**Why it matters**:
- Metric bloat creates noise
- Unnecessary metrics increase cognitive load
- Professional tools are selective
- Quality > quantity

**Implementation**:
- Apply decision filter to metrics
- Check if metric improves transitions
- Check if metric is interpretable
- Check if metric is actionable

**Anti-patterns**:
❌ Adding metrics "because users might want them"
❌ Adding metrics for completeness
❌ Adding metrics without justification
❌ Adding retail sentiment metrics

**Examples**:
✅ "This metric improves transition detection by..."
✅ "This metric is interpretable because..."
❌ "Let's add social sentiment score"
❌ "Let's add 50 more indicators"

---

## RULE 5: AVOID FEATURE CREEP

**The rule**:
- Every feature must pass decision filter
- Features must improve operational speed
- Features must reduce cognitive load
- Features must maintain scarcity

**Why it matters**:
- Feature bloat kills products
- Complexity increases maintenance
- Users get confused
- Edge is lost

**Implementation**:
- Apply DECISION_FILTER.md to every feature
- Reject features that don't pass
- Document rejections
- Maintain focus

**Anti-patterns**:
❌ Adding features for completeness
❌ Adding features to compete
❌ Adding features users request
❌ "Me too" features

**Examples**:
✅ "This feature passes decision filter because it improves..."
✅ "This feature is rejected because it violates..."
❌ "Let's add a backtesting module"
❌ "Competitors have X, we should too"

---

## RULE 6: PRIORITIZE WORKFLOW CONTINUITY

**The rule**:
- Changes must support existing workflow
- Changes must not break workflow
- Changes must improve workflow
- Workflow is sacred

**Why it matters**:
- Workflow continuity is critical
- Breaking changes disrupt operations
- Professional tools are stable
- Workflow is the product

**Implementation**:
- Understand current workflow
- Test workflow impact
- Maintain workflow consistency
- Improve workflow incrementally

**Anti-patterns**:
❌ Breaking existing workflow
❌ Changing workflow without justification
❌ Multiple parallel workflows
❌ No clear workflow

**Examples**:
✅ "This change improves workflow by..."
✅ "This maintains workflow continuity by..."
❌ "Let's add a new way to do X"
❌ "Let's change the workflow to..."

---

## RULE 7: MAINTAIN VISUAL COHERENCE

**The rule**:
- Follow VISUAL_LANGUAGE.md exactly
- Maintain institutional feel
- Use correct colors
- Use correct typography
- Use correct spacing

**Why it matters**:
- Visual coherence is identity
- Drift creates confusion
- Institutional feel is critical
- Consistency builds trust

**Implementation**:
- Read VISUAL_LANGUAGE.md before design
- Use design tokens
- Follow component guidelines
- Check against anti-aesthetics

**Anti-patterns**:
❌ Using SaaS startup aesthetics
❌ Using bright colors
❌ Using gradients
❌ Using decorative elements

**Examples**:
✅ "This design follows VISUAL_LANGUAGE.md by using..."
✅ "This maintains institutional feel by..."
❌ "Let's make it more colorful"
❌ "Let's add gradients"

---

## RULE 8: EXPLAIN RATIONALE FOR EVERY SUGGESTION

**The rule**:
- Every suggestion must have rationale
- Rationale must cite principles
- Rationale must cite documentation
- Rationale must be clear

**Why it matters**:
- Rationale enables review
- Rationale maintains coherence
- Rationale prevents drift
- Rationale builds trust

**Implementation**:
- Explicitly state rationale
- Cite relevant principles
- Cite relevant documentation
- Be clear and specific

**Anti-patterns**:
❌ Suggestions without rationale
❌ Vague justifications
❌ No citations
❌ "Users want it"

**Examples**:
✅ "This suggestion aligns with Principle 1: Transitions > Static States because..."
✅ "This follows VISUAL_LANGUAGE.md section on color philosophy..."
❌ "Users want this feature"
❌ "This would be cool"

---

## RULE 9: CHECK ANTI-PATTERNS BEFORE SUGGESTING

**The rule**:
- Read ANTI_PATTERNS.md
- Check suggestion against anti-patterns
- Reject if matches anti-pattern
- Document why rejected

**Why it matters**:
- Anti-patterns are known traps
- LLMs tend to suggest anti-patterns
- Checking prevents drift
- Anti-patterns are learned from experience

**Implementation**:
- Read ANTI_PATTERNS.md before suggesting
- Explicitly check against anti-patterns
- Reject if match found
- Document rejection

**Anti-patterns**:
❌ Suggesting anti-patterns
❌ Not checking anti-patterns
❌ Ignoring anti-patterns
❌ "This is different" (when it's not)

**Examples**:
✅ "This suggestion was rejected because it matches anti-pattern X in ANTI_PATTERNS.md"
✅ "This avoids anti-pattern by..."
❌ Suggesting giant tables
❌ Suggesting analytics overload

---

## RULE 10: NEVER ASSUME USER WANTS MORE

**The rule**:
- Don't assume users want more features
- Don't assume users want more data
- Don't assume users want more options
- Scarcity is a feature, not a bug

**Why it matters**:
- More is not always better
- Scarcity creates value
- Professional tools are focused
- Users are overwhelmed by choice

**Implementation**:
- Default to scarcity
- Require justification for more
- Apply decision filter
- Maintain quality

**Anti-patterns**:
❌ "Users want more options"
❌ "Users want more data"
❌ "Users want more features"
❌ "Let's expand the scope"

**Examples**:
✅ "This maintains scarcity by..."
✅ "This is justified because it improves..."
❌ "Let's add more filters"
❌ "Let's show more data"

---

## LLM WORKFLOW

### Before Suggesting
1. Read PRODUCT_BRAIN.md
2. Read WHAT_THIS_PRODUCT_IS_NOT.md
3. Read NON_NEGOTIABLE_PRINCIPLES.md
4. Read relevant operational documents
5. Read ANTI_PATTERNS.md

### While Suggesting
1. Cite relevant principles
2. Cite relevant documentation
3. Check against anti-patterns
4. Apply decision filter
5. Explain rationale clearly

### After Suggesting
1. Verify alignment with principles
2. Verify alignment with visual language
3. Verify alignment with UX philosophy
4. Verify no anti-patterns
5. Document the suggestion

---

## LLM CHECKLIST

Before any suggestion:
- [ ] Read PRODUCT_BRAIN.md
- [ ] Read WHAT_THIS_PRODUCT_IS_NOT.md
- [ ] Read NON_NEGOTIABLE_PRINCIPLES.md
- [ ] Read relevant operational documents
- [ ] Read ANTI_PATTERNS.md
- [ ] Checked against decision filter
- [ ] Explained rationale
- [ ] Cited principles
- [ ] Cited documentation
- [ ] Verified no anti-patterns

---

## LLM DRIFT DETECTION

**Signs of LLM drift**:
- Suggesting retail/SaaS patterns
- Ignoring boundaries
- Violating principles
- Not citing documentation
- Not explaining rationale
- Suggesting anti-patterns

**When drift is detected**:
1. Stop the interaction
2. Re-read PRODUCT_BRAIN.md
3. Re-read relevant documents
4. Reset context
5. Restart with proper context

---

## LLM INTERACTION EXAMPLES

### Good Interaction
```
User: "Add a feature to show social sentiment"

LLM: "Per WHAT_THIS_PRODUCT_IS_NOT.md, social sentiment is a retail pattern
that we explicitly avoid. This violates Principle 9: Institutional Sponsorship
is Primary Signal. Instead, consider improving institutional sponsorship tracking
by adding more granular time-window analysis. This aligns with Principle 1:
Transitions > Static States because it would show how sponsorship changes over
shorter time periods."
```

### Bad Interaction
```
User: "Add a feature to show social sentiment"

LLM: "Sure, I'll add a social sentiment feature. Users will love seeing
what people are saying about stocks on social media."
```

---

## LLM CONSTRAINTS

**LLMs are constrained by**:
- PRODUCT_BRAIN.md (all documents)
- WHAT_THIS_PRODUCT_IS_NOT.md (boundaries)
- NON_NEGOTIABLE_PRINCIPLES.md (principles)
- DECISION_FILTER.md (decision criteria)
- ANTI_PATTERNS.md (anti-patterns)
- VISUAL_LANGUAGE.md (visual rules)
- UX_PHILOSOPHY.md (UX principles)
- ARCHITECTURAL_PHILOSOPHY.md (architecture rules)

**LLMs must**:
- Always cite these documents
- Always check against these documents
- Always explain rationale
- Always maintain coherence

**LLMs must not**:
- Violate any document
- Ignore any principle
- Suggest any anti-pattern
- Break any boundary

---

## LLM TRAINING

**For developers using LLMs**:
1. Always provide PRODUCT_BRAIN context
2. Always remind LLM of constraints
3. Always ask for rationale
4. Always ask for citations
5. Always check against anti-patterns

**For LLM system prompts**:
1. Include PRODUCT_BRAIN summary
2. Include constraint list
3. Include decision filter
4. Include anti-patterns
5. Include citation requirements

---

## LLM VERSION CONTROL

**LLM interactions should be**:
- Documented
- Versioned
- Reviewed
- Approved

**LLM suggestions should be**:
- Tracked
- Evaluated
- Approved or rejected
- Documented

---

## LLM INTERACTION RULES SUMMARY

1. **Always read PRODUCT_BRAIN first**: Context is critical
2. **Work in surgical iterations**: Small, focused changes
3. **Preserve operational philosophy**: Don't drift
4. **Avoid adding unnecessary metrics**: Quality > quantity
5. **Avoid feature creep**: Every feature must earn its place
6. **Prioritize workflow continuity**: Workflow is sacred
7. **Maintain visual coherence**: Follow VISUAL_LANGUAGE.md
8. **Explain rationale for every suggestion**: Enable review
9. **Check anti-patterns before suggesting**: Avoid known traps
10. **Never assume user wants more**: Scarcity is a feature

---

## EMERGENCY LLM RESET

**If LLM drifts**:
1. Stop the interaction
2. Re-read all foundational documents
3. Reset context
4. Restart with proper context
5. Document the drift

**This document is the LLM interaction guide. All AI interactions must follow these rules.**
