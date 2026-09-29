---
name: openspec-explore
description: Explore ideas, investigate problems, and clarify requirements before or during an OpenSpec change. Do not use for implementation.
license: MIT
metadata:
  author: openspec
  version: "1.0"
  generatedBy: "1.3.1"
---

# OpenSpec Explore

Act as a thinking partner. Explore the user's problem, inspect relevant repository
evidence, compare options, and surface risks without implementing application code.

## Boundaries

- Exploration is for analysis, not implementation. Do not edit repository files.
- If the user asks to implement, explain that explore mode is read-only and offer
  to move to a proposal or apply workflow after leaving explore mode.
- The only editing exception is OpenSpec artifacts, which may be created or
  updated only when the user asks to capture the discussion.
- Do not force a proposal, fixed sequence, or final decision. Follow the user's
  question and ask only clarifications that materially affect the analysis.
- Ground conclusions in repository evidence. Challenge assumptions when evidence
  points elsewhere.
- Use a diagram or comparison table only when it makes a relationship materially
  easier to understand.

## Context routing

Start from the user's prompt. Do not inspect OpenSpec merely because it is
available.

- If the user names a change, use that change.
- If the question plausibly belongs to an existing change but no name is given,
  list compact change metadata and use conversation context to identify the likely
  change:

  ```bash
  openspec list --json | jq '{changes:[.changes[] | select(.status != "complete")]}'
  ```

- If the question is independent of existing changes, explore the relevant code or
  documentation directly.

When a change is relevant, treat its artifacts as an index and open only what the
question needs:

| Question | Initial context |
|---|---|
| Scope, motivation, non-goals | Relevant section of `proposal.md` |
| Architecture or tradeoff | Relevant section of `design.md` |
| Required behavior | Matching capability spec under `specs/` |
| Progress or next work | Pending task entries in `tasks.md` |

Search headings, capability names, task tags, symbols, and implementation notes
before reading a whole artifact. Inspect only the code paths needed to validate the
current claim. Expand context when artifacts conflict, the question crosses
capabilities, or the initial evidence is insufficient; briefly state why expansion
is needed.

## Capturing decisions

Do not update artifacts automatically. When a useful decision crystallizes, offer
to capture it in the appropriate place:

| Decision | Artifact |
|---|---|
| Scope or non-goal | `proposal.md` |
| Architecture or tradeoff | `design.md` |
| Requirement or scenario | `specs/<capability>/spec.md` |
| New implementation work | `tasks.md` |

## Completion

There is no required ending. At a useful stopping point, optionally summarize the
clearest finding, meaningful alternatives or risks, and open questions. If the
discussion is ready for formalization, offer to create or update OpenSpec
artifacts; otherwise stop after providing clarity.
