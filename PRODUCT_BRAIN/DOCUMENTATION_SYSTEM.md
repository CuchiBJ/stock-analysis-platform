# DOCUMENTATION SYSTEM
## How to Maintain and Use the PRODUCT BRAIN

**Purpose**: Define how to maintain, update, and use the PRODUCT BRAIN documentation system to prevent conceptual drift and maintain product coherence.

---

## DOCUMENTATION SYSTEM PHILOSOPHY

**The documentation system is**:
- The source of truth
- The conceptual nervous system
- The operational guide
- The persistent memory

**The documentation system must**:
- Be kept current
- Be used for all decisions
- Be maintained rigorously
- Be accessible to all

---

## DOCUMENTATION STRUCTURE

### Foundational Documents (READ FIRST)
- `PRODUCT_BRAIN.md` - Central anchor and index
- `WHAT_THIS_PRODUCT_IS_NOT.md` - Explicit boundaries
- `NON_NEGOTIABLE_PRINCIPLES.md` - Immutable rules
- `ARCHITECTURAL_PHILOSOPHY.md` - System design philosophy
- `UX_PHILOSOPHY.md` - User experience principles
- `VISUAL_LANGUAGE.md` - Visual identity rules

### Operational Documents
- `SETUP_LIFECYCLE.md` - How setups evolve
- `MARKET_REGIME_ENGINE.md` - Regime detection logic
- `TRANSITION_ENGINE.md` - State transition system
- `NARRATIVE_ENGINE.md` - Story construction logic
- `PRIORITY_ENGINE.md` - Ranking and filtering logic
- `INVALIDATION_ENGINE.md` - Setup failure detection

### Implementation Documents
- `ARCHITECTURE.md` - Technical architecture
- `SYSTEM_RULES.md` - Concrete system rules
- `COMPONENT_GUIDELINES.md` - UI component standards
- `DESIGN_PRINCIPLES.md` - Design decision framework

### Meta Documents
- `LLM_INTERACTION_RULES.md` - How to work with AI
- `DECISION_FILTER.md` - Feature evaluation criteria
- `ANTI_PATTERNS.md` - What to avoid
- `DOCUMENTATION_SYSTEM.md` - This document
- `ROADMAP.md` - Planned evolution

---

## DOCUMENTATION VERSIONING

### Versioning Philosophy

This documentation uses **conceptual versioning**, not semantic versioning.

**Format**: `v{major}.{minor}.{philosophy}`

- **major**: Philosophy shift (rare, requires consensus)
- **minor**: New principle or rule addition
- **philosophy**: Clarification, examples, refinement

**Current version**: v1.0.0

### When to Bump Versions

**Major bump** (rare):
- Philosophy shift
- Core principle change
- Fundamental architectural change
- Requires consensus and review

**Minor bump**:
- New principle added
- New rule added
- New anti-pattern added
- New document added

**Philosophy bump**:
- Clarification of existing principle
- New examples added
- Better explanations
- Formatting improvements
- Typo fixes

### Version Control

- All documentation in Git
- Each version tagged
- Changelog maintained
- Backwards compatibility maintained where possible

---

## DOCUMENTATION MAINTENANCE

### Maintenance Schedule

**Daily**:
- No daily maintenance needed
- Documentation is stable

**Weekly**:
- Review recent changes
- Update if philosophy evolved
- Check for drift

**Monthly**:
- Review all documents for accuracy
- Update examples if needed
- Add new anti-patterns if discovered
- Clarify ambiguous sections

**Quarterly**:
- Full documentation review
- Philosophy review
- Version bump if needed
- Stakeholder review

**Annually**:
- Major philosophy review
- Architecture review
- Complete refresh if needed
- Stakeholder workshop

### Maintenance Process

1. **Review**: Read relevant documents
2. **Identify changes**: What needs updating?
3. **Propose changes**: Draft updates
4. **Review proposal**: Get stakeholder input
5. **Approve changes**: Get consensus
6. **Implement changes**: Update documents
7. **Bump version**: Update version number
8. **Communicate**: Notify stakeholders
9. **Archive**: Keep old versions

### Maintenance Roles

**Documentation Maintainer**:
- Responsible for keeping documentation current
- Reviews changes monthly
- Proposes updates quarterly
- Coordinates with stakeholders

**Philosophy Owner**:
- Responsible for philosophy coherence
- Reviews major changes
- Approves philosophy shifts
- Maintains principles

**Product Architect**:
- Responsible for overall coherence
- Reviews architectural documents
- Approves architectural changes
- Maintains vision

---

## DOCUMENTATION USAGE

### For Developers

**Before coding**:
1. Read relevant operational documents
2. Check against decision filter
3. Verify alignment with principles
4. Check anti-patterns
5. Apply visual language rules

**During coding**:
1. Refer to component guidelines
2. Follow architectural philosophy
3. Maintain visual coherence
4. Document decisions

**After coding**:
1. Update documentation if philosophy evolved
2. Add new anti-patterns if discovered
3. Clarify ambiguous sections
4. Bump version if needed

### For Product Managers

**Before prioritizing**:
1. Read PRODUCT_BRAIN.md
2. Apply decision filter
3. Check against principles
4. Verify alignment with philosophy
5. Check anti-patterns

**During planning**:
1. Refer to roadmap
2. Check against WHAT_THIS_PRODUCT_IS_NOT
3. Verify operational philosophy
4. Maintain scarcity

**After decisions**:
1. Update roadmap if needed
2. Document rationale
3. Update principles if evolved
4. Bump version if needed

### For Designers

**Before designing**:
1. Read VISUAL_LANGUAGE.md
2. Read UX_PHILOSOPHY.md
3. Read DESIGN_PRINCIPLES.md
4. Check anti-aesthetics
5. Verify institutional feel

**During designing**:
1. Follow component guidelines
2. Maintain visual hierarchy
3. Apply color philosophy
4. Use correct typography

**After designing**:
1. Update component guidelines if needed
2. Add new patterns if discovered
3. Clarify ambiguous sections
4. Bump version if needed

### For LLMs

**Before suggesting**:
1. Read PRODUCT_BRAIN.md
2. Read WHAT_THIS_PRODUCT_IS_NOT.md
3. Read NON_NEGOTIABLE_PRINCIPLES.md
4. Read relevant operational documents
5. Read ANTI_PATTERNS.md

**While suggesting**:
1. Cite relevant principles
2. Cite relevant documentation
3. Check against anti-patterns
4. Apply decision filter
5. Explain rationale

**After suggesting**:
1. Verify alignment with principles
2. Verify alignment with visual language
3. Verify no anti-patterns
4. Document the suggestion

---

## DOCUMENTATION ACCESS

### Where to Find Documentation

**Location**: `/PRODUCT_BRAIN/` directory in project root

**Access methods**:
- Direct file access
- Git repository
- Internal wiki (if available)
- Printed copies (if needed)

### Documentation Distribution

**Who should have access**:
- All developers
- All product managers
- All designers
- All stakeholders
- LLMs (via context)

**How to distribute**:
- Onboarding includes documentation reading
- Quarterly reviews for all
- Changes communicated via email/slack
- Version updates announced

---

## DOCUMENTATION QUALITY

### Quality Standards

**All documents must**:
- Have clear purpose
- Have principles section
- Have rules section
- Have anti-patterns section
- Have examples (good and bad)
- Have rationale for decisions
- Be consistent with other documents
- Be well-formatted
- Be typo-free
- Be current

### Quality Checklist

Before publishing any document:
- [ ] Clear purpose statement
- [ ] Principles section
- [ ] Rules section
- [ ] Anti-patterns section
- [ ] Good examples
- [ ] Bad examples
- [ ] Rationale for decisions
- [ ] Consistent with other documents
- [ ] Well-formatted
- [ ] No typos
- [ ] Current and accurate

---

## DOCUMENTATION DRIFT DETECTION

### Signs of Documentation Drift

- Documents not being read
- Documents being ignored
- Philosophy violations in code
- Visual drift in design
- Feature creep
- Anti-patterns appearing

### Drift Detection Process

1. **Monitor**: Watch for drift signs
2. **Investigate**: Identify drift source
3. **Reset**: Re-read documentation
4. **Correct**: Fix drift issues
5. **Document**: Add drift to anti-patterns
6. **Communicate**: Notify stakeholders

### Drift Prevention

- Require documentation reading for all decisions
- Include documentation in code review
- Include documentation in design review
- Include documentation in product review
- Quarterly documentation reviews
- LLM context always includes documentation

---

## DOCUMENTATION EMERGENCIES

### Emergency Scenarios

**Documentation is outdated**:
1. Stop all work
2. Review all documents
3. Identify outdated sections
4. Update documents
5. Bump version
6. Communicate changes

**Philosophy has drifted**:
1. Stop all work
2. Re-read foundational documents
3. Identify drift points
4. Revert to philosophy
5. Document the lesson
6. Update anti-patterns

**Documentation is being ignored**:
1. Stop all work
2. Require documentation reading
3. Include in review process
4. Enforce documentation usage
5. Monitor compliance

### Emergency Reset Process

1. **Stop**: Stop all work
2. **Read**: Re-read all foundational documents
3. **Identify**: Identify drift or issues
4. **Revert**: Revert to philosophy-aligned state
5. **Document**: Document the lesson
6. **Update**: Update documentation if needed
7. **Communicate**: Notify stakeholders

---

## DOCUMENTATION METRICS

### Metrics to Track

- Documentation read rate
- Documentation citation rate
- Philosophy violation rate
- Anti-pattern occurrence rate
- Documentation update frequency
- Documentation version history

### How to Measure

- Track documentation access logs
- Track code review citations
- Track design review citations
- Track product review citations
- Track LLM context inclusion

---

## DOCUMENTATION GOVERNANCE

### Governance Structure

**Documentation Maintainer**: Day-to-day maintenance
**Philosophy Owner**: Philosophy coherence
**Product Architect**: Overall coherence
**Stakeholders**: Review and approval

### Decision Rights

**Documentation Maintainer**:
- Can update philosophy bump changes
- Can add examples
- Can clarify sections
- Can fix typos

**Philosophy Owner**:
- Can approve minor bump changes
- Can approve new principles
- Can approve new rules
- Must approve major bump changes

**Product Architect**:
- Can approve architectural changes
- Can approve new documents
- Must approve philosophy shifts
- Must approve major changes

**Stakeholders**:
- Review major changes
- Provide input
- Approve philosophy shifts

---

## DOCUMENTATION TOOLS

### Recommended Tools

**Editing**:
- Markdown editors
- VS Code
- Git

**Version Control**:
- Git
- GitHub/GitLab

**Review**:
- Pull requests
- Review tools
- Stakeholder review process

**Distribution**:
- Git repository
- Internal wiki
- Email/slack announcements

---

## DOCUMENTATION BEST PRACTICES

### Writing Guidelines

- Use clear, concise language
- Use active voice
- Use present tense
- Use specific examples
- Avoid jargon where possible
- Be consistent with terminology
- Use formatting for hierarchy
- Use code blocks for examples

### Formatting Guidelines

- Use Markdown
- Use headings for structure
- Use bullet points for lists
- Use code blocks for examples
- Use bold for emphasis
- Use horizontal rules for sections
- Use consistent spacing

### Review Guidelines

- Review for clarity
- Review for accuracy
- Review for consistency
- Review for completeness
- Review for formatting
- Review for typos

---

## DOCUMENTATION EVOLUTION

### How Documentation Evolves

**Organic evolution**:
- Examples added over time
- Clarifications added
- Anti-patterns discovered
- Lessons learned documented

**Planned evolution**:
- Quarterly reviews
- Philosophy reviews
- Architecture reviews
- Major refreshes

**Emergency evolution**:
- Drift correction
- Philosophy re-alignment
- Emergency updates

### Evolution Process

1. **Identify need**: What needs updating?
2. **Draft changes**: Write the update
3. **Review proposal**: Get input
4. **Approve changes**: Get consensus
5. **Implement changes**: Update documents
6. **Bump version**: Update version
7. **Communicate**: Notify stakeholders
8. **Archive**: Keep old versions

---

## DOCUMENTATION SYSTEM SUMMARY

**The documentation system is**:
- The source of truth
- The conceptual nervous system
- The operational guide
- The persistent memory

**Key principles**:
- Keep it current
- Use it for all decisions
- Maintain it rigorously
- Make it accessible

**Maintenance schedule**:
- Monthly reviews
- Quarterly philosophy reviews
- Annual major reviews

**Versioning**:
- Conceptual versioning
- Major/minor/philosophy bumps
- Git version control

**This document is the guide for maintaining the PRODUCT BRAIN.**
