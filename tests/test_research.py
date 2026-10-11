import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from coach import jsonio, missed, program, research, stats, structure
from coach.validate import check_schema
from tests.support import INSTANCES, MINIMAL_CONFIG, REPO_ROOT, VALID, TempInstance, run_cli, run_module

NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}
TODAY = date(2026, 10, 11)
RESEARCH_CHECKS = ("research_notes", "research_citations", "research_render_fresh", "research_expiry")
DOSE = "research/fixture-dose.md"
KNEE = "research/local/local-fixture-knee.md"
GUIDE = "reference/fixture-guide.md"
CHECKIN = "check-ins/2026-08-30.md"
DISCLAIMER = "This note does not replace assessment by a qualified professional."

RETIRE_DOSE_2 = ('n = 2\ntext = "The fixture program caps one session at 6 hard sets per muscle."\n'
                 'basis = "evidence"\nsources = ["fixture-rct-2025"]\nstatus = "current"',
                 'n = 2\ntext = "The fixture program caps one session at 6 hard sets per muscle."\n'
                 'basis = "evidence"\nsources = ["fixture-rct-2025"]\nstatus = "retired"\nretired_on = 2026-10-05')


def note_text(note_id, *, written="2026-04-01", review_by="2026-10-01", areas='["sleep"]', extra="",
              body="## Answer\n\nA synthetic note.\n"):
    return (
        "<!-- coach:note\n"
        "schema_version = 1\n"
        f'id = "{note_id}"\n'
        'topic = "Synthetic"\n'
        'question = "A synthetic question?"\n'
        f"written = {written}\n"
        f"review_by = {review_by}\n"
        'confidence = "moderate"\n'
        f"applies_to = {areas}\n"
        f"{extra}"
        "\n[[claims]]\n"
        "n = 1\n"
        'text = "A synthetic heuristic."\n'
        'basis = "heuristic"\n'
        "sources = []\n"
        'status = "current"\n'
        "-->\n\n"
        f"{body}"
    )


class InstanceCase(unittest.TestCase):
    """Each test works on a fresh copy of the valid instance."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "instance"
        shutil.copytree(VALID, self.root)

    def path(self, rel):
        return self.root / rel

    def read(self, rel):
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel, text):
        target = self.path(rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def edit(self, rel, old, new):
        text = self.read(rel)
        self.assertIn(old, text, f"{old!r} not in {rel}")
        self.write(rel, text.replace(old, new, 1))

    def append(self, rel, text):
        self.write(rel, (self.read(rel) if self.path(rel).exists() else "") + text)

    def coach(self, *argv):
        return run_cli(["--root", str(self.root), *argv], env=NOW)

    def checks(self):
        """Run `coach check`; return (exit code, {check id: [statuses]}, rows)."""
        code, envelope, stderr = self.coach("check")
        self.assertIn(code, (0, 1), (envelope, stderr))
        rows = envelope["data"]["results"]
        statuses = {}
        for row in rows:
            statuses.setdefault(row["id"], []).append(row["status"])
        return code, statuses, rows

    def assert_only_notes_fail(self, fragment=None):
        code, statuses, rows = self.checks()
        self.assertEqual(code, 1, rows)
        failing = sorted({row["id"] for row in rows if row["status"] == "fail"})
        self.assertEqual(failing, ["research_notes"], rows)
        if fragment:
            messages = " ".join(row["message"] for row in rows if row["id"] == "research_notes")
            self.assertIn(fragment, messages)
        return rows

    def render(self):
        code, envelope, stderr = self.coach("research", "render")
        self.assertEqual(code, 0, (envelope, stderr))


class ValidInstanceTest(InstanceCase):
    def test_check_passes_with_all_four_research_checks(self):
        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        for check_id in RESEARCH_CHECKS:
            self.assertEqual(statuses[check_id], ["pass"], (check_id, rows))

    def test_check_from_the_command_line(self):
        code, envelope, stderr = run_module(["--root", str(VALID), "check"], env=NOW)
        self.assertEqual(code, 0, (envelope, stderr))
        statuses = {row["id"]: row["status"] for row in envelope["data"]["results"]}
        for check_id in RESEARCH_CHECKS:
            self.assertEqual(statuses[check_id], "pass")

    def test_shipped_fixture_regions_are_fresh(self):
        for rel in (DOSE, KNEE):
            note_id = Path(rel).stem
            self.assertIn(research.render_research(VALID, note_id), (VALID / rel).read_text(encoding="utf-8"))


class StatusCommandTest(InstanceCase):
    def test_lists_both_kinds_and_local_supersession(self):
        code, envelope, _ = self.coach("research", "status")
        self.assertEqual(code, 0, envelope)
        data = envelope["data"]
        self.assertEqual(data["today"], "2026-10-11")
        kinds = {note["id"]: note["kind"] for note in data["notes"]}
        self.assertEqual(kinds, {"fixture-dose": "template", "local-fixture-knee": "local"})
        self.assertEqual(data["superseded_locally"], [{"ref": "rn:fixture-dose.2", "by": "local-fixture-knee"}])
        self.assertEqual(data["areas"], {"rehab": "current", "volume": "current"})
        self.assertEqual(data["summary"], {"current": 2, "due_soon": 0, "expired": 0})

    def test_note_fields(self):
        _, envelope, _ = self.coach("research", "status")
        dose = next(note for note in envelope["data"]["notes"] if note["id"] == "fixture-dose")
        self.assertEqual(dose, {
            "id": "fixture-dose", "kind": "template", "topic": "Fixture dose", "path": DOSE,
            "written": "2026-09-01", "review_by": "2028-03-01", "status": "current", "days_to_review": 507,
            "confidence": "moderate", "applies_to": ["volume"], "tags": ["fixture"],
            "claims": 2, "retired_claims": 0, "cited_by": 2, "updates": [],
        })

    def test_filters(self):
        _, envelope, _ = self.coach("research", "status", "--kind", "local")
        self.assertEqual([note["id"] for note in envelope["data"]["notes"]], ["local-fixture-knee"])
        _, envelope, _ = self.coach("research", "status", "--area", "volume")
        self.assertEqual([note["id"] for note in envelope["data"]["notes"]], ["fixture-dose"])
        _, envelope, _ = self.coach("research", "status", "--expired")
        self.assertEqual(envelope["data"]["notes"], [])

    def test_unknown_area_is_a_usage_error_naming_all_known_areas(self):
        code, envelope, _ = self.coach("research", "status", "--area", "bogus")
        self.assertEqual(code, 2)
        self.assertEqual(envelope["error"]["code"], "usage")
        schema = jsonio.load_schema("research_note")
        for area in schema["properties"]["applies_to"]["items"]["enum"]:
            self.assertIn(area, envelope["error"]["message"])

    def test_known_area_without_notes_is_an_honest_empty_result(self):
        code, envelope, _ = self.coach("research", "status", "--area", "sleep")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["notes"], [])
        self.assertNotIn("sleep", envelope["data"]["areas"])

    def test_invalid_note_exits_1(self):
        self.edit(DOSE, "\nn = 2\n", "\nn = 1\n")
        code, envelope, _ = self.coach("research", "status")
        self.assertEqual(code, 1)
        self.assertEqual(envelope["error"]["code"], "validation")


class ShowCommandTest(InstanceCase):
    def test_superseded_claim_names_the_local_note(self):
        code, envelope, _ = self.coach("research", "show", "rn:fixture-dose.2")
        self.assertEqual(code, 0, envelope)
        data = envelope["data"]
        self.assertEqual(data["superseded_locally_by"], "local-fixture-knee")
        self.assertEqual(data["claim"]["n"], 2)
        self.assertEqual([source["id"] for source in data["sources"]], ["fixture-rct-2025"])
        self.assertEqual(data["sources"][0]["url"], "https://doi.org/10.0000/fixture-rct-2025")
        self.assertEqual(data["note"]["status"], "current")

    def test_claim_ref_without_the_rn_prefix(self):
        code, envelope, _ = self.coach("research", "show", "fixture-dose.2")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["ref"], "rn:fixture-dose.2")

    def test_unknown_claim_exits_1(self):
        code, envelope, _ = self.coach("research", "show", "rn:fixture-dose.9")
        self.assertEqual(code, 1)
        self.assertIn("rn:fixture-dose.9", envelope["error"]["message"])

    def test_note_id(self):
        code, envelope, _ = self.coach("research", "show", "local-fixture-knee")
        self.assertEqual(code, 0, envelope)
        data = envelope["data"]
        self.assertEqual(data["note"]["path"], KNEE)
        self.assertEqual(data["note"]["status"], "current")
        self.assertEqual(data["data"]["updates"], ["rn:fixture-dose.2"])
        self.assertEqual(data["data"]["written"], "2026-10-01")
        self.assertEqual(self.coach("research", "show", "no-such-note")[0], 1)

    def test_retired_claim_is_shown(self):
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.render()
        code, envelope, _ = self.coach("research", "show", "rn:fixture-dose.2")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["claim"]["status"], "retired")


class CitationTest(InstanceCase):
    def citation_rows(self):
        _, _, rows = self.checks()
        return [row for row in rows if row["id"] == "research_citations"]

    def assert_framework_fails(self, ref, fragment):
        self.append(GUIDE, f"\nA second line.\nIt cites {ref} here.\n")
        code, statuses, rows = self.checks()
        self.assertEqual(code, 1, rows)
        failing = [row for row in rows if row["status"] == "fail"]
        self.assertEqual({row["id"] for row in failing}, {"research_citations"}, rows)
        message = failing[0]["message"]
        self.assertIn(GUIDE, message)
        self.assertIn(":8", message)
        self.assertIn(ref, message)
        self.assertIn(fragment, message)
        self.assertEqual(failing[0]["path"], GUIDE)

    def test_framework_citing_a_missing_claim_fails(self):
        self.assert_framework_fails("rn:fixture-dose.9", "does not exist")
        code, envelope, _ = self.coach("research", "cites", "--unresolved")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["citations"], [
            {"ref": "rn:fixture-dose.9", "path": GUIDE, "line": 8, "scope": "framework",
             "resolved": False, "retired": False},
        ])

    def test_framework_citing_a_retired_claim_fails(self):
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.render()
        self.assert_framework_fails("rn:fixture-dose.2", "retired")

    def test_framework_citing_a_local_claim_fails(self):
        self.assert_framework_fails("rn:local-fixture-knee.1", "local")

    def test_cites_lists_every_reference(self):
        code, envelope, _ = self.coach("research", "cites")
        self.assertEqual(code, 0, envelope)
        found = {(c["ref"], c["path"], c["scope"], c["resolved"]) for c in envelope["data"]["citations"]}
        self.assertEqual(found, {
            ("rn:fixture-dose.1", GUIDE, "framework", True),
            ("rn:local-fixture-knee.1", CHECKIN, "instance", True),
            ("rn:fixture-dose.2", KNEE, "instance", True),
        })

    def test_profile_citing_a_missing_claim_warns(self):
        self.write("profile.md", "# Profile\n\nQuads cap (rn:local-fixture-knee.7).\n")
        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        self.assertEqual(statuses["research_citations"], ["warn"])
        warning = next(row for row in rows if row["id"] == "research_citations")
        self.assertIn("profile.md:3", warning["message"])

    def test_checkin_citing_a_retired_claim_passes(self):
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.edit(KNEE, 'updates = ["rn:fixture-dose.2"]\n', "")
        self.render()
        self.append(CHECKIN, "\nThe old cap was 6 sets (rn:fixture-dose.2).\n")
        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        self.assertEqual(statuses["research_citations"], ["pass"], rows)

    def test_profile_citing_a_retired_claim_warns(self):
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.edit(KNEE, 'updates = ["rn:fixture-dose.2"]\n', "")
        self.render()
        self.write("profile.md", "Old cap (rn:fixture-dose.2).\n")
        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        self.assertEqual(statuses["research_citations"], ["warn"], rows)

    def test_scan_citations_fields(self):
        found = research.scan_citations(self.root)
        guide = next(c for c in found if c.path == GUIDE)
        self.assertEqual(guide.to_json(), {"ref": "rn:fixture-dose.1", "path": GUIDE, "line": 5,
                                           "scope": "framework", "resolved": True, "retired": False})

    def test_several_references_on_one_line(self):
        self.write("profile.md", "Caps (rn:fixture-dose.1, rn:fixture-dose.2).\n")
        refs = [c.ref for c in research.scan_citations(self.root) if c.path == "profile.md"]
        self.assertEqual(refs, ["rn:fixture-dose.1", "rn:fixture-dose.2"])


class TemplateRepoTest(unittest.TestCase):
    def test_every_reference_in_the_template_resolves(self):
        notes = research.load_notes(REPO_ROOT)
        citations = research.scan_citations(REPO_ROOT)
        unresolved = [c.to_json() for c in citations if not c.resolved]
        self.assertEqual(unresolved, [])
        self.assertTrue(all(c.scope == "framework" for c in citations if c.path.startswith("coach/")))
        self.assertEqual([n for n in notes if n.kind == "local"], [])

    def test_every_shipped_note_is_valid_and_rendered(self):
        notes, problems, _ = research.load_all(REPO_ROOT)
        self.assertEqual([p.message for p in problems], [])
        stale = [note.id for note in notes if research.region_in(note) != research.render_note(note)]
        self.assertEqual(stale, [])

    def test_schema_uses_only_the_supported_subset(self):
        check_schema(jsonio.load_schema("research_note"))

    def test_dose_defaults_cite_their_claims(self):
        notes = research.load_notes(REPO_ROOT)
        fold = research.resolve("rn:minimum-effective-dose.5", notes)
        self.assertIsNotNone(fold)
        self.assertEqual(fold.basis, "heuristic")
        self.assertEqual(fold.sources, ("spiering-2021", "androulakis-korakakis-2020"))
        for module, refs in ((structure, ("rn:volume-frequency.1", "rn:volume-frequency.3")),
                             (missed, ("rn:minimum-effective-dose.5",))):
            for ref in refs:
                with self.subTest(module=module.__name__, ref=ref):
                    self.assertIn(ref, module.__doc__)
        contract = (REPO_ROOT / "docs/design/coach-contract.md").read_text(encoding="utf-8")
        c37 = contract.split("## C37.", 1)[1].split("\n## C38.", 1)[0]
        self.assertIn("rn:minimum-effective-dose.5", c37)

    def test_the_priority_floor_default_cites_its_claim(self):
        self.assertIn("rn:minimum-effective-dose.4", program.normalised.__doc__)
        contract = (REPO_ROOT / "docs/design/coach-contract.md").read_text(encoding="utf-8")
        c40 = contract.split("## C40.", 1)[1].split("\n## C41.", 1)[0]
        self.assertIn("`floor.sets` default 2 (rn:minimum-effective-dose.4)", c40)
        cited = {c.ref for c in research.scan_citations(REPO_ROOT) if c.path == "coach/program.py"}
        self.assertIn("rn:minimum-effective-dose.4", cited)

    def test_dose_default_values_are_unchanged(self):
        self.assertEqual((structure.DEFAULT_TARGET, structure.SESSION_CEILING), (10, 11.0))
        self.assertEqual(stats.SECONDARY_WEIGHT, 0.5)
        self.assertEqual(missed.DEFAULT_FOLD_SETS, 2)
        self.assertEqual(program._FLOOR_DEFAULTS, {"sets": 2, "rpe": None})


class NoteValidationTest(InstanceCase):
    def test_arrow_inside_the_block(self):
        self.edit(DOSE, 'topic = "Fixture dose"', 'topic = "Fixture --> dose"')
        self.assert_only_notes_fail("contains '-->'")

    def test_review_by_before_written(self):
        self.edit(DOSE, "review_by = 2028-03-01", "review_by = 2026-08-01")
        self.assert_only_notes_fail("is before written")

    def test_review_by_more_than_24_months_after_written(self):
        self.edit(DOSE, "review_by = 2028-03-01", "review_by = 2028-09-02")
        self.assert_only_notes_fail("24 months")

    def test_review_by_exactly_24_months_after_written_is_valid(self):
        self.edit(DOSE, "review_by = 2028-03-01", "review_by = 2028-09-01")
        self.render()
        self.assertEqual(self.checks()[1]["research_notes"], ["pass"])

    def test_unknown_source_id(self):
        self.edit(DOSE, 'sources = ["fixture-rct-2025"]', 'sources = ["fixture-rct-2052"]')
        self.assert_only_notes_fail("fixture-rct-2052")

    def test_duplicate_claim_number(self):
        self.edit(DOSE, "\nn = 2\n", "\nn = 1\n")
        self.assert_only_notes_fail("more than one claim numbered 1")

    def test_duplicate_source_id(self):
        self.edit(DOSE, 'id = "fixture-rct-2025"', 'id = "fixture-meta-2024"')
        self.assert_only_notes_fail("more than one source")

    def test_id_differs_from_stem(self):
        self.edit(DOSE, 'id = "fixture-dose"', 'id = "fixture-doses"')
        self.assert_only_notes_fail("file name")

    def test_template_id_with_local_prefix(self):
        self.write("research/local-misplaced.md", note_text("local-misplaced", review_by="2027-10-01"))
        self.assert_only_notes_fail("must not start 'local-'")

    def test_local_id_without_prefix(self):
        self.write("research/local/knee.md", note_text("knee", review_by="2027-10-01"))
        self.assert_only_notes_fail("must start 'local-'")

    def test_evidence_claim_without_sources(self):
        self.edit(DOSE, 'sources = ["fixture-meta-2024"]', "sources = []")
        self.assert_only_notes_fail("needs at least one source")

    def test_template_note_without_areas(self):
        self.edit(DOSE, 'applies_to = ["volume"]\n', "")
        self.assert_only_notes_fail("at least one area in applies_to")

    def test_local_note_without_areas_or_tags(self):
        self.edit(KNEE, 'applies_to = ["rehab"]\ntags = ["knee"]\n', "applies_to = []\n")
        self.assert_only_notes_fail("or one tag")

    def test_local_note_with_tags_only_is_valid(self):
        self.edit(KNEE, 'applies_to = ["rehab"]\n', "")
        self.render()
        self.assertEqual(self.checks()[1]["research_notes"], ["pass"])

    def test_rehab_note_without_the_disclaimer(self):
        self.edit(KNEE, DISCLAIMER + "\n", "")
        self.assert_only_notes_fail(DISCLAIMER)

    def test_updates_on_a_template_note(self):
        self.edit(DOSE, 'tags = ["fixture"]\n', 'tags = ["fixture"]\nupdates = ["rn:fixture-dose.1"]\n')
        self.assert_only_notes_fail("local notes only")

    def test_updates_naming_a_local_claim(self):
        self.edit(KNEE, 'updates = ["rn:fixture-dose.2"]', 'updates = ["rn:local-fixture-knee.1"]')
        self.assert_only_notes_fail("template claim")

    def test_schema_violation(self):
        self.edit(DOSE, 'basis = "evidence"', 'basis = "anecdote"')
        self.assert_only_notes_fail("$.claims[0].basis")

    def test_newer_schema_version(self):
        self.edit(DOSE, "schema_version = 1", "schema_version = 2")
        self.assert_only_notes_fail("/framework-sync")

    def test_impossible_date(self):
        self.edit(DOSE, "review_by = 2028-03-01", 'review_by = "2028-02-30"')
        self.assert_only_notes_fail("not a real date")

    def test_claim_number_with_a_decimal_point(self):
        self.edit(DOSE, "\nn = 2\n", "\nn = 2.0\n")
        self.assert_only_notes_fail("whole number")

    def test_retired_claim_needs_retired_on(self):
        self.edit(DOSE, 'sources = ["fixture-rct-2025"]\nstatus = "current"',
                  'sources = ["fixture-rct-2025"]\nstatus = "retired"')
        self.assert_only_notes_fail("retired_on")

    def test_datablock_errors_name_the_file(self):
        cases = {
            "no opener": lambda text: "# Fixture dose\n" + text.split("\n", 1)[1],
            "no closer": lambda text: text.replace("\n-->\n", "\n", 1),
            "card opener": lambda text: text.replace("<!-- coach:note", "<!-- coach:card", 1),
            "invalid toml": lambda text: text.replace('topic = "Fixture dose"', "topic = Fixture dose", 1),
        }
        original = self.read(DOSE)
        for name, mutate in cases.items():
            with self.subTest(case=name):
                self.write(DOSE, mutate(original))
                rows = self.assert_only_notes_fail()
                failing = [row for row in rows if row["status"] == "fail"]
                self.assertEqual(len(failing), 1, failing)
                self.assertIn("fixture-dose.md", failing[0]["message"])
                self.assertEqual(failing[0]["path"], DOSE)

    def test_updates_naming_a_retired_claim_warns(self):
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.render()
        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        self.assertEqual(statuses["research_notes"], ["warn"], rows)
        warning = next(row for row in rows if row["id"] == "research_notes")
        self.assertIn("rn:fixture-dose.2", warning["message"])
        self.assertEqual(warning["path"], KNEE)

    def test_load_notes_raises_on_an_invalid_note(self):
        self.edit(DOSE, "\nn = 2\n", "\nn = 1\n")
        with self.assertRaises(research.ValidationError):
            research.load_notes(self.root)

    def test_validate_command(self):
        code, envelope, _ = self.coach("research", "validate")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["valid"], 2)
        self.edit(DOSE, "\nn = 2\n", "\nn = 1\n")
        code, envelope, _ = self.coach("research", "validate")
        self.assertEqual(code, 1)
        self.assertEqual(envelope["error"]["details"][0]["path"], DOSE)


class ExpiryTest(InstanceCase):
    OLD = "research/fixture-old.md"

    def add_old_note(self, review_by="2026-10-01"):
        self.write(self.OLD, note_text("fixture-old", review_by=review_by))
        self.render()

    def test_expired_area(self):
        self.add_old_note()
        _, envelope, _ = self.coach("research", "status")
        self.assertEqual(envelope["data"]["areas"]["sleep"], "expired")
        old = next(note for note in envelope["data"]["notes"] if note["id"] == "fixture-old")
        self.assertEqual((old["status"], old["days_to_review"]), ("expired", -10))
        _, envelope, _ = self.coach("research", "status", "--expired")
        self.assertEqual([note["id"] for note in envelope["data"]["notes"]], ["fixture-old"])

        code, statuses, rows = self.checks()
        self.assertEqual(code, 0, rows)
        self.assertEqual(statuses["research_expiry"], ["warn"])
        warning = next(row for row in rows if row["id"] == "research_expiry")
        self.assertIn("sleep", warning["message"])
        self.assertIn("fixture-old", warning["message"])
        self.assertEqual(research.expired_by_area(self.root, TODAY), {"sleep": ["fixture-old"]})

    def test_current_local_note_keeps_the_area_current(self):
        self.add_old_note()
        self.write("research/local/local-sleep.md",
                   note_text("local-sleep", written="2026-10-10", review_by="2027-10-10"))
        self.render()
        self.assertEqual(research.expired_by_area(self.root, TODAY), {})
        _, envelope, _ = self.coach("research", "status")
        self.assertEqual(envelope["data"]["areas"]["sleep"], "current")
        self.assertEqual(self.checks()[1]["research_expiry"], ["pass"])

    def test_due_soon(self):
        self.add_old_note(review_by="2026-11-30")
        _, envelope, _ = self.coach("research", "status")
        self.assertEqual(envelope["data"]["areas"]["sleep"], "due_soon")
        self.assertEqual(envelope["data"]["summary"], {"current": 2, "due_soon": 1, "expired": 0})
        self.assertEqual(self.checks()[1]["research_expiry"], ["pass"])

    def test_local_updates_cover_an_expired_template_note(self):
        self.edit(DOSE, "written = 2026-09-01\nreview_by = 2028-03-01", "written = 2025-04-01\nreview_by = 2026-10-01")
        self.render()
        self.assertEqual(research.expired_by_area(self.root, TODAY), {})

    def test_expired_local_note_stops_superseding(self):
        self.edit(KNEE, "written = 2026-10-01\nreview_by = 2027-10-01", "written = 2025-10-01\nreview_by = 2026-10-01")
        self.render()
        self.assertEqual(research.local_updates(self.root, TODAY), {})
        self.assertEqual(research.expired_by_area(self.root, TODAY), {"rehab": ["local-fixture-knee"]})

    def test_local_updates(self):
        self.assertEqual(research.local_updates(self.root, TODAY), {"rn:fixture-dose.2": "local-fixture-knee"})


class NoteStatusTest(unittest.TestCase):
    def note(self, review_by):
        return research.Note(id="x", kind="template", path="research/x.md", topic="X", question="X?",
                             written=date(2025, 1, 1), review_by=review_by, confidence="moderate",
                             applies_to=(), tags=(), updates=(), sources=(), claims=(), data={}, rest="")

    def test_thresholds(self):
        cases = [
            (date(2026, 10, 10), "expired"),
            (date(2026, 10, 11), "due_soon"),
            (date(2026, 12, 10), "due_soon"),
            (date(2026, 12, 11), "current"),
        ]
        for review_by, expected in cases:
            with self.subTest(review_by=review_by):
                self.assertEqual(research.note_status(self.note(review_by), TODAY), expected)


class ResolveTest(InstanceCase):
    def test_resolve(self):
        notes = research.load_notes(self.root)
        self.assertEqual(research.resolve("rn:fixture-dose.1", notes).n, 1)
        self.assertIsNone(research.resolve("rn:fixture-dose.9", notes))
        self.assertIsNone(research.resolve("rn:nothing.1", notes))
        self.edit(DOSE, *RETIRE_DOSE_2)
        self.render()
        self.assertIsNone(research.resolve("rn:fixture-dose.2", research.load_notes(self.root)))


class RenderTest(InstanceCase):
    TABLE_ROW = "| 1 | The fixture program aims for 10 hard sets per muscle per week. |"

    def split(self, text, note_id="fixture-dose"):
        begin = text.index(f"<!-- coach:begin research {note_id} -->")
        end_marker = f"<!-- coach:end research {note_id} -->"
        end = text.index(end_marker) + len(end_marker)
        return text[:begin], text[begin:end], text[end:]

    def test_hand_edit_fails_and_render_restores(self):
        original = self.read(DOSE)
        self.edit(DOSE, self.TABLE_ROW, self.TABLE_ROW.replace("10 hard sets", "12 hard sets"))
        edited = self.read(DOSE)

        code, statuses, rows = self.checks()
        self.assertEqual(code, 1, rows)
        self.assertEqual(statuses["research_render_fresh"], ["fail"])
        self.assertEqual({row["id"] for row in rows if row["status"] == "fail"}, {"research_render_fresh"})

        code, envelope, _ = self.coach("research", "render", "--dry-run")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"], {"dry_run": True, "notes": [
            {"id": "fixture-dose", "path": DOSE, "changed": True},
            {"id": "local-fixture-knee", "path": KNEE, "changed": False},
        ]})
        self.assertEqual(self.read(DOSE), edited)

        code, envelope, _ = self.coach("research", "render", "fixture-dose")
        self.assertEqual(code, 0, envelope)
        self.assertEqual(envelope["data"]["notes"], [{"id": "fixture-dose", "path": DOSE, "changed": True}])
        restored = self.read(DOSE)
        self.assertEqual(restored, original)
        head, _, prose = self.split(restored)
        edited_head, _, edited_prose = self.split(edited)
        self.assertEqual((head, prose), (edited_head, edited_prose))
        self.assertEqual(self.checks()[1]["research_render_fresh"], ["pass"])

    def test_render_leaves_the_data_block_and_prose_byte_identical(self):
        self.edit(DOSE, "## Open questions\n\nNone.\n", "## Open questions\n\nNone yet.  \n\n\n")
        self.edit(DOSE, 'text = "The fixture program aims for 10', 'text = "The fixture program aims for 11')
        before = self.read(DOSE)
        self.coach("research", "render", "fixture-dose")
        after = self.read(DOSE)
        self.assertNotEqual(before, after)
        self.assertEqual(self.split(before)[0], self.split(after)[0])
        self.assertEqual(self.split(before)[2], self.split(after)[2])
        self.assertIn("aims for 11 hard sets", self.split(after)[1])

    def test_render_inserts_a_missing_region_after_the_block(self):
        self.write("research/fixture-new.md", note_text("fixture-new", review_by="2027-10-01"))
        self.assertEqual(self.checks()[1]["research_render_fresh"], ["fail"])
        self.coach("research", "render", "fixture-new")
        text = self.read("research/fixture-new.md")
        self.assertIn("-->\n<!-- coach:begin research fixture-new -->\n", text)
        self.assertTrue(text.endswith("<!-- coach:end research fixture-new -->\n\n## Answer\n\nA synthetic note.\n"))
        self.assertEqual(self.checks()[1]["research_render_fresh"], ["pass"])

    def test_region_contents(self):
        region = research.render_research(self.root, "fixture-dose")
        self.assertTrue(region.startswith("<!-- coach:begin research fixture-dose -->\n"))
        self.assertTrue(region.endswith("\n<!-- coach:end research fixture-dose -->"))
        self.assertIn("**Template note** · written 2026-09-01 · review by 2028-03-01", region)
        self.assertIn(self.TABLE_ROW, region)
        self.assertIn("[Fixture C. A synthetic trial used only by the coach test suite. "
                      "Test Data J. 2025;2:11-20.](<https://doi.org/10.0000/fixture-rct-2025>)", region)
        knee = research.render_research(self.root, "local-fixture-knee")
        self.assertIn("**Local note**", knee)
        self.assertIn("updates rn:fixture-dose.2", knee)

    def test_render_unknown_note_exits_1(self):
        self.assertEqual(self.coach("research", "render", "no-such-note")[0], 1)

    def test_render_refuses_an_invalid_note(self):
        self.edit(DOSE, "\nn = 2\n", "\nn = 1\n")
        before = self.read(DOSE)
        self.assertEqual(self.coach("research", "render", "fixture-dose")[0], 1)
        self.assertEqual(self.read(DOSE), before)

    def test_region_with_no_end_marker_fails(self):
        self.edit(DOSE, "<!-- coach:end research fixture-dose -->", "")
        code, statuses, rows = self.checks()
        self.assertEqual(statuses["research_render_fresh"], ["fail"])


class NoResearchDirectoryTest(unittest.TestCase):
    def test_all_four_checks_skip(self):
        with TempInstance(MINIMAL_CONFIG) as root:
            code, envelope, _ = run_cli(["--root", str(root), "check"], env=NOW)
        self.assertEqual(code, 0, envelope)
        statuses = {row["id"]: row["status"] for row in envelope["data"]["results"]}
        for check_id in RESEARCH_CHECKS:
            self.assertEqual(statuses[check_id], "skip", check_id)


class FailingInstanceTest(unittest.TestCase):
    def test_research_bad_instance(self):
        code, envelope, _ = run_cli(["--root", str(INSTANCES / "research-bad"), "check"], env=NOW)
        self.assertEqual(code, 1, envelope)
        statuses = {}
        for row in envelope["data"]["results"]:
            statuses.setdefault(row["id"], set()).add(row["status"])
        self.assertIn("fail", statuses["research_notes"])
        self.assertIn("fail", statuses["research_citations"])
        self.assertIn("fail", statuses["research_render_fresh"])
        self.assertEqual(statuses["research_expiry"], {"warn"})


if __name__ == "__main__":
    unittest.main()
