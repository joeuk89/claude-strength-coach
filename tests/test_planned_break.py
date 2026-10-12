"""Planned no-training breaks: status, the brief, catch-up tagging, block counting and return planning (C42, C50)."""

import copy
import unittest
from datetime import date

from coach import checkin, jsonio, migrate, research, statusdays, structure
from tests.support import REPO_ROOT, VALID
from tests.support.config_edit import set_key
from tests.support.history import read_json, write_json
from tests.support.skills import step_text
from tests.test_block import BlockCase, NEXT_SUNDAY
from tests.test_status import sections, text

BREAK = ("--kind", "travel", "--from", "2026-10-19", "--to", "2026-11-01", "--note", "Holiday, no gym")
MIDWEEK = "2026-10-21T09:00:00Z"
SUNDAY_BEFORE = "2026-10-18T09:00:00Z"
CLOSE_DAY = "2026-11-01T18:00:00Z"
PLAN_PROMPT = "plan it with /program-week"


class BreakCase(BlockCase):
    """The block fixture with three hard weeks through W41 and a fully trained W42, closed."""

    def setUp(self):
        super().setUp()
        self.init(3, through="2026-W41")
        self.train_week("2026-10-12")
        self.close("2026-W42", now=NEXT_SUNDAY)

    def add_break(self, *argv, now=NEXT_SUNDAY):
        return self.data("status-days", "add", *argv, now=now)["day"]

    def overlay_section(self, now=MIDWEEK):
        return sections(self.coach("status", now=now))["overlay"]

    def brief(self, now=MIDWEEK):
        self.data("pages", "render", now=now)
        return (self.root / "this-week.md").read_text(encoding="utf-8")

    def copy_workout(self, day, to):
        path = self.root / "data" / "history" / "2026-10.json"
        doc = read_json(path)
        workout = copy.deepcopy(next(w for w in doc["workouts"] if w["date"] == day))
        workout.update(workout_id=workout["workout_id"][:-3] + "900", date=to, start_time=f"{to}T18:00:00Z",
                       end_time=f"{to}T19:00:00Z")
        doc["workouts"].append(workout)
        write_json(path, doc)

    def write_record(self, day):
        path = self.root / "check-ins" / f"{day}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# Check-in — {day} (weekly)\n", encoding="utf-8")

    def catch_up(self, now=CLOSE_DAY):
        self.write_record("2026-10-18")
        return self.data("checkin", "prepare", now=now)["card"]["catch_up"]

    def write_overlay(self, overlay_id, kind, span, days):
        """An overlay over `span` whose sessions (A then B, alternating) fall on `days`."""
        doc = read_json(VALID / "data" / "overlays" / "2026-10-12-weekly.json")
        sessions = [dict(copy.deepcopy(doc["sessions"][n % 2]), date=day) for n, day in enumerate(days)]
        doc.update(id=overlay_id, kind=kind, created_at="2026-10-18T18:00:00Z", span=span, supersedes=None,
                   approval=None, flags=[], sessions=sessions, focus="Travel")
        write_json(self.root / "data" / "overlays" / f"{overlay_id}.json", doc)

    def write_one_off(self):
        """A one-off overlay over the break with one session on its first Monday, as a travel week is written."""
        self.write_overlay("2026-10-19-one-off", "one_off", {"start": "2026-10-19", "end": "2026-11-01"},
                           ["2026-10-19"])


class StatusTest(BreakCase):
    def test_a_covered_week_asks_for_no_programming(self):
        self.add_break(*BREAK, "--no-training")
        for now in (SUNDAY_BEFORE, MIDWEEK):
            with self.subTest(now=now):
                section = self.overlay_section(now)
                self.assertNotIn("/program-week", text(section))
                self.assertIn("Planned break s-0001 (travel: Holiday, no gym): no training Mon 2026-10-19 to "
                              "Sun 2026-11-01; training resumes Mon 2026-11-02.", section["lines"])
                self.assertEqual(section["level"], "info")
                self.assertEqual(section["data"]["uncovered"], [])

    def test_travel_without_the_intent_still_asks_for_the_week(self):
        self.add_break(*BREAK)
        section = self.overlay_section()
        self.assertIn(PLAN_PROMPT, text(section))
        self.assertEqual(section["data"]["uncovered"][0], "2026-10-21")
        self.assertEqual(section["level"], "attention")

    def test_a_partial_break_leaves_the_other_days_to_plan(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        section = self.overlay_section(SUNDAY_BEFORE)
        self.assertIn("No overlay covers 2026-10-21 to 2026-10-25 in the coming week; plan it with /program-week.",
                      section["lines"])

    def test_withdrawing_the_break_brings_the_prompt_back(self):
        self.add_break(*BREAK, "--no-training")
        self.data("status-days", "withdraw", "s-0001", "--reason", "trip cancelled", now=MIDWEEK)
        self.assertIn(PLAN_PROMPT, text(self.overlay_section()))

    def test_the_next_sessions_and_the_first_session_skip_break_days(self):
        self.add_break(*BREAK, "--no-training")
        self.write_overlay("2026-10-19-one-off", "one_off", {"start": "2026-10-19", "end": "2026-11-08"},
                           ["2026-10-19", "2026-11-02", "2026-11-05"])
        section = self.overlay_section(SUNDAY_BEFORE)
        self.assertEqual([(s["date"], s["title"]) for s in section["data"]["next_sessions"]],
                         [("2026-11-02", "Session B"), ("2026-11-05", "Session A")])
        self.assertIn("first session Session B on Mon 2026-11-02.", section["lines"][0])

    def test_a_break_week_with_nothing_planned_on_its_other_days_asks_for_no_programming(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-23", "--note", "Away",
                       "--no-training")
        section = self.overlay_section(SUNDAY_BEFORE)
        self.assertNotIn("/program-week", text(section))
        self.assertEqual((section["level"], section["data"]["uncovered"]), ("info", []))

    def test_ending_an_ongoing_break_brings_the_prompt_back_after_its_last_day(self):
        self.add_break("--kind", "injured", "--from", "2026-10-19", "--note", "Rest the calf", "--no-training")
        section = self.overlay_section()
        self.assertNotIn(PLAN_PROMPT, text(section))
        self.assertIn("until it is ended (status-days end s-0001)", text(section))
        self.data("status-days", "end", "s-0001", "--date", "2026-10-21", now=MIDWEEK)
        section = self.overlay_section()
        self.assertEqual(section["data"]["uncovered"], ["2026-10-22", "2026-10-23", "2026-10-24", "2026-10-25"])
        self.assertIn(PLAN_PROMPT, text(section))


class BriefTest(BreakCase):
    def test_the_brief_explains_the_break(self):
        self.add_break(*BREAK, "--no-training")
        page = self.brief()
        self.assertIn("Planned break Mon 19 Oct to Sun 1 Nov (Holiday, no gym): no training. Training resumes "
                      "Mon 2 Nov.", page)
        self.assertNotIn("No overlay covers", page)

    def test_a_partial_break_still_says_the_rest_needs_programming(self):
        self.add_break("--kind", "travel", "--from", "2026-10-26", "--to", "2026-10-27", "--note", "Away",
                       "--no-training")
        page = self.brief(now=SUNDAY_BEFORE.replace("10-18", "10-25"))
        self.assertIn("Planned break Mon 26 Oct to Tue 27 Oct (Away)", page)
        self.assertIn("No overlay covers the rest of this week yet", page)

    def test_with_an_overlay_the_focus_is_its_focus_then_the_break(self):
        self.add_break(*BREAK, "--no-training")
        self.write_one_off()
        page = self.brief()
        focus = page.index("Travel")
        self.assertLess(focus, page.index("Planned break Mon 19 Oct to Sun 1 Nov (Holiday, no gym)"))
        self.assertNotIn("No overlay covers", page)

    def test_a_break_week_with_nothing_planned_on_its_other_days_needs_no_overlay(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-23", "--note", "Away",
                       "--no-training")
        page = self.brief(now=SUNDAY_BEFORE)
        self.assertIn("Planned break Mon 19 Oct to Fri 23 Oct (Away): no training.", page)
        self.assertNotIn("No overlay covers", page)


class MissesTest(BreakCase):
    def misses_with_a_note_on_the_break(self, *argv):
        self.add_break(*BREAK, *argv)
        self.write_one_off()
        self.data("history", "annotate", "--kind", "miss", "--date", "2026-10-19", "--session", "session-a",
                  "--tag", "other", now=CLOSE_DAY)
        return checkin.misses(self.root, "2026-10-19", "2026-11-01", now=CLOSE_DAY)["sessions_missed"]

    def test_a_miss_note_on_a_break_day_is_not_a_miss(self):
        self.assertEqual(self.misses_with_a_note_on_the_break("--no-training"), 0)

    def test_without_the_intent_the_noted_session_is_one_miss(self):
        self.assertEqual(self.misses_with_a_note_on_the_break(), 1)


class CatchUpTest(BreakCase):
    def test_covered_sessions_need_no_tag(self):
        self.add_break(*BREAK, "--no-training")
        catch_up = self.catch_up()
        self.assertEqual(catch_up["missed"], [])
        self.assertEqual([(m["date"], m["break_id"]) for m in catch_up["on_break"]],
                         [("2026-10-19", "s-0001"), ("2026-10-22", "s-0001"), ("2026-10-26", "s-0001"),
                          ("2026-10-29", "s-0001")])
        self.assertEqual([(row["planned_core"], row["missed_by_tag"], row["on_break"]) for row in catch_up["summary"]],
                         [(0, {}, 2), (0, {}, 2)])
        gap = next(q for q in catch_up["questions"] if q["id"] == "gap")["ask"]
        self.assertTrue(gap.startswith("The planned break covers the remaining sessions not trained, so none needs a tag."))
        tagged = self.data("checkin", "tag-gap", "--tag", "other", now=CLOSE_DAY)
        self.assertEqual(tagged["annotations"], [])

    def test_travel_without_the_intent_still_asks_for_tags(self):
        self.add_break(*BREAK)
        catch_up = self.catch_up()
        self.assertEqual([m["tag"] for m in catch_up["missed"]], ["untagged"] * 4)
        self.assertEqual([row["on_break"] for row in catch_up["summary"]], [0, 0])
        gap = next(q for q in catch_up["questions"] if q["id"] == "gap")["ask"]
        self.assertTrue(gap.startswith("One tag for the whole gap"))

    def test_the_weekly_card_names_covered_sessions_and_skips_their_coach_led_session(self):
        self.write_overlay("2026-10-19-weekly", "weekly", {"start": "2026-10-19", "end": "2026-10-25"},
                           ["2026-10-19", "2026-10-22"])
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        self.write_record("2026-10-18")
        card = self.data("checkin", "prepare", now="2026-10-25T18:00:00Z")["card"]
        sessions = card["sessions"]
        self.assertEqual([(r["date"], r["status"], r["tag"]) for r in sessions["rows"]],
                         [("2026-10-22", "missed", "untagged")])
        self.assertEqual([(r["date"], r["break_id"]) for r in sessions["on_break"]], [("2026-10-19", "s-0001")])
        self.assertNotIn("2026-10-20", [e["date"] for e in sessions["external"]])
        field = next(f for f in card["fields"] if f["id"] == "sessions")
        self.assertIn("Planned break, so not misses: Mon 19 Oct Session A.", field["prefill"])

    def test_the_return_week_counts_the_real_days_off(self):
        self.add_break(*BREAK, "--no-training")
        week = self.catch_up()["return_week"]
        self.assertEqual((week["days_off"], week["band"]), (18, "11-21"))


class BlockCloseTest(BreakCase):
    def test_closing_both_covered_weeks_keeps_the_count_and_the_block(self):
        self.add_break(*BREAK, "--no-training")
        closed = self.close("2026-W44", now=CLOSE_DAY)
        self.assertEqual([(w["class"], w["planned"], w["on_break"], w["count_after"]) for w in closed["weeks"]],
                         [("break", 0, 3, 4), ("break", 0, 3, 4)])
        self.assertEqual(closed["ended"], [])
        self.assertTrue(closed["status_line"].startswith("Block 1 · 4 of 6 hard weeks"))
        again = self.close("2026-W44", now=CLOSE_DAY)
        self.assertTrue(again["replaced"])
        self.assertEqual([b["id"] for b in self.ledger()["blocks"]], ["b-0001"])
        self.assertEqual(self.state_block()["hard_weeks_completed"], 4)

    def test_the_same_break_counts_the_same_with_a_one_off_overlay(self):
        self.add_break(*BREAK, "--no-training")
        self.write_one_off()
        closed = self.close("2026-W44", now=CLOSE_DAY)
        self.assertEqual([(w["class"], w["count_after"]) for w in closed["weeks"]], [("break", 4), ("break", 4)])
        self.assertEqual(closed["ended"], [])

    def test_travel_without_the_intent_is_an_ordinary_low_week(self):
        self.add_break(*BREAK)
        closed = self.close("2026-W44", now=CLOSE_DAY)
        self.assertEqual([w["class"] for w in closed["weeks"]], ["low", "low"])
        self.assertEqual(closed["ended"], ["b-0001", "b-0002"])

    def test_a_partial_break_counts_only_the_sessions_left(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        self.copy_workout("2026-10-15", "2026-10-22")
        report = structure.week(self.root, "2026-10-19", today=date(2026, 10, 25))
        self.assertEqual((report["kind"], report["planned"], report["trained"]), ("ordinary", 1, 1))
        self.assertEqual([(r.get("session_id") or r.get("external_id"), r["date"]) for r in report["on_break"]],
                         [("session-a", "2026-10-19"), ("pt-tue", "2026-10-20")])
        closed = self.close("2026-W43", now="2026-10-25T18:00:00Z")
        self.assertEqual([(w["class"], w["planned"], w["on_break"], w["count_after"]) for w in closed["weeks"]],
                         [("hard", 1, 2, 5)])

    def test_a_one_off_overlay_over_only_the_break_days_leaves_a_partial_break_counted_as_usual(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        self.write_overlay("2026-10-19-one-off", "one_off", {"start": "2026-10-19", "end": "2026-10-20"},
                           ["2026-10-19"])
        self.copy_workout("2026-10-15", "2026-10-22")
        report = structure.week(self.root, "2026-10-19", today=date(2026, 10, 25))
        self.assertEqual((report["kind"], report["planned"], report["trained"]), ("ordinary", 1, 1))
        closed = self.close("2026-W43", now="2026-10-25T18:00:00Z")
        self.assertEqual([(w["class"], w["planned"], w["on_break"], w["count_after"]) for w in closed["weeks"]],
                         [("hard", 1, 2, 5)])

    def test_a_one_off_overlay_planning_the_days_left_still_pauses_a_partial_break(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        self.write_overlay("2026-10-19-one-off", "one_off", {"start": "2026-10-19", "end": "2026-10-25"},
                           ["2026-10-19", "2026-10-22"])
        self.copy_workout("2026-10-15", "2026-10-22")
        closed = self.close("2026-W43", now="2026-10-25T18:00:00Z")
        self.assertEqual([(w["class"], w["count_after"]) for w in closed["weeks"]], [("one_off", 4)])

    def test_a_partial_break_still_counts_a_missed_remaining_session(self):
        self.add_break("--kind", "travel", "--from", "2026-10-19", "--to", "2026-10-20", "--note", "Away",
                       "--no-training")
        closed = self.close("2026-W43", now="2026-10-25T18:00:00Z")
        self.assertEqual([(w["class"], w["planned"], w["trained"]) for w in closed["weeks"]], [("low", 1, 0)])

    def test_the_ledger_counts_only_core_and_coach_led_sessions_on_the_break(self):
        def optional_b(doc):
            next(s for s in doc["sessions"] if s["id"] == "session-b")["tier"] = "optional"

        self.edit("data/program.json", optional_b)
        self.add_break(*BREAK, "--no-training")
        closed = self.close("2026-W44", now=CLOSE_DAY)
        self.assertEqual([w["on_break"] for w in closed["weeks"]], [2, 2])

    def test_priority_rows_leave_out_sessions_on_the_break(self):
        def squat_priority(doc):
            doc["priority"] = [{"exercise_id": "bb_back_squat", "kpi": {"kind": "e1rm", "target": None, "by": None},
                                "floor": {"sets": 2, "rpe": None}}]

        self.edit("data/program.json", squat_priority)
        self.add_break(*BREAK, "--no-training")
        found = structure.priority(self.root, "2026-10-19", today=date(2026, 11, 1))
        self.assertEqual([(w["label"], w["planned"], w["missed"]) for w in found["lifts"][0]["weeks"]],
                         [("2026-W43", 0, 0), ("2026-W44", 0, 0)])
        self.assertEqual(found["flags"], [])

    def test_a_covered_week_skips_adherence_with_its_reason(self):
        self.add_break(*BREAK, "--no-training")
        skipped = self.data("structure", "adherence", now=CLOSE_DAY)["skipped"]
        self.assertEqual({s["label"]: s["kind"] for s in skipped}, {"2026-W43": "break", "2026-W44": "break"})

    def test_a_sunday_week_is_a_break_when_every_planned_session_is_covered(self):
        config = self.root / "config.toml"
        config.write_text(set_key(config.read_text(encoding="utf-8"), "athlete", "week_starts", "sunday"),
                          encoding="utf-8")
        self.add_break(*BREAK, "--no-training")
        today = date(2026, 11, 7)
        self.assertEqual(structure.week(self.root, "2026-10-18", today=today)["kind"], "break")
        self.assertEqual(structure.week(self.root, "2026-11-01", today=today)["kind"], "layoff")


class StatusDaysTest(BreakCase):
    def test_the_intent_is_recorded_on_the_row(self):
        row = self.add_break(*BREAK, "--no-training")
        self.assertTrue(row["no_training"])
        self.assertFalse(self.add_break("--kind", "travel", "--from", "2026-12-01", "--note", "Work")["no_training"])
        self.assertEqual([r["id"] for r in statusdays.breaks(self.root, statusdays.span_of(row))], ["s-0001"])

    def test_an_illness_is_never_a_planned_break(self):
        envelope = self.coach("status-days", "add", "--kind", "ill", "--from", "2026-10-19", "--note", "flu",
                              "--no-training", expect=1)
        self.assertIn("illness keeps its own return rule", envelope["error"]["message"])


class MigrationTest(BlockCase):
    def test_status_days_v1_rows_are_not_breaks(self):
        path = self.root / "data" / "status-days.json"
        write_json(path, {"schema_version": 1, "days": [
            {"id": "s-0001", "kind": "travel", "span": {"start": "2026-10-19", "end": "2026-11-01"}, "note": "Trip",
             "created_at": "2026-10-11T18:00:00Z", "source": "coach", "withdrawn": None}]})
        migrate.run(self.root, dry_run=False)
        doc = read_json(path)
        self.assertEqual((doc["schema_version"], doc["days"][0]["no_training"]), (2, False))

    def test_a_v1_ledger_gains_the_break_count(self):
        self.close()
        path = self.root / "data" / "blocks.json"
        doc = read_json(path)
        doc["schema_version"] = 1
        for week in doc["blocks"][0]["weeks"]:
            del week["on_break"]
        write_json(path, doc)
        migrate.run(self.root, dry_run=False)
        doc = read_json(path)
        self.assertEqual(doc["schema_version"], 2)
        self.assertEqual({week["on_break"] for week in doc["blocks"][0]["weeks"]}, {0})

    def test_the_schemas_carry_the_new_fields(self):
        self.assertIn("break", jsonio.load_schema("blocks")["$defs"]["week"]["properties"]["class"]["enum"])
        self.assertIn("no_training", jsonio.load_schema("status_days")["$defs"]["day"]["required"])


class EvidenceTest(unittest.TestCase):
    def test_the_pause_is_its_own_heuristic_claim(self):
        notes = research.load_notes(REPO_ROOT)
        claim = research.resolve("rn:deloads.13", notes)
        self.assertEqual((claim.basis, claim.sources), ("heuristic", ()))
        self.assertIn("planned no-training break", claim.text)
        self.assertNotIn("break", research.resolve("rn:deloads.2", notes).text)

    def test_the_skills_record_a_break_only_when_no_training_is_agreed(self):
        for skill, filename in (("check-in", "sunday-message.md"), ("program-week", "SKILL.md")):
            with self.subTest(skill=skill):
                words = " ".join(step_text(skill, filename).split())
                self.assertIn("--no-training", words)
                self.assertRegex(words, r"(Travel alone is not a break|Leave it off when they will train while away)")

    def test_claude_md_cites_the_pause_apart_from_the_reset(self):
        text = " ".join((REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8").split())
        self.assertIn("A week at 50–75 % neither counts nor resets (rn:deloads.2).", text)
        self.assertIn("planned no-training break week neither counts nor resets either (rn:deloads.13)", text)


if __name__ == "__main__":
    unittest.main()
