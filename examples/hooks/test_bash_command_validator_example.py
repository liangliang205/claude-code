#!/usr/bin/env python3
"""Regression tests for the example Bash PreToolUse hook (#105758).

Run from the repository root:

    python -m unittest discover -s examples/hooks -p 'test_*.py'
"""

import json
import pathlib
import subprocess
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bash_command_validator_example as validator  # noqa: E402

HOOK = pathlib.Path(__file__).resolve().parent / "bash_command_validator_example.py"


class LeadingBlanksTests(unittest.TestCase):
    """Bash ignores leading blanks, so the example's rules must not depend on them."""

    def test_prefixed_and_unprefixed_commands_agree(self):
        cases = [
            ("grep needle file.txt", 1),
            (" grep needle file.txt", 1),
            ("\tgrep needle file.txt", 1),
            ("  \t grep needle file.txt", 1),
            ('find . -name "*.py"', 1),
            (' find . -name "*.py"', 1),
            ('\tfind . -name "*.py"', 1),
            ("rg needle file.txt", 0),
            ("mygrep needle file.txt", 0),
            ("grep needle file.txt | head", 0),
            ("", 0),
        ]
        for command, expected in cases:
            with self.subTest(command=command):
                self.assertEqual(len(validator._validate_command(command)), expected)

    def test_hook_exit_codes(self):
        cases = [
            ("grep needle file.txt", 2),
            (" grep needle file.txt", 2),
            ("\tgrep needle file.txt", 2),
            (' find . -name "*.py"', 2),
            ("rg needle file.txt", 0),
        ]
        for command, expected_code in cases:
            with self.subTest(command=command):
                payload = json.dumps(
                    {"tool_name": "Bash", "tool_input": {"command": command}}
                )
                result = subprocess.run(
                    [sys.executable, str(HOOK)],
                    input=payload,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, expected_code, result.stderr)
                if expected_code == 2:
                    self.assertIn("rg", result.stderr)

    def test_non_bash_tool_is_ignored(self):
        payload = json.dumps(
            {"tool_name": "Read", "tool_input": {"command": "grep needle file.txt"}}
        )
        result = subprocess.run(
            [sys.executable, str(HOOK)],
            input=payload,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
