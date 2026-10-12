"""Run git in a fixture repository without the developer's global or system config."""

import os
import subprocess
from pathlib import Path

# Commits and pushes otherwise start a detached `git maintenance` that can still be writing
# into .git when the test deletes its temporary directory. A global file, unlike
# GIT_CONFIG_COUNT, also reaches the receive-pack of a local bare remote.
GLOBAL_CONFIG = str(Path(__file__).with_name("fixture.gitconfig"))

ENV = {"GIT_CONFIG_GLOBAL": GLOBAL_CONFIG, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "Fixture",
       "GIT_AUTHOR_EMAIL": "fixture@example.invalid", "GIT_COMMITTER_NAME": "Fixture",
       "GIT_COMMITTER_EMAIL": "fixture@example.invalid"}


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
                   env=dict(os.environ, **ENV))
