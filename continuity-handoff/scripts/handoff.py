#!/usr/bin/env python3
"""Portable handoff state helper for agent continuity."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
HANDOFF_DIR = ".handoff"
STATE_JSON = "state.json"
STATE_MD = "STATE.md"
THRESHOLD_PCT = 95.0
CHECKLIST_STATUSES = {"pending", "in_progress", "done", "blocked", "skipped"}
COMMAND_STATUSES = {"not_run", "running", "passed", "failed", "skipped"}
BLOCKER_STATUSES = {"open", "resolved"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def repo_name(root: Path) -> str:
    return root.resolve().name


def handoff_paths(root: Path) -> tuple[Path, Path]:
    handoff_dir = root / HANDOFF_DIR
    return handoff_dir / STATE_JSON, handoff_dir / STATE_MD


def default_state(root: Path, goal: str = "", mode: str = "normal") -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {"name": repo_name(root), "root": str(root.resolve())},
        "goal": goal,
        "definition_of_done": [],
        "mode": mode,
        "checklist": [],
        "files_touched": [],
        "decisions": [],
        "commands": [],
        "blockers": [],
        "assumptions": [],
        "next_step": "Continue from the latest user request.",
        "resume_instructions": "Read this handoff first, then execute next_step without broad repo rescanning unless state is stale.",
        "thresholds": {
            "context_used_pct": None,
            "max_minutes": int(os.environ.get("HANDOFF_MAX_MINUTES", "270")),
            "elapsed_minutes": None,
            "max_chars": None,
            "transcript_chars": None,
            "last_check": now,
            "should_handoff": False,
            "reasons": [],
        },
        "last_updated": now,
    }


def load_state(root: Path) -> dict[str, Any]:
    state_path, _ = handoff_paths(root)
    if not state_path.exists():
        return default_state(root)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {state_path}: {exc}") from exc
    if not isinstance(state, dict):
        raise SystemExit(f"Invalid state in {state_path}: top-level value must be an object")
    return normalize_state(root, state)


def normalize_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    base = default_state(root)
    for key, value in base.items():
        state.setdefault(key, value)
    state.setdefault("project", {})
    state["project"].setdefault("name", repo_name(root))
    state["project"].setdefault("root", str(root.resolve()))
    for key in ["definition_of_done", "checklist", "files_touched", "decisions", "commands", "blockers", "assumptions"]:
        if not isinstance(state.get(key), list):
            state[key] = []
    if not isinstance(state.get("thresholds"), dict):
        state["thresholds"] = base["thresholds"]
    for key, value in base["thresholds"].items():
        state["thresholds"].setdefault(key, value)
    return state


def save_state(root: Path, state: dict[str, Any]) -> None:
    state_path, md_path = handoff_paths(root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = utc_now()
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(state), encoding="utf-8")


def merge_by_id(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    item_id = item.get("id")
    if not item_id:
        raise SystemExit(f"Item missing required id: {item}")
    for existing in items:
        if existing.get("id") == item_id:
            existing.update({k: v for k, v in item.items() if v is not None})
            return
    items.append({k: v for k, v in item.items() if v is not None})


def merge_file(items: list[dict[str, Any]], item: dict[str, Any]) -> None:
    path = item.get("path")
    if not path:
        raise SystemExit(f"File item missing required path: {item}")
    normalized = str(Path(path))
    item["path"] = normalized
    for existing in items:
        if existing.get("path") == normalized:
            existing.update({k: v for k, v in item.items() if v is not None})
            return
    items.append({k: v for k, v in item.items() if v is not None})


def split_parts(value: str, expected: int, label: str) -> list[str]:
    parts = value.split(":", expected - 1)
    if len(parts) != expected:
        raise SystemExit(f"{label} must contain {expected} colon-separated fields: {value}")
    return [part.strip() for part in parts]


def apply_update_payload(state: dict[str, Any], payload: dict[str, Any]) -> None:
    scalar_keys = ["goal", "mode", "next_step", "resume_instructions"]
    for key in scalar_keys:
        if payload.get(key) is not None:
            state[key] = payload[key]
    if payload.get("definition_of_done"):
        existing = set(state["definition_of_done"])
        for item in payload["definition_of_done"]:
            if item not in existing:
                state["definition_of_done"].append(item)
                existing.add(item)
    for item in payload.get("checklist", []):
        merge_by_id(state["checklist"], item)
    for item in payload.get("files_touched", []):
        merge_file(state["files_touched"], item)
    for key in ["decisions", "commands", "blockers", "assumptions"]:
        for item in payload.get(key, []):
            merge_by_id(state[key], item)


def parse_update_args(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "goal": args.goal,
        "mode": args.mode,
        "next_step": args.next_step,
        "resume_instructions": args.resume_instructions,
        "definition_of_done": args.dod or [],
        "checklist": [],
        "files_touched": [],
        "decisions": [],
        "commands": [],
        "blockers": [],
        "assumptions": [],
    }
    if args.update_json:
        parsed = json.loads(args.update_json)
        if not isinstance(parsed, dict):
            raise SystemExit("--update-json must be a JSON object")
        for key, value in parsed.items():
            if isinstance(value, list) and isinstance(payload.get(key), list):
                payload[key].extend(value)
            else:
                payload[key] = value
    if args.update_file:
        parsed = json.loads(Path(args.update_file).read_text(encoding="utf-8"))
        if not isinstance(parsed, dict):
            raise SystemExit("--update-file must contain a JSON object")
        for key, value in parsed.items():
            if isinstance(value, list) and isinstance(payload.get(key), list):
                payload[key].extend(value)
            else:
                payload[key] = value
    for raw in args.item or []:
        item_id, status, text = split_parts(raw, 3, "--item")
        if status not in CHECKLIST_STATUSES:
            raise SystemExit(f"Invalid checklist status '{status}'")
        payload["checklist"].append({"id": item_id, "status": status, "text": text})
    for raw in args.file or []:
        parts = raw.split(":", 2)
        payload["files_touched"].append({
            "path": parts[0].strip(),
            "status": parts[1].strip() if len(parts) > 1 and parts[1].strip() else "touched",
            "notes": parts[2].strip() if len(parts) > 2 else "",
        })
    for raw in args.decision or []:
        item_id, summary, rationale = split_parts(raw, 3, "--decision")
        payload["decisions"].append({"id": item_id, "summary": summary, "rationale": rationale})
    for raw in args.command or []:
        item_id, command, status, notes = split_parts(raw, 4, "--command")
        if status not in COMMAND_STATUSES:
            raise SystemExit(f"Invalid command status '{status}'")
        payload["commands"].append({"id": item_id, "command": command, "status": status, "notes": notes})
    for raw in args.blocker or []:
        item_id, status, summary, notes = split_parts(raw, 4, "--blocker")
        if status not in BLOCKER_STATUSES:
            raise SystemExit(f"Invalid blocker status '{status}'")
        payload["blockers"].append({"id": item_id, "status": status, "summary": summary, "notes": notes})
    for raw in args.assumption or []:
        item_id, text = split_parts(raw, 2, "--assumption")
        payload["assumptions"].append({"id": item_id, "text": text})
    return payload


def render_list(items: list[Any], empty: str = "None recorded.") -> str:
    if not items:
        return f"- {empty}\n"
    lines = []
    for item in items:
        if isinstance(item, dict):
            label = item.get("id") or item.get("path") or item.get("command") or "item"
            rest = []
            for key in ["status", "text", "summary", "command", "rationale", "notes"]:
                value = item.get(key)
                if value:
                    rest.append(f"{key}: {value}")
            lines.append(f"- `{label}`" + (f" - {'; '.join(rest)}" if rest else ""))
        else:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def render_markdown(state: dict[str, Any]) -> str:
    thresholds = state.get("thresholds", {})
    return f"""# Handoff State

Last updated: {state.get("last_updated", "")}

## Goal

{state.get("goal") or "Not recorded."}

## Mode

`{state.get("mode", "normal")}`

## Definition of Done

{render_list(state.get("definition_of_done", []))}
## Checklist

{render_list(state.get("checklist", []))}
## Files Touched

{render_list(state.get("files_touched", []))}
## Decisions

{render_list(state.get("decisions", []))}
## Commands

{render_list(state.get("commands", []))}
## Blockers

{render_list(state.get("blockers", []))}
## Assumptions

{render_list(state.get("assumptions", []))}
## Next Step

{state.get("next_step") or "Not recorded."}

## Resume Instructions

{state.get("resume_instructions") or "Read state.json and continue from next_step."}

## Thresholds

- context_used_pct: {thresholds.get("context_used_pct")}
- elapsed_minutes: {thresholds.get("elapsed_minutes")}
- max_minutes: {thresholds.get("max_minutes")}
- transcript_chars: {thresholds.get("transcript_chars")}
- max_chars: {thresholds.get("max_chars")}
- should_handoff: {thresholds.get("should_handoff")}
- reasons: {", ".join(thresholds.get("reasons", [])) if thresholds.get("reasons") else "none"}
"""


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["schema_version", "project", "goal", "mode", "checklist", "next_step", "resume_instructions", "thresholds", "last_updated"]
    for key in required:
        if key not in state:
            errors.append(f"missing top-level key: {key}")
    if state.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {state.get('schema_version')}")
    for item in state.get("checklist", []):
        if item.get("status") not in CHECKLIST_STATUSES:
            errors.append(f"invalid checklist status for {item.get('id')}: {item.get('status')}")
    for item in state.get("commands", []):
        if item.get("status") not in COMMAND_STATUSES:
            errors.append(f"invalid command status for {item.get('id')}: {item.get('status')}")
    for item in state.get("blockers", []):
        if item.get("status") not in BLOCKER_STATUSES:
            errors.append(f"invalid blocker status for {item.get('id')}: {item.get('status')}")
    for key in ["checklist", "decisions", "commands", "blockers", "assumptions"]:
        seen: set[str] = set()
        for item in state.get(key, []):
            item_id = item.get("id")
            if not item_id:
                errors.append(f"{key} item missing id")
            elif item_id in seen:
                errors.append(f"duplicate {key} id: {item_id}")
            seen.add(item_id)
    seen_paths: set[str] = set()
    for item in state.get("files_touched", []):
        path = item.get("path")
        if not path:
            errors.append("files_touched item missing path")
        elif path in seen_paths:
            errors.append(f"duplicate file path: {path}")
        seen_paths.add(path)
    return errors


def parse_started_at(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(float(raw), tz=timezone.utc)
    except ValueError:
        pass
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SystemExit(f"Invalid HANDOFF_STARTED_AT value: {raw}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def calculate_thresholds() -> dict[str, Any]:
    reasons: list[str] = []
    context_pct_raw = os.environ.get("HANDOFF_CONTEXT_USED_PCT")
    context_pct = float(context_pct_raw) if context_pct_raw else None
    if context_pct is not None and context_pct >= THRESHOLD_PCT:
        reasons.append(f"context usage is {context_pct:g}%")

    max_minutes = int(os.environ.get("HANDOFF_MAX_MINUTES", "270"))
    started_at = parse_started_at(os.environ.get("HANDOFF_STARTED_AT"))
    elapsed_minutes = None
    if started_at:
        elapsed_minutes = (datetime.now(timezone.utc) - started_at).total_seconds() / 60
        if elapsed_minutes >= max_minutes * (THRESHOLD_PCT / 100):
            reasons.append(f"elapsed time is {elapsed_minutes:.1f}/{max_minutes} minutes")

    max_chars_raw = os.environ.get("HANDOFF_MAX_CHARS")
    transcript_path = os.environ.get("HANDOFF_TRANSCRIPT_PATH")
    max_chars = int(max_chars_raw) if max_chars_raw else None
    transcript_chars = None
    if max_chars and transcript_path:
        path = Path(transcript_path)
        if path.exists():
            transcript_chars = len(path.read_text(encoding="utf-8", errors="ignore"))
            if transcript_chars >= max_chars * (THRESHOLD_PCT / 100):
                reasons.append(f"transcript size is {transcript_chars}/{max_chars} chars")

    return {
        "context_used_pct": context_pct,
        "max_minutes": max_minutes,
        "elapsed_minutes": round(elapsed_minutes, 1) if elapsed_minutes is not None else None,
        "max_chars": max_chars,
        "transcript_chars": transcript_chars,
        "last_check": utc_now(),
        "should_handoff": bool(reasons),
        "reasons": reasons,
    }


def print_status(state: dict[str, Any]) -> None:
    checklist = state.get("checklist", [])
    done = sum(1 for item in checklist if item.get("status") == "done")
    open_blockers = [item for item in state.get("blockers", []) if item.get("status") == "open"]
    print(f"Goal: {state.get('goal') or 'Not recorded'}")
    print(f"Mode: {state.get('mode', 'normal')}")
    print(f"Checklist: {done}/{len(checklist)} done")
    print(f"Open blockers: {len(open_blockers)}")
    print(f"Next step: {state.get('next_step') or 'Not recorded'}")
    commands = state.get("commands", [])
    if commands:
        latest = commands[-1]
        print(f"Latest command: {latest.get('command')} [{latest.get('status')}] {latest.get('notes', '')}".rstrip())
    print(f"Last updated: {state.get('last_updated')}")


def command_init(args: argparse.Namespace) -> int:
    root = Path(args.root)
    state_path, _ = handoff_paths(root)
    if state_path.exists():
        state = load_state(root)
        changed = False
        if args.goal and not state.get("goal"):
            state["goal"] = args.goal
            changed = True
        if args.mode and state.get("mode") != args.mode:
            state["mode"] = args.mode
            changed = True
        if changed:
            save_state(root, state)
        print(f"Handoff already exists: {state_path}")
        return 0
    state = default_state(root, goal=args.goal or "", mode=args.mode)
    if args.next_step:
        state["next_step"] = args.next_step
    save_state(root, state)
    print(f"Created {state_path}")
    return 0


def command_update(args: argparse.Namespace) -> int:
    root = Path(args.root)
    state = load_state(root)
    apply_update_payload(state, parse_update_args(args))
    save_state(root, state)
    print(f"Updated {handoff_paths(root)[0]}")
    return 0


def command_render(args: argparse.Namespace) -> int:
    root = Path(args.root)
    state = load_state(root)
    _, md_path = handoff_paths(root)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(state), encoding="utf-8")
    print(f"Rendered {md_path}")
    return 0


def command_validate(args: argparse.Namespace) -> int:
    state = load_state(Path(args.root))
    errors = validate_state(state)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Handoff state is valid")
    return 0


def command_status(args: argparse.Namespace) -> int:
    print_status(load_state(Path(args.root)))
    return 0


def command_check_threshold(args: argparse.Namespace) -> int:
    root = Path(args.root)
    state = load_state(root)
    state["thresholds"].update(calculate_thresholds())
    save_state(root, state)
    if state["thresholds"]["should_handoff"]:
        print("handoff recommended: " + "; ".join(state["thresholds"]["reasons"]))
        return 2
    print("handoff not required")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage portable agent handoff state")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init", help="Create handoff files if missing")
    init.add_argument("--root", default=".", help="Repository root")
    init.add_argument("--goal", default="", help="Global task goal")
    init.add_argument("--mode", default="normal", help="Work mode, for example normal or acaba")
    init.add_argument("--next-step", help="Immediate next step")
    init.set_defaults(func=command_init)

    update = subparsers.add_parser("update", help="Merge idempotent updates into state")
    update.add_argument("--root", default=".", help="Repository root")
    update.add_argument("--goal")
    update.add_argument("--mode")
    update.add_argument("--next-step")
    update.add_argument("--resume-instructions")
    update.add_argument("--dod", action="append", help="Append Definition of Done item")
    update.add_argument("--item", action="append", help="Checklist item as id:status:text")
    update.add_argument("--file", action="append", help="Touched file as path[:status[:notes]]")
    update.add_argument("--decision", action="append", help="Decision as id:summary:rationale")
    update.add_argument("--command", action="append", help="Command as id:command:status:notes")
    update.add_argument("--blocker", action="append", help="Blocker as id:status:summary:notes")
    update.add_argument("--assumption", action="append", help="Assumption as id:text")
    update.add_argument("--update-json", help="JSON object to merge")
    update.add_argument("--update-file", help="Path to JSON object to merge")
    update.set_defaults(func=command_update)

    render = subparsers.add_parser("render", help="Regenerate STATE.md from state.json")
    render.add_argument("--root", default=".", help="Repository root")
    render.set_defaults(func=command_render)

    status = subparsers.add_parser("status", help="Print compact resume summary")
    status.add_argument("--root", default=".", help="Repository root")
    status.set_defaults(func=command_status)

    validate = subparsers.add_parser("validate", help="Validate state schema and idempotency")
    validate.add_argument("--root", default=".", help="Repository root")
    validate.set_defaults(func=command_validate)

    threshold = subparsers.add_parser("check-threshold", help="Evaluate approximate handoff threshold signals")
    threshold.add_argument("--root", default=".", help="Repository root")
    threshold.set_defaults(func=command_check_threshold)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
