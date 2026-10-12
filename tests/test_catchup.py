"""Catch-up mode, `checkin tag-gap` and `checkin return-brief` (contract C36, C22, C24)."""

import json
import unittest
from unittest import mock

from coach import checkin, checkin_parts, jsonio, validity
from coach.checkin_parts import nutrition as nutrition_part
from tests.support import FIXTURES, INSTANCES, REPO_ROOT
from tests.support.config_edit import apply
from tests.support.history import HistoryCase, read_json, write_json
from tests.support.skills import skill_text

GAP = INSTANCES / "gap"
CHECKIN = INSTANCES / "checkin"
NOHEVY = INSTANCES / "nohevy"
WEEKS = ["2026-W38", "2026-W39", "2026-W40", "2026-W41"]
WRITE_LINE = 'Reply "go" to train this and write: Session A, Session B (Hevy).'
REPLY_OK = "Reply ok to accept all of this, or answer any of 1–4."
PLAN_ASK = "Anything in the plan that didn't work?"
NEXT_WEEK_FOOD = "food exceptions next week"
MISSED_CORE = ["2026-09-17", "2026-09-21", "2026-09-24", "2026-09-28", "2026-10-01", "2026-10-05", "2026-10-08"]
ALTERNATING = {
    "rule": "alternating_external_anchor",
    "params": {"weeks": [{"name": "week-a", "days": {"mon": "session-a", "thu": "session-b"}},
                         {"name": "week-b", "days": {"mon": "session-b", "thu": "session-a"}}],
               "anchor_external_id": "pt-tue"},
}


class GapCase(HistoryCase):
    base = GAP

    def prepare(self, *argv, expect=0, env=None):
        return self.coach("checkin", "prepare", *argv, expect=expect, env=env)

    def card(self, *argv, env=None):
        return self.prepare(*argv, env=env)["data"]["card"]

    def at(self, day):
        return {"COACH_NOW": f"{day}T18:00:00Z"}

    def replace_records(self, records):
        for path in (self.root / "check-ins").glob("*.md"):
            path.unlink()
        for day, tier in records:
            (self.root / "check-ins" / f"{day}.md").write_text(f"# Check-in — {day} ({tier})\n\nSynthetic.\n",
                                                               encoding="utf-8")

    def alternate(self, position="week-a", week="2026-09-14", confirmed=True):
        self.edit_json("data/program.json", lambda doc: doc.update(schedule=ALTERNATING))
        self.edit_json("data/state.json", lambda doc: doc.update(rotation={
            "position": position, "confirmed": confirmed, "confirmed_at": "2026-09-13", "week": week}))


class CatchUpCardTest(GapCase):
    def test_a_28_day_gap_is_catch_up_with_a_weekly_summary_and_four_questions(self):
        card = self.card()
        self.assertEqual((card["mode"], card["days_since_last"], card["fields"]), ("catch_up", 28, []))
        catch_up = card["catch_up"]
        self.assertEqual(catch_up["layoff_days"], 28)
        summary = catch_up["summary"]
        self.assertEqual([row["week"] for row in summary], WEEKS)
        self.assertEqual({row["planned_from"] for row in summary}, {"schedule"})
        self.assertEqual([(row["planned_core"], row["trained_core"]) for row in summary],
                         [(2, 1), (2, 0), (2, 0), (2, 0)])
        self.assertEqual(summary[0]["missed_by_tag"], {"untagged": 1})
        self.assertEqual([row["workouts"] for row in summary], [1, 0, 0, 0])
        self.assertEqual([q["id"] for q in catch_up["questions"]], ["gap", "now", "nutrition", "next_week"])
        self.assertEqual([q["n"] for q in catch_up["questions"]], [1, 2, 3, 4])
        self.assertEqual([q["label"] for q in catch_up["questions"]], ["The gap", "Now", "Food", "Next week"])
        gap = catch_up["questions"][0]["ask"]
        self.assertIn("time / sleep / ill / family / skipped / other", gap)
        self.assertIn(f"{validity.SYMPTOM_FREE_HOURS} hours symptom-free", gap)

    def test_the_return_week_is_proposed_and_summarised(self):
        envelope = self.prepare()
        card, text = envelope["data"]["card"], envelope["data"]["text"]
        week = card["catch_up"]["return_week"]
        self.assertEqual((week["band"], week["days_off"], week["load_factor"], week["set_delta"], week["rpe_cap"]),
                         ("22-42", 28, 0.9, -1, None))
        self.assertEqual((week["week"], week["overlay_id"]), ("2026-W42", "2026-10-12-weekly"))
        first = week["sessions"][0]
        self.assertEqual((first["date"], first["title"]), ("2026-10-12", "Session A"))
        squat = next(line for line in first["lines"] if line.startswith("Back Squat"))
        self.assertIn("2×5 @ 90", squat)
        self.assertTrue(week["lines_digest"].startswith("sha256:"))
        self.assertIn("return_week", [f["code"] for f in week["flags"]])
        self.assertEqual(card["catch_up"]["write_line"], WRITE_LINE)
        self.assertIn("2×5 @ 90", text)
        self.assertIn("22-42", text)
        self.assertTrue(text.rstrip("\n").endswith(WRITE_LINE + "\n" + REPLY_OK), text)
        self.assertNotIn("catch_up_pending", " ".join(envelope["warnings"]))

    def test_ok_then_the_real_proposal_gives_the_same_digest(self):
        digest = self.card()["catch_up"]["return_week"]["lines_digest"]
        before = set((self.root / ".coach").rglob("*.json")) if (self.root / ".coach").exists() else set()
        self.assertEqual(before, set())
        proposed = self.coach("propose", "week", "--week", "2026-W42")["data"]
        self.assertEqual(jsonio.canonical_hash(proposed["lines"]), digest)
        self.assertEqual(proposed["lines_digest"], digest)

    def test_the_text_has_the_summary_table_and_the_numbered_questions(self):
        text = self.prepare()["data"]["text"]
        self.assertIn("catch_up", text.splitlines()[0])
        self.assertIn("| 14 Sep | 1 of 2 |", text)
        for n in (1, 2, 3, 4):
            self.assertIn(f"\n{n}. ", text)

    def test_ten_days_is_weekly_and_eleven_is_catch_up(self):
        self.assertEqual(self.card(env=self.at("2026-09-23"))["mode"], "weekly")
        self.assertEqual(self.card(env=self.at("2026-09-24"))["mode"], "catch_up")
        self.assertEqual(self.coach("checkin", "due", env=self.at("2026-09-23"))["data"]["mode"], "weekly")
        self.assertEqual(self.coach("checkin", "due", env=self.at("2026-09-24"))["data"]["mode"], "catch_up")

    def test_tier_weekly_still_overrides(self):
        card = self.card("--tier", "weekly")
        self.assertEqual((card["mode"], card["catch_up"]), ("weekly", None))
        self.assertTrue(card["fields"])

    def test_parts_add_no_fields_in_catch_up(self):
        self.assertEqual(self.card()["fields"], [])

    def test_sunday_weeks(self):
        path = self.root / "config.toml"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace('week_starts = "monday"', 'week_starts = "sunday"'), encoding="utf-8")
        summary = self.card()["catch_up"]["summary"]
        self.assertEqual([row["week"] for row in summary], WEEKS + ["2026-W42"])
        self.assertEqual(summary[-1]["planned_core"], 0)


class OverlayPlannedTest(GapCase):
    base = CHECKIN

    def test_weeks_with_an_overlay_in_force_plan_from_it(self):
        card = self.card(env=self.at("2026-10-20"))
        self.assertEqual(card["mode"], "catch_up")
        summary = card["catch_up"]["summary"]
        self.assertEqual([row["week"] for row in summary], ["2026-W41", "2026-W42", "2026-W43"])
        first, second = summary[0], summary[1]
        self.assertEqual((first["planned_from"], first["planned_core"], first["trained_core"]), ("overlay", 3, 2))
        self.assertEqual(first["missed_by_tag"], {"untagged": 1})
        self.assertEqual((second["planned_from"], second["planned_core"], second["trained_core"]), ("overlay", 2, 0))
        self.assertEqual(summary[2]["planned_from"], "schedule")


class TagGapTest(GapCase):
    def test_one_tag_for_the_gap_writes_one_miss_per_missed_core_session(self):
        data = self.coach("checkin", "tag-gap", "--tag", "ill")["data"]
        self.assertTrue(data["written"])
        self.assertEqual([(a["date"], a["tag"]) for a in data["annotations"]], [(d, "ill") for d in MISSED_CORE])
        stored = read_json(self.root / "data" / "history" / "annotations.json")["annotations"]
        misses = [a for a in stored if a["kind"] == "miss"]
        self.assertEqual([a["date"] for a in misses], MISSED_CORE)
        self.assertTrue(all(a["session_id"] in ("session-a", "session-b") for a in misses))
        self.assertEqual(self.coach("checkin", "tag-gap", "--tag", "ill")["data"]["annotations"], [])

    def test_the_next_card_carries_the_illness_rule(self):
        self.coach("checkin", "tag-gap", "--tag", "ill")
        card = self.card()
        summary = card["catch_up"]["summary"]
        self.assertEqual(summary[0]["missed_by_tag"], {"ill": 1})
        week = card["catch_up"]["return_week"]
        self.assertIn("return_after_illness", [f["code"] for f in week["flags"]])
        first, later = week["sessions"]
        self.assertEqual((first["rpe_cap"], later["rpe_cap"]), (validity.ILLNESS_RPE_CAP, None))

    def test_dry_run_writes_nothing(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        data = self.coach("checkin", "tag-gap", "--tag", "time", "--dry-run")["data"]
        self.assertEqual(len(data["annotations"]), len(MISSED_CORE))
        self.assertFalse(data["written"])
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_an_unknown_tag_is_refused(self):
        self.coach("checkin", "tag-gap", "--tag", "holiday", expect=2)


class ReturnBriefTest(GapCase):
    def setUp(self):
        super().setUp()
        self.proposal = self.coach("propose", "week")["data"]["id"]

    def brief(self, *argv, expect=0):
        return self.coach("checkin", "return-brief", *argv, expect=expect)

    def one_off(self):
        draft = read_json(FIXTURES / "overlay" / "draft-kg.json")
        draft["kind"] = "one_off"
        write_json(self.tmp / "one-off.json", draft)
        return self.coach("overlay", "build", "--input", str(self.tmp / "one-off.json"))["data"]["id"]

    def test_illness_brief_has_the_safety_lines_band_and_write_line(self):
        self.coach("checkin", "tag-gap", "--tag", "ill")
        proposal = self.coach("propose", "week")["data"]["id"]
        data = self.brief("--proposal", proposal, "--reason", "ill")["data"]
        text = data["text"]
        for words in ("48 hours", "caps every set at RPE 7", "Session A (RPE cap 7)", "qualified professional",
                      "This is a return week: return band 22-42 after 28 days off", WRITE_LINE):
            with self.subTest(words=words):
                self.assertIn(words, text)
        self.assertIn("2×5 @ 90", text)
        self.assertEqual(data["warnings"], [])
        self.assertTrue(text.rstrip("\n").endswith(WRITE_LINE), text)

    def test_an_uncapped_ill_proposal_does_not_claim_the_cap(self):
        data = self.brief("--proposal", self.proposal, "--reason", "ill")["data"]
        self.assertNotIn("(RPE cap 7)", data["text"])
        self.assertNotIn("caps every set", data["text"])
        self.assertIn("48 hours", data["text"])
        self.assertEqual(len(data["warnings"]), 1)
        self.assertIn("checkin tag-gap --tag ill", data["warnings"][0])
        self.assertIn("propose the week again", data["warnings"][0])

    def test_travel_from_a_one_off_overlay_has_no_illness_lines(self):
        text = self.brief("--overlay", self.one_off(), "--reason", "travel")["data"]["text"]
        for words in ("48 hours", "qualified professional"):
            with self.subTest(words=words):
                self.assertNotIn(words, text)
        self.assertIn("travel", text)
        self.assertTrue(text.rstrip("\n").endswith(WRITE_LINE), text)

    def test_a_one_off_overlay_at_full_loads_does_not_claim_the_band(self):
        envelope = self.brief("--overlay", self.one_off(), "--reason", "travel")
        text = envelope["data"]["text"]
        self.assertIn("3×5 @ 100", text)
        self.assertNotIn("This is a return week", text)
        self.assertNotIn("so loads −10 %", text)
        self.assertIn("28 days off puts this in return band 22-42, whose guideline is loads −10 %", text)
        warning = envelope["data"]["warnings"][0]
        self.assertIn("Back Squat (Barbell)", warning)
        self.assertIn("rebuild the overlay", warning)
        self.assertNotIn("propose the week again", warning)
        self.assertEqual(envelope["warnings"], envelope["data"]["warnings"])

    def test_an_uncapped_ill_overlay_asks_for_a_rebuild(self):
        warnings = self.brief("--overlay", self.one_off(), "--reason", "ill")["data"]["warnings"]
        self.assertIn("RPE 7 or below (overlay build)", warnings[-1])

    def test_the_brief_writes_nothing(self):
        before = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.brief("--proposal", self.proposal, "--reason", "layoff")
        after = {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(after, before)

    def test_one_source_only(self):
        self.brief("--reason", "ill", expect=2)
        self.brief("--proposal", self.proposal, "--overlay", "2026-10-12-weekly", "--reason", "ill", expect=2)


class DeepDeferralTest(GapCase):
    def test_a_due_deep_review_is_deferred_to_the_next_check_in(self):
        self.replace_records([("2026-08-22", "deep"), ("2026-09-13", "weekly")])
        card = self.card()
        self.assertEqual((card["mode"], card["deep_deferred"], card["misses"]), ("catch_up", True, None))
        record = self.coach("checkin", "skeleton", "--date", "2026-10-11")["data"]
        self.assertEqual(record["tier"], "catch-up")
        self.assertTrue((self.root / "check-ins" / "2026-10-11.md").read_text(encoding="utf-8").startswith(
            "# Check-in — 2026-10-11 (catch-up)\n"))
        later = self.card(env=self.at("2026-10-18"))
        self.assertEqual(later["mode"], "deep")
        self.assertIn("deferred from catch-up 2026-10-11", later["tier_reasons"])
        self.assertEqual(self.coach("checkin", "due", env=self.at("2026-10-18"))["data"]["mode"], "deep")

    def test_a_catch_up_with_no_deep_due_defers_nothing(self):
        card = self.card()
        self.assertFalse(card["deep_deferred"])
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        later = self.card(env=self.at("2026-10-17"))
        self.assertEqual((later["mode"], later["tier_reasons"]), ("weekly", []))

    def test_the_catch_up_record_region_holds_the_summary_and_stays_fresh(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-11")
        text = (self.root / "check-ins" / "2026-10-11.md").read_text(encoding="utf-8")
        self.assertIn("| 14 Sep | 1 of 2 |", text)
        self.assertEqual(checkin.render_week_review(self.root, "2026-10-11") in text, True)
        results = self.coach("check", "--only", "render_fresh_sweep,checkin_records")["data"]["results"]
        self.assertEqual({r["status"] for r in results} - {"skip"}, {"pass"}, results)


class RotationTest(GapCase):
    def test_the_coach_led_field_states_the_schedule_plan_position(self):
        self.alternate()
        card = self.card("--tier", "weekly")
        coach_led = next(f for f in card["fields"] if f["id"] == "coach_led")
        self.assertIn("next week is week-a", coach_led["prefill"])
        self.assertIn("not confirmed", coach_led["prefill"])
        planned = self.coach("schedule", "plan")["data"]["rotation"]
        self.assertEqual((planned["position"], planned["confirmed"]), ("week-a", False))

    def test_a_confirmed_position_says_so(self):
        self.alternate()
        self.coach("schedule", "confirm", "--position", "week-b")
        coach_led = next(f for f in self.card("--tier", "weekly")["fields"] if f["id"] == "coach_led")
        self.assertIn("next week is week-b (confirmed)", coach_led["prefill"])

    def test_the_catch_up_card_states_it_in_the_next_week_question(self):
        self.alternate()
        question = next(q for q in self.card()["catch_up"]["questions"] if q["id"] == "next_week")["ask"]
        self.assertIn("next week is week-a", question)


class CatchUpFoodTest(HistoryCase):
    """`nohevy/` with MacroFactor on, last reviewed Sunday 11 October, prepared on Sunday 25 October."""

    base = NOHEVY

    def setUp(self):
        super().setUp()
        self.env = {"COACH_NOW": "2026-10-25T18:00:00Z"}

    def configure(self, values):
        path = self.root / "config.toml"
        path.write_text(apply(path.read_text(encoding="utf-8"), values), encoding="utf-8")

    def prepared(self, *argv):
        return self.coach("checkin", "prepare", *argv)["data"]

    def food(self, card):
        return next((q for q in card["catch_up"]["questions"] if q["id"] == "nutrition"), None)

    def test_macrofactor_food_comes_from_nutrition_status_alongside_the_three_questions(self):
        data = self.prepared()
        card = data["card"]
        self.assertEqual((card["mode"], card["days_since_last"], card["schema_version"]), ("catch_up", 14, 6))
        questions = card["catch_up"]["questions"]
        self.assertEqual([q["id"] for q in questions], ["gap", "now", "nutrition", "next_week"])
        self.assertEqual([q["n"] for q in questions], [1, 2, 3, 4])
        food = self.food(card)
        self.assertEqual(food["label"], "Food")
        asked = self.coach("nutrition", "status")["data"]["questions"]
        self.assertEqual(food["ask"].splitlines(), [f"{letter}. {ask}" for letter, ask in zip("abc", asked)])
        for ask in asked:
            self.assertEqual(data["text"].count(ask), 1, ask)
        self.assertIn("7-day average (kcal/protein)", food["ask"])
        self.assertIn(NEXT_WEEK_FOOD, food["ask"])
        self.assertNotIn(PLAN_ASK, data["text"])

    def test_the_seven_day_readings_name_the_days_they_cover_not_the_whole_gap(self):
        food = self.food(self.prepared()["card"])
        self.assertEqual(food["prefill"],
                         "Readings for the last 7 days (Mon 19 Oct – Sun 25 Oct) only, not the whole gap since "
                         "Mon 12 Oct.")
        self.assertNotIn("14-day", food["ask"])

    def test_the_food_prefill_sits_on_its_own_line_above_the_lettered_asks(self):
        lines = self.prepared()["text"].splitlines()
        at = lines.index("3. Food.")
        self.assertEqual(lines[at + 1], "   Readings for the last 7 days (Mon 19 Oct – Sun 25 Oct) only, not the "
                                        "whole gap since Mon 12 Oct.")
        self.assertTrue(lines[at + 2].startswith("   a. trend weight"), lines[at + 2])

    def test_a_part_that_leaves_food_out_drops_the_question_and_renumbers(self):
        def no_food(ctx):
            return checkin_parts.Contribution(fields={"nutrition": None})

        with mock.patch.object(nutrition_part, "contribute", no_food):
            data = self.prepared()
        questions = data["card"]["catch_up"]["questions"]
        self.assertEqual([(q["id"], q["n"]) for q in questions], [("gap", 1), ("now", 2), ("next_week", 3)])
        self.assertNotIn("Food.", data["text"])
        self.assertNotIn("Bodyweight.", data["text"])
        self.assertIn("\n3. Next week.", data["text"])
        self.assertTrue(data["text"].splitlines()[-1].endswith("any of 1–3."))

    def test_known_values_stay_prefills_and_are_not_asked_again(self):
        self.edit_json("data/nutrition/plans/2026-10-12.json",
                       lambda doc: doc["span"].update(start="2026-10-19", end="2026-10-25"))
        data = self.prepared()
        food = self.food(data["card"])
        self.assertIn("Meal plan: nutrition/plans/2026-10-12.md.", food["prefill"])
        self.assertNotIn("Meal plan:", food["ask"])
        self.assertIn(PLAN_ASK, food["ask"])
        self.assertEqual(data["text"].count("Meal plan: nutrition/plans/2026-10-12.md."), 1)

    def test_without_an_app_food_asks_the_scale_questions_and_no_macrofactor_fields(self):
        self.configure({"nutrition": {"app": "none"}})
        food = self.food(self.prepared()["card"])
        self.assertIn("this week's morning weigh-ins", food["ask"])
        for word in ("trend weight", "expenditure", "MacroFactor"):
            self.assertNotIn(word, food["ask"])

    def test_nutrition_off_asks_one_morning_scale_weight_only(self):
        self.configure({"nutrition": {"enabled": False}})
        data = self.prepared()
        food = self.food(data["card"])
        self.assertEqual((food["n"], food["label"], food["prefill"], food["ask"]),
                         (3, "Bodyweight", None, "One morning scale weight."))
        self.assertIn("\n3. Bodyweight. One morning scale weight.\n", data["text"])
        self.assertNotIn("Meal plan", data["text"])
        self.assertNotIn("Food.", data["text"])

    def test_labels_numbering_and_the_reply_line_agree(self):
        data = self.prepared()
        lines = data["text"].splitlines()
        questions = data["card"]["catch_up"]["questions"]
        for question in questions:
            self.assertTrue(any(line.startswith(f"{question['n']}. {question['label']}.") for line in lines),
                            question)
        self.assertEqual(lines[-1], "Reply ok to accept all of this, or answer any of 1–4."
                         if data["card"]["catch_up"]["write_line"] else "Answer any of 1–4.")

    def test_a_deferred_deep_review_stays_catch_up_with_food(self):
        card = self.prepared("--deep-reason", "light_week_proposed")["card"]
        self.assertEqual((card["mode"], card["deep_deferred"], card["fields"]), ("catch_up", True, []))
        self.assertIn("deep review deferred (no deep check-in on record; a light week is being proposed)",
                      card["tier_reasons"])
        self.assertEqual(self.food(card)["label"], "Food")

    def test_the_reading_is_saved_with_its_own_date_and_no_backfilled_weeks(self):
        before = [r["date"] for r in self.coach("nutrition", "readings")["data"]["readings"]]
        self.coach("nutrition", "record", "--date", "2026-10-25", "--trend-weight", "80.4", "--avg-kcal", "2350",
                   "--avg-protein", "131", "--days-logged", "7", "--anchors", "yes")
        after = self.coach("nutrition", "readings")["data"]["readings"]
        self.assertEqual([r["date"] for r in after], before + ["2026-10-25"])
        self.assertEqual((after[-1]["avg_protein_g"], after[-1]["days_logged"]), (131, 7))
        self.assertEqual(self.prepared()["card"]["mode"], "catch_up")

    def test_food_answers_in_the_record_survive_a_re_render(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-25")
        path = self.root / "check-ins" / "2026-10-25.md"
        answers = ("Weight: trend 80.4 kg (MacroFactor, 25 Oct).\n"
                   "Nutrition: 7-day average 2,350 kcal / 131 g protein (19–25 Oct), 7 of 7 days logged.\n")
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# Check-in — 2026-10-25 (catch-up)\n"))
        path.write_text(text.replace("## Coach's read\n", "## Coach's read\n\n" + answers), encoding="utf-8")
        before = path.read_text(encoding="utf-8")
        self.coach("checkin", "skeleton", "--date", "2026-10-25", "--refresh")
        self.assertEqual(path.read_text(encoding="utf-8"), before)
        self.assertIn(answers, before)


class RegistrationTest(unittest.TestCase):
    def test_commands_are_allowlisted(self):
        allowed = set(read_json(REPO_ROOT / ".claude" / "settings.json")["permissions"]["allow"])
        for name in ("tag-gap", "return-brief"):
            with self.subTest(command=name):
                self.assertIn(f"Bash(python3 -m coach checkin {name}:*)", allowed)

    def test_symptom_free_hours_match_claude_md(self):
        text = (REPO_ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        self.assertIn(f"no training until {validity.SYMPTOM_FREE_HOURS} hours symptom-free", text)


class CheckInSkillTest(unittest.TestCase):
    def setUp(self):
        self.text = " ".join(skill_text("check-in").split())

    def test_catch_up_path(self):
        for words in ("catch_up", "python3 -m coach checkin tag-gap", "lines_digest", "propose finalize",
                      "overlay approve", "routines push"):
            with self.subTest(words=words):
                self.assertIn(words, self.text)

    def test_catch_up_food(self):
        for words in ("or answer any of 1–4", "with nutrition off, **Bodyweight**",
                      "one reading dated the check-in date, and nothing for the earlier weeks of the gap"):
            with self.subTest(words=words):
                self.assertIn(words, self.text)

    def test_return_template(self):
        self.assertIn("python3 -m coach checkin return-brief", self.text)


if __name__ == "__main__":
    unittest.main()
