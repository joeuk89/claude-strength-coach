"""Flag codes raised when a missed-day rule is applied or none applies (contract C20, C37)."""

from coach.flags import register

register("missed_day_rule", owner="R-22", severities=("info",),
         summary="A missed-day rule or the athlete's choice changed this line or session; the message names the "
                 "rule or the choice.")
register("missed_rule_unmatched", owner="R-22", severities=("info",),
         summary="No missed-day rule matched, or the chosen day cannot take the session; ask the athlete to "
                 "move it to a free day or drop it this week.")
