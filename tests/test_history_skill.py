"""The check-in skill calls the history and stats commands in the steps they replace (contract preamble, C17, C18)."""

import re
import unittest

from tests.support.skills import flat, skill_text, step_text


class CheckInSkillTest(unittest.TestCase):
    def setUp(self):
        self.text = skill_text("check-in")

    def test_names_each_command_in_its_step(self):
        pull = flat(step_text("check-in", "pull.md"))
        analyse = flat(step_text("check-in", "analyze.md"))
        self.assertIn("python3 -m coach history sync", pull)
        for command in ("stats e1rm", "stats adherence", "stats audit", "history annotate"):
            with self.subTest(command=command):
                self.assertIn(f"python3 -m coach {command}", analyse)

    def test_reads_e1rm_basis_and_unavailable_reasons(self):
        analyse = flat(step_text("check-in", "analyze.md"))
        self.assertIn("A KPI with `unavailable` quotes its message as the reason its newest exposure gave no e1RM",
                      analyse)
        self.assertIn('`total_system` point counts body mass: say "total system mass"', analyse)

    def test_profile_e1rms_carry_the_total_system_label(self):
        act = flat(step_text("check-in", "act.md"))
        self.assertIn('e1RMs (a `total_system` one with "total system mass" after its number) '
                      'in whole units as the card shows them', act)

    def test_ambiguous_cardio_rows_point_at_cardio_associate(self):
        analyse = flat(step_text("check-in", "analyze.md"))
        self.assertIn("`ambiguous` reconcile row", analyse)
        self.assertIn("`cardio associate ACTIVITY_ID --planned-id PLANNED_ID`", analyse)
        self.assertIn("A `duplicate` row was done, not missed.", analyse)

    def test_carries_no_e1rm_formula(self):
        self.assertIsNone(re.search(r"Epley|reps\s*/\s*30|1 \+ reps", self.text))


if __name__ == "__main__":
    unittest.main()
