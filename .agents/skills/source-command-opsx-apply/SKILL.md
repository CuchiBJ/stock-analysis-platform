---
name: "source-command-opsx-apply"
description: "Implement tasks from an OpenSpec change (Experimental)"
---

# source-command-opsx-apply

Use this skill when the user asks to run the migrated source command `opsx-apply`.

## Command Template

Implement tasks from an OpenSpec change.

**Input**: Optionally specify a change name (e.g., `/opsx:apply add-auth`). If omitted, check if it can be inferred from conversation context. If vague or ambiguous you MUST prompt for available changes.

**Steps**

1. **Select the change**

   If a name is provided, use it. Otherwise:
   - Infer from conversation context if the user mentioned a change
   - Auto-select if only one active change exists
   - If ambiguous, run `openspec list --json` to get available changes and use the **AskUserQuestion tool** to let the user select

   Always announce: "Using change: <name>" and how to override (e.g., `/opsx:apply <other>`).

2. **Check status to understand the schema**
   ```bash
   openspec status --change "<name>" --json
   ```
   Parse the JSON to understand:
   - `schemaName`: The workflow being used (e.g., "spec-driven")
   - Which artifact contains the tasks (typically "tasks" for spec-driven, check status for others)

3. **Get compact apply instructions**

   ```bash
   openspec instructions apply --change "<name>" --json \
     | jq '{changeName,changeDir,schemaName,state,instruction,progress,contextFiles,tasks:[.tasks[] | select(.done | not)]}'
   ```

   This returns:
   - `contextFiles`: artifact ID -> array of concrete file paths (varies by schema)
   - `changeDir`: canonical directory for optional continuation state
   - Progress (total, complete, remaining)
   - Pending tasks only
   - Dynamic instruction based on current state

   If `jq` is unavailable, obtain the full JSON but retain only those fields and
   avoid echoing completed tasks back into the conversation.

   **Handle states:**
   - If `state: "blocked"` (missing artifacts): show message, suggest using `/opsx:continue`
   - If `state: "all_done"`: congratulate, suggest archive
   - Otherwise: proceed to implementation

4. **Resume from a relevant handoff**

   Choose the explicit task ID supplied by the user, or the first pending task as
   the current candidate. Then check for `<changeDir>/memory/current.md`.
   If it exists, inspect it; use it only when it names a task that is still pending
   or an unresolved blocker that affects the selected task.

   Treat the handoff as a context cache, never as a source of truth:
   - Confirm task status against the apply instructions.
   - Confirm mutable repository facts with focused Git, file, or test checks.
   - Ignore stale or mismatched handoffs and briefly state why.
   - Do not read the handoff when the change is `all_done`.

5. **Route context for the current task**

   Treat `contextFiles` as an index, not a mandatory reading list. Select the
   current task before opening artifacts, and load only the context required for
   that task.

   For a spec-driven change:
   - Use the current candidate selected in the previous step.
   - Extract the capability tag from the task when present, such as
     `[journal-ownership]`, and read only the matching capability spec under
     `specs/<capability>/`.
   - Read only the matching task entry or local task group from the tasks artifact;
     do not read the completed task history by default.
   - Search the relevant spec for `Implementation` notes, named symbols, and paths,
     then inspect those implementation files and their direct consumers.
   - Search the design artifact by task terms, capability name, headings, or named
     components. Read only the relevant section unless the task is explicitly
     cross-cutting.
   - Read the proposal only when scope, non-goals, or user intent is unclear from
     the task and relevant spec.

   For other schemas, use artifact roles from `contextFiles` in the same way:
   begin with the task-local requirement and implementation references, then
   expand only as evidence requires. Do not assume spec-driven filenames.

   Expand context when the task crosses capabilities, a requirement is ambiguous,
   artifacts conflict, or verification exposes an undocumented dependency. State
   briefly why broader context is needed. Do not preload artifacts for later tasks;
   route context again when moving to the next task.

6. **Show current progress**

   Display:
   - Schema being used
   - Progress: "N/M tasks complete"
   - Remaining tasks overview
   - Dynamic instruction from CLI

7. **Implement tasks (loop until done or blocked)**

   For each pending task:
   - Show which task is being worked on
   - Make the code changes required
   - Keep changes minimal and focused
   - Mark task complete in the tasks file: `- [ ]` → `- [x]`
   - Continue to next task

   **Pause if:**
   - Task is unclear → ask for clarification
   - Implementation reveals a design issue → suggest updating artifacts
   - Error or blocker encountered → report and wait for guidance
   - User interrupts

8. **On completion or pause, show status**

   Display:
   - Tasks completed this session
   - Overall progress: "N/M tasks complete"
   - If all done: suggest archive
   - If paused: explain why and wait for guidance

   When pausing material unfinished work that another session or agent is likely to
   continue, create or replace `<changeDir>/memory/current.md`. Use the
   `session-handoff` skill when available; otherwise write the same compact fields:
   objective and acceptance criteria, current task ID/capability/status, relevant
   paths, edits and preserved invariants, decisions, exact verification commands
   and outcomes, blockers or assumptions, repository state, and the next concrete
   action. Recorded verification is historical evidence: rerun the checks required
   by the current diff before marking a task complete.

   Keep the handoff under approximately 2 KB. Do not paste diffs, logs, secrets, or
   information recoverable with one cheap command. Do not create one for completed
   work, a trivial pause, or an optional review checkpoint. Replace the previous
   handoff rather than appending a history. Remove a handoff created by this flow
   once no pending work or relevant blocker remains.

**Output During Implementation**

```
## Implementing: <change-name> (schema: <schema-name>)

Working on task 3/7: <task description>
[...implementation happening...]
✓ Task complete

Working on task 4/7: <task description>
[...implementation happening...]
✓ Task complete
```

**Output On Completion**

```
## Implementation Complete

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 7/7 tasks complete ✓

### Completed This Session
- [x] Task 1
- [x] Task 2
...

All tasks complete! You can archive this change with `/opsx:archive`.
```

**Output On Pause (Issue Encountered)**

```
## Implementation Paused

**Change:** <change-name>
**Schema:** <schema-name>
**Progress:** 4/7 tasks complete

### Issue Encountered
<description of the issue>

**Options:**
1. <option 1>
2. <option 2>
3. Other approach

What would you like to do?
```

**Guardrails**
- Keep going through tasks until done or blocked
- Read the current task's routed context before implementation; do not read every
  file in `contextFiles` by default
- If task is ambiguous, pause and ask before implementing
- If implementation reveals issues, pause and suggest artifact updates
- Keep code changes minimal and scoped to each task
- Update task checkbox immediately after completing each task
- Pause on errors, blockers, or unclear requirements - don't guess
- Use `contextFiles` from CLI output as the artifact index; don't assume specific file names
- A handoff may accelerate discovery but never overrides current artifacts, code,
  Git state, or verification results

**Fluid Workflow Integration**

This skill supports the "actions on a change" model:

- **Can be invoked anytime**: Before all artifacts are done (if tasks exist), after partial implementation, interleaved with other actions
- **Allows artifact updates**: If implementation reveals design issues, suggest updating artifacts - not phase-locked, work fluidly
