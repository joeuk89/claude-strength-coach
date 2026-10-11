import subprocess
import sys
from pathlib import Path

from coach import paths, plugins, units
from coach.commands import arg, command
from coach.errors import ValidationError

_KINDS = ("scheme", "schedule", "transform", "interference", "conditioning")


@command("plugins list", help="Every plugin, framework and instance, by kind",
         args=(arg("--kind", choices=_KINDS, help="only this kind"),))
def list_plugins(args, ctx):
    registry = plugins.load(ctx.root)
    return {"plugins": [p.summary() for p in registry.plugins if args.kind is None or p.kind == args.kind]}


@command("plugins show", help="One plugin's summary, parameters, state and cited claims",
         args=(arg("name", metavar="NAME", help="plugin name"),))
def show(args, ctx):
    found = plugins.load(ctx.root).find(args.name)
    if not found:
        raise ValidationError(f"No plugin named {args.name}; run python3 -m coach plugins list")
    shown = []
    for plugin in found:
        item = plugin.summary()
        module = plugin.module
        if module is not None:
            item.update(params=getattr(module, "PARAMS", None), state=getattr(module, "STATE", None),
                        cites=list(getattr(module, "CITES", ())), flags=getattr(module, "FLAGS", None))
            if plugin.kind == "scheme":
                item["load_modes"] = list(getattr(module, "LOAD_MODES", None) or units.LOAD_MODES)
        item["problems"] = plugin.problems
        shown.append(item)
    return {"plugins": shown}


@command("plugins validate",
         help="Check every plugin against the contract: shape, schemas, purity, no x2, instance names and tests")
def validate(args, ctx):
    registry = plugins.load(ctx.root)
    problems = registry.problems()
    if problems:
        raise ValidationError(f"{len(problems)} plugin problem(s)",
                              details=[{"path": p["path"], "message": f"{p['name']}: {p['message']}"} for p in problems])
    return {"valid": True, "plugins": [p.summary() for p in registry.plugins]}


def _test_env(ctx, framework):
    env = {key: value for key, value in ctx.env.items() if not key.startswith("COACH_")}
    env["PYTHONPATH"] = framework
    env["COACH_ROOT"] = str(ctx.root)
    return env


@command("plugins test", help="Run the instance plugins' tests in plugins/tests/ (runs instance code)")
def test(args, ctx):
    directory = Path(ctx.root) / paths.PLUGIN_TESTS_DIR
    if not directory.is_dir():
        return {"ran": False, "message": f"no {paths.PLUGIN_TESTS_DIR.as_posix()}/ directory"}
    framework = str(Path(plugins.__file__).resolve().parents[2])
    proc = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", paths.PLUGIN_TESTS_DIR.as_posix(), "-t",
         paths.PLUGIN_TESTS_DIR.as_posix()],
        cwd=str(ctx.root), capture_output=True, text=True, env=_test_env(ctx, framework),
    )
    for line in proc.stderr.splitlines():
        ctx.log(line)
    if proc.returncode != 0:
        raise ValidationError("Instance plugin tests failed; the output is on stderr",
                              data={"ran": True, "passed": False})
    return {"ran": True, "passed": True}
