"""Review identity, first-review timing and record rendering across command consumers."""

from datetime import date

from coach import block, checkin, dates, pages, render
from coach.errors import ValidationError
from tests.support import INSTANCES
from tests.support.history import HistoryCase, write_json


class ReviewContextTest(HistoryCase):
    base = INSTANCES / "nohevy"

    def setUp(self):
        super().setUp()
        for path in (self.root / "check-ins").glob("*.md"):
            path.unlink()
        self.edit_json("data/state.json", lambda doc: doc["block"].update(started="2026-10-11"))

    def record(self, day, title):
        path = self.root / "check-ins" / f"{day}.md"
        path.write_text(title + "\n\nSetup prose.\n", encoding="utf-8")
        return path

    def status(self, day):
        result = self.coach("status", env={"COACH_NOW": f"{day}T18:00:00Z"})
        return next(section for section in result["data"]["sections"] if section["id"] == "checkin")

    def checks(self, check_id, expect=0):
        return self.coach("check", "--only", check_id, expect=expect)["data"]["results"]

    def test_program_start_record_does_not_complete_a_review_and_first_due_is_consistent(self):
        for program_start in (False, True):
            with self.subTest(program_start=program_start):
                if program_start:
                    self.record("2026-10-11", "# Program start — 2026-10-11")
                first = self.status("2026-10-11")
                self.assertEqual(first["level"], "info")
                self.assertEqual(first["data"]["due_date"], "2026-10-18")
                self.assertIsNone(first["data"]["last"])
                self.assertEqual(self.status("2026-10-18")["level"], "attention")
                due = checkin.due(self.root, date(2026, 10, 18))
                self.assertEqual((due.mode, due.tier_reasons), ("first", ["first check-in"]))
                card = self.coach("checkin", "prepare", "--until", "2026-10-18")["data"]["card"]
                self.assertEqual(card["mode"], "deep")
                self.assertEqual(card["tier_reasons"], ["first check-in"])
                self.assertEqual({row["status"] for row in self.checks("checkin_records")}, {"pass"})
                dashboard = pages.render_dashboard(self.root, dates.parse_timestamp("2026-10-11T18:00:00Z"))
                self.assertIn("Last check-in: none yet", dashboard)
                if program_start:
                    self.assertIn("[Program start](check-ins/2026-10-11.md)", dashboard)
                    self.assertEqual(checkin.records(self.root)[0].kind, checkin.PROGRAM_START)

    def test_configured_cadence_changes_first_due_with_and_without_a_program_start_record(self):
        with (self.root / "config.toml").open("a", encoding="utf-8") as handle:
            handle.write("\n[checkin]\ncadence_days = 14\n")
        for program_start in (False, True):
            with self.subTest(program_start=program_start):
                if program_start:
                    self.record("2026-10-11", "# Program start — 2026-10-11")
                status = self.status("2026-10-18")
                self.assertEqual(status["level"], "info")
                self.assertEqual(status["data"]["due_date"], "2026-10-25")
                self.assertEqual(checkin.due(self.root, date(2026, 10, 18)).due_date, date(2026, 10, 25))
                self.assertEqual(self.status("2026-10-25")["level"], "attention")

    def test_later_program_start_record_cannot_postpone_adoption_due_date(self):
        config_path = self.root / "config.toml"
        config = config_path.read_text(encoding="utf-8")
        for cadence, due_day in ((7, "2026-10-18"), (14, "2026-10-25")):
            with self.subTest(cadence=cadence):
                (self.root / "check-ins/2026-10-12.md").unlink(missing_ok=True)
                config_path.write_text(config + f"\n[checkin]\ncadence_days = {cadence}\n", encoding="utf-8")
                before = self.status(due_day)
                self.assertEqual((before["level"], before["data"]["due_date"]), ("attention", due_day))
                setup = self.record("2026-10-12", "# Program start — 2026-10-12")
                after = self.status(due_day)
                self.assertEqual(after, before)
                self.assertEqual(checkin.due(self.root, dates.parse_date(due_day)).due_date.isoformat(), due_day)
                self.assertEqual(self.status("2026-10-11")["level"], "info")
                setup.unlink()

    def test_program_start_anchor_survives_a_later_block_start(self):
        self.record("2026-10-11", "# Program start — 2026-10-11")
        self.edit_json("data/state.json", lambda doc: doc["block"].update(started="2026-11-01"))
        self.assertEqual(checkin.due(self.root, date(2026, 11, 1)).due_date, date(2026, 10, 18))

    def test_earliest_ledger_start_survives_a_later_block_start_without_a_program_start_record(self):
        self.edit_json("data/state.json", lambda doc: doc["block"].update(started="2026-11-01"))
        write_json(self.root / "data/blocks.json", {"schema_version": 1, "blocks": [{
            "id": "b-0001", "started": "2026-10-11", "seed_hard_weeks": 0, "seed_reason": None,
            "ended": None, "end_reason": None, "weeks": []}]})
        self.assertEqual(checkin.due(self.root, date(2026, 11, 1)).due_date, date(2026, 10, 18))
        self.record("2026-10-12", "# Program start — 2026-10-12")
        self.assertEqual(checkin.due(self.root, date(2026, 11, 1)).due_date, date(2026, 10, 18))
        self.assertEqual(self.status("2026-10-18")["level"], "attention")

    def test_an_invalid_block_ledger_leaves_the_first_due_date_on_the_other_starts(self):
        open_block = {"seed_hard_weeks": 0, "seed_reason": None, "ended": None, "end_reason": None, "weeks": []}
        write_json(self.root / "data/blocks.json", {"schema_version": 1, "blocks": [
            dict(open_block, id="b-0001", started="2026-10-04"),
            dict(open_block, id="b-0002", started="2026-10-11")]})
        with self.assertRaises(ValidationError):
            block.load(self.root)
        due = self.coach("checkin", "due", env={"COACH_NOW": "2026-10-11T18:00:00Z"})["data"]
        self.assertEqual((due["mode"], due["due_date"]), ("first", "2026-10-18"))
        status = self.status("2026-10-11")
        self.assertEqual((status["level"], status["data"]["due_date"]), ("info", "2026-10-18"))
        self.assertEqual(self.status("2026-10-18")["level"], "attention")

    def test_malformed_and_mismatched_titles_do_not_count_but_legacy_checkins_do(self):
        for day, title in (("2026-10-11", "# Notes"),
                           ("2026-10-12", "# Check-in — 2026-10-13 (deep)"),
                           ("2026-10-14", "# Check-in — 2026-10-14 (other)")):
            self.record(day, title)
        self.assertEqual([r.kind for r in checkin.records(self.root)], [checkin.UNRECOGNISED] * 3)
        self.assertEqual(checkin.reviews(self.root), [])
        self.assertEqual(len([r for r in self.checks("checkin_records") if r["status"] == "warn"]), 3)
        self.assertEqual(checkin.due(self.root, date(2026, 10, 18)).mode, "first")
        self.record("2026-10-18", "# Check-in — 2026-10-18")
        self.assertEqual([(r.date, r.tier) for r in checkin.reviews(self.root)], [(date(2026, 10, 18), "deep")])

    def test_without_any_start_the_first_due_date_is_unknown(self):
        (self.root / "data/state.json").unlink()
        status = self.status("2026-10-18")
        self.assertEqual((status["level"], status["lines"]),
                         ("info", ["No check-in recorded yet; the first due date is unknown."]))
        self.assertIsNone(status["data"]["due_date"])
        dashboard = pages.render_dashboard(self.root, dates.parse_timestamp("2026-10-18T18:00:00Z"))
        self.assertIn("First check-in date unknown (deep)", dashboard)

    def test_first_window_starts_at_adoption_when_no_overlay_exists(self):
        for path in (self.root / "data/overlays").glob("*.json"):
            path.unlink()
        self.record("2026-10-11", "# Program start — 2026-10-11")
        card = self.coach("checkin", "prepare", "--until", "2026-10-18")["data"]["card"]
        self.assertEqual(card["window"], {"start": "2026-10-11", "end": "2026-10-18"})

    def test_misses_command_defaults_to_the_deep_cards_tally_before_any_review(self):
        self.record("2026-10-11", "# Program start — 2026-10-11")
        for overlays, since in ((True, "2026-10-12"), (False, "2026-10-11")):
            with self.subTest(overlays=overlays):
                if not overlays:
                    for path in (self.root / "data/overlays").glob("*.json"):
                        path.unlink()
                card = self.coach("checkin", "prepare", "--until", "2026-10-18")["data"]["card"]
                command = self.coach("checkin", "misses", "--until", "2026-10-18")["data"]
                self.assertEqual(card["mode"], "deep")
                self.assertEqual(command, card["misses"])
                self.assertEqual(command["since"], since)

    def test_misses_since_spans_the_program_when_only_weekly_reviews_came_before(self):
        self.record("2026-10-18", "# Check-in — 2026-10-18 (weekly)")
        card = self.coach("checkin", "prepare", "--until", "2026-10-25", "--tier", "deep")["data"]["card"]
        command = self.coach("checkin", "misses", "--until", "2026-10-25")["data"]
        self.assertEqual(card["window"]["start"], "2026-10-19")
        self.assertEqual(card["misses"]["since"], "2026-10-12")
        self.assertEqual(command, card["misses"])

    def test_an_unrecognised_record_keeps_its_week_review_region_as_archive(self):
        for day in ("2026-10-18", "2026-10-25"):
            self.coach("checkin", "skeleton", "--date", day, "--tier", "deep")
        path = self.root / "check-ins/2026-10-25.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("# Check-in — 2026-10-25", "# Check-in 2026-10-25"), encoding="utf-8")
        self.assertEqual(checkin.render_week_review(self.root, date(2026, 10, 25)),
                         text[slice(*render.find_regions(text, checkin.REGION_KIND)[0][1:])])
        sweep = self.checks("render_fresh_sweep")
        self.assertEqual({r["status"] for r in sweep}, {"pass"})

    def test_refresh_refuses_a_malformed_record_without_changing_it(self):
        path = self.record("2026-10-11", "# Notes")
        before = path.read_bytes()
        result = self.coach("checkin", "skeleton", "--date", "2026-10-11", "--refresh", expect=1)
        self.assertIn("invalid record title", result["error"]["message"])
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(checkin.reviews(self.root), [])

    def test_real_deep_review_and_refresh_keep_the_42_day_clock(self):
        self.record("2026-10-11", "# Program start — 2026-10-11")
        self.coach("checkin", "skeleton", "--date", "2026-10-18")
        for _ in range(2):
            self.coach("checkin", "skeleton", "--date", "2026-10-18", "--refresh")
        self.assertEqual(len(checkin.reviews(self.root)), 1)
        self.assertEqual(checkin.due(self.root, date(2026, 10, 19)).due_date, date(2026, 10, 25))
        self.assertEqual(checkin.deep_reasons(checkin.reviews(self.root), date(2026, 11, 28)), [])
        self.assertIn("42 days ago", checkin.deep_reasons(checkin.reviews(self.root), date(2026, 11, 29))[0])

    def test_cardio_and_overlay_regions_stay_in_their_sections_and_preserve_prose(self):
        self.coach("checkin", "skeleton", "--date", "2026-10-18", "--tier", "deep")
        path = self.root / "check-ins/2026-10-18.md"
        original = path.read_text(encoding="utf-8").replace("## Coach's read\n", "## Coach's read\n\nKeep this prose.\n")
        path.write_text(original, encoding="utf-8")
        self.assertIn("## The week ahead", original)
        for _ in range(2):
            self.coach("cardio", "render", "--week", "2026-10-12", "--into", str(path))
            self.coach("checkin", "skeleton", "--date", "2026-10-18", "--refresh", "--overlay", "2026-10-12-weekly")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("<!-- coach:begin cardio "), 1)
        self.assertEqual(text.count("<!-- coach:begin overlay "), 1)
        self.assertLess(text.index("<!-- coach:begin cardio "), text.index("## Coach's read"))
        self.assertGreater(text.index("<!-- coach:begin overlay "), text.index("## The week ahead"))
        self.assertIn("## Coach's read\n\nKeep this prose.\n", text)
        self.coach("cardio", "render", "--week", "2026-10-12", "--into", str(path))
        self.assertEqual(path.read_text(encoding="utf-8"), text)

    def test_empty_overlay_warns_unrendered_and_changed_content_fails(self):
        path = self.record("2026-10-11", "# Program start — 2026-10-11")
        overlay_id = "2026-10-12-weekly"
        empty = render.begin_marker("overlay", overlay_id) + "\n\n" + render.end_marker("overlay", overlay_id)
        path.write_text(path.read_text(encoding="utf-8") + empty, encoding="utf-8")
        warnings = self.checks("overlay_render_fresh")
        self.assertEqual([r["status"] for r in warnings], ["warn"])
        self.assertIn("not rendered yet", warnings[0]["message"])
        self.coach("checkin", "skeleton", "--date", "2026-10-11", "--refresh")
        self.assertEqual({r["status"] for r in self.checks("overlay_render_fresh")}, {"pass"})
        self.assertEqual(checkin.reviews(self.root), [])
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("<!-- coach:end overlay", "Changed content\n<!-- coach:end overlay"), encoding="utf-8")
        failures = self.checks("overlay_render_fresh", expect=1)
        self.assertEqual([r["status"] for r in failures], ["fail"])
        self.assertIn("edited by hand or is out of date", failures[0]["message"])
        self.coach("overlay", "render", overlay_id, "--into", str(path))
        self.assertEqual({r["status"] for r in self.checks("overlay_render_fresh")}, {"pass"})

    def test_block_reasons_reach_the_card_without_being_labelled_an_explicit_request(self):
        self.record("2026-10-11", "# Check-in — 2026-10-11 (deep)")
        self.edit_json("data/state.json", lambda doc: doc["block"]["light_week"].update(
            status="proposed", type="deload", reason="ceiling", week="2026-10-19"))
        report = block.status(self.root, today=date(2026, 10, 18))
        reasons = report["deep_review"]["reasons"]
        self.assertIn("light_week_proposed", reasons)
        args = [part for reason in reasons for part in ("--deep-reason", reason)]
        result = self.coach("checkin", "prepare", "--until", "2026-10-18", "--tier", "deep", *args)["data"]
        self.assertIn("a light week is being proposed", result["text"])
        self.assertNotIn("asked for", result["text"])
        weekly = self.coach("checkin", "prepare", "--until", "2026-10-18", "--tier", "weekly", *args)["data"]["card"]
        self.assertEqual((weekly["mode"], weekly["tier_reasons"]), ("weekly", []))

    def test_a_deep_reason_leaves_a_catch_up_card_in_catch_up(self):
        self.record("2026-10-01", "# Check-in — 2026-10-01 (deep)")
        card = self.coach("checkin", "prepare", "--until", "2026-10-18",
                          "--deep-reason", "light_week_proposed")["data"]["card"]
        self.assertEqual((card["mode"], card["deep_deferred"]), ("catch_up", True))
        self.assertIn("deep review deferred (a light week is being proposed)", card["tier_reasons"])

    def test_block_reasons_in_a_catch_up_week_keep_the_card_and_record_catch_up(self):
        self.record("2026-08-30", "# Check-in — 2026-08-30 (deep)")
        self.record("2026-10-04", "# Check-in — 2026-10-04 (weekly)")
        reasons = block.status(self.root, today=date(2026, 10, 18))["deep_review"]["reasons"]
        self.assertIn("six_weeks", reasons)
        args = [part for reason in reasons for part in ("--deep-reason", reason)]
        card = self.coach("checkin", "prepare", "--until", "2026-10-18", *args)["data"]["card"]
        self.assertEqual((card["mode"], card["deep_deferred"]), ("catch_up", True))
        tier = checkin.TIER_OF_MODE.get(card["mode"], card["mode"])
        self.coach("checkin", "skeleton", "--date", "2026-10-18", "--tier", tier)
        found = checkin.reviews(self.root)
        self.assertEqual(found[-1].tier, "catch-up")
        self.assertEqual(checkin.mode_for(found, date(2026, 10, 25))[0], "deep")

    def test_record_derived_block_reasons_do_not_repeat_the_card_reasons(self):
        args = ("--deep-reason", "first_close", "--deep-reason", "light_week_proposed")
        card = self.coach("checkin", "prepare", "--until", "2026-10-18", *args)["data"]["card"]
        self.assertEqual(card["tier_reasons"], ["first check-in", "a light week is being proposed"])

    def test_only_a_pure_explicit_deep_request_says_asked_for(self):
        self.record("2026-10-11", "# Check-in — 2026-10-11 (deep)")
        card = self.coach("checkin", "prepare", "--until", "2026-10-18", "--tier", "deep")["data"]["card"]
        self.assertEqual(card["tier_reasons"], ["asked for"])
