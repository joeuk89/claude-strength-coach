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


@dataclass(frozen=True)
class AvailableLoads:
    equipment: str
    mode: str
    kit: dict
    increment: float
    plates_win: bool = True

    @property
    def geometry_warning(self):
        if self.equipment == "smith_machine" and self.mode == "total" and "smith_base_weight" not in self.kit:
            return ("Smith load feasibility is unknown: set equipment.smith_base_weight (or the session's "
                    "location override) to the known effective unloaded mass in athlete units; "
                    "the ordinary bar_weight cannot supply it")
        return None

    @property
    def base_weight(self):
        if self.mode == "total":
            if self.equipment == "barbell":
                return self.kit["bar_weight"]
            if self.equipment == "smith_machine":
                return self.kit.get("smith_base_weight")
        return None

    @property
    def plate_built(self):
        return self.plates_win and self.base_weight is not None and bool(self.kit.get("plates"))

    def select(self, value, direction="nearest", cap=None):
        if self.geometry_warning:
            return value
        if self.equipment == "dumbbell" and self.mode in units.PER_HAND_MODES and self.kit.get("dumbbells"):
            return units.select_available(value, self.kit["dumbbells"], direction, cap)
        if self.plate_built:
            return units.round_plate_load(value, self.base_weight, self.kit["plates"], direction, cap)
        if self.increment:
            return units.round_grid_load(value, self.increment, direction, cap, self.base_weight or 0)
        return value

    def problem(self, value):
        if self.geometry_warning:
            return None
        selected = self.select(value)
        if selected is not None and abs(selected - value) < 1e-6:
            return None
        if self.plate_built:
            return f"no plate breakdown with base mass {units.json_number(self.base_weight)}"
        if self.equipment == "dumbbell" and self.kit.get("dumbbells"):
            return "no matching dumbbell in the declared rack"
        return f"not on the physical load grid (step {units.json_number(self.increment)})"
