"""Physical kit interpretation shared by proposal generation and independent validation."""

from dataclasses import dataclass

from coach import units


@dataclass(frozen=True)
class AvailableLoads:
    equipment: str
    mode: str
    kit: dict
    increment: float

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

    def select(self, value, direction="nearest", cap=None):
        if self.geometry_warning:
            return value
        if self.equipment == "dumbbell" and self.mode in units.PER_HAND_MODES and self.kit.get("dumbbells"):
            return units.select_available(value, self.kit["dumbbells"], direction, cap)
        if self.base_weight is not None and self.kit.get("plates"):
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
        if self.base_weight is not None and self.kit.get("plates"):
            return f"no plate breakdown with base mass {units.json_number(self.base_weight)}"
        if self.equipment == "dumbbell" and self.kit.get("dumbbells"):
            return "no matching dumbbell in the declared rack"
        return f"not on the physical load grid (step {units.json_number(self.increment)})"
