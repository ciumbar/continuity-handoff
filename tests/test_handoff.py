import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "continuity-handoff" / "scripts" / "handoff.py"


def run_handoff(*args, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class HandoffScriptTests(unittest.TestCase):
    def test_init_update_validate_status_and_render_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            init = run_handoff("init", "--root", tmp, "--goal", "Implement continuity")
            self.assertEqual(init.returncode, 0, init.stderr)

            update_args = [
                "update",
                "--root",
                tmp,
                "--dod",
                "Feature works",
                "--item",
                "tests:in_progress:Run verification",
                "--file",
                "src/example.ts:modified:Adjusted behavior",
                "--decision",
                "test-scope:Use focused tests first:Faster feedback",
                "--command",
                "pytest:pytest:passed:All green",
                "--blocker",
                "api-key:open:API key missing:Use placeholder",
                "--assumption",
                "creds:Credentials use env vars",
                "--next-step",
                "Finish documentation",
            ]
            self.assertEqual(run_handoff(*update_args).returncode, 0)

            update_args[update_args.index("tests:in_progress:Run verification")] = "tests:done:Run verification"
            update_args[update_args.index("api-key:open:API key missing:Use placeholder")] = (
                "api-key:resolved:API key missing:Use placeholder"
            )
            update_args[update_args.index("Finish documentation")] = "No further action required"
            self.assertEqual(run_handoff(*update_args).returncode, 0)

            validate = run_handoff("validate", "--root", tmp)
            self.assertEqual(validate.returncode, 0, validate.stderr)

            status = run_handoff("status", "--root", tmp)
            self.assertIn("Checklist: 1/1 done", status.stdout)
            self.assertIn("Open blockers: 0", status.stdout)

            render = run_handoff("render", "--root", tmp)
            self.assertEqual(render.returncode, 0, render.stderr)
            self.assertTrue((Path(tmp) / ".handoff" / "STATE.md").exists())

            state = json.loads((Path(tmp) / ".handoff" / "state.json").read_text())
            self.assertEqual(len(state["checklist"]), 1)
            self.assertEqual(len(state["files_touched"]), 1)
            self.assertEqual(len(state["decisions"]), 1)
            self.assertEqual(len(state["commands"]), 1)
            self.assertEqual(len(state["blockers"]), 1)
            self.assertEqual(len(state["assumptions"]), 1)
            self.assertEqual(len(state["definition_of_done"]), 1)

    def test_threshold_recommends_handoff_at_95_percent_or_above(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run_handoff("init", "--root", tmp).returncode, 0)
            normal = run_handoff("check-threshold", "--root", tmp)
            self.assertEqual(normal.returncode, 0, normal.stderr)

            high = run_handoff(
                "check-threshold",
                "--root",
                tmp,
                env={"HANDOFF_CONTEXT_USED_PCT": "96"},
            )
            self.assertEqual(high.returncode, 2)
            self.assertIn("handoff recommended", high.stdout)


if __name__ == "__main__":
    unittest.main()
