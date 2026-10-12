"""The whole training week and current recovery context on the athlete pages and in the coach's brief (C38, C24).

The cardio fixture with a coach-led PT session added on Wednesdays: Session A Monday, PT and an easy 5 km Wednesday,
Session B Thursday, a planned tempo Friday, and an open left-knee niggle that applies to runs.
"""

import json

from coach import jsonio, paths, render
from coach.activity import records
from tests.support.history import read_json, write_json
from tests.support.skills import flat, step_text
from tests.test_block import BlockCase
from tests.test_cardio import CardioCase
from tests.test_cardio_identity import activity

SUNDAY = "2026-10-11T20:00:00Z"
MONDAY = "2026-10-12T20:00:00Z"
WEEKLY = "2026-10-12-weekly"
PT = {"id": "pt-wed", "title": "PT", "weekday": "wed", "estimated_sets": {}}


def section(text, heading):
    lines = text.splitlines()
    start = lines.index(f"## {heading}") + 1
    found = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        if line:
            found.append(line)
    return found


def table(text):
    return [[cell.strip() for cell in line.strip("|").split("|")] for line in section(text, "Sessions")[2:]]


class WeekCase(CardioCase):
    def setUp(self):
        super().setUp()
        self.edit("data/program.json", lambda doc: doc.update(external_sessions=[PT]))

    def edit(self, relative, change):
        path = self.root / relative
        doc = read_json(path)
        change(doc)
        write_json(path, doc)

    def brief(self, now=SUNDAY):
        return self.coach("pages", "show", "brief", now=now)["data"]["text"]

    def log_runs(self, *found):
        path = self.root / "data" / "activity" / "activities.jsonl"
        with path.open("a", encoding="utf-8") as out:
            for item in found:
                out.write(json.dumps(records.upsert_line(item, SUNDAY, "activity")) + "\n")

    def pt(self, day, *extra, now=SUNDAY):
        self.coach("history", "annotate", "--kind", "external", "--external", "pt-wed", "--date", day,
                   "--source", "test", *extra, now=now)

    def set_light_week(self, **fields):
        self.edit("data/state.json", lambda doc: doc["block"]["light_week"].update(fields))

    def close_week(self, week, triggers, sleep="ok", **block):
        """A ledger whose newest closed week is `week` with the given triggers, and the state pointing at it."""
        signals = {"readiness": "unknown", "sleep": sleep, "sleep_source": "sleep_debt" if sleep != "unknown" else
                   "none", "sleep_reason": None, "rpe_drift": False, "niggle": False}
        entry = {"week": week, "class": "hard", "planned": 2, "trained": 2, "as_prescribed": 2, "on_break": 0,
                 "signals": signals, "triggers": list(triggers), "count_after": 3,
                 "outcome": "watch" if len(triggers) == 1 else "none", "deep": False, "closed_at": SUNDAY}
        ledger = {"schema_version": jsonio.current_version(jsonio.load_schema("blocks")),
                  "blocks": [{"id": "b-0001", "started": "2026-09-28", "seed_hard_weeks": 0, "seed_reason": None,
                              "ended": None, "end_reason": None, "weeks": [entry]}]}
        write_json(self.root / paths.BLOCKS, ledger)
        self.edit("data/state.json", lambda doc: doc["block"].update(last_closed_week=week, **block))


class SessionsTest(WeekCase):
    def test_lifts_pt_and_both_runs_show_in_date_order_with_the_tempo_marked_quality(self):
        rows = table(self.brief())
        self.assertEqual([(r[0], r[1], r[2]) for r in rows], [
            ("Mon 12", "Session A", "core"), ("Wed 14", "PT", "coach-led"), ("Wed 14", "Easy 5 km", "run"),
            ("Thu 15", "Session B", "core"), ("Fri 16", "Tempo", "run")])
        self.assertEqual(rows[2][3], "easy (planned), 5 km")
        self.assertEqual(rows[4][3], "quality (planned), 40 min")
        self.assertEqual({r[4] for r in rows}, {""})

    def test_a_logged_run_replaces_its_planned_status_instead_of_adding_a_row(self):
        self.log_runs(activity("manual:wed-run", "2026-10-14", 5100, 1740, name="Easy run"),
                      activity("manual:thu-tempo", "2026-10-15", None, 2400, name="Tempo", rpe=8))
        rows = table(self.brief("2026-10-16T20:00:00Z"))
        runs = [r for r in rows if r[2] == "run"]
        self.assertEqual([(r[0], r[1], r[4]) for r in runs], [("Wed 14", "Easy 5 km", "✔"),
                                                              ("Fri 16", "Tempo", "✔ moved to Thu 15")])
        self.assertEqual(runs[1][3], "quality (logged RPE), 40 min")

    def test_a_trainer_cancellation_shows_the_status_adherence_gives_it(self):
        self.pt("2026-10-14", "--trainer-cancelled", "trainer away")
        row = next(r for r in table(self.brief("2026-10-14T20:00:00Z")) if r[1] == "PT")
        self.assertEqual(row[4], "cancelled by the trainer")
        week = self.data("structure", "week", "--week", "2026-W42")
        self.assertEqual([s["status"] for s in week["sessions"] if s.get("external_id")], ["cancelled"])

    def test_a_coach_led_session_done_another_day_shows_where_it_moved_with_what_was_recorded(self):
        self.pt("2026-10-15", "--done", "--minutes", "45", "--rpe", "7", "--modality", "lifting",
                now="2026-10-15T19:00:00Z")
        row = next(r for r in table(self.brief("2026-10-15T20:00:00Z")) if r[1] == "PT")
        self.assertEqual((row[0], row[3], row[4]), ("Wed 14", "lifting, 45 min, RPE 7", "✔ moved to Thu 15"))

    def test_an_unconfirmed_coach_led_session_reads_not_confirmed_once_its_day_is_over(self):
        self.assertEqual(next(r for r in table(self.brief("2026-10-14T20:00:00Z")) if r[1] == "PT")[4], "")
        self.assertEqual(next(r for r in table(self.brief("2026-10-15T20:00:00Z")) if r[1] == "PT")[4],
                         "not confirmed")

    def test_the_count_tier_shows_no_planned_runs_as_prescribed_work(self):
        self.config('tier = "count"')
        self.assertEqual([r[1] for r in table(self.brief())], ["Session A", "PT", "Session B"])
        self.log_runs(activity("manual:wed-run", "2026-10-14", 5100, 1740, name="Easy run"))
        rows = table(self.brief("2026-10-16T20:00:00Z"))
        self.assertEqual([(r[1], r[4]) for r in rows if r[2] == "run"], [("Easy run", "✔ logged")])

    def test_a_rerender_is_byte_identical(self):
        self.assertEqual(self.brief(), self.brief())


class WatchTest(WeekCase):
    def test_an_open_niggle_and_a_poor_sleep_watch_both_show(self):
        self.close_week("2026-10-05", ["sleep"], sleep="poor")
        self.set_light_week(status="watch")
        watch = section(self.brief(), "Watch")
        self.assertEqual(watch, [
            "- Left knee niggle (watching since 11 Oct): tell the coach how it responds to runs.",
            "- Fatigue watch: poor sleep in the week of 5 Oct. Tell the coach how you recover this week."])

    def test_a_declined_light_week_keeps_its_decision_and_reason(self):
        self.set_light_week(status="proposed", type="deload", reason="ceiling", week="2026-10-12")
        self.data("block", "decide", "--outcome", "declined", "--reason", "racing a 10k on Saturday")
        watch = section(self.brief(), "Watch")
        self.assertIn("- Light week declined: racing a 10k on Saturday. It is proposed again at the next check-in.",
                      watch)
        self.assertNotIn("Nothing flagged.", "\n".join(watch))

    def test_resolving_the_niggle_and_superseding_the_watch_retire_them_and_keep_the_records(self):
        self.close_week("2026-10-05", ["sleep"], sleep="poor")
        self.set_light_week(status="watch")
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].append(niggle_link()))
        self.assertEqual(len(section(self.brief(MONDAY), "Watch")), 2)
        self.coach("niggles", "resolve", "n-0001", "--note", "settled", "--date", "2026-10-12", now=MONDAY)
        niggles_before, overlay_before = self.read("data/niggles.json"), self.read(f"data/overlays/{WEEKLY}.json")
        self.close_week("2026-10-05", [], sleep="ok")
        self.set_light_week(status="not_due")
        self.assertEqual(section(self.brief(MONDAY), "Watch"), ["- Nothing flagged."])
        dashboard = self.coach("pages", "show", "dashboard", now=MONDAY)["data"]["text"]
        self.assertIn("- Open flags: none", dashboard)
        history = read_json(self.root / "data" / "niggles.json")["niggles"][0]["history"]
        self.assertEqual([e["status"] for e in history], ["watching", "resolved"])
        self.assertEqual((self.read("data/niggles.json"), self.read(f"data/overlays/{WEEKLY}.json")),
                         (niggles_before, overlay_before))

    def test_equivalent_overlay_and_block_warnings_show_once(self):
        self.close_week("2026-10-05", ["sleep"], sleep="poor")
        self.set_light_week(status="watch")
        sleep = {"code": "sleep_debt", "severity": "warn", "session_id": None, "exercise_id": None,
                 "message": "4 of the 7 nights to 2026-10-11 were under 7 h asleep.", "resolved": False,
                 "resolution": None}
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].extend([niggle_link(), sleep, sleep]))
        watch = section(self.brief(), "Watch")
        self.assertEqual(len(watch), 2, watch)
        self.assertEqual(sum("knee" in line for line in watch), 1)
        self.assertEqual(sum("sleep" in line for line in watch), 1)
        self.assertIn("Left knee niggle (watching since 11 Oct)", watch[0])
        self.assertIn("- 4 of the 7 nights to 2026-10-11 were under 7 h asleep.", watch)

    def test_three_unrelated_warnings_do_not_push_out_the_sleep_watch(self):
        self.close_week("2026-10-05", ["sleep"], sleep="poor")
        self.set_light_week(status="watch")
        others = [dict(niggle_link(), code="collision", message=f"Warning {n}.") for n in range(3)]
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].extend(others))
        watch = section(self.brief(), "Watch")
        self.assertIn("- Fatigue watch: poor sleep in the week of 5 Oct. Tell the coach how you recover this week.",
                      watch)

    def test_a_chronic_niggle_keeps_its_current_flag_on_watch(self):
        self.coach("niggles", "update", "n-0001", "--status", "chronic", "--date", "2026-10-12", now=MONDAY)
        flag = dict(niggle_link(), message=niggle_link()["message"].replace("watching", "chronic"))
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].append(flag))
        self.assertEqual(section(self.brief(MONDAY), "Watch"), [f"- {flag['message']}"])

    def test_a_chronic_niggle_shows_while_its_limits_apply_and_once_beside_its_flag(self):
        self.coach("niggles", "update", "n-0001", "--status", "chronic", "--pattern", "squat", "--constraint",
                   "rpe_cap=7", "--date", "2026-10-12", now=MONDAY)
        self.assertEqual(section(self.brief(MONDAY), "Watch"),
                         ["- Left knee niggle (chronic): its limits apply to this week's loads."])
        flag = dict(niggle_link(), message=niggle_link()["message"].replace("watching", "chronic"))
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].append(flag))
        self.assertEqual(section(self.brief(MONDAY), "Watch"), [f"- {flag['message']}"])
        self.edit(f"data/overlays/{WEEKLY}.json", lambda doc: doc["flags"].remove(flag))
        self.coach("niggles", "update", "n-0001", "--clear-constraints", "--date", "2026-10-12", now=MONDAY)
        self.assertEqual(section(self.brief(MONDAY), "Watch"), ["- Nothing flagged."])

    def test_a_niggle_with_limits_in_force_says_they_apply_to_this_weeks_loads(self):
        self.coach("niggles", "update", "n-0001", "--pattern", "squat", "--flare-constraint", "rpe_cap=7",
                   "--note", "sore on squats", "--date", "2026-10-12", now=MONDAY)
        self.assertEqual(section(self.brief(MONDAY), "Watch"), [
            "- Left knee niggle (watching since 11 Oct): tell the coach how it responds to runs and squat. Its limits "
            "apply to this week's loads."])

    def test_an_escalating_niggle_says_to_have_it_assessed(self):
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--date", "2026-10-12", now=MONDAY)
        self.assertEqual(section(self.brief(MONDAY), "Watch")[0],
                         "- Left knee niggle (aggravated since 12 Oct): worse: watching to aggravated. Have it assessed "
                         "by a qualified professional (a doctor or physiotherapist); the program works around it "
                         "meanwhile.")

    def test_a_page_dated_before_a_niggle_worsened_does_not_say_it_worsened(self):
        self.coach("niggles", "update", "n-0001", "--status", "aggravated", "--date", "2026-10-13",
                   now="2026-10-13T20:00:00Z")
        self.assertEqual(section(self.brief(MONDAY), "Watch")[0],
                         "- Left knee niggle (watching since 11 Oct): tell the coach how it responds to runs.")

    def test_a_proposed_light_week_names_its_week_type_and_reason(self):
        self.edit("data/state.json", lambda doc: doc["block"].update(hard_weeks_completed=6))
        self.set_light_week(status="proposed", type="light", reason="ceiling", week="2026-10-19")
        self.assertIn("- Light week proposed for the week of 19 Oct: a light week, because 6 completed hard weeks "
                      "reach the ceiling. Decide it with the coach at the check-in.", section(self.brief(), "Watch"))

    def test_a_skipped_light_week_names_its_triggers_and_the_hard_week_count(self):
        self.close_week("2026-10-05", ["sleep", "readiness"], sleep="poor")
        self.set_light_week(status="skipped")
        self.assertIn("- Two fatigue triggers (poor sleep and poor readiness) with 2 completed hard weeks, too few "
                      "for a light week: watch how you recover this week.", section(self.brief(), "Watch"))

    def read(self, relative):
        return (self.root / relative).read_bytes()


def niggle_link():
    return {"code": "niggle_link", "severity": "warn", "session_id": None, "exercise_id": None,
            "message": "Niggle n-0001 (left knee, watching) applies to run: 2 runs, 5 km in 2026-10-12 to "
                       "2026-10-18. Ask how it responded.", "resolved": False, "resolution": None}


class ProposalContextTest(WeekCase):
    def test_the_proposal_names_the_coach_led_and_planned_runs_and_its_interference_flags(self):
        self.log_planned({"id": "manual:mon-intervals", "source": "manual", "date": "2026-10-12", "kind": "run",
                          "title": "Intervals", "quality": True, "start": None,
                          "target": {"distance_meters": 6000, "duration_seconds": None}})
        data = self.data("propose", "week", "--week", "2026-W42", "--dry-run")
        self.assertEqual([(r["date"], r["type"], r["title"], r["quality"]) for r in data["other_work"]], [
            ("2026-10-12", "activity", "Intervals", True), ("2026-10-14", "coach_led", "PT", None),
            ("2026-10-14", "activity", "Easy 5 km", False), ("2026-10-16", "activity", "Tempo", True)])
        self.assertIn("collision", [f["code"] for f in data["overlay"]["flags"] if not f["resolved"]])

    def test_the_coach_brief_names_the_rest_of_the_week_and_its_interference(self):
        brief = flat(step_text("program-week", "brief.md"))
        focus = brief[brief.index("**Week focus:**"):brief.index("**What's changing:**")]
        for words in ("`other_work`", "coach-led session", "planned run", "quality", "`collision`",
                      "`quality_stack`"):
            with self.subTest(words=words):
                self.assertIn(words, focus)
        self.assertIn('"Light — <title>"', flat(step_text("program-week", "compute.md")))

    def log_planned(self, item):
        path = self.root / "data" / "activity" / "planned.jsonl"
        with path.open("a", encoding="utf-8") as out:
            out.write(json.dumps(records.upsert_line(item, SUNDAY, "planned")) + "\n")


class RecoveryTitleTest(BlockCase):
    """The block fixture: Session A Monday, PT Tuesday, Session B Thursday."""

    def light_week(self, transform):
        argv = ("--transform", transform) if transform else ()
        data = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload", *argv)
        self.data("propose", "finalize", "--proposal", data["id"])
        return data

    def test_light_deload_and_return_weeks_carry_their_own_titles_and_summaries(self):
        for transform, label, summary in (("light", "Light", "at the loads already lifted"),
                                          (None, "Deload", "aims 10 % off the loads"),
                                          ("return", "Return", "Drops one working set per line")):
            with self.subTest(transform=transform):
                doc = self.data("propose", "week", "--week", "2026-W42", "--kind", "deload",
                                *(("--transform", transform) if transform else ()), "--dry-run")["overlay"]
                self.assertEqual({s["title"].split(" — ")[0] for s in doc["sessions"]}, {label})
                self.assertTrue(doc["focus"].startswith(f"{label} week of 2026-10-12: "), doc["focus"])
                self.assertIn(summary, doc["focus"])
                rationales = [line["provenance"]["rationale"] for s in doc["sessions"] for line in s["exercises"]]
                if transform == "light":
                    self.assertTrue(all("the light week" in r and "deload" not in r for r in rationales), rationales)

    def test_a_light_week_is_not_called_a_deload_on_the_page_or_in_the_record(self):
        data = self.light_week("light")
        text = self.data("pages", "show", "brief")["text"]
        self.assertNotIn("Deload", text)
        self.assertIn("| Light — Session A |", text)
        changed = section(text, "Changed")
        self.assertTrue(changed and all(line.endswith(": light week") for line in changed), changed)
        self.assertNotIn("Double progression", "\n".join(changed))
        region = render.render_overlay(self.root, data["id"])
        self.assertIn(f"`{data['id']}` (light week)", region)

    def test_rendering_the_region_again_keeps_the_record_prose_and_the_region_stable(self):
        data = self.light_week("light")
        record = self.root / "check-ins" / "2026-10-11.md"
        record.parent.mkdir(exist_ok=True)
        record.write_text("# Check-in 2026-10-11\n\nThe athlete's own words stay.\n\n## The week ahead\n\n"
                          "Coach's note above the region.\n", encoding="utf-8")
        self.data("overlay", "render", data["id"], "--into", str(record))
        first = record.read_text(encoding="utf-8")
        second = self.data("overlay", "render", data["id"], "--into", str(record))
        self.assertFalse(second["changed"])
        self.assertEqual(record.read_text(encoding="utf-8"), first)
        self.assertIn("The athlete's own words stay.", first)
        self.assertIn("Coach's note above the region.", first)
