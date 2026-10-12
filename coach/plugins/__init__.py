"""The plugin loader: framework plugins in `coach/plugins/<kind>/`, instance plugins in `plugins/<kind>/` (contract C23).

A kind is a subpackage here whose `__init__.py` names its KIND and the
functions its plugins must define. Instance plugins are scanned before they
are imported: a module that does I/O, imports beyond the allowed list or
doubles a load is never run.
"""

import ast
import importlib
import importlib.util
import pkgutil
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from coach import flags, paths, units
from coach.validate import SchemaError, check_schema
from coach.validate import validate as validate_schema

API = 1
FRAMEWORK_DIR = Path(__file__).resolve().parent
INSTANCE_PREFIX = "custom_"
ALLOWED_IMPORTS = frozenset({"coach.plugins.base", "coach.stats.e1rm", "coach.stats.load_for",
                             "coach.stats.implied_rpe", "math", "dataclasses", "typing", "datetime"})
FORBIDDEN_CALLS = frozenset({"open", "exec", "eval", "compile", "__import__", "input", "breakpoint", "globals",
                             "locals", "vars", "getattr", "setattr", "delattr"})
MODULE_KEYS = ("API", "KIND", "NAME", "SUMMARY", "PARAMS", "FLAGS", "CITES")
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
_CLAIM_REF = re.compile(r"^rn:([a-z0-9]+(?:-[a-z0-9]+)*)\.([0-9]+)$")
_DOUBLING = {2, 0.5}
_KG_LB = ("0.45359237", "2.20462")


class PluginError(Exception):
    """A plugin broke its contract while running: a bug in the plugin, reported with its name."""


@dataclass
class Kind:
    package: str
    kind: str
    required: tuple
    optional: tuple
    stateful: bool


@dataclass
class Plugin:
    name: str
    kind: str
    package: str
    source: str
    path: Path
    file: Path = None
    module: object = None
    problems: list = field(default_factory=list)

    @property
    def valid(self):
        return self.module is not None and not self.problems

    def summary(self):
        return {"name": self.name, "kind": self.kind, "source": self.source, "path": self.path.as_posix(),
                "summary": getattr(self.module, "SUMMARY", None), "valid": self.valid}


def kinds():
    """{package name: Kind} for every kind subpackage of coach/plugins."""
    found = {}
    for info in pkgutil.iter_modules(__path__):
        if not info.ispkg:
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        found[info.name] = Kind(info.name, module.KIND, tuple(module.REQUIRED), tuple(getattr(module, "OPTIONAL", ())),
                                bool(getattr(module, "STATEFUL", False)))
    return found


def _constant(node):
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return abs(node.value)
    return None


def _allowed(name):
    """True when the dotted name, or a package or module it lies inside, is on the allowed list."""
    parts = name.split(".")
    return any(".".join(parts[:end]) in ALLOWED_IMPORTS for end in range(1, len(parts) + 1))


def _import_problems(node):
    """What an import statement brings in that a plugin may not have."""
    allowed = ", ".join(sorted(ALLOWED_IMPORTS))
    if isinstance(node, ast.ImportFrom):
        if node.level:
            return [f"imports relative import {'.' * node.level}{node.module or ''}; plugins import only {allowed}"]
        found = [f"imports the private name {a.name}" for a in node.names if a.name.startswith("_")]
        names = [f"{node.module}.{alias.name}" for alias in node.names]
    else:
        names = [alias.name for alias in node.names]
        found = [f"import {a.name} binds the whole {a.name.split('.')[0]} package; write import {a.name} as <name>"
                 for a in node.names
                 if a.asname is None and "." in a.name and _allowed(a.name) and not _allowed(a.name.split(".")[0])]
    return found + [f"imports {name}; plugins import only {allowed}" for name in names if not _allowed(name)]


def scan_source(source, filename="<plugin>"):
    """[(line, problem)] for a plugin's source: I/O, imports outside the allowed list, private access, x2 or /2."""
    try:
        tree = ast.parse(source, filename, feature_version=(3, 11))
    except SyntaxError as exc:
        return [(exc.lineno or 0, f"does not parse as Python 3.11: {exc.msg}")]
    found = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found += [(node.lineno, problem) for problem in _import_problems(node)]
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            found.append((node.lineno, f"calls {node.func.id}(); plugins do no I/O and no introspection"))
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            found.append((node.lineno, f"reads the private attribute {node.attr}"))
        elif isinstance(node, ast.Name) and node.id.startswith("__") and node.id != "__name__":
            found.append((node.lineno, f"uses {node.id}"))
        elif isinstance(node, ast.BinOp):
            left, right = _constant(node.left), _constant(node.right)
            if isinstance(node.op, ast.Mult) and (left in _DOUBLING or right in _DOUBLING):
                found.append((node.lineno, "multiplies by 2 or 0.5; only coach.units doubles or halves a load"))
            elif isinstance(node.op, (ast.Div, ast.FloorDiv)) and right in (2, 0.5):
                found.append((node.lineno, "divides by 2 or 0.5; only coach.units doubles or halves a load"))
        elif isinstance(node, ast.AugAssign):
            value = _constant(node.value)
            if isinstance(node.op, (ast.Mult, ast.Div, ast.FloorDiv)) and value in _DOUBLING:
                found.append((node.lineno, "doubles or halves in place; only coach.units does that"))
        elif isinstance(node, ast.Constant) and type(node.value) is float and repr(node.value).startswith(_KG_LB):
            found.append((node.lineno, "holds a kg/lb factor; only coach.units converts units"))
    return sorted(found)


def framework_code_uses(source):
    """[(line, problem)] for each framework flag code an instance plugin passes to a call (it emits custom_ ones)."""
    framework = {code for code in flags.registry() if not code.startswith(INSTANCE_PREFIX)}
    found = []
    for node in ast.walk(ast.parse(source, feature_version=(3, 11))):
        if not isinstance(node, ast.Call):
            continue
        for value in [*node.args, *(k.value for k in node.keywords)]:
            if isinstance(value, ast.Constant) and value.value in framework:
                found.append((node.lineno, f"emits the framework flag code {value.value}; an instance plugin emits "
                                           f"only its own {INSTANCE_PREFIX} codes"))
    return found


def _framework_plugins(kind):
    package = importlib.import_module(f"{__name__}.{kind.package}")
    found = []
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda i: i.name):
        if info.ispkg:
            continue
        path = FRAMEWORK_DIR / kind.package / f"{info.name}.py"
        plugin = Plugin(info.name, kind.kind, kind.package, "framework", Path("coach", "plugins", kind.package, path.name),
                        path)
        plugin.problems += [f"line {line}: {problem}" for line, problem in
                            scan_source(path.read_text(encoding="utf-8"), str(path))]
        plugin.module = importlib.import_module(f"{__name__}.{kind.package}.{info.name}")
        found.append(plugin)
    return found


def _import_instance(plugin):
    module_name = f"coach_instance_plugins.{plugin.package}.{plugin.name}"
    spec = importlib.util.spec_from_file_location(module_name, plugin.file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        sys.modules.pop(module_name, None)
        plugin.problems.append(f"fails to import: {type(exc).__name__}: {exc}")
        return None
    return module


def _instance_plugins(root, kind, framework_names):
    root = Path(root).resolve()
    directory = root / paths.PLUGINS_DIR / kind.package
    if not directory.is_dir():
        return []
    found = []
    for path in sorted(directory.glob("*.py")):
        if path.name == "__init__.py":
            continue
        name = path.stem
        plugin = Plugin(name, kind.kind, kind.package, "instance", path.relative_to(root), path)
        if not name.startswith(INSTANCE_PREFIX):
            plugin.problems.append(f"an instance plugin's name starts {INSTANCE_PREFIX}, found {name}")
        if name in framework_names:
            plugin.problems.append(f"{name} collides with the framework {kind.kind} {name}; rename it {INSTANCE_PREFIX}…")
        test = root / paths.PLUGIN_TESTS_DIR / f"test_{name}.py"
        if not test.is_file():
            plugin.problems.append(f"no test file {paths.PLUGIN_TESTS_DIR.as_posix()}/test_{name}.py; every instance "
                                   "plugin ships one")
        source = path.read_text(encoding="utf-8")
        scanned = scan_source(source, str(path))
        plugin.problems += [f"line {line}: {problem}" for line, problem in scanned]
        if kind.kind == "interference" and not scanned:
            plugin.problems += [f"line {line}: {problem}" for line, problem in framework_code_uses(source)]
        if not scanned:
            plugin.module = _import_instance(plugin)
        found.append(plugin)
    return found


def _schema_problem(schema, label):
    if not isinstance(schema, dict):
        return f"{label} schema must be an object"
    try:
        check_schema(schema)
    except SchemaError as exc:
        return f"{label} schema: {exc}"
    return None


def _shape_problems(plugin, kind):
    module = plugin.module
    problems = [f"defines no {key}" for key in MODULE_KEYS if not hasattr(module, key)]
    if problems:
        return problems
    if module.API != API:
        problems.append(f"API is {module.API!r}; this coach runs API {API}")
    if module.KIND != kind.kind:
        problems.append(f"KIND is {module.KIND!r} but the module lives in {kind.package}/ ({kind.kind})")
    if module.NAME != plugin.name:
        problems.append(f"NAME is {module.NAME!r}; it must equal the file name {plugin.name}")
    if not isinstance(module.SUMMARY, str) or not module.SUMMARY.strip():
        problems.append("SUMMARY must be one plain sentence")
    params = module.PARAMS
    if not isinstance(params, dict) or set(params) != {"schema", "defaults"} or not isinstance(params.get("defaults"), dict):
        problems.append('PARAMS must be {"schema": {...}, "defaults": {...}}')
    else:
        problem = _schema_problem(params["schema"], "PARAMS")
        if problem:
            problems.append(problem)
    if kind.stateful:
        state = getattr(module, "STATE", None)
        if not isinstance(state, dict) or set(state) != {"schema", "initial"}:
            problems.append('STATE must be {"schema": {...}, "initial": {...}}')
        else:
            problem = _schema_problem(state["schema"], "STATE")
            if problem:
                problems.append(problem)
            elif validate_schema(state["initial"], state["schema"]):
                problems.append("STATE initial does not validate against STATE schema")
    modes = getattr(module, "LOAD_MODES", None)
    if modes is not None and (not isinstance(modes, tuple) or not modes
                              or any(m not in units.LOAD_MODES for m in modes)):
        problems.append(f"LOAD_MODES must be a tuple of load modes from {', '.join(units.LOAD_MODES)}")
    problems += _flag_problems(plugin, module.FLAGS)
    problems += _cite_problems(module.CITES)
    for name in kind.required:
        if not callable(getattr(module, name, None)):
            problems.append(f"defines no {name}() function; a {kind.kind} needs {', '.join(kind.required)}")
    return problems


def _flag_problems(plugin, declared):
    if not isinstance(declared, dict):
        return ["FLAGS must be a dict"]
    if plugin.source == "framework":
        return [] if not declared else ["framework plugins register flag codes in coach/flags/, not FLAGS"]
    problems = []
    for code, spec in declared.items():
        if not isinstance(code, str) or not code.startswith(INSTANCE_PREFIX) or not _NAME.fullmatch(code):
            problems.append(f"flag code {code!r} must start {INSTANCE_PREFIX} and be lowercase snake case")
            continue
        severities = spec.get("severities") if isinstance(spec, dict) else None
        if not severities or any(s not in flags.SEVERITIES for s in severities):
            problems.append(f"flag {code}: severities must be some of {', '.join(flags.SEVERITIES)}")
        if not isinstance(spec, dict) or not str(spec.get("summary") or "").strip():
            problems.append(f"flag {code}: give a summary")
    return problems


def _cite_problems(cites):
    if not isinstance(cites, tuple):
        return ["CITES must be a tuple of claim refs"]
    problems = []
    for ref in cites:
        match = _CLAIM_REF.fullmatch(ref) if isinstance(ref, str) else None
        if not match:
            problems.append(f"CITES entry {ref!r} is not a claim ref rn:<note>.<n>")
        elif match.group(1).startswith("local-"):
            problems.append(f"CITES entry {ref} is a local claim; plugins cite template claims only")
    return problems


def _register_flags(plugin):
    for code, spec in plugin.module.FLAGS.items():
        known = flags.registry().get(code)
        if known is None:
            flags.register(code, owner=f"plugin {plugin.name}", severities=tuple(spec["severities"]),
                           summary=spec["summary"])


@dataclass
class Registry:
    plugins: list

    def get(self, kind, name):
        """The valid plugin of a kind (scheme, schedule, transform, interference, conditioning) with this name, or None."""
        return next((p for p in self.plugins if p.kind == kind and p.name == name and p.valid), None)

    def find(self, name):
        return [p for p in self.plugins if p.name == name]

    def names(self, kind):
        return sorted(p.name for p in self.plugins if p.kind == kind and p.valid)

    def problems(self):
        return [{"name": p.name, "kind": p.kind, "source": p.source, "path": p.path.as_posix(), "message": message}
                for p in self.plugins for message in p.problems]


def load(root=None):
    """Every framework plugin and, with a root, every instance plugin, each checked against the contract."""
    found = []
    for kind in kinds().values():
        framework = _framework_plugins(kind)
        found += framework
        if root is not None:
            found += _instance_plugins(root, kind, {p.name for p in framework})
    for kind in kinds().values():
        for plugin in found:
            if plugin.package == kind.package and plugin.module is not None:
                plugin.problems += _shape_problems(plugin, kind)
                if plugin.source == "instance" and not plugin.problems:
                    _register_flags(plugin)
    return Registry(found)


def merged_params(plugin, params):
    """(params with defaults filled, [Error]) for a plugin's params; error paths start at the params object."""
    schema = plugin.module.PARAMS["schema"]
    merged = dict(plugin.module.PARAMS["defaults"])
    merged.update(params or {})
    return merged, validate_schema(merged, schema)


def initial_state(plugin):
    return dict(plugin.module.STATE["initial"])


def state_errors(plugin, data):
    return validate_schema(data, plugin.module.STATE["schema"])


def _supported_path(registry, mode):
    """Where a slot of `mode` can go instead: hold for a timed or distance line, else the schemes that take it."""
    if registry.get("scheme", "hold") is not None:
        if mode == "duration":
            return '; use hold, and change the duration with propose override --sets "2x35s rpe7"'
        if mode == "distance":
            return "; use hold, which repeats the program's distance"
    names = [name for name in registry.names("scheme")
             if mode in (getattr(registry.get("scheme", name).module, "LOAD_MODES", None) or units.LOAD_MODES)]
    return f"; schemes that program it: {', '.join(names)}" if names else ""


def program_problems(doc, registry):
    """(JSONPath, message) for every scheme, session scheme, schedule rule, deload rule and interference rule the
    registry lacks or whose params fail, and every slot whose load mode its scheme's LOAD_MODES leaves out."""
    found = []

    def check(kind, name, params, path):
        plugin = registry.get(kind, name)
        if plugin is None:
            known = ", ".join(registry.names(kind)) or "none"
            found.append((f"{path}.{'rule' if kind == 'schedule' else 'name'}",
                          f"no {kind} named {name}; known: {known}"))
            return None
        _, errors = merged_params(plugin, params)
        found.extend((f"{path}.params{error.path[1:]}", error.message) for error in errors)
        return plugin

    for s_index, session in enumerate(doc["sessions"]):
        for e_index, exercise in enumerate(session["exercises"]):
            scheme = exercise["scheme"]
            path = f"$.sessions[{s_index}].exercises[{e_index}].scheme"
            plugin = check("scheme", scheme["name"], scheme["params"], path)
            modes = getattr(plugin.module, "LOAD_MODES", None) if plugin else None
            if modes is not None and exercise["load_mode"] not in modes:
                found.append((f"{path}.name", f"{scheme['name']} programs only {', '.join(modes)} lines; this slot "
                                              f"is {exercise['load_mode']}"
                                              f"{_supported_path(registry, exercise['load_mode'])}"))
    for s_index, session in enumerate(doc["sessions"]):
        scheme = session.get("scheme")
        if scheme is None or session["kind"] != "conditioning":
            continue
        path = f"$.sessions[{s_index}].scheme"
        plugin = check("conditioning", scheme["name"], scheme["params"], path)
        hook = getattr(plugin.module, "problems", None) if plugin else None
        if hook is not None and not any(p.startswith(f"{path}.params") for p, _ in found):
            merged, _ = merged_params(plugin, scheme["params"])
            found.extend((f"{path}.params{where[1:]}", message) for where, message in hook(merged, session))
    schedules = [(doc["schedule"], "$.schedule")]
    if doc.get("minimum_week"):
        schedules.append((doc["minimum_week"]["schedule"], "$.minimum_week.schedule"))
    for schedule, at in schedules:
        plugin = check("schedule", schedule["rule"], schedule["params"], at)
        if plugin is not None and not any(p.startswith(f"{at}.params") for p, _ in found):
            hook = getattr(plugin.module, "problems", None)
            if hook is not None:
                merged, _ = merged_params(plugin, schedule["params"])
                found.extend((f"{at}.params{path[1:]}", message) for path, message in hook(merged, doc))
    deload = doc["blocks"]["deload_rule"]
    check("transform", deload["name"], deload["params"], "$.blocks.deload_rule")
    seen = set()
    for index, rule in enumerate(doc.get("interference", [])):
        path = f"$.interference[{index}]"
        if rule["name"] in seen:
            found.append((f"{path}.name", f"interference rule {rule['name']} is listed twice"))
        seen.add(rule["name"])
        check("interference", rule["name"], rule["params"], path)
    return found
