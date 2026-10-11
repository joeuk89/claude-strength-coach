"""Edit config.toml text the way /setup does with the Edit tool: set a key in place, uncommenting it if needed."""

import json
import re

_HEADER = re.compile(r"^\[([A-Za-z0-9_.-]+)\]\s*(#.*)?$")


def toml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float, str)):
        return json.dumps(value)
    if isinstance(value, list):
        return "[" + ", ".join(toml_value(item) for item in value) + "]"
    raise TypeError(f"no TOML form for {value!r}")


def _span(lines, table):
    """(header index, end index) of an uncommented [table], or None."""
    start = next((i for i, line in enumerate(lines) if (m := _HEADER.match(line)) and m.group(1) == table), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if _HEADER.match(lines[i])), len(lines))
    return start, end


def set_key(text, table, key, value):
    lines = text.split("\n")
    span = _span(lines, table)
    if span is None:
        lines.extend(["", f"[{table}]", f"{key} = {toml_value(value)}"])
        return "\n".join(lines)
    start, end = span
    live = re.compile(rf"^{re.escape(key)}\s*=")
    commented = re.compile(rf"^#\s*{re.escape(key)}\s*=")
    found = next((i for i in range(start + 1, end) if live.match(lines[i])), None)
    if found is None:
        found = next((i for i in range(start + 1, end) if commented.match(lines[i])), None)
    if found is None:
        lines.insert(start + 1, f"{key} = {toml_value(value)}")
    else:
        lines[found] = f"{key} = {toml_value(value)}"
    return "\n".join(lines)


def apply(text, values):
    """values: {"table" or "table.sub": {key: value}}, applied in order."""
    for table, keys in values.items():
        for key, value in keys.items():
            text = set_key(text, table, key, value)
    return text
