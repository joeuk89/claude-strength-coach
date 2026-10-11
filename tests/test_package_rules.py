"""Rules every file in the package must follow (contract C1, C5)."""

import ast
import sys
import unittest

from tests.support import REPO_ROOT

PACKAGE = REPO_ROOT / "coach"
UNITS_MODULE = "coach/units.py"

# (path, stripped source line) pairs allowed to double, halve or convert
# outside coach/units.py. Adding one is a reviewed change to this test.
ALLOWLIST = set()

_DOUBLING = {2, 0.5}
_HALVING = {2}
_KG_LB = ("0.45359237", "2.20462")


def _constant(node):
    """The number a node stands for, seeing through a unary sign."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        node = node.operand
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return abs(node.value)
    return None


def find_unit_arithmetic(source, filename="<sample>"):
    """Return [(line number, form)] for every doubling, halving or kg/lb literal."""
    found = []
    for node in ast.walk(ast.parse(source, filename)):
        if isinstance(node, ast.BinOp):
            left, right = _constant(node.left), _constant(node.right)
            if isinstance(node.op, ast.Mult) and (left in _DOUBLING or right in _DOUBLING):
                found.append((node.lineno, "multiplies by 2 or 0.5"))
            elif isinstance(node.op, (ast.Div, ast.FloorDiv)) and right in _HALVING:
                found.append((node.lineno, "divides by 2"))
            elif isinstance(node.op, (ast.Div, ast.FloorDiv)) and right == 0.5:
                found.append((node.lineno, "divides by 0.5"))
        elif isinstance(node, ast.AugAssign):
            value = _constant(node.value)
            if isinstance(node.op, ast.Mult) and value in _DOUBLING:
                found.append((node.lineno, "multiplies by 2 or 0.5"))
            elif isinstance(node.op, (ast.Div, ast.FloorDiv)) and value in _HALVING | {0.5}:
                found.append((node.lineno, "divides by 2 or 0.5"))
        elif isinstance(node, ast.Constant) and type(node.value) is float:
            if repr(node.value).startswith(_KG_LB):
                found.append((node.lineno, "kg/lb conversion factor"))
    return found


def package_files():
    return sorted(PACKAGE.rglob("*.py"))


class ScannerTest(unittest.TestCase):
    CAUGHT = [
        "y = x * 2", "y = 2 * x", "y = x * 2.0", "y = 2.0 * x", "y = x * 0.5", "y = 0.5 * x", "y = x * -2",
        "y = x / 2", "y = x / 2.0", "y = x // 2", "y = x // 2.0", "y = x / 0.5",
        "x *= 2", "x *= 2.0", "x *= 0.5", "x /= 2", "x /= 2.0", "x //= 2", "x //= 2.0",
        "f = 0.45359237", "f = 2.20462", "f = 2.2046226218", "y = x * 0.45359237", "y = x / 2.20462",
    ]
    ALLOWED = [
        "y = x * 3", "y = x / 4", "y = round(x, 2)", "y = x ** 2", "y = x - 2", "y = x + 0.5",
        "y = [1, 2][0]", "y = x % 2", "x *= 3", "x += 2", "y = '2.20462'",
    ]

    def test_catches_every_form(self):
        for source in self.CAUGHT:
            with self.subTest(source=source):
                self.assertTrue(find_unit_arithmetic(source), source)

    def test_ignores_other_arithmetic(self):
        for source in self.ALLOWED:
            with self.subTest(source=source):
                self.assertEqual(find_unit_arithmetic(source), [])


class UnitArithmeticTest(unittest.TestCase):
    def test_only_units_module_doubles_halves_or_converts(self):
        offenders = []
        for path in package_files():
            relative = path.relative_to(REPO_ROOT).as_posix()
            if relative == UNITS_MODULE:
                continue
            source = path.read_text(encoding="utf-8")
            lines = source.splitlines()
            for line, form in find_unit_arithmetic(source, relative):
                if (relative, lines[line - 1].strip()) not in ALLOWLIST:
                    offenders.append(f"{relative}:{line} {form}: {lines[line - 1].strip()}")
        self.assertEqual(offenders, [], "use coach.units for this arithmetic")

    def test_units_module_exists(self):
        self.assertTrue((REPO_ROOT / UNITS_MODULE).is_file())


class PythonFloorTest(unittest.TestCase):
    def test_every_module_parses_as_python_3_11(self):
        for path in package_files():
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding="utf-8"), str(path), feature_version=(3, 11))

    def test_entry_point_parses_as_python_3_6(self):
        for name in ("__init__.py", "__main__.py"):
            with self.subTest(name=name):
                ast.parse((PACKAGE / name).read_text(encoding="utf-8"), name, feature_version=(3, 6))


class StandardLibraryOnlyTest(unittest.TestCase):
    def test_no_third_party_imports(self):
        local = {"coach", "tests"}
        allowed = set(sys.stdlib_module_names) | local | {"__future__"}
        offenders = []
        for path in package_files() + sorted((REPO_ROOT / "tests").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if name.split(".")[0] not in allowed:
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: {name}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
