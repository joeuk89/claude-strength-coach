"""Goal events: the document, the commands, status, the card, proposal review flags and planned-activity links (contract C55)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from coach import events, flags, migrate, paths, status
from tests.support import INSTANCES, REPO_ROOT, run_cli
from tests.support.skills import skill_text
from tests.test_cardio import CardioCase

RACE = ("events", "add", "--id", "autumn-10k", "--title", "Autumn 10K", "--date", "2026-10-21", "--priority", "A",
        "--activity", "run", "--distance-km", "10")
WINDOW = ("events", "window", "autumn-10k", "--from", "2026-10-15", "--to", "2026-10-20",
          "--rationale", "keep the legs fresh for the A race")
AFTER_RACE = "2026-10-24T18:00:00Z"


class EventCase(CardioCase):
    def section(self, now=None):
        envelope = self.coach("status", **({"now": now} if now else {}))
        return next((s for s in envelope["data"]["sections"] if s["id"] == "events"), None)

    def card(self, *argv, now=None):
        return self.coach("checkin", "prepare", *argv, **({"now": now} if now else {}))["data"]["card"]

    def event_flags(self, week, *codes):
        found = self.data("propose", "week", "--week", week, "--dry-run")["overlay"]["flags"]
        return [f for f in found if f["code"] in (codes or ("event_window_heavy_lower", "event_window_pending"))]

    def stored(self):
        return json.loads((self.root / paths.EVENTS).read_text(encoding="utf-8"))


class AddAndShowTest(EventCase):
    def test_a_priority_race_ten_days_out_shows_its_countdown_in_status_and_the_card(self):
        event = self.data(*RACE)["event"]
        self.assertEqual((event["days_to_go"], event["pending"], event["window"]), (10, ["window"], None))
        section = self.section()
        self.assertEqual(section["level"], "attention")
        [line] = section["lines"]
        for words in ("Autumn 10K", "(A, run 10 km)", "2026-10-21", "10 days to go", "no event window"):
            self.assertIn(words, line)
        card = self.card("--tier", "weekly")
        self.assertIn(line, card["facts"])
        [field] = [f for f in card["fields"] if f["id"] == "events"]
        self.assertEqual(field["label"], "Events")
        self.assertIn("is there a window before it", field["ask"])
        self.assertIn(line, self.card()["facts"])

    def test_an_agreed_window_is_shown_and_ends_the_decision_prompt(self):
        self.data(*RACE)
        event = self.data(*WINDOW)["event"]
        self.assertEqual(event["window"]["start"], "2026-10-15")
        self.assertEqual(event["pending"], [])
        [line] = self.section()["lines"]
        self.assertIn("agreed window 2026-10-15 to 2026-10-20", line)
        self.assertNotIn("events", [f["id"] for f in self.card("--tier", "weekly")["fields"]])

    def test_an_agreed_decision_to_keep_no_window_is_recorded_and_ends_the_prompt(self):
        self.data(*RACE)
        event = self.data("events", "window", "autumn-10k", "--none", "--rationale", "a C-style tune-up")["event"]
        self.assertEqual((event["window"]["start"], event["window"]["end"], event["pending"]), (None, None, []))
        self.assertIn("agreed: no event window", self.section()["lines"][0])
        self.assertEqual(self.event_flags("2026-W43"), [])

    def test_the_check_skips_without_the_file_and_passes_after_the_commands_write_it(self):
        self.assertEqual([r["status"] for r in self.data("check", "--only", "events_valid")["results"]], ["skip"])
        self.data(*RACE)
        self.data(*WINDOW)
        self.data("events", "add", "--id", "parkrun", "--title", "Parkrun", "--date", "2026-10-03", "--priority", "C")
        self.data("events", "complete", "parkrun", "--result", "24:10")
        self.data("events", "add", "--id", "club-5k", "--title", "Club 5K", "--date", "2026-11-01", "--priority", "B")
        self.data("events", "cancel", "club-5k", "--reason", "clash")
        self.assertEqual([r["status"] for r in self.data("check", "--only", "events_valid")["results"]], ["pass"])

    def test_dry_run_writes_nothing(self):
        self.data(*RACE, "--dry-run")
        self.assertFalse((self.root / paths.EVENTS).exists())


class InvalidInputTest(EventCase):
    def test_invalid_dates_and_priorities_fail_as_usage(self):
        envelope = self.coach(*RACE[:7], "2026-10-32", *RACE[8:], expect=2)
        self.assertIn("--date", envelope["error"]["message"])
        self.coach(*RACE[:9], "D", *RACE[10:], expect=2)
        self.assertFalse((self.root / paths.EVENTS).exists())

    def test_a_duplicate_id_fails_naming_the_id(self):
        self.data(*RACE)
        envelope = self.coach(*RACE, expect=1)
        self.assertIn("already has the id autumn-10k", envelope["error"]["message"])
        self.data("events", "cancel", "autumn-10k", "--reason", "clash")
        self.coach(*RACE, expect=1)

    def test_a_bad_id_or_window_fails(self):
        self.coach("events", "add", "--id", "Autumn 10K", "--title", "x", "--date", "2026-10-21", "--priority", "A",
                   expect=1)
        self.data(*RACE)
        envelope = self.coach("events", "window", "autumn-10k", "--from", "2026-10-15", "--to", "2026-10-22",
                              "--rationale", "x", expect=1)
        self.assertIn("after the event", envelope["error"]["message"])
        self.coach("events", "window", "autumn-10k", "--from", "2026-10-15", expect=2)
        self.coach("events", "window", "autumn-10k", "--from", "2026-10-15", "--to", "2026-10-20", expect=1)

    def test_a_hand_edited_duplicate_fails_the_check_and_every_reader(self):
        self.data(*RACE)
        doc = self.stored()
        doc["events"].append(dict(doc["events"][0], priority="B"))
        (self.root / paths.EVENTS).write_text(json.dumps(doc), encoding="utf-8")
        [result] = self.coach("check", "--only", "events_valid", expect=1)["data"]["results"]
        self.assertEqual(result["status"], "fail")
        self.assertIn("appears twice", result["message"])
        self.coach("events", "list", expect=1)


class WindowReviewTest(EventCase):
    def setUp(self):
        super().setUp()
        self.data(*RACE)

    def test_a_heavy_lower_session_inside_the_agreed_window_is_flagged_for_review(self):
        self.data(*WINDOW)
        [flag] = self.event_flags("2026-W43")
        self.assertEqual((flag["code"], flag["severity"], flag["session_id"]),
                         ("event_window_heavy_lower", "warn", "session-a"))
        for words in ("Autumn 10K", "2026-10-21", "2026-10-15 to 2026-10-20", "Session A (2026-10-19)",
                      "keep the legs fresh", "propose override"):
            self.assertIn(words, flag["message"])

    def test_a_session_before_the_window_or_light_on_the_legs_is_not_flagged(self):
        self.data(*WINDOW)
        self.assertEqual(self.event_flags("2026-W42"), [])

    def test_no_window_is_a_decision_prompt_not_an_assumed_rule(self):
        for week in ("2026-W42", "2026-W43"):
            [flag] = self.event_flags(week)
            self.assertEqual((flag["code"], flag["severity"], flag["session_id"]),
                             ("event_window_pending", "info", None))
            self.assertIn("none is assumed", flag["message"])

    def test_an_event_already_past_in_a_midweek_reprogram_gets_no_window_prompt(self):
        self.data("events", "add", "--id", "club-5k", "--title", "Club 5K", "--date", "2026-10-13", "--priority", "C")
        found = self.coach("propose", "week", "--week", "2026-W42", "--dry-run", now="2026-10-14T07:00:00Z")["data"]
        messages = [f["message"] for f in found["overlay"]["flags"] if f["code"] == "event_window_pending"]
        self.assertEqual(len(messages), 1)
        self.assertIn("Autumn 10K", messages[0])

    def test_flags_and_reads_leave_the_prescriptions_alone(self):
        def lines(data):
            return [(s["date"], s["session_id"], line["exercise_id"], line["sets"])
                    for s in data["overlay"]["sessions"] for line in s["exercises"]]
        self.data(*WINDOW)
        with_event = self.data("propose", "week", "--week", "2026-W43", "--dry-run")
        before = {p: p.read_bytes() for p in (self.root / "data").rglob("*") if p.is_file()}
        self.coach("status")
        self.data("events", "list")
        self.card()
        self.assertEqual({p: p.read_bytes() for p in (self.root / "data").rglob("*") if p.is_file()}, before)
        self.data("events", "cancel", "autumn-10k", "--reason", "injury")
        without = self.data("propose", "week", "--week", "2026-W43", "--dry-run")
        self.assertEqual(lines(with_event), lines(without))

    def test_the_flag_is_settled_through_the_ordinary_reviewed_route(self):
        self.data(*WINDOW)
        draft = self.data("propose", "week", "--week", "2026-W43")
        proposal_id = draft["overlay"]["id"]
        ref = next(f["ref"] for f in draft["flags"] if f["code"] == "event_window_heavy_lower")
        self.data("propose", "resolve", "--proposal", proposal_id, "--flag", ref,
                  "--resolution", "keep it: the squats are at RPE 7 and the race is a test")
        shown = self.data("propose", "show", proposal_id)
        [flag] = [f for f in shown["overlay"]["flags"] if f["code"] == "event_window_heavy_lower"]
        self.assertTrue(flag["resolved"])
        self.assertNotIn("event_window_heavy_lower", [f["code"] for f in shown["unresolved_blocks"]])

    def test_the_existing_plan_in_the_window_is_named_in_status(self):
        overlay = self.data("propose", "week", "--week", "2026-W43", "--dry-run")["overlay"]
        path = self.root / paths.OVERLAYS_DIR / f"{overlay['id']}.json"
        path.write_text(json.dumps(overlay, indent=2) + "\n", encoding="utf-8")
        self.data(*WINDOW)
        section = self.section()
        self.assertIn("heavy lower-body work in the window to review: Session A (2026-10-19)", section["lines"][0])
        self.assertEqual(section["level"], "attention")
        [listed] = self.data("events", "list")["events"]
        self.assertEqual(listed["window_sessions"], [{"date": "2026-10-19", "session_id": "session-a",
                                                      "title": "Session A"}])


class ChangesTest(EventCase):
    def setUp(self):
        super().setUp()
        self.data(*RACE)
        self.data(*WINDOW)

    def test_postponing_clears_the_window_and_its_conflicts(self):
        data = self.data("events", "update", "autumn-10k", "--date", "2026-11-04", "--reason", "course flooded")
        self.assertEqual(data["cleared"], ["window"])
        self.assertEqual((data["event"]["days_to_go"], data["event"]["window"]), (24, None))
        self.assertIn("24 days to go", self.section()["lines"][0])
        self.assertEqual(self.event_flags("2026-W43", "event_window_heavy_lower"), [])
        self.assertIn("date 2026-10-21 → 2026-11-04", self.stored()["events"][0]["changes"][-1]["change"])

    def test_cancelling_removes_the_countdown_and_flags_but_keeps_the_history(self):
        self.data("events", "cancel", "autumn-10k", "--reason", "work trip")
        self.assertIsNone(self.section())
        self.assertEqual(self.event_flags("2026-W43"), [])
        self.assertEqual(self.data("events", "list")["count"], 0)
        [kept] = self.data("events", "list", "--all")["events"]
        self.assertEqual((kept["status"], kept["window"]["start"]), ("cancelled", "2026-10-15"))
        self.coach("events", "update", "autumn-10k", "--priority", "B", expect=1)

    def test_completing_records_the_result_and_stops_the_prompts(self):
        envelope = self.coach("events", "complete", "autumn-10k", "--result", "41:30", expect=1)
        self.assertIn("after today", envelope["error"]["message"])
        section = self.section(now=AFTER_RACE)
        self.assertIn("was 3 days ago: record the result", section["lines"][0])
        self.coach("events", "complete", "autumn-10k", "--result", "41:30, a 2 min PB", now=AFTER_RACE)
        self.assertIsNone(self.section(now=AFTER_RACE))
        [kept] = self.data("events", "list", "--all")["events"]
        self.assertEqual(kept["result"]["text"], "41:30, a 2 min PB")
        facts = self.card("--until", "2026-10-24", now=AFTER_RACE)["facts"]
        self.assertIn('Event "Autumn 10K" (A, run 10 km) on 2026-10-21 completed: 41:30, a 2 min PB.', facts)


class LinkTest(EventCase):
    def setUp(self):
        super().setUp()
        self.data("planned", "add", "--date", "2026-10-21", "--kind", "run", "--title", "Autumn 10K", "--quality",
                  "--distance-km", "10")
        self.plan = next(p["id"] for p in self.data("planned", "list", "--from", "2026-10-21", "--to",
                                                     "2026-10-21")["planned"])

    def test_a_linked_race_logged_as_a_run_counts_once(self):
        self.data(*RACE, "--planned-id", self.plan)
        self.coach("activity", "add", "--kind", "run", "--start", "2026-10-21T09:00:00Z", "--duration-min", "42",
                   "--distance-km", "10", "--rpe", "9", "--name", "Autumn 10K", now=AFTER_RACE)
        week = self.coach("cardio", "week", "--week", "2026-W43", now=AFTER_RACE)["data"]
        self.assertEqual((week["run"]["count"], week["run"]["distance"]), (1, 10))
        [kept] = self.coach("events", "list", now=AFTER_RACE)["data"]["events"]
        self.assertEqual(kept["link"]["status"], "done")
        self.assertTrue(kept["link"]["activity_id"].startswith("manual:2026-10-21-run"))

    def test_one_plan_links_one_event_on_its_own_date(self):
        self.data(*RACE, "--planned-id", self.plan)
        envelope = self.coach("events", "add", "--id", "club-10k", "--title", "Club 10K", "--date", "2026-10-21",
                              "--priority", "B", "--planned-id", self.plan, expect=1)
        self.assertIn("one planned activity is one event", envelope["error"]["message"])
        self.coach("events", "add", "--id", "other", "--title", "Other", "--date", "2026-10-22", "--priority", "C",
                   "--planned-id", self.plan, expect=1)
        self.coach("events", "add", "--id", "ride", "--title", "Ride", "--date", "2026-10-21", "--priority", "C",
                   "--activity", "ride", "--planned-id", "manual:no-such-plan", expect=1)

    def test_postponing_drops_a_plan_left_on_the_old_date(self):
        self.data(*RACE, "--planned-id", self.plan)
        data = self.data("events", "update", "autumn-10k", "--date", "2026-11-04")
        self.assertEqual((data["cleared"], data["event"]["planned_id"]), (["planned_id"], None))

    def test_linking_needs_the_activity_source(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("[activity]\nenabled = true",
                                                                 "[activity]\nenabled = false"), encoding="utf-8")
        self.coach(*RACE, "--planned-id", self.plan, expect=5)

    def test_a_linked_event_keeps_its_other_edits_once_the_activity_source_is_off(self):
        self.data(*RACE, "--planned-id", self.plan)
        path = self.root / "config.toml"
        path.write_text(path.read_text(encoding="utf-8").replace("[activity]\nenabled = true",
                                                                 "[activity]\nenabled = false"), encoding="utf-8")
        event = self.data("events", "update", "autumn-10k", "--title", "Autumn 10K (club)")["event"]
        self.assertEqual((event["title"], event["planned_id"]), ("Autumn 10K (club)", self.plan))
        self.data(*WINDOW)
        self.coach("events", "update", "autumn-10k", "--activity", "ride", expect=5)


class ManyEventsTest(EventCase):
    def test_each_event_is_shown_in_date_order_with_its_own_priority_and_window(self):
        self.data(*RACE)
        self.data(*WINDOW)
        self.data("events", "add", "--id", "parkrun", "--title", "Parkrun", "--date", "2026-10-17", "--priority", "C",
                  "--activity", "run", "--distance-km", "5")
        lines = self.section()["lines"]
        self.assertEqual(len(lines), 2)
        self.assertIn('"Parkrun" (C, run 5 km) on 2026-10-17: 6 days to go; no event window', lines[0])
        self.assertIn('"Autumn 10K" (A, run 10 km) on 2026-10-21: 10 days to go; agreed window', lines[1])
        found = self.event_flags("2026-W43")
        self.assertEqual([f["code"] for f in found], ["event_window_heavy_lower"])
        found = self.event_flags("2026-W42")
        self.assertEqual([f["code"] for f in found], ["event_window_pending"])
        self.assertIn("Parkrun", found[0]["message"])

    def test_more_than_three_events_end_with_a_pointer(self):
        for n in range(4):
            self.data("events", "add", "--id", f"race-{n}", "--title", f"Race {n}", "--date", f"2026-11-0{n + 1}",
                      "--priority", "B")
        lines = self.section()["lines"]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[-1], "2 more events: python3 -m coach events list.")
        self.assertEqual(len(self.section()["data"]["events"]), 4)


class BlockTest(EventCase):
    def test_an_event_and_its_window_leave_the_block_count_alone(self):
        before = self.data("block", "status")
        self.data(*RACE)
        self.data(*WINDOW)
        self.assertEqual(self.data("block", "status"), before)


class CheckTest(unittest.TestCase):
    def check(self, root):
        code, envelope, _ = run_cli(["--root", str(root), "check", "--only", "events_valid"])
        return code, envelope["data"]["results"]

    def test_the_failing_fixture_names_each_problem_and_its_repair_passes(self):
        code, results = self.check(INSTANCES / "valid")
        self.assertEqual((code, [r["status"] for r in results]), (0, ["skip"]))
        code, results = self.check(INSTANCES / "events-invalid")
        self.assertEqual((code, [r["status"] for r in results]), (1, ["fail", "fail"]))
        messages = " ".join(r["message"] for r in results)
        self.assertIn("$.events[0].window.end: ends (2026-10-22) after the event (2026-10-21)", messages)
        self.assertIn("$.events[1].result: a completed event has a result", messages)
        self.assertEqual({r["path"] for r in results}, {"data/events.json"})
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "instance"
            shutil.copytree(INSTANCES / "events-invalid", root)
            path = root / paths.EVENTS
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["events"][0]["window"]["end"] = "2026-10-20"
            doc["events"][1]["result"] = {"text": "24:10", "recorded_at": "2026-10-04T12:00:00Z"}
            path.write_text(json.dumps(doc), encoding="utf-8")
            code, results = self.check(root)
        self.assertEqual((code, [r["status"] for r in results]), (0, ["pass"]))


class RegistryTest(unittest.TestCase):
    def test_codes_provider_check_and_document_are_registered(self):
        registry = flags.registry()
        self.assertEqual(registry["event_window_heavy_lower"].severities, ("warn",))
        self.assertEqual(registry["event_window_pending"].severities, ("info",))
        self.assertIn("events", {p.id for p in status.discover()})
        self.assertEqual(migrate.registry().documents["events"].files, (paths.EVENTS.as_posix(),))
        self.assertEqual(events.empty(), {"schema_version": 1, "events": []})

    def test_every_events_command_is_allowlisted(self):
        allowed = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        for name in ("list", "add", "update", "window", "complete", "cancel"):
            self.assertIn(f"Bash(python3 -m coach events {name}:*)", allowed["permissions"]["allow"])


class SkillTest(unittest.TestCase):
    def test_program_week_settles_the_event_flags(self):
        text = " ".join(skill_text("program-week").split())
        self.assertIn("`event_window_heavy_lower`", text)
        self.assertIn("`event_window_pending`", text)

    def test_check_in_records_events_and_never_assumes_a_window(self):
        text = " ".join(skill_text("check-in").split())
        self.assertIn("python3 -m coach events add", text)
        self.assertIn("python3 -m coach events complete", text)
        self.assertIn("An event's window is always one the athlete agreed", text)


if __name__ == "__main__":
    unittest.main()
