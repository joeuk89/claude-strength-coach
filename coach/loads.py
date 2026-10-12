"""Physical kit interpretation shared by proposal generation and independent validation."""

from dataclasses import dataclass

from coach import config as config_module
from coach import stats, units


def available_loads(library, config, exercise_id, mode, location):
    """The loads one exercise can take at a location; raises ConfigError for a location config does not name."""
    entry = (library.get(exercise_id) if library is not None else None) or {}
    kit = config_module.equipment_for(config, location)
    declared = config_module.declared_equipment_for(config, location)
    increment = (stats.load_increment(library, config, exercise_id, location) or 0) if library is not None else 0
    plates_win = "plates" in declared or "barbell_increment" not in declared
    return AvailableLoads(entry.get("equipment"), mode, kit, increment, plates_win)


_BASE_MASS_KEYS = {"barbell": "bar_weight", "smith_machine": "smith_base_weight",
                   "ez_bar": "ez_bar_weight", "trap_bar": "trap_bar_weight"}
# Only bar_weight has a default, so these bars' masses are unknown until declared.
_UNDEFAULTED_BARS = {"smith_machine": "Smith", "ez_bar": "EZ-bar", "trap_bar": "Trap-bar"}


@dataclass(frozen=True)
class AvailableLoads:
    equipment: str
    mode: str
    kit: dict
    increment: float
    plates_win: bool = True

    @property
    def geometry_warning(self):
        if self.mode != "total" or self.equipment not in _UNDEFAULTED_BARS:
            return None
        key = _BASE_MASS_KEYS[self.equipment]
        if key in self.kit:
            return None
        return (f"{_UNDEFAULTED_BARS[self.equipment]} load feasibility is unknown: set equipment.{key} (or the "
                "session's location override) to the known effective unloaded mass in athlete units; "
                "the ordinary bar_weight cannot supply it")

    @property
    def base_weight(self):
        if self.mode == "total" and self.equipment in _BASE_MASS_KEYS:
            return self.kit.get(_BASE_MASS_KEYS[self.equipment])
        return None

    @property
    def rack(self):
        """The enumerated loads that replace any grid: the per-hand dumbbell rack or the declared kettlebells."""
        if self.equipment == "dumbbell" and self.mode in units.PER_HAND_MODES:
            return self.kit.get("dumbbells") or []
        if self.equipment == "kettlebell":
            return self.kit.get("kettlebells") or []
        return []

    @property
    def plate_built(self):
        return self.plates_win and self.base_weight is not None and bool(self.kit.get("plates"))

    def select(self, value, direction="nearest", cap=None):
        if self.geometry_warning:
            return value
        if self.rack:
            return units.select_available(value, self.rack, direction, cap)
        if self.equipment == "kettlebell":
            return value
        if self.plate_built:
            return units.round_plate_load(value, self.base_weight, self.kit["plates"], direction, cap)
        if self.increment:
            return units.round_grid_load(value, self.increment, direction, cap, self.base_weight or 0)
        return value

    def problem(self, value):
        if self.geometry_warning or (self.equipment == "kettlebell" and not self.rack):
            return None
        selected = self.select(value)
        if selected is not None and abs(selected - value) < 1e-6:
            return None
        if self.plate_built:
            return f"no plate breakdown with base mass {units.json_number(self.base_weight)}"
        if self.rack:
            declared = "rack" if self.equipment == "dumbbell" else "kettlebells"
            return f"no matching {self.equipment} in the declared {declared}"
        return f"not on the physical load grid (step {units.json_number(self.increment)})"
