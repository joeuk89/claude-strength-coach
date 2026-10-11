import unittest
from datetime import date
from types import SimpleNamespace

from coach import dates
from coach.dates import Span, iso_week, parse_date, parse_week, today, week_span


class ParseDateTest(unittest.TestCase):
    def test_parses_iso_date(self):
        self.assertEqual(parse_date("2026-10-11"), date(2026, 10, 11))

    def test_rejects_other_shapes(self):
        for text in ("2026-10-1", "11/10/2026", "2026-13-01", "20261011", "", "2026-10-11T00:00:00"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    parse_date(text)


class WeekTest(unittest.TestCase):
    def test_iso_week(self):
        self.assertEqual(iso_week(date(2026, 10, 11)), "2026-W41")
        self.assertEqual(iso_week(date(2026, 10, 12)), "2026-W42")
        self.assertEqual(iso_week(date(2027, 1, 1)), "2026-W53")

    def test_monday_week(self):
        span = week_span(date(2026, 10, 11), "monday")
        self.assertEqual(span, Span(date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(span.label(), "2026-W41")

    def test_sunday_week(self):
        span = week_span(date(2026, 10, 11), "sunday")
        self.assertEqual(span, Span(date(2026, 10, 11), date(2026, 10, 17)))
        self.assertEqual(span.label(), "2026-W42")
        self.assertEqual(week_span(date(2026, 10, 10), "sunday"), Span(date(2026, 10, 4), date(2026, 10, 10)))

    def test_rejects_unknown_week_start(self):
        with self.assertRaises(ValueError):
            week_span(date(2026, 10, 11), "saturday")

    def test_parse_week_takes_a_label_or_a_date(self):
        self.assertEqual(parse_week("2026-W41", "monday"), Span(date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(parse_week("2026-10-08", "monday"), Span(date(2026, 10, 5), date(2026, 10, 11)))
        self.assertEqual(parse_week("2026-W42", "sunday"), Span(date(2026, 10, 11), date(2026, 10, 17)))
        with self.assertRaises(ValueError):
            parse_week("2026-W54", "monday")
        with self.assertRaises(ValueError):
            parse_week("week 41", "monday")


class SpanTest(unittest.TestCase):
    def test_contains_overlaps_days(self):
        span = Span(date(2026, 10, 12), date(2026, 10, 18))
        self.assertTrue(span.contains(date(2026, 10, 12)))
        self.assertTrue(span.contains(date(2026, 10, 18)))
        self.assertFalse(span.contains(date(2026, 10, 19)))
        self.assertTrue(span.overlaps(Span(date(2026, 10, 18), date(2026, 10, 20))))
        self.assertFalse(span.overlaps(Span(date(2026, 10, 19), date(2026, 10, 20))))
        self.assertEqual(len(span.days()), 7)
        self.assertEqual(span.days()[0], date(2026, 10, 12))
        self.assertEqual(span.to_json(), {"start": "2026-10-12", "end": "2026-10-18"})

    def test_rejects_reversed_span(self):
        with self.assertRaises(ValueError):
            Span(date(2026, 10, 18), date(2026, 10, 12))


def _ctx(now, timezone=None):
    return SimpleNamespace(now=lambda: now, timezone=lambda: timezone)


class TodayTest(unittest.TestCase):
    def test_coach_now_in_utc(self):
        now = dates.parse_timestamp("2026-10-11T18:00:00Z")
        self.assertEqual(today(_ctx(now, dates.zone("UTC"))), date(2026, 10, 11))

    def test_timezone_moves_the_date(self):
        now = dates.parse_timestamp("2026-10-11T23:30:00Z")
        self.assertEqual(today(_ctx(now, dates.zone("Australia/Sydney"))), date(2026, 10, 12))
        self.assertEqual(today(_ctx(now, dates.zone("America/New_York"))), date(2026, 10, 11))

    def test_parse_timestamp(self):
        self.assertEqual(dates.parse_timestamp("2026-10-11T18:00:00Z").utcoffset().total_seconds(), 0)
        self.assertEqual(dates.parse_timestamp("2026-10-11T18:00:00").utcoffset().total_seconds(), 0)
        with self.assertRaises(ValueError):
            dates.parse_timestamp("yesterday")

    def test_unknown_zone(self):
        with self.assertRaises(ValueError):
            dates.zone("Mars/Olympus")


if __name__ == "__main__":
    unittest.main()
