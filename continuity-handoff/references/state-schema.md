# Handoff State Schema

`state.json` is the machine-readable source of truth for cross-model and cross-session continuity. `STATE.md` is rendered from it for humans.

## Location

Store files in the target repository:

- `.handoff/state.json`
- `.handoff/STATE.md`

## Top-Level Fields

- `schema_version`: string. Current value is `1.0`.
- `project`: object with `name` and `root`.
- `goal`: string describing the global objective.
- `definition_of_done`: array of strings.
- `mode`: string, usually `normal` or `acaba`.
- `checklist`: array of work items.
- `files_touched`: array of touched files.
- `decisions`: array of decisions and rationale.
- `commands`: array of build/test/lint/verification command records.
- `blockers`: array of open or resolved blockers.
- `assumptions`: array of assumptions made without user input.
- `next_step`: string with the immediate action for the next model/session.
- `resume_instructions`: string with compact continuation guidance.
- `thresholds`: object with time/context/transcript limit settings and latest readings.
- `last_updated`: ISO 8601 UTC timestamp.

## Item Shapes

Checklist items:

```json
{
  "id": "tests",
  "status": "in_progress",
  "text": "Run verification",
  "notes": ""
}
```

Allowed checklist statuses: `pending`, `in_progress`, `done`, `blocked`, `skipped`.

Files touched:

```json
{
  "path": "src/example.ts",
  "status": "modified",
  "notes": "Adjusted parser behavior"
}
```

Decisions:

```json
{
  "id": "test-scope",
  "summary": "Use focused tests first",
  "rationale": "Faster feedback before full suite"
}
```

Commands:

```json
{
  "id": "pytest",
  "command": "pytest",
  "status": "passed",
  "notes": "All tests green"
}
```

Command statuses should be one of `not_run`, `running`, `passed`, `failed`, or `skipped`.

Blockers:

```json
{
  "id": "missing-api-key",
  "status": "open",
  "summary": "API key unavailable",
  "notes": "Use placeholder until user provides credentials"
}
```

Assumptions:

```json
{
  "id": "credential-placeholder",
  "text": "Use environment variable placeholders for credentials"
}
```

## Idempotency Rules

- Merge checklist, decisions, commands, blockers, and assumptions by stable `id`.
- Merge files by normalized `path`.
- Repeating the same update must not create duplicates.
- Updating an existing ID replaces provided fields and preserves unspecified fields.
- `STATE.md` can always be regenerated from `state.json`.

## Threshold Environment Variables

- `HANDOFF_CONTEXT_USED_PCT`: current context usage percentage when provided by the host.
- `HANDOFF_STARTED_AT`: ISO timestamp or Unix seconds for session start.
- `HANDOFF_MAX_MINUTES`: session limit in minutes. Defaults to `270`.
- `HANDOFF_MAX_CHARS`: maximum transcript characters for approximation.
- `HANDOFF_TRANSCRIPT_PATH`: transcript file used for character-count estimation.

At or above 95% of any known threshold, checkpoint immediately and prepare a clean handoff.
