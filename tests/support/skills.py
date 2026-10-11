"""Read a skill folder: its SKILL.md plus the step files it points to."""

from tests.support import REPO_ROOT

SKILLS = REPO_ROOT / ".claude" / "skills"


def skill_names():
    return sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))


def skill_files(name):
    """SKILL.md first, then each step file in the order SKILL.md first names it."""
    folder = SKILLS / name
    main = folder / "SKILL.md"
    text = main.read_text(encoding="utf-8")
    steps = [path for path in folder.glob("*.md") if path.name != "SKILL.md"]
    steps.sort(key=lambda path: (text.find(path.name) == -1, text.find(path.name), path.name))
    return [main, *steps]


def skill_text(name):
    """Every `.md` file in the skill folder, joined in reading order."""
    return "\n\n".join(path.read_text(encoding="utf-8") for path in skill_files(name))


def step_text(name, filename):
    return (SKILLS / name / filename).read_text(encoding="utf-8")


def all_skills():
    return {name: skill_text(name) for name in skill_names()}


def body_lines(path):
    """The file's lines, without a SKILL.md's front matter."""
    lines = path.read_text(encoding="utf-8").rstrip("\n").splitlines()
    if lines and lines[0] == "---":
        lines = lines[lines.index("---", 1) + 1:]
    return lines


def flat(text):
    return " ".join(text.split())
