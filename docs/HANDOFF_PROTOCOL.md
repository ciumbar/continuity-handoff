# Handoff Protocol

This is the model-agnostic protocol implemented by the skill.

## 1. Start

Before scanning the repository:

1. Check for `.handoff/state.json`.
2. If it exists, validate it.
3. Read `next_step`, open blockers, latest command status, touched files, and decisions.
4. Continue from `next_step`.

If no handoff exists, initialize it.

## 2. Work

Checkpoint after:

- plan changes;
- edits to important files;
- build/test/lint commands;
- errors or blockers;
- assumptions or decisions;
- finishing any checklist item.

Use stable IDs for checklist items, decisions, commands, blockers, and assumptions.

## 3. Threshold

Approximate cutoff risk with:

- `HANDOFF_CONTEXT_USED_PCT`;
- `HANDOFF_STARTED_AT`;
- `HANDOFF_MAX_MINUTES`;
- `HANDOFF_TRANSCRIPT_PATH`;
- `HANDOFF_MAX_CHARS`.

If any known signal is at or above 95%, checkpoint immediately and prepare for a new session/model.

## 4. Resume

The next model/session should:

1. read the handoff first;
2. avoid asking the user to restate the goal;
3. avoid broad rescans unless the handoff is stale;
4. execute the next concrete step;
5. update state before stopping.

## 5. Finish

Only mark complete when:

- the Definition of Done is met;
- checklist items are done or explicitly skipped;
- verification commands are recorded;
- blockers are resolved or documented;
- `next_step` says no further action is required.
