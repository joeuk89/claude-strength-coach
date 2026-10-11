"""Hidden data blocks: TOML inside an HTML comment at the top of a markdown file (contract C11).

The first line is exactly `<!-- coach:<kind>`; the block ends at the first
line that is exactly `-->`. Everything after that line is returned
verbatim, so a caller can rewrite the markdown and keep the block's bytes.
"""

import tomllib
from pathlib import Path

from coach.errors import ValidationError

KINDS = ("note", "card")
CLOSER = "-->"


def read(path, kind):
    """Return (data, rest): the parsed TOML and the text after the closing line."""
    if kind not in KINDS:
        raise ValueError(f"data block kind must be one of {', '.join(KINDS)}, found {kind!r}")
    path = Path(path)
    return _parse(path.read_text(encoding="utf-8"), kind, str(path))


def _parse(text, kind, name):
    opener = f"<!-- coach:{kind}"
    lines = text.split("\n")
    first = lines[0].rstrip("\r")
    if first != opener:
        raise ValidationError(f"{name}: the first line must be exactly {opener!r}, found {first!r}")

    closing = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r") == CLOSER), None)
    if closing is None:
        raise ValidationError(f"{name}: the data block is never closed by a line that is exactly '-->'")

    body = "\n".join(lines[1:closing])
    if CLOSER in body:
        raise ValidationError(f"{name}: the data block contains '-->' before its closing line, "
                              "which would end the hidden comment early")
    try:
        data = tomllib.loads(body)
    except tomllib.TOMLDecodeError as exc:
        raise ValidationError(f"{name}: the data block is not valid TOML ({exc})") from None
    return data, "\n".join(lines[closing + 1:])
