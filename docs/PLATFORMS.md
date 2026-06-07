# Platform Guide

This guide documents how to use `continuity-handoff` with common agent platforms.

## Codex

Install:

```bash
mkdir -p ~/.codex/skills
cp -R continuity-handoff ~/.codex/skills/
```

Use:

```text
Use $continuity-handoff. Resume from the existing handoff if present.
```

Expected behavior:

- Codex loads `continuity-handoff/SKILL.md` when the request mentions handoff, resume, fallback, continuity, context limits, token limits, or "acaba".
- The skill instructs Codex to read `.handoff/state.json` before broad repo exploration.
- The helper script can be run directly from the installed skill folder.

## Claude Code

Global install:

```bash
mkdir -p ~/.claude/skills
cp -R continuity-handoff ~/.claude/skills/
```

Project install:

```bash
mkdir -p .claude/skills
cp -R /path/to/continuity-handoff .claude/skills/
```

Use:

```text
Use the continuity-handoff skill. Before doing repo exploration, read .handoff/state.json and continue from next_step.
```

Notes:

- Claude Code skills are directories containing `SKILL.md`.
- `~/.claude/skills/<skill-name>/SKILL.md` makes a skill available globally.
- `.claude/skills/<skill-name>/SKILL.md` keeps it scoped to a project.

## OpenClaw

Global install:

```bash
mkdir -p ~/.openclaw/skills
cp -R continuity-handoff ~/.openclaw/skills/
```

Workspace install depends on your OpenClaw configuration. Use the workspace skills directory configured for your agent and copy the full `continuity-handoff` folder there.

Use:

```text
Use the continuity-handoff skill. Keep .handoff/state.json updated continuously and resume from next_step.
```

Notes:

- OpenClaw skills use a `SKILL.md` file with YAML frontmatter and markdown instructions.
- Some OpenClaw setups watch skills folders and refresh when `SKILL.md` changes; restart the agent if your setup does not hot reload.

## Generic Agent CLI

For agents without native skills support:

1. Put this repo somewhere stable.
2. Add the full path to `continuity-handoff/SKILL.md` in your system/project prompt.
3. Tell the agent to call `scripts/handoff.py` for state updates.

Prompt snippet:

```text
Use /path/to/continuity-handoff/SKILL.md as a reusable workflow.
At startup, read .handoff/state.json if it exists.
During work, run scripts/handoff.py update after meaningful progress.
Before stopping, validate and render the handoff.
```

## Shared Handoff Commands

Initialize:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py init --root "$PWD" --goal "Finish the task"
```

Resume:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py status --root "$PWD"
```

Checkpoint:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py update --root "$PWD" \
  --item implementation:in_progress:"Implement the next change" \
  --next-step "Continue from the current failing test"
```

Threshold:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py check-threshold --root "$PWD"
```

Validate:

```bash
python3 /path/to/continuity-handoff/scripts/handoff.py validate --root "$PWD"
python3 /path/to/continuity-handoff/scripts/handoff.py render --root "$PWD"
```
