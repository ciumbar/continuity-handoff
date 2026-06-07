---
name: continuity-handoff
description: Use this skill to preserve and resume coding work across context exhaustion, token or time limits, model switches, new sessions, handoffs, fallbacks, and autonomous "acaba" mode work in Codex CLI, Claude Code, OpenClaw, or other agent CLIs.
---

# Continuity Handoff

## Purpose

Use this skill when work must survive a context window filling up, a model/provider switch, a time or token limit, an interrupted session, or an autonomous long-running request such as "acaba".

The durable state lives in the target repo:

- `.handoff/state.json` for machines.
- `.handoff/STATE.md` for humans.

Do not rely on private model telemetry. Checkpoint continuously and use conservative threshold estimates.

## Startup Protocol

At the start of a task, before broad repo exploration:

1. Look for `.handoff/state.json` and `.handoff/STATE.md` in the repo root.
2. If state exists, read it first and continue from `next_step`.
3. Use `scripts/handoff.py status --root <repo>` for a compact resume summary.
4. Avoid rescanning the whole repo unless the handoff is missing, invalid, stale, or contradicts the current files.
5. If no state exists, initialize it with:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py init --root <repo> --goal "<task goal>"
```

Read `references/state-schema.md` only when you need the full JSON contract.

## Checkpoint Protocol

Update the handoff after every meaningful transition:

- after understanding or changing the plan;
- before risky edits, migrations, destructive commands, or long-running work;
- after edits to important files;
- after build, test, lint, or verification commands;
- when blocked, making assumptions, or choosing a tradeoff;
- before ending a turn while work remains;
- when threshold checks indicate high context, time, token, or transcript usage.

Use stable IDs so repeated resumes do not duplicate work. Prefer the helper:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py update --root <repo> \
  --next-step "Run the focused test suite and fix any failures" \
  --item tests:in_progress:"Run verification" \
  --file src/example.ts \
  --decision test-scope:"Use focused tests first":"Faster feedback before full suite"
```

Regenerate the human document after manual JSON edits:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py render --root <repo>
```

## Threshold Protocol

Run threshold checks periodically during long sessions:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py check-threshold --root <repo>
```

Default signals:

- `HANDOFF_CONTEXT_USED_PCT >= 95` means checkpoint and prepare handoff.
- `HANDOFF_MAX_MINUTES` defaults to `270`; elapsed time at or above 95% means checkpoint.
- `HANDOFF_MAX_CHARS` combined with `HANDOFF_TRANSCRIPT_PATH` estimates transcript usage; 95% means checkpoint.
- Missing telemetry is normal. In that case, rely on frequent checkpointing.

If a threshold is exceeded, immediately update `next_step`, checklist, files touched, command status, blockers, and assumptions. Then stop cleanly or ask the host CLI to open a fresh session if available.

## Resume Behavior

When resuming from a handoff:

1. Validate state with `handoff.py validate --root <repo>`.
2. Read the compact `status` output.
3. Execute only the `next_step` unless it is obsolete.
4. Mark completed checklist items by stable ID.
5. Record new decisions and verification results.

If state is inconsistent with the repo, record a blocker or decision explaining the mismatch before repairing it.

## "Acaba" Mode

When the user asks for autonomous completion, set `mode` to `acaba` and work without further user input unless a real blocker prevents safe progress.

In this mode:

- define or refine `definition_of_done` before deep work;
- record every assumption that replaces a user decision;
- prefer reversible, well-scoped changes;
- keep tests/builds current in `commands`;
- checkpoint before each major phase;
- stop only when the Definition of Done is met or a blocker truly requires user input.

Do not hide uncertainty. If final verification is not green, document exact failures, commands, and the next concrete fix.

## Definition of Done

Declare the work finished only when:

- the user's requested behavior is implemented;
- all checklist items are `done` or explicitly marked `skipped` with a reason;
- touched files and decisions are recorded;
- build, lint, tests, or equivalent verification are green;
- remaining known issues are absent or documented as accepted scope;
- `next_step` clearly says no further action is required.

Before final response, run:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py validate --root <repo>
python3 /path/to/continuity-handoff/scripts/handoff.py render --root <repo>
```
