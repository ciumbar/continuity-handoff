# continuity-handoff

Portable agent continuity skill for Codex CLI, Claude Code, OpenClaw, and other coding agents.

It keeps durable handoff state in a target repo so another model or a fresh session can resume without rebuilding context from scratch:

- `.handoff/state.json` for machine-readable state.
- `.handoff/STATE.md` for human-readable state.

## Install

Copy the skill folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R continuity-handoff ~/.codex/skills/
```

Other agent CLIs can use the same `SKILL.md`, `references/`, and `scripts/` files as plain instructions and helpers.

## Quick Use

Initialize handoff files in a project:

```bash
python3 continuity-handoff/scripts/handoff.py init --root /path/to/repo --goal "Finish the feature"
```

Record progress:

```bash
python3 continuity-handoff/scripts/handoff.py update --root /path/to/repo \
  --item tests:in_progress:"Run verification" \
  --next-step "Run focused tests and fix failures"
```

Resume later:

```bash
python3 continuity-handoff/scripts/handoff.py status --root /path/to/repo
```

## Test

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py continuity-handoff
python3 -m unittest discover -s tests
```

