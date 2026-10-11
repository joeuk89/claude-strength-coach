"""Run git in a fixture repository without the developer's global or system config."""

import os
import subprocess

ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fixture",
       "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture",
       "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
                   env=dict(os.environ, **ENV))
