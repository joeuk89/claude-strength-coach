import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures"
INSTANCES = FIXTURES / "instances"
VALID = INSTANCES / "valid"


def run_cli(argv, env=None, commands=None):
    """Run coach.cli.main in-process; return (exit_code, envelope, stderr_text)."""
    from coach import cli

    stdout, stderr = io.StringIO(), io.StringIO()
    code = cli.main(list(argv), env=dict(env or {}), stdout=stdout, stderr=stderr, commands=commands)
    out = stdout.getvalue()
    envelope = json.loads(out) if out.strip() else None
    return code, envelope, stderr.getvalue()


def run_module(argv, cwd=REPO_ROOT, env=None):
    """Run `python -m coach` in a subprocess with the current interpreter."""
    import os

    full_env = {k: v for k, v in os.environ.items() if not k.startswith("COACH_")}
    full_env.update(env or {})
    proc = subprocess.run(
        [sys.executable, "-m", "coach", *argv],
        cwd=str(cwd),
        env=full_env,
        capture_output=True,
        text=True,
    )
    envelope = json.loads(proc.stdout) if proc.stdout.strip() else None
    return proc.returncode, envelope, proc.stderr


class TempInstance:
    def __init__(self, config_text=None):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        if config_text is not None:
            (self.root / "config.toml").write_text(config_text, encoding="utf-8")

    def __enter__(self):
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


MINIMAL_CONFIG = 'schema_version = 1\n\n[athlete]\nunits = "kg"\n'
