# Continuity Handoff

`continuity-handoff` is a portable agent skill for keeping coding work alive across context exhaustion, token/time limits, model switches, and new sessions.

It is designed for Codex CLI, Claude Code, OpenClaw, and any agent that can read a `SKILL.md` folder and run local helper scripts.

This is not automatic model switching; it is a portable handoff protocol and helper skill.

## What It Solves

When one model or session stops mid-project, the next one often wastes tokens rediscovering:

- the original goal;
- what has already been done;
- what files changed;
- why decisions were made;
- what tests passed or failed;
- the exact next step.

This skill writes that information continuously into the target repo:

- `.handoff/state.json` is the machine-readable source of truth.
- `.handoff/STATE.md` is the human-readable handoff.

The result is a clean resume point for another model, another CLI, or a fresh context window.

## Repository Contents

```text
continuity-handoff/
  SKILL.md                         # Main skill instructions
  scripts/handoff.py               # Portable handoff helper CLI
  references/state-schema.md       # state.json schema and merge rules
  agents/openai.yaml               # Codex/OpenAI UI metadata
tests/
  test_handoff.py                  # Regression tests for helper behavior
```

## Install

Clone the repo:

```bash
git clone https://github.com/ciumbar/continuity-handoff.git
cd continuity-handoff
```

### Codex

Install the skill into Codex's local skills folder:

```bash
mkdir -p ~/.codex/skills
cp -R continuity-handoff ~/.codex/skills/
```

Restart Codex so it reloads available skills.

### Claude Code

Install globally for your user:

```bash
mkdir -p ~/.claude/skills
cp -R continuity-handoff ~/.claude/skills/
```

Or install only inside one project:

```bash
mkdir -p /path/to/project/.claude/skills
cp -R continuity-handoff /path/to/project/.claude/skills/
```

Restart Claude Code or start a new session after installing.

### OpenClaw

Install globally:

```bash
mkdir -p ~/.openclaw/skills
cp -R continuity-handoff ~/.openclaw/skills/
```

If your OpenClaw setup uses workspace-scoped skills, copy the same folder into that workspace's configured skills directory. OpenClaw skills are plain directories containing `SKILL.md`, so this repo is intentionally compatible with that shape.

### Generic Agent

If your agent does not have a formal skills system, add this instruction to your project prompt:

```text
Use the continuity-handoff skill at /path/to/continuity-handoff/SKILL.md.
Before working, read .handoff/state.json if it exists. During work, keep it updated with scripts/handoff.py.
```

## Quick Start

Initialize handoff files in a project:

```bash
python3 continuity-handoff/scripts/handoff.py init \
  --root /path/to/project \
  --goal "Finish the feature with tests passing"
```

Record progress:

```bash
python3 continuity-handoff/scripts/handoff.py update \
  --root /path/to/project \
  --item tests:in_progress:"Run verification" \
  --file src/example.ts:modified:"Adjusted behavior" \
  --decision test-scope:"Run focused tests first":"Faster feedback before full suite" \
  --command unit-tests:"npm test":passed:"All unit tests passed" \
  --next-step "Run the full test suite and fix any failures"
```

Resume from a new model or session:

```bash
python3 continuity-handoff/scripts/handoff.py status --root /path/to/project
```

Validate and render the handoff:

```bash
python3 continuity-handoff/scripts/handoff.py validate --root /path/to/project
python3 continuity-handoff/scripts/handoff.py render --root /path/to/project
```

## Agent Startup Protocol

Tell any agent using this skill:

```text
Before scanning the repo, check for .handoff/state.json and .handoff/STATE.md.
If they exist, read them first and continue from next_step.
Do not ask me to re-explain the task unless the handoff is missing, invalid, or contradictory.
Update the handoff after meaningful progress and before stopping.
```

## Threshold Detection

Most CLIs do not expose exact model context or token telemetry. The skill uses conservative signals instead:

- checkpoint continuously after meaningful progress;
- checkpoint before ending any turn when work remains;
- use `HANDOFF_CONTEXT_USED_PCT` if the host exposes context usage;
- use `HANDOFF_STARTED_AT` and `HANDOFF_MAX_MINUTES` for time-based limits;
- use `HANDOFF_TRANSCRIPT_PATH` and `HANDOFF_MAX_CHARS` for approximate transcript size.

Example:

```bash
HANDOFF_CONTEXT_USED_PCT=96 \
python3 continuity-handoff/scripts/handoff.py check-threshold --root /path/to/project
```

Exit codes:

- `0`: handoff not required yet.
- `2`: handoff recommended now.
- `1`: invalid command/state/error.

## Autonomous "Acaba" Mode

For overnight or unattended work, initialize or update state with `mode=acaba`:

```bash
python3 continuity-handoff/scripts/handoff.py update \
  --root /path/to/project \
  --mode acaba \
  --dod "Requested behavior implemented" \
  --dod "Build and tests pass" \
  --next-step "Continue autonomously until the Definition of Done is met or a true blocker is reached"
```

In this mode the agent should:

- avoid asking the user unless blocked;
- document assumptions instead of silently guessing;
- keep commands and test results current;
- record every important decision and rationale;
- stop only when the Definition of Done is met or a blocker requires user input.

## State Format

See [continuity-handoff/references/state-schema.md](continuity-handoff/references/state-schema.md).

Key fields:

- `goal`
- `definition_of_done`
- `checklist`
- `files_touched`
- `decisions`
- `commands`
- `blockers`
- `assumptions`
- `next_step`
- `thresholds`

The helper merges checklist items, decisions, commands, blockers, and assumptions by stable `id`. Files are merged by `path`. Running the same update twice should not duplicate work.

## Prior Art / Comparison

This project is intentionally small and portable. It is best understood as a common handoff format plus helper script, not a replacement for native agent session systems.

- [`cli-continues`](https://github.com/yigitkonur/cli-continues) is the closest broader project I found. It focuses on continuing sessions across many CLI agents and includes more ambitious cross-tool orchestration. `continuity-handoff` is smaller: a skill folder, a deterministic Python helper, and repo-local state files.
- [OpenClaw Context Handoff](https://openclawlab.com/en/docs/features/context-handoff/) is a native OpenClaw feature for automatically preserving context near limits. `continuity-handoff` complements this by giving non-OpenClaw tools the same repo-local handoff convention.
- Claude Code has native session/memory tools such as `/resume`, `/compact`, checkpoints, and `CLAUDE.md` memory. `continuity-handoff` does not replace those; it adds a provider-neutral state file that another model or CLI can read.

The goal is interoperability: if one tool stops, another tool can read `.handoff/state.json` and `.handoff/STATE.md` and continue with less rediscovery.

## Test

Run the regression tests:

```bash
python3 -m unittest discover -s tests
```

If you have Codex's skill creator validator available:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py continuity-handoff
```

## Security Notes

This skill contains one Python script using only the standard library. It writes `.handoff/state.json` and `.handoff/STATE.md` inside the target repo you pass with `--root`.

Before installing any community skill, read the code. Agent skills can influence local tool use and may execute scripts if the agent invokes them.

## License

MIT. See [LICENSE](LICENSE).
