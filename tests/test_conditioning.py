"""Conditioning sessions: density schemes, conditioning Activities and the drop rule (contract C51)."""

import copy
import json
import unittest
from datetime import date
from unittest import mock

from coach import history, jsonio, migrate, overlay, render, state
from coach.plugins import base
from coach.plugins.conditioning import circuit_rounds, emom_density
from tests.support import FIXTURES, INSTANCES, REPO_ROOT
from tests.support.activity import write_hevy_cache
from tests.support.history import HistoryCase
from tests.support.skills import skill_text

SWING = base.ExerciseInfo(id="kb_swing", name="Kettlebell Swing", pattern="hinge", muscles={"glutes": "primary"},
                          equipment="kettlebell", load_mode="single_implement", increment=4, is_compound=True)
BURPEE = base.ExerciseInfo(id="burpee", name="Burpee", pattern="conditioning", muscles={}, equipment="bodyweight",
                           load_mode="bodyweight", increment=0, is_compound=False)
SESSION_DATE = date(2026, 10, 17)
EMOM = {"minutes": 10, "reps": {"kb_swing": 10, "burpee": 5}, "reps_cap": {"kb_swing": 12, "burpee": 8}}
CIRCUIT = {"rounds": 3, "reps": {"kb_swing": 15, "burpee": 10}}


def bout(rpe, minutes=12, day="2026-10-10"):
    return {"date": day, "activity_id": "hevy_conditioning:c3", "duration_seconds": minutes * 60, "rpe": rpe}


def context(plugin, params, state=None, bouts=(), days_off=0):
    merged = dict(plugin.PARAMS["defaults"], **params)
    return base.ConditioningContext(
        today=date(2026, 10, 11), session_date=SESSION_DATE, session_id="circuit", exercises=(SWING, BURPEE),
        params=merged, state=state if state is not None else plugin.STATE["initial"], bouts=tuple(bouts),
        last_prescription=None, days_off=days_off,
    )


def emom_state(minutes, swing, burpee, turn=0, previous=()):
    return {"current": {"minutes": minutes, "reps": {"kb_swing": swing, "burpee": burpee}, "turn": turn},
            "previous": list(previous)}


def reps(proposal):
    return {exercise_id: [s.reps for s in sets] for exercise_id, sets in proposal.lines.items()}


def codes(proposal):
    return [f["code"] for f in proposal.flags]


class EmomDensityTest(unittest.TestCase):
    def test_first_prescription_is_the_params_start(self):
        proposal = emom_density.propose(context(emom_density, EMOM))
        self.assertEqual(reps(proposal), {"kb_swing": [10] * 5, "burpee": [5] * 5})
        self.assertEqual(proposal.state, emom_state(10, 10, 5))

    def test_rpe_under_target_adds_a_rep_to_the_next_exercise_in_turn(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 10, 5), [bout(6)]))
        self.assertEqual(reps(proposal), {"kb_swing": [11] * 5, "burpee": [5] * 5})
        following = emom_density.propose(context(emom_density, EMOM, proposal.state, [bout(6)]))
        self.assertEqual(reps(following), {"kb_swing": [11] * 5, "burpee": [6] * 5})

    def test_with_every_exercise_at_its_cap_minutes_rise_by_the_step(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 12, 8), [bout(7)]))
        self.assertEqual(reps(proposal), {"kb_swing": [12] * 6, "burpee": [8] * 6})
        self.assertEqual(proposal.state["current"]["minutes"], 12)

    def test_an_exercise_at_its_cap_passes_the_turn_on(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 12, 5), [bout(6)]))
        self.assertEqual(proposal.state["current"]["reps"], {"kb_swing": 12, "burpee": 6})

    def test_at_every_cap_it_holds_and_says_so(self):
        params = dict(EMOM, minutes_cap=10)
        proposal = emom_density.propose(context(emom_density, params, emom_state(10, 12, 8), [bout(6)]))
        self.assertEqual(proposal.state, emom_state(10, 12, 8))
        self.assertIn("at cap: coach to change", proposal.rationale)

    def test_rpe_two_over_target_steps_back_to_the_previous_prescription_exactly(self):
        stepped = emom_density.propose(context(emom_density, EMOM, emom_state(10, 10, 5), [bout(6)]))
        stepped = emom_density.propose(context(emom_density, EMOM, stepped.state, [bout(6)]))
        back = emom_density.propose(context(emom_density, EMOM, stepped.state, [bout(9)]))
        self.assertEqual(back.state, emom_state(10, 11, 5, turn=1, previous=[emom_state(10, 10, 5)["current"]]))
        self.assertEqual(reps(back), {"kb_swing": [11] * 5, "burpee": [5] * 5})

    def test_rpe_one_over_target_holds(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 10, 5), [bout(8)]))
        self.assertEqual(proposal.state, emom_state(10, 10, 5))
        self.assertEqual(codes(proposal), [])

    def test_no_rpe_holds_and_raises_no_data(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 10, 5), [bout(None)]))
        self.assertEqual(proposal.state, emom_state(10, 10, 5))
        self.assertEqual(codes(proposal), ["no_data"])
        self.assertEqual(proposal.flags[0]["session_id"], "circuit")

    def test_no_bout_since_the_last_prescription_holds(self):
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 11, 5, turn=1)))
        self.assertEqual(proposal.state, emom_state(10, 11, 5, turn=1))
        self.assertEqual(codes(proposal), [])

    def test_minutes_alternate_between_exercises_in_program_order(self):
        proposal = emom_density.propose(context(emom_density, dict(EMOM, minutes=11)))
        self.assertEqual({k: len(v) for k, v in proposal.lines.items()}, {"kb_swing": 6, "burpee": 5})

    def test_the_focus_names_the_format_and_how_to_log_rpe(self):
        proposal = emom_density.propose(context(emom_density, EMOM))
        self.assertIn("EMOM 10 min", proposal.focus)
        self.assertIn("RPE", proposal.focus)

    def test_summary_and_rationale_say_the_steps_are_a_coaching_heuristic(self):
        self.assertIn("coaching heuristic", emom_density.SUMMARY)
        proposal = emom_density.propose(context(emom_density, EMOM, emom_state(10, 10, 5), [bout(6)]))
        self.assertIn("coaching heuristic", proposal.rationale)

    def test_problems_name_an_exercise_without_reps(self):
        session = {"exercises": [{"exercise_id": "kb_swing"}, {"exercise_id": "burpee"}]}
        merged = dict(emom_density.PARAMS["defaults"], reps={"kb_swing": 10})
        self.assertEqual([path for path, _ in emom_density.problems(merged, session)], ["$.reps"])


class CircuitRoundsTest(unittest.TestCase):
    def state(self, rounds, previous=()):
        return {"current": {"rounds": rounds}, "previous": [{"rounds": r} for r in previous]}

    def test_rpe_at_target_inside_the_time_cap_adds_a_round(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, CIRCUIT, self.state(3), [bout(7, minutes=18)]))
        self.assertEqual(reps(proposal), {"kb_swing": [15] * 4, "burpee": [10] * 4})
        self.assertEqual(proposal.state, self.state(4, previous=[3]))

    def test_over_the_time_cap_steps_back_a_round(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, CIRCUIT, self.state(4, previous=[3]),
                                                  [bout(7, minutes=22)]))
        self.assertEqual(proposal.state, self.state(3))

    def test_over_the_time_cap_at_the_start_holds(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, CIRCUIT, self.state(3), [bout(7, minutes=22)]))
        self.assertEqual(proposal.state, self.state(3))
        self.assertEqual(len(proposal.lines["kb_swing"]), 3)

    def test_rounds_hold_at_their_cap(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, dict(CIRCUIT, rounds_cap=3), self.state(3),
                                                  [bout(6, minutes=15)]))
        self.assertEqual(proposal.state, self.state(3))
        self.assertIn("at cap: coach to change", proposal.rationale)

    def test_no_rpe_holds_and_raises_no_data(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, CIRCUIT, self.state(3), [bout(None, minutes=15)]))
        self.assertEqual(codes(proposal), ["no_data"])

    def test_the_focus_names_rounds_the_time_cap_and_rpe(self):
        proposal = circuit_rounds.propose(context(circuit_rounds, CIRCUIT))
        self.assertIn("3 rounds", proposal.focus)
        self.assertIn("20 min", proposal.focus)
        self.assertIn("RPE", proposal.focus)


class DecayTest(unittest.TestCase):
    def decayed(self, plugin, params, state, days_off):
        ctx = context(plugin, params, state, days_off=days_off)
        return plugin.decay(ctx, plugin.propose(ctx), days_off)

    def test_thirty_days_off_steps_back_one(self):
        state = emom_state(10, 11, 6, previous=[emom_state(10, 10, 5)["current"],
                                                 emom_state(10, 11, 5, turn=1)["current"]])
        decayed = self.decayed(emom_density, EMOM, state, 30)
        self.assertEqual(decayed.state["current"]["reps"], {"kb_swing": 11, "burpee": 5})
        self.assertIn("30 days", decayed.rationale)

    def test_fifty_days_off_resets_to_the_params_start(self):
        state = emom_state(12, 12, 8, previous=[emom_state(10, 12, 8)["current"]])
        decayed = self.decayed(emom_density, EMOM, state, 50)
        self.assertEqual(decayed.state, emom_state(10, 10, 5))
        self.assertEqual(reps(decayed), {"kb_swing": [10] * 5, "burpee": [5] * 5})

    def test_circuits_decay_the_same_way(self):
        state = {"current": {"rounds": 5}, "previous": [{"rounds": 3}, {"rounds": 4}]}
        self.assertEqual(self.decayed(circuit_rounds, CIRCUIT, state, 30).state["current"], {"rounds": 4})
        self.assertEqual(self.decayed(circuit_rounds, CIRCUIT, state, 50).state,
                         {"current": {"rounds": 3}, "previous": []})


class WiringTest(unittest.TestCase):
    def test_program_week_restores_a_dropped_session_with_the_command(self):
        text = skill_text("program-week")
        self.assertIn("`conditioning_dropped`", text)
        self.assertIn("python3 -m coach propose restore", text)

    def test_propose_restore_is_allowlisted(self):
        allowed = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        self.assertIn("Bash(python3 -m coach propose restore:*)", allowed["permissions"]["allow"])


CONDITIONING_SET = FIXTURES / "hevy" / "conditioning"
CONDITIONING_ROUTINE = "00000000-0000-4000-8000-000000000003"
SWINGS_WORKOUT = "00000000-0000-4000-8000-0000000000c3"
EMOM_SCHEME = {"name": "emom_density", "params": EMOM}
LIBRARY = {
    "kb_swing": {"hevy_template_id": "F00000A3", "load_mode": "single_implement",
                 "load_mode_proposed": "single_implement", "confidence": "high", "avoid": None},
    "burpee": {"hevy_template_id": "F00000A2", "load_mode": "bodyweight", "load_mode_proposed": "bodyweight",
               "confidence": "high", "avoid": None},
}


def circuit_session(tier, scheme=EMOM_SCHEME):
    hold = {"name": "hold", "params": {}}

    def line(exercise_id, mode, start_load):
        return {"exercise_id": exercise_id, "load_mode": mode, "sets": [{"count": 5, "type": "normal", "reps": 10}],
                "rest_seconds": None, "superset_id": None, "cues": None, "constraints": [], "scheme": hold,
                "start_load": start_load}

    return {"id": "circuit", "title": "Circuit", "kind": "conditioning", "tier": tier, "status": "active",
            "location": None, "focus": None, "scheme": copy.deepcopy(scheme),
            "exercises": [line("kb_swing", "single_implement", 24), line("burpee", "bodyweight", 0)]}


class CircuitCase(HistoryCase):
    """An instance with a Circuit session (kettlebell swings and burpees) under a density scheme."""

    tier = "core"
    weekday = "sat"

    def setUp(self):
        super().setUp()
        self.add_circuit(self.tier, self.weekday)

    def add_circuit(self, tier, weekday, scheme=EMOM_SCHEME):
        def change(doc):
            doc["sessions"] = [s for s in doc["sessions"] if s["id"] != "circuit"] + [circuit_session(tier, scheme)]
            days = doc["schedule"]["params"]["days"]
            for day in [d for d, session_id in days.items() if session_id == "circuit"]:
                del days[day]
            days[weekday] = "circuit"
        self.edit_json("data/program.json", change)
        self.edit_json("data/exercises.json", lambda doc: doc["exercises"].update(copy.deepcopy(LIBRARY)))

    def data(self, *argv, expect=0, env=None):
        return self.coach(*argv, expect=expect, env=env)["data"]

    def propose(self, *extra, week="2026-W42", env=None):
        return self.data("propose", "week", "--week", week, *extra, env=env)

    def circuit_lines(self, doc):
        return {line["exercise_id"]: line for s in doc["sessions"] if s["session_id"] == "circuit"
                for line in s["exercises"]}


class ProgramTest(CircuitCase):
    def test_a_valid_session_scheme_passes_and_its_page_names_it(self):
        self.assertTrue(self.data("program", "validate")["valid"])
        self.data("program", "render")
        page = (self.root / "routine" / "circuit.md").read_text(encoding="utf-8")
        self.assertIn("Session scheme: emom density (minutes: 10;", page)

    def test_a_non_hold_exercise_under_a_session_scheme_fails_validate(self):
        def change(doc):
            doc["sessions"][-1]["exercises"][1]["scheme"] = {"name": "double_progression", "params": {}}
        self.edit_json("data/program.json", change)
        envelope = self.coach("program", "validate", expect=1)
        paths = [d["path"] for d in envelope["error"]["details"]]
        self.assertIn("$.sessions[2].exercises[1].scheme.name", paths)

    def test_a_lifting_session_cannot_carry_a_session_scheme(self):
        self.edit_json("data/program.json", lambda doc: doc["sessions"][0].update(scheme=EMOM_SCHEME))
        envelope = self.coach("program", "validate", expect=1)
        self.assertIn("$.sessions[0].scheme", [d["path"] for d in envelope["error"]["details"]])

    def test_params_missing_an_exercise_s_reps_fail_at_the_params(self):
        scheme = {"name": "emom_density", "params": {"reps": {"kb_swing": 10}}}
        self.add_circuit("core", "sat", scheme)
        envelope = self.coach("program", "validate", expect=1)
        self.assertIn("$.sessions[2].scheme.params.reps", [d["path"] for d in envelope["error"]["details"]])

    def test_an_unknown_session_scheme_fails(self):
        self.add_circuit("core", "sat", {"name": "double_progression", "params": {}})
        envelope = self.coach("program", "validate", expect=1)
        self.assertIn("$.sessions[2].scheme.name", [d["path"] for d in envelope["error"]["details"]])

    def test_the_session_state_key_names_a_conditioning_session(self):
        program_doc = json.loads((self.root / "data" / "program.json").read_text(encoding="utf-8"))
        doc = json.loads((self.root / "data" / "state.json").read_text(encoding="utf-8"))
        entry = {"scheme": "emom_density", "data": emom_density.STATE["initial"], "pending": None}
        doc["scheme_state"] = {"circuit/_session": entry}
        self.assertEqual(state.problems(doc, program_doc), [])
        doc["scheme_state"] = {"session-a/_session": entry}
        self.assertEqual([e.path for e in state.problems(doc, program_doc)], ["$.scheme_state['session-a/_session']"])


class MigrationTest(HistoryCase):
    def test_migrate_run_gives_every_session_an_empty_scheme(self):
        current = jsonio.current_version(jsonio.load_schema("program"))
        [step] = [s for s in migrate.registry().documents["program"].steps if s.name.endswith("_session_scheme")]

        def older(doc):
            doc["schema_version"] = step.from_version
            for session in doc["sessions"]:
                session.pop("scheme")
        self.edit_json("data/program.json", older)
        dry = self.coach("migrate", "run", "--dry-run")["data"]
        self.assertEqual([(f["path"], f["from"], f["to"]) for f in dry["files"]],
                         [("data/program.json", step.from_version, current)])
        self.coach("migrate", "run")
        migrated = json.loads((self.root / "data" / "program.json").read_text(encoding="utf-8"))
        self.assertEqual([s["scheme"] for s in migrated["sessions"]], [None, None])
        self.assertTrue(self.coach("program", "validate")["data"]["valid"])


class PipelineTest(CircuitCase):
    def test_the_session_scheme_sets_every_exercise_s_sets_and_loads_hold(self):
        doc = self.propose("--dry-run")["overlay"]
        lines = self.circuit_lines(doc)
        swings = [(s["reps"], s["load"]["per_hand"]) for s in lines["kb_swing"]["sets"]]
        self.assertEqual(swings, [(10, 24)] * 5)
        self.assertEqual([s["reps"] for s in lines["burpee"]["sets"]], [5] * 5)
        self.assertEqual({line["provenance"]["scheme"] for line in lines.values()}, {"emom_density"})
        self.assertEqual(overlay.validate(doc, self.root), [])

    def test_the_first_exercise_s_note_carries_the_format_and_rpe_and_nothing_else_changes(self):
        doc = self.propose("--dry-run")["overlay"]
        session = next(s for s in doc["sessions"] if s["session_id"] == "circuit")
        first = session["exercises"][0]
        note = render.render_hevy_note(doc, session, first, True).split("\n")
        plain = render.render_hevy_note(doc, session, dict(first, focus=None), True).split("\n")
        focus = [line for line in note if line.startswith("Focus: ")]
        self.assertEqual(len(focus), 1)
        self.assertIn("EMOM 10 min", focus[0])
        self.assertIn("RPE", focus[0])
        self.assertEqual([line for line in note if not line.startswith("Focus: ")], plain)
        self.assertIsNone(session["exercises"][1]["focus"])

    def test_finalize_leaves_the_session_state_pending(self):
        proposal = self.propose()["id"]
        self.data("propose", "finalize", "--proposal", proposal)
        entry = json.loads((self.root / "data" / "state.json").read_text(encoding="utf-8"))["scheme_state"][
            "circuit/_session"]
        self.assertEqual(entry["scheme"], "emom_density")
        self.assertEqual(entry["pending"]["data"]["current"]["reps"], {"kb_swing": 10, "burpee": 5})
        self.data("state", "show")


class ActivityTest(CircuitCase):
    """The C14 conditioning workout `...0c3` (swings and burpees, "RPE 7") from the routine mapped to Circuit."""

    weekday = "fri"

    def setUp(self):
        super().setUp()
        self.edit_json("data/state.json", lambda doc: doc["hevy"]["routines"].update(
            {CONDITIONING_ROUTINE: {"session_id": "circuit"}}))
        earlier = {"COACH_NOW": "2026-10-04T18:00:00Z"}
        proposal = self.propose(week="2026-W41", env=earlier)["id"]
        self.data("propose", "finalize", "--proposal", proposal, env=earlier)
        self.data("overlay", "approve", proposal, env=earlier)
        write_hevy_cache(self.root, CONDITIONING_SET)
        self.data("activity", "sync")
        self.data("history", "sync")

    def test_the_workout_is_one_conditioning_activity_and_adds_no_dose(self):
        workout = next(w for w in history.workouts(self.root) if w["workout_id"] == SWINGS_WORKOUT)
        self.assertEqual((workout["session_id"], workout["conditioning"]), ("circuit", True))
        activities = [line for line in (self.root / "data" / "activity" / "activities.jsonl").read_text(
            encoding="utf-8").splitlines() if SWINGS_WORKOUT in line]
        records = [json.loads(line) for line in activities]
        self.assertEqual([(r["kind"], r["rpe"]) for r in records], [("conditioning", 7)])
        dose = self.data("stats", "dose", "--week", "2026-W41")
        self.assertNotIn(SWINGS_WORKOUT, dose["by_workout"])
        self.assertNotIn(SWINGS_WORKOUT, [e["workout_id"] for e in history.exposures(self.root, "kb_swing")])
        week = self.data("cardio", "week", "--week", "2026-W41")
        bout = next(b for b in week["bouts"] if b["ref"] == f"hevy_conditioning:{SWINGS_WORKOUT}")
        self.assertEqual(bout["srpe"]["method"], "athlete")

    def test_the_next_proposal_steps_up_from_the_logged_session_rpe(self):
        doc = self.propose("--dry-run")["overlay"]
        lines = self.circuit_lines(doc)
        self.assertEqual([s["reps"] for s in lines["kb_swing"]["sets"]], [11] * 5)
        self.assertIn("RPE 7", lines["kb_swing"]["provenance"]["rationale"])


class LayoffTest(CircuitCase):
    """The Circuit on Wednesday and Saturday after 30 days without conditioning."""

    def setUp(self):
        super().setUp()
        self.edit_json("data/program.json", lambda doc: doc["schedule"]["params"]["days"].update(wed="circuit"))
        stored = emom_state(10, 11, 6, previous=[emom_state(10, 10, 5)["current"],
                                                  emom_state(10, 11, 5, turn=1)["current"]])
        self.edit_json("data/state.json", lambda doc: doc["scheme_state"].update(
            {"circuit/_session": {"scheme": "emom_density", "data": stored, "pending": None}}))

    def propose_after_layoff(self, *extra):
        with mock.patch("coach.conditioning.days_off", return_value=30):
            return self.propose(*extra)

    def reps_by_date(self, doc):
        return {s["date"]: {line["exercise_id"]: line["sets"][0]["reps"] for line in s["exercises"]}
                for s in doc["sessions"] if s["session_id"] == "circuit"}

    def test_every_date_steps_back_once(self):
        doc = self.propose_after_layoff("--dry-run")["overlay"]
        once = {"kb_swing": 11, "burpee": 5}
        self.assertEqual(self.reps_by_date(doc), {"2026-10-14": once, "2026-10-17": once})
        self.assertEqual(len([f for f in doc["flags"] if f["code"] == "return_week"
                              and f["session_id"] == "circuit"]), 1)

    def test_the_pending_state_is_one_step_back(self):
        proposal = self.propose_after_layoff()["id"]
        self.data("propose", "finalize", "--proposal", proposal)
        entry = json.loads((self.root / "data" / "state.json").read_text(encoding="utf-8"))["scheme_state"][
            "circuit/_session"]
        self.assertEqual(entry["pending"]["data"]["current"]["reps"], {"kb_swing": 11, "burpee": 5})

    def test_a_deload_steps_back_once(self):
        doc = self.propose_after_layoff("--kind", "deload", "--dry-run")["overlay"]
        once = {"kb_swing": 11, "burpee": 5}
        self.assertEqual(self.reps_by_date(doc), {"2026-10-14": once, "2026-10-17": once})


class DropCase(CircuitCase):
    base = INSTANCES / "cardio"
    tier = "optional"

    def no_sleep_data(self):
        (self.root / ".coach" / "activity" / "wellness.jsonl").unlink()

    def dropped_flags(self, doc):
        return [f for f in doc["flags"] if f["code"] == "conditioning_dropped"]


class DropTest(DropCase):
    def test_sleep_debt_drops_the_optional_session_with_an_info_flag(self):
        data = self.propose("--dry-run")
        self.assertNotIn("circuit", [s["session_id"] for s in data["overlay"]["sessions"]])
        self.assertEqual([(d["session_id"], d["date"], d["trigger"]) for d in data["dropped"]],
                         [("circuit", "2026-10-17", "sleep_debt")])
        [flag] = self.dropped_flags(data["overlay"])
        self.assertEqual((flag["severity"], flag["resolved"]), ("info", False))
        self.assertIn("sleep debt", flag["message"])

    def test_restore_brings_it_back_resolved_and_finalize_succeeds(self):
        proposal = self.propose()["id"]
        restored = self.data("propose", "restore", "--proposal", proposal, "--session", "circuit",
                             "--reason", "athlete slept well since and wants the circuit")
        self.assertIn("circuit", [row["session_id"] for row in restored["lines"]])
        [flag] = [f for f in restored["flags"] if f["code"] == "conditioning_dropped"]
        self.assertTrue(flag["resolved"])
        self.assertEqual(flag["resolution"], "athlete slept well since and wants the circuit")
        final = self.data("propose", "finalize", "--proposal", proposal)
        self.assertIn("circuit", [s["session_id"] for s in final["overlay"]["sessions"]])
        self.assertIn("circuit/_session", final["pending"])
        shown = self.data("propose", "show", proposal)
        self.assertEqual(shown["dropped"][0]["restored"]["reason"], "athlete slept well since and wants the circuit")

    def test_a_dropped_session_takes_its_own_flags_with_it_and_restore_brings_them_back(self):
        self.edit_json("data/program.json", lambda doc: doc["sessions"][-1]["exercises"][0].update(start_load=None))
        data = self.propose()
        self.assertNotIn("circuit", [f["session_id"] for f in data["overlay"]["flags"]])
        restored = self.data("propose", "restore", "--proposal", data["id"], "--session", "circuit",
                             "--reason", "athlete wants it")
        self.assertIn(("no_data", "kb_swing"), [(f["code"], f["exercise_id"]) for f in restored["flags"]])
        self.data("propose", "finalize", "--proposal", data["id"])

    def test_restore_refuses_a_session_that_was_not_dropped(self):
        proposal = self.propose()["id"]
        self.coach("propose", "restore", "--proposal", proposal, "--session", "session-a", "--reason", "x", expect=1)

    def test_a_status_day_on_its_date_drops_it(self):
        self.no_sleep_data()
        self.add_circuit("optional", "thu")
        data = self.propose("--dry-run")
        self.assertEqual([(d["date"], d["trigger"]) for d in data["dropped"]], [("2026-10-15", "status_active")])

    def test_a_planned_quality_run_the_day_before_drops_it(self):
        self.no_sleep_data()
        data = self.propose("--dry-run")
        self.assertEqual([(d["date"], d["trigger"]) for d in data["dropped"]], [("2026-10-17", "quality_stack")])
        self.assertIn("2026-10-16", data["dropped"][0]["reason"])

    def test_without_a_trigger_nothing_is_dropped(self):
        self.no_sleep_data()
        self.add_circuit("optional", "sun")
        self.drop_tempo()
        data = self.propose("--dry-run")
        self.assertEqual(data["dropped"], [])
        self.assertEqual(self.dropped_flags(data["overlay"]), [])

    def drop_tempo(self):
        path = self.root / "data" / "activity" / "planned.jsonl"
        kept = [line for line in path.read_text(encoding="utf-8").splitlines() if '"Tempo"' not in line]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")


class CoreTest(DropCase):
    tier = "core"

    def assert_kept_with_a_warning(self, data, trigger_words):
        self.assertIn("circuit", [s["session_id"] for s in data["overlay"]["sessions"]])
        self.assertEqual(data["dropped"], [])
        [flag] = self.dropped_flags(data["overlay"])
        self.assertEqual((flag["severity"], flag["session_id"]), ("warn", "circuit"))
        self.assertIn(trigger_words, flag["message"])

    def test_sleep_debt_keeps_a_core_session_with_a_warning(self):
        self.assert_kept_with_a_warning(self.propose("--dry-run"), "sleep debt")

    def test_a_status_day_keeps_a_core_session_with_a_warning(self):
        self.no_sleep_data()
        self.add_circuit("core", "thu")
        self.assert_kept_with_a_warning(self.propose("--dry-run"), "travel status day")

    def test_a_quality_run_the_day_before_keeps_a_core_session_with_a_warning(self):
        self.no_sleep_data()
        self.assert_kept_with_a_warning(self.propose("--dry-run"), "quality_stack")


if __name__ == "__main__":
    unittest.main()
