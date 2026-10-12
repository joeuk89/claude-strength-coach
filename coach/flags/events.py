"""Goal-event flag codes: heavy lower-body work in an agreed window, and an event with no window decision (contract C20, C55)."""

from coach.flags import register

OWNER = "R-47"

register("event_window_heavy_lower", owner=OWNER, severities=("warn",),
         summary="A heavy squat or hinge session falls inside a goal event's agreed window; review it with the "
                 "athlete.")
register("event_window_pending", owner=OWNER, severities=("info",),
         summary="An upcoming goal event has no agreed taper or review window; agree one or record none.")
