"""What a command or a check sees: the root, the environment, config, now."""

from datetime import datetime, timezone
from pathlib import Path

from coach import config as config_module
from coach import dates
from coach.errors import ConfigError


class Context:
    def __init__(self, root, env, stderr):
        self.root = Path(root)
        self.env = env
        self.warnings = []
        self._stderr = stderr

    @property
    def stderr(self):
        return self._stderr

    @property
    def config(self):
        """The validated config; raises ConfigError (exit 5) when it is missing or invalid."""
        if not hasattr(self, "_config"):
            self._config = config_module.load(self.root, today=self.now())
        return self._config

    def warn(self, message):
        self.warnings.append(message)

    def log(self, message):
        for line in str(message).splitlines() or [""]:
            self._stderr.write(f"coach: {line}\n")

    def now(self):
        """An aware datetime: COACH_NOW when set, else the real time."""
        fixed = self.env.get("COACH_NOW")
        if fixed:
            try:
                return dates.parse_timestamp(fixed)
            except ValueError:
                raise ConfigError(f"COACH_NOW must be an ISO 8601 timestamp, found {fixed!r}") from None
        return datetime.now(timezone.utc)

    def timezone(self):
        """The athlete's zone from config, or None (system local time)."""
        try:
            name = self.config.athlete.timezone
        except ConfigError:
            return None
        return dates.zone(name) if name else None

    def today(self):
        return dates.today(self)
