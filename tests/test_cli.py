import contextlib
import io
import json
import sys
import unittest
from unittest import mock

from coach import cli, commands, jsonio
from coach.commands import Command, arg, command
from coach.validate import validate
from tests.support import INSTANCES, MINIMAL_CONFIG, VALID, TempInstance, run_cli, run_module

ENVELOPE = jsonio.load_schema("envelope")
NOW = {"COACH_NOW": "2026-10-11T18:00:00Z"}


class EnvelopeMixin:
    def run_ok(self, *argv, env=None):
        code, envelope, stderr = run_cli(argv, env=env)
        self.assertEqual(code, 0, (envelope, stderr))
        self.assert_envelope(envelope)
        self.assertTrue(envelope["ok"])
        return envelope["data"]

    def run_fail(self, expected_code, *argv, env=None, commands=None):
        code, envelope, stderr = run_cli(argv, env=env, commands=commands)
        self.assertEqual(code, expected_code, (envelope, stderr))
        self.assert_envelope(envelope)
        self.assertFalse(envelope["ok"])
        return envelope, stderr

    def assert_envelope(self, envelope):
        self.assertEqual(validate(envelope, ENVELOPE), [], envelope)


class UnitsCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_format_per_hand_lb(self):
        data = self.run_ok("units", "format", "--mode", "per_hand_x2", "--value", "25", "--unit", "lb")
        self.assertEqual(data["text"], "25/hand (Hevy: 50)")
        self.assertEqual(data["load"]["hevy_kg"], 22.6796)

    def test_format_other_modes(self):
        cases = [
            (("single_implement", "25", "kg"), "25 (Hevy: 25)"),
            (("total", "80", "kg"), "80"),
            (("bodyweight", "0", "kg"), "BW"),
            (("bodyweight", "10", "kg"), "BW+10"),
        ]
        for (mode, value, unit), text in cases:
            with self.subTest(mode=mode, value=value):
                data = self.run_ok("units", "format", "--mode", mode, "--value", value, "--unit", unit)
                self.assertEqual(data["text"], text)

    def test_format_unloaded_mode(self):
        data = self.run_ok("units", "format", "--mode", "band", "--unit", "kg")
        self.assertEqual(data, {"text": None, "load": None})

    def test_format_needs_a_value(self):
        self.run_fail(2, "units", "format", "--mode", "total", "--unit", "kg")

    def test_format_rejects_negative(self):
        self.run_fail(1, "units", "format", "--mode", "total", "--value", "-5", "--unit", "kg")

    def test_unit_from_config(self):
        env = {"COACH_ROOT": str(VALID)}
        data = self.run_ok("units", "format", "--mode", "per_hand_x2", "--value", "25", env=env)
        self.assertEqual(data["load"]["unit"], "kg")

    def test_unit_without_config_is_exit_5(self):
        with TempInstance() as root:
            self.run_fail(5, "--root", str(root), "units", "format", "--mode", "total", "--value", "80")

    def test_convert_from_hevy(self):
        data = self.run_ok("units", "convert", "--from-hevy-kg", "50", "--mode", "per_hand_x2", "--unit", "kg")
        self.assertEqual(data["value"], 25)
        self.assertIsInstance(data["value"], int)

    def test_convert_to_hevy(self):
        data = self.run_ok("units", "convert", "--value", "25", "--mode", "per_hand_x2", "--unit", "lb")
        self.assertEqual(data["hevy_kg"], 22.6796)

    def test_convert_needs_exactly_one_input(self):
        self.run_fail(2, "units", "convert", "--mode", "total", "--unit", "kg")
        self.run_fail(2, "units", "convert", "--mode", "total", "--unit", "kg", "--value", "1", "--from-hevy-kg", "1")

    def test_round(self):
        data = self.run_ok("units", "round", "--value", "23.7", "--increment", "2.5", "--direction", "up")
        self.assertEqual(data["value"], 25)
        self.run_fail(1, "units", "round", "--value", "23.7", "--increment", "0")


class DatesCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_week(self):
        data = self.run_ok("--root", str(VALID), "dates", "week", "--date", "2026-10-11")
        self.assertEqual(data["iso_week"], "2026-W41")
        self.assertEqual(data["span"], {"start": "2026-10-05", "end": "2026-10-11"})
        self.assertEqual(data["label"], "2026-W41")

    def test_week_sunday_start(self):
        data = self.run_ok("--root", str(VALID), "dates", "week", "--date", "2026-10-11", "--week-starts", "sunday")
        self.assertEqual(data["iso_week"], "2026-W41")
        self.assertEqual(data["span"], {"start": "2026-10-11", "end": "2026-10-17"})
        self.assertEqual(data["label"], "2026-W42")

    def test_week_defaults_to_today(self):
        data = self.run_ok("--root", str(VALID), "dates", "week", env=NOW)
        self.assertEqual(data["date"], "2026-10-11")

    def test_bad_date_and_bad_now(self):
        self.run_fail(1, "--root", str(VALID), "dates", "week", "--date", "2026-02-30")
        self.run_fail(5, "--root", str(VALID), "dates", "week", env={"COACH_NOW": "soon"})

    def test_span(self):
        data = self.run_ok("--root", str(VALID), "dates", "span", "--week", "2026-W42")
        self.assertEqual(data["span"], {"start": "2026-10-12", "end": "2026-10-18"})
        data = self.run_ok("dates", "span", "--start", "2026-10-12", "--end", "2026-10-14")
        self.assertEqual(data["days"], 3)
        self.run_fail(2, "dates", "span")
        self.run_fail(1, "dates", "span", "--start", "2026-10-14", "--end", "2026-10-12")


class ConfigCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_missing_config(self):
        with TempInstance() as root:
            envelope, _ = self.run_fail(5, "--root", str(root), "config", "show")
        self.assertIn("config.example.toml", envelope["error"]["message"])
        self.assertEqual(envelope["error"]["code"], "config")

    def test_unknown_key(self):
        with TempInstance(MINIMAL_CONFIG + 'colour = "blue"\n') as root:
            envelope, _ = self.run_fail(5, "--root", str(root), "config", "show")
        self.assertIn("config.toml", envelope["error"]["message"])
        self.assertIn('"colour"', envelope["error"]["message"])

    def test_validate_valid_fixture(self):
        data = self.run_ok("--root", str(VALID), "config", "validate")
        self.assertTrue(data["valid"])

    def test_profile_fact_errors(self):
        for line, key in (('experience = "expert"', "experience"), ('available_days = ["monday"]', "available_days")):
            with self.subTest(key=key):
                with TempInstance(MINIMAL_CONFIG + line + "\n") as root:
                    envelope, _ = self.run_fail(5, "--root", str(root), "config", "validate")
                self.assertIn(key, envelope["error"]["message"])

    def test_location_errors(self):
        cases = [
            ("[equipment.locations.home]\ndumbells = [5]\n", ("config.toml", "[equipment.locations.home]", "dumbells")),
            ('[equipment.locations."Home Gym"]\ndumbbell_max = 20.0\n', ("config.toml", "Home Gym")),
        ]
        for text, fragments in cases:
            with self.subTest(text=text):
                with TempInstance(MINIMAL_CONFIG + text) as root:
                    envelope, _ = self.run_fail(5, "--root", str(root), "config", "validate")
                for fragment in fragments:
                    self.assertIn(fragment, envelope["error"]["message"])

    def test_show_location(self):
        data = self.run_ok("--root", str(VALID), "config", "show", "--location", "home")
        self.assertEqual(data["equipment"]["dumbbell_max"], 20.0)
        self.assertEqual(data["equipment"]["bar_weight"], 20.0)
        envelope, _ = self.run_fail(5, "--root", str(VALID), "config", "show", "--location", "hotel")
        self.assertIn("hotel", envelope["error"]["message"])

    def test_root_from_environment(self):
        data = self.run_ok("config", "validate", env={"COACH_ROOT": str(VALID)})
        self.assertTrue(data["valid"])


class CheckCommandTest(EnvelopeMixin, unittest.TestCase):
    def test_valid_instance_passes(self):
        data = self.run_ok("--root", str(VALID), "check")
        statuses = {row["id"]: row["status"] for row in data["results"]}
        self.assertEqual(statuses["python_floor"], "pass")
        self.assertEqual(statuses["config"], "pass")
        self.assertEqual(data["summary"]["fail"], 0)

    def test_bad_config_fails_with_exit_1(self):
        envelope, _ = self.run_fail(1, "--root", str(INSTANCES / "bad-config"), "check")
        statuses = {row["id"]: row["status"] for row in envelope["data"]["results"]}
        self.assertEqual(statuses["config"], "fail")
        self.assertEqual(envelope["error"]["code"], "validation")

    def test_missing_config_is_a_fail_not_exit_5(self):
        with TempInstance() as root:
            envelope, _ = self.run_fail(1, "--root", str(root), "check")
        self.assertEqual(envelope["data"]["summary"]["fail"], 1)

    def test_only_and_list(self):
        data = self.run_ok("--root", str(VALID), "check", "--only", "python_floor")
        self.assertEqual([row["id"] for row in data["results"]], ["python_floor"])
        data = self.run_ok("--root", str(VALID), "check", "--list")
        self.assertIn({"id": "config", "owner": "R-10"}, data["checks"])
        self.run_fail(2, "--root", str(VALID), "check", "--only", "nope")

    def test_old_python_fails_the_floor_check(self):
        with mock.patch.object(sys, "version_info", (3, 10, 4, "final", 0)):
            envelope, _ = self.run_fail(1, "--root", str(VALID), "check", "--only", "python_floor")
        self.assertIn("3.11", envelope["data"]["results"][0]["message"])


class ExitCodeTest(EnvelopeMixin, unittest.TestCase):
    def test_unknown_flag_is_exit_2(self):
        envelope, _ = self.run_fail(2, "units", "format", "--mode", "total", "--value", "1", "--unit", "kg", "--bogus")
        self.assertEqual(envelope["error"]["code"], "usage")
        self.run_fail(2, "no-such-group")
        self.run_fail(2, "units")

    def test_uncaught_exception_is_exit_9(self):
        @command("boom now", help="raises")
        def boom(args, ctx):
            raise RuntimeError("kaboom")

        envelope, stderr = self.run_fail(9, "boom", "now", commands=[boom.coach_command])
        self.assertEqual(envelope["error"]["code"], "internal")
        self.assertIn("Traceback", stderr)
        self.assertIn("RuntimeError: kaboom", stderr)
        for line in stderr.splitlines():
            self.assertTrue(line.startswith("coach: "), line)

    def test_version(self):
        data = self.run_ok("version")
        self.assertIn("version", data)


class DryRunTest(unittest.TestCase):
    def test_every_writing_command_accepts_dry_run(self):
        registered = commands.discover()
        _, subparsers = cli.build_parser(registered)
        for cmd in registered:
            if cmd.writes or cmd.hevy_write or cmd.git_write:
                with self.subTest(command=cmd.name):
                    self.assertIn("--dry-run", subparsers[cmd.name]._option_string_actions)

    def test_the_helper_adds_dry_run_to_writers(self):
        @command("demo write", help="writes", writes=True, args=(arg("--name"),))
        def write(args, ctx):
            return {"dry_run": args.dry_run}

        cmd = write.coach_command
        self.assertEqual(cmd.writes_scope, "data")
        code, envelope, _ = run_cli(["demo", "write", "--dry-run"], commands=[cmd])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"], {"dry_run": True})

    def test_a_hook_command_prints_its_response_without_the_envelope(self):
        @command("demo hook", help="hook", envelope=False, args=(arg("--quiet", action="store_true"),))
        def hook(args, ctx):
            return None if args.quiet else {"decision": "ask"}

        stdout = io.StringIO()
        code = cli.main(["demo", "hook"], env={}, stdout=stdout, stderr=io.StringIO(), commands=[hook.coach_command])
        self.assertEqual((code, stdout.getvalue()), (0, '{"decision": "ask"}\n'))
        stdout = io.StringIO()
        code = cli.main(["demo", "hook", "--quiet"], env={}, stdout=stdout, stderr=io.StringIO(),
                        commands=[hook.coach_command])
        self.assertEqual((code, stdout.getvalue()), (0, ""))

    def test_declarations_are_checked(self):
        with self.assertRaises(ValueError):
            command("too many words here", help="x")
        with self.assertRaises(ValueError):
            command("push it", help="x", hevy_write=True)
        with self.assertRaises(ValueError):
            command("cache it", help="x", writes_scope="cache")

    def test_every_command_records_its_metadata(self):
        for cmd in commands.discover():
            with self.subTest(command=cmd.name):
                self.assertIsInstance(cmd, Command)
                self.assertEqual(set(cmd.metadata()), {"writes", "hevy_write", "network", "git_write", "writes_scope"})


class MainModuleTest(unittest.TestCase):
    def test_old_python_exits_5_naming_3_11(self):
        from coach import __main__ as entry

        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, "version_info", (3, 10, 4, "final", 0)), \
                contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = entry.run()
        self.assertEqual(code, 5)
        lines = stderr.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("3.11", lines[0])
        envelope = json.loads(stdout.getvalue())
        self.assertEqual(envelope["error"]["code"], "config")
        self.assertIn("3.11", envelope["error"]["message"])
        self.assertEqual(validate(envelope, ENVELOPE), [])

    def test_subprocess_end_to_end(self):
        code, envelope, _ = run_module(["units", "format", "--mode", "per_hand_x2", "--value", "25", "--unit", "lb"])
        self.assertEqual(code, 0)
        self.assertEqual(envelope["data"]["text"], "25/hand (Hevy: 50)")
        code, envelope, _ = run_module(["--root", "tests/fixtures/instances/valid", "check"])
        self.assertEqual(code, 0)
        code, envelope, _ = run_module(["version"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
