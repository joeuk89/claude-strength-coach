"""Whether an exercise fits the athlete: confirmed equipment, apparatus and ability, avoids and niggles (C45, C54).

Unknown is not confirmed. An apparatus the place's `apparatus` does not list
is missing, and an exercise that needs demonstrated ability fits only once
`[athlete] demonstrated_exercises` lists it, whatever the athlete's
experience. An empty `available` with no apparatus listed keeps its meaning
of every piece.
"""

from coach import config as config_module
from coach import niggles
from coach.library import APPARATUS_SERVES, DEMONSTRATED


class Kit:
    """The equipment and apparatus at one place, and the exercises the athlete has shown they can do."""

    def __init__(self, config, location=None, available=None):
        table = config_module.equipment_for(config, location)
        self.location = location
        self.available = list(table.get("available") or []) if available is None else list(available)
        listed = list(table.get("apparatus") or [])
        self.every_piece = not self.available and not listed
        self.apparatus = set(listed) | {served for piece in listed for served in APPARATUS_SERVES.get(piece, ())}
        self.demonstrated = set(config.athlete.get("demonstrated_exercises") or [])
        self.table = "[equipment]" if location is None else f"[equipment.locations.{location}]"

    def why_not(self, entry):
        """Why the place or the athlete cannot do this library entry, or None."""
        if self.available and entry["equipment"] not in self.available:
            return f"needs {entry['equipment']}, which {self.table} available does not list"
        if not self.every_piece:
            missing = [piece for piece in entry["requires"] if piece not in self.apparatus]
            if missing:
                return f"needs {', '.join(missing)}, which {self.table} apparatus does not list"
        if entry["ability"] == DEMONSTRATED and entry["id"] not in self.demonstrated:
            return "needs demonstrated ability, which [athlete] demonstrated_exercises does not list"
        return None


class Fit:
    """A Kit plus the athlete's avoid list and the niggles open on a day."""

    def __init__(self, library, kit, niggle_rows=(), day=None):
        self.library = library
        self.kit = kit
        self.open_niggles = [row for row in niggle_rows if day is not None
                             and niggles.status_on(row, day) not in (None, "resolved")]

    def why_not(self, entry, replacing=None):
        """Why `entry` cannot stand, or None.

        With `replacing`, `entry` is a substitute for that entry: an open niggle
        that covers it but not the line it replaces also rules it out, so a swap
        never brings in a movement the athlete is nursing.
        """
        avoid = self.library.avoided(entry["id"])
        if avoid:
            return f"marked avoid in the exercise library ({avoid['reason']})"
        reason = self.kit.why_not(entry)
        if reason or replacing is None:
            return reason
        for row in self.open_niggles:
            if niggles.matches(row, entry) and not niggles.matches(row, replacing):
                return f"niggle {row['id']} ({row['area']}) covers it"
        return None
