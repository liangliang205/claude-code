#!/usr/bin/env python3
"""Regression tests for the workflow hardening checker's settings handling (#106455).

Run from the repository root:

    python -m unittest discover -s .github/scripts -p 'test_*.py'
"""

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import check_workflow_hardening as checker  # noqa: E402

GENERATED = "settings-generated-at-runtime.json"
OLD_MODEL = "claude-3-5-sonnet-latest"
CURRENT_MODEL = "claude-sonnet-4-6"


def claude_step(*args, **inputs):
    with_block = {"claude_args": " ".join(args)}
    with_block.update(inputs)
    return {"name": "claude", "uses": "anthropics/claude-code-action@beta", "with": with_block}


class SettingsTextTests(unittest.TestCase):
    def test_inline_settings_passed_through(self):
        inline = json.dumps({"model": CURRENT_MODEL})
        self.assertEqual(checker.settings_text(inline), inline)

    def test_empty_settings(self):
        self.assertEqual(checker.settings_text(""), "")

    def test_path_outside_repository_is_unreadable(self):
        self.assertIsNone(checker.settings_text("/tmp/outside-the-repo/settings.json"))

    def test_runtime_generated_path_is_unreadable(self):
        # Before the fix this returned the path string. permission_mode_problem()
        # then treated the failed json.loads() as "no settings", so neither the
        # model check nor the defaultMode check ran.
        self.assertIsNone(checker.settings_text(GENERATED))

    def test_existing_in_repo_file_is_still_read(self):
        root = pathlib.Path.cwd().resolve()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", dir=root, delete=False, encoding="utf-8"
        ) as handle:
            json.dump({"model": OLD_MODEL}, handle)
            name = pathlib.Path(handle.name).name
        try:
            self.assertEqual(
                json.loads(checker.settings_text(name))["model"], OLD_MODEL
            )
        finally:
            (root / name).unlink(missing_ok=True)


class PermissionModeTests(unittest.TestCase):
    def test_generated_settings_file_is_rejected(self):
        step = claude_step(
            "--permission-mode auto", "--model", CURRENT_MODEL, "--settings", GENERATED
        )
        problem = checker.permission_mode_problem(step, False, {})
        self.assertIsNotNone(problem)
        self.assertIn("cannot read", problem)

    def test_generated_settings_file_fails_the_whole_job(self):
        step = claude_step(
            "--permission-mode auto", "--model", CURRENT_MODEL, "--settings", GENERATED
        )
        job = {"runs-on": checker.FIREWALL_RUNNER, "steps": [step]}
        with contextlib.redirect_stdout(io.StringIO()):
            errors = checker.check_job("synthetic.yml", "synthetic", job, {})
        self.assertTrue(any("cannot read" in error for error in errors), errors)

    def test_clean_step_still_passes(self):
        step = claude_step("--permission-mode auto", "--model", CURRENT_MODEL)
        self.assertIsNone(checker.permission_mode_problem(step, False, {}))

    def test_inline_old_model_still_rejected(self):
        step = claude_step(
            "--permission-mode auto", settings=json.dumps({"model": OLD_MODEL})
        )
        problem = checker.permission_mode_problem(step, False, {})
        self.assertIsNotNone(problem)
        self.assertIn("auto mode", problem)

    def test_inline_default_mode_still_rejected(self):
        step = claude_step(
            "--permission-mode auto",
            settings=json.dumps({"permissions": {"defaultMode": "default"}}),
        )
        problem = checker.permission_mode_problem(step, False, {})
        self.assertIsNotNone(problem)
        self.assertIn("defaultMode", problem)


if __name__ == "__main__":
    unittest.main()
