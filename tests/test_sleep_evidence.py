import unittest
from datetime import date

from coach import cardio, config as config_module
from coach.activity import records
from coach.activity.store import ActivityStore
from coach.dates import Span
from tests.test_activity_commands import ActivityCase, LOCAL_WELLNESS
from tests.test_activity_store import wellness


class SleepEvidenceTest(ActivityCase):
    def setUp(self):
        super().setUp()
        (self.root / LOCAL_WELLNESS).unlink(missing_ok=True)
        self.span = Span(date(2026, 9, 28), date(2026, 10, 11))

    def summary(self, start="2026-09-28", end="2026-10-11"):
        return self.ok("wellness", "summary", "--from", start, "--to", end)

    def diary(self, hours, source="manual", count=14):
        self.diary_of([hours] * count, source)

    def diary_of(self, nightly_hours, source):
        for day, hours in zip(self.span.days(), nightly_hours):
            if source == "manual":
                self.ok("wellness", "add", "--date", day.isoformat(), "--sleep-hours", str(hours))
            else:
                records.append_lines(self.root / LOCAL_WELLNESS,
                                     [wellness(f"{source}:{day}", day.isoformat(), asleep=hours)])

    def test_complete_manual_and_tracker_diaries_resolve_to_same_gate(self):
        for source in ("manual", "apple_health"):
            for hours, status in ((6.4, "recomp"), (7.0, "passed"), (7.2, "passed")):
                with self.subTest(source=source, hours=hours):
                    (self.root / LOCAL_WELLNESS).unlink(missing_ok=True)
                    self.assertEqual(self.summary()["sleep_gate"]["status"], "pending measurement")
                    self.diary(hours, source)
                    data = self.summary()
                    self.assertEqual(data["sleep_gate"]["status"], status)
                    self.assertEqual(data["sleep"]["avg_asleep_hours"], hours)
                    self.assertEqual(data["sleep"]["nights"], 14)
                    self.assertEqual(data["sleep"]["covered_dates"], [day.isoformat() for day in self.span.days()])
                    self.assertEqual(data["sleep"]["sources"], [source])
                    self.assertTrue(data["sleep"]["complete"])
                    self.assertEqual({item["self_report"] for item in data["sleep"]["evidence"]},
                                     {source == "manual"})

    def test_period_mean_settles_gate_without_manufacturing_nights(self):
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-11", "--sleep-hours", "6.4")
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "recomp")
        self.assertEqual(data["nights"], [])
        self.assertEqual(data["sleep"]["nights"], 0)
        evidence, = data["sleep"]["evidence"]
        self.assertEqual(evidence["span"], self.span.to_json())
        self.assertEqual(evidence["kind"], "period_mean")
        self.assertTrue(evidence["self_report"])
        store = ActivityStore(self.root, config_module.load(self.root))
        settings = {"sleep_short_hours": 7, "sleep_min_nights": 4, "sleep_debt_nights": 3}
        self.assertEqual(cardio.sleep_judgement(store, settings, self.span.end), (0, 0, None))

    def test_display_rounding_does_not_pass_an_under_seven_hour_mean(self):
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-11", "--sleep-hours", "6.999")
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "recomp")
        self.assertEqual(data["sleep"]["avg_asleep_hours"], 6.99)

    def test_varied_diary_averaging_exactly_seven_hours_passes(self):
        for source in ("manual", "apple_health"):
            with self.subTest(source=source):
                (self.root / LOCAL_WELLNESS).unlink(missing_ok=True)
                self.diary_of([6.4] * 7 + [7.6] * 7, source)
                data = self.summary()
                self.assertTrue(data["sleep"]["complete"])
                self.assertEqual(data["sleep"]["avg_asleep_hours"], 7.0)
                self.assertEqual(data["sleep_gate"]["status"], "passed")

    def test_varied_diary_just_under_seven_hours_shows_under_seven_and_resolves_recomp(self):
        self.diary_of([6.4] * 7 + [7.59] * 7, "manual")
        data = self.summary()
        self.assertEqual(data["sleep"]["avg_asleep_hours"], 6.99)
        self.assertEqual(data["sleep_gate"]["status"], "recomp")

    def test_nightly_and_overall_averages_of_the_same_nights_agree(self):
        self.diary_of([6.5, 6.8, 7.2, 6.0, 6.9, 7.5, 7.1], "manual")
        sleep = self.summary(end="2026-10-04")["sleep"]
        self.assertEqual((sleep["avg_asleep_hours"], sleep["nightly_avg_asleep_hours"]), (6.85, 6.85))

    def test_two_complete_period_means_are_weighted_by_their_full_spans(self):
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-01", "--sleep-hours", "6")
        self.ok("wellness", "add", "--from", "2026-10-02", "--to", "2026-10-11", "--sleep-hours", "7.4")
        data = self.summary()
        self.assertEqual(data["sleep"]["avg_asleep_hours"], 7)
        self.assertEqual(data["sleep_gate"]["status"], "passed")
        self.assertEqual(data["sleep"]["nights"], 0)

    def test_incomplete_diary_keeps_missing_dates_and_pending_status(self):
        self.diary(6.4, count=13)
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "pending measurement")
        self.assertEqual(data["sleep"]["missing_dates"], ["2026-10-11"])
        self.assertEqual(data["sleep"]["nights"], 13)
        self.assertFalse(data["sleep"]["complete"])

    def test_subjective_quality_and_time_in_bed_cannot_supply_asleep_hours(self):
        self.cli("wellness", "add", "--date", "2026-10-11", "--sleep-hours", "sleep felt fine", expect=2)
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-11", "--in-bed-hours", "8")
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "pending measurement")
        self.assertIsNone(data["sleep"]["avg_asleep_hours"])

    def test_time_in_bed_only_nights_leave_a_complete_period_mean_to_settle_the_gate(self):
        records.append_lines(self.root / LOCAL_WELLNESS, [
            wellness(f"apple_health:{day}", day.isoformat(),
                     sleep={"asleep_hours": None, "in_bed_hours": 8, "start": None, "end": None})
            for day in self.span.days()])
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-11", "--sleep-hours", "6.4")
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "recomp")
        evidence, = data["sleep"]["evidence"]
        self.assertEqual((evidence["kind"], evidence["span"]), ("period_mean", self.span.to_json()))
        self.assertTrue(evidence["included_in_average"])
        self.assertEqual(data["sleep"]["nights"], 0)
        store = ActivityStore(self.root, config_module.load(self.root))
        settings = {"sleep_short_hours": 7, "sleep_min_nights": 4, "sleep_debt_nights": 3}
        self.assertEqual(cardio.sleep_judgement(store, settings, self.span.end), (0, 0, None))

    def test_a_lower_ranked_night_with_hours_asleep_beats_time_in_bed_only(self):
        self.ok("wellness", "add", "--date", "2026-10-11", "--in-bed-hours", "8")
        records.append_lines(self.root / LOCAL_WELLNESS,
                             [wellness("apple_health:2026-10-11", "2026-10-11", asleep=6.5)])
        data = self.summary(start="2026-10-11")
        self.assertEqual(data["sleep"]["avg_asleep_hours"], 6.5)
        self.assertEqual(data["sleep"]["nights"], 1)
        self.assertEqual([(night["asleep_hours"], night["source"]) for night in data["nights"]],
                         [(6.5, "apple_health")])
        store = ActivityStore(self.root, config_module.load(self.root))
        settings = {"sleep_short_hours": 7, "sleep_min_nights": 1, "sleep_debt_nights": 1}
        self.assertEqual(cardio.sleep_judgement(store, settings, date(2026, 10, 11)), (1, 1, True))

    def test_clipped_or_partly_replaced_mean_cannot_fill_unknown_nights(self):
        self.ok("wellness", "add", "--from", "2026-09-28", "--to", "2026-10-11", "--sleep-hours", "6.4")
        clipped = self.summary(start="2026-10-01")
        self.assertIsNone(clipped["sleep"]["avg_asleep_hours"])
        self.assertEqual(clipped["sleep"]["evidence"][0]["span"], self.span.to_json())
        self.ok("wellness", "add", "--date", "2026-10-11", "--sleep-hours", "8")
        data = self.summary()
        self.assertEqual(data["sleep_gate"]["status"], "pending measurement")
        self.assertEqual(data["sleep"]["covered_dates"], ["2026-10-11"])
        self.assertFalse(data["sleep"]["evidence"][0]["included_in_average"])
        self.assertEqual(len(data["nights"]), 1)

    def test_complete_old_period_does_not_settle_current_gate(self):
        self.ok("wellness", "add", "--from", "2026-09-01", "--to", "2026-09-14", "--sleep-hours", "7.2")
        data = self.summary("2026-09-01", "2026-09-14")
        self.assertTrue(data["sleep"]["complete"])
        self.assertEqual(data["sleep_gate"]["status"], "pending measurement")
        self.assertEqual(data["sleep_gate"]["span"], self.span.to_json())

    def test_disabled_activity_explains_approved_manual_setup(self):
        path = self.root / "config.toml"
        path.write_text(path.read_text().replace("[activity]\nenabled = true", "[activity]\nenabled = false"))
        result = self.cli("wellness", "summary", expect=5)
        message = result["error"]["message"]
        for text in ("/setup", "athlete's approval", "enabled = true", "config validate", "no watch"):
            self.assertIn(text, message)


if __name__ == "__main__":
    unittest.main()
