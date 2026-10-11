"""Finding the Hevy API key: the environment first, then `.env` at the instance root."""

from coach import paths

KEY_NAME = "HEVY_API_KEY"


def _from_dotenv(root):
    path = root / paths.ENV_FILE
    if not path.is_file():
        return None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("export "):
            line = line[len("export "):].strip()
        name, sep, value = line.partition("=")
        if sep and name.strip() == KEY_NAME:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value
    return None


def api_key(root, env):
    """The key, or None when neither the environment nor `.env` has a non-empty one."""
    for value in (env.get(KEY_NAME), _from_dotenv(root)):
        if value and value.strip():
            return value.strip()
    return None
