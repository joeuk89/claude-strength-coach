"""Exit codes and the exceptions that carry them (contract C3)."""

from enum import IntEnum


class ExitCode(IntEnum):
    OK = 0
    VALIDATION = 1
    USAGE = 2
    REFUSED = 3
    NETWORK = 4
    CONFIG = 5
    INTERNAL = 9


ERROR_CODES = {
    ExitCode.VALIDATION: "validation",
    ExitCode.USAGE: "usage",
    ExitCode.REFUSED: "refused",
    ExitCode.NETWORK: "network",
    ExitCode.CONFIG: "config",
    ExitCode.INTERNAL: "internal",
}


class CoachError(Exception):
    """An expected failure: its message is one plain sentence for the envelope.

    `details` is a list of {"path": ..., "message": ...} dicts. `data`, when
    set, is a report the envelope keeps next to the error (`coach check`).
    """

    exit_code = ExitCode.INTERNAL

    def __init__(self, message, details=None, data=None):
        super().__init__(message)
        self.message = message
        self.details = list(details or [])
        self.data = data

    @property
    def code(self):
        return ERROR_CODES[self.exit_code]


class ValidationError(CoachError):
    exit_code = ExitCode.VALIDATION


class UsageError(CoachError):
    exit_code = ExitCode.USAGE


class RefusedError(CoachError):
    exit_code = ExitCode.REFUSED


class NetworkError(CoachError):
    exit_code = ExitCode.NETWORK


class ConfigError(CoachError):
    exit_code = ExitCode.CONFIG
