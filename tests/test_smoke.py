"""Smoke tests for dotenv-diff. Run with: python3 -m unittest tests.test_smoke -v"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

CLI = Path(__file__).resolve().parent.parent / "dotenv_diff.py"


def run_cli(*args, stdin=None):
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        input=stdin, capture_output=True, text=True,
    )


class TempFixture:
    """Context manager creating temp .env / .env.example files (FAKE_ values only)."""

    def __init__(self, env_text, example_text):
        self.env_text = env_text
        self.example_text = example_text

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        env_path = base / ".env"
        example_path = base / ".env.example"
        env_path.write_text(self.env_text)
        example_path.write_text(self.example_text)
        return str(env_path), str(example_path)

    def __exit__(self, *exc):
        self.tmp.cleanup()


EXAMPLE = """\
# Example environment
DATABASE_URL=postgres://localhost:5432/fakeapp
STRIPE_WEBHOOK_SECRET=whsec_example
REDIS_URL=redis://localhost:6379/0
DEBUG=false
"""

CLEAN_ENV = """\
DATABASE_URL=postgres://localhost:5432/fakeapp
STRIPE_WEBHOOK_SECRET=whsec_FAKE_abc123
REDIS_URL=redis://localhost:6379/0
DEBUG=false
"""


class TestDotenvDiff(unittest.TestCase):
    def test_missing_key_exits_1(self):
        env = "DATABASE_URL=postgres://localhost/fake\nDEBUG=false\n"
        with TempFixture(env, EXAMPLE) as (env_p, ex_p):
            proc = run_cli(env_p, ex_p)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("missing", proc.stdout)
        self.assertIn("STRIPE_WEBHOOK_SECRET", proc.stdout)

    def test_clean_exits_0(self):
        with TempFixture(CLEAN_ENV, EXAMPLE) as (env_p, ex_p):
            proc = run_cli(env_p, ex_p)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("clean", proc.stdout)

    def test_extra_and_empty_warnings(self):
        env = CLEAN_ENV + "LEGACY_FAKE_KEY=yes\nDEBUG2_UNUSED=x\nEMPTY_FAKE=\n"
        example = EXAMPLE + "DEBUG2_UNUSED=x\nEMPTY_FAKE=\n"
        with TempFixture(env, example) as (env_p, ex_p):
            proc = run_cli(env_p, ex_p)
        self.assertEqual(proc.returncode, 0)  # warnings only -> exit 0
        self.assertIn("extra", proc.stdout)
        self.assertIn("LEGACY_FAKE_KEY", proc.stdout)
        self.assertIn("empty", proc.stdout)
        self.assertIn("EMPTY_FAKE", proc.stdout)

    def test_placeholder_warning(self):
        env = CLEAN_ENV.replace("whsec_FAKE_abc123", "your-stripe-secret-here")
        with TempFixture(env, EXAMPLE) as (env_p, ex_p):
            proc = run_cli(env_p, ex_p)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("placeholder", proc.stdout)
        self.assertIn("STRIPE_WEBHOOK_SECRET", proc.stdout)

    def test_strict_exits_1_on_warnings(self):
        env = CLEAN_ENV + "LEGACY_FAKE_KEY=yes\n"
        with TempFixture(env, EXAMPLE) as (env_p, ex_p):
            normal = run_cli(env_p, ex_p)
            strict = run_cli("--strict", env_p, ex_p)
        self.assertEqual(normal.returncode, 0)
        self.assertEqual(strict.returncode, 1)

    def test_quoted_values_and_export_prefix(self):
        env = """\
export DATABASE_URL="postgres://localhost:5432/fake app"
STRIPE_WEBHOOK_SECRET='whsec_FAKE_abc123'
REDIS_URL=redis://localhost:6379/0
export DEBUG=false
"""
        with TempFixture(env, EXAMPLE) as (env_p, ex_p):
            proc = run_cli(env_p, ex_p)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_json_output_is_valid(self):
        env = "DATABASE_URL=postgres://localhost/fake\n"
        with TempFixture(env, EXAMPLE) as (env_p, ex_p):
            proc = run_cli("--json", env_p, ex_p)
        self.assertEqual(proc.returncode, 1)
        findings = json.loads(proc.stdout)
        codes = {(f["code"], f["level"]) for f in findings}
        self.assertIn(("missing", "error"), codes)

    def test_stdin_dash(self):
        env = "DATABASE_URL=postgres://localhost/fake\nDEBUG=false\n"
        with TempFixture("", EXAMPLE) as (_, ex_p):
            proc = run_cli("-", ex_p, stdin=env)
        self.assertEqual(proc.returncode, 1)  # missing keys via stdin
        self.assertIn("STRIPE_WEBHOOK_SECRET", proc.stdout)


if __name__ == "__main__":
    unittest.main()
