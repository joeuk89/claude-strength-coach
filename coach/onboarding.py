"""Suggested config values for a new athlete (contract C44): what `/setup` writes unless the athlete says otherwise."""

UNITS = ("kg", "lb")
GYMS = ("commercial", "home")

_EQUIPMENT = {
    "kg": {
        "bar_weight": 20,
        "plates": [25, 20, 15, 10, 5, 2.5, 1.25],
        "barbell_increment": 2.5,
        "dumbbell_increment": {"commercial": 2, "home": 2.5},
        "dumbbell_max": {"commercial": 50},
        "machine_increment": 5,
        "cable_increment": 2.5,
    },
    "lb": {
        "bar_weight": 45,
        "plates": [45, 35, 25, 10, 5, 2.5],
        "barbell_increment": 5,
        "dumbbell_increment": 5,
        "dumbbell_max": {"commercial": 120},
        "machine_increment": 10,
        "cable_increment": 5,
    },
}

_SMALLEST_PLATE = {"kg": 1.25, "lb": 2.5}


def suggest(unit, gym="commercial"):
    if unit not in UNITS:
        raise ValueError(f"unit must be one of {', '.join(UNITS)}")
    if gym not in GYMS:
        raise ValueError(f"gym must be one of {', '.join(GYMS)}")
    equipment = {}
    for key, value in _EQUIPMENT[unit].items():
        if isinstance(value, dict):
            if gym not in value:
                continue
            value = value[gym]
        equipment[key] = list(value) if isinstance(value, list) else value
    return {
        "unit": unit,
        "gym": gym,
        "values": {"athlete": {"units": unit, "bodyweight_units": unit}, "equipment": equipment},
        "notes": _notes(unit, gym, equipment),
    }


def _notes(unit, gym, equipment):
    notes = []
    if "dumbbell_max" in equipment:
        notes.append({
            "key": "equipment.dumbbell_max",
            "message": f"Confirm the heaviest dumbbell the gym has; {equipment['dumbbell_max']} {unit} per hand "
                       "is a common top end, and prescriptions are capped there.",
        })
    else:
        notes.append({
            "key": "equipment.dumbbell_max",
            "message": f"Ask the heaviest dumbbell the athlete owns, per hand in {unit}: there is no default for "
                       "a home gym, and prescriptions are capped there.",
        })
    notes.append({
        "key": "equipment.dumbbell_increment",
        "message": f"Confirm the jump between the dumbbells, per hand; {equipment['dumbbell_increment']} {unit} is "
                   "only a guess, and with no dumbbells list every per-hand load is held to that step. If the "
                   "jumps vary, list the per-hand weights in dumbbells instead.",
    })
    notes.append({
        "key": "equipment.apparatus",
        "message": "Ask which of a flat bench, an incline bench, a pull-up bar, a dip station, somewhere to anchor "
                   "the heels for Nordic curls, and a sturdy box or step the place has; list them in apparatus. Once "
                   "available lists the kit, an unlisted one counts as missing.",
    })
    notes.append({
        "key": "equipment.plates",
        "message": f"Ask whether there are {_SMALLEST_PLATE[unit]} {unit} plates; leave that size out of plates "
                   "if not.",
    })
    if gym == "home":
        notes.append({
            "key": "equipment.bar_weight",
            "message": "Ask what bar and plates the athlete owns, if any; without a barbell, leave barbell out of "
                       "available and keep these values.",
        })
    notes.append({
        "key": "athlete.bodyweight_units",
        "message": "Ask only if the athlete weighs themselves in the other unit.",
    })
    return notes
