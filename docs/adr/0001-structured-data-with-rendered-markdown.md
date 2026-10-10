---
status: accepted
date: 2026-10-11
---

# Structured data is the source of truth; markdown is rendered from it

The system began as markdown edited by the coach: session tables, a weekly
prescription inside the newest check-in, a profile that accumulated dated
reports. Nothing could be computed from it, the same fact lived in several
places, and the one convention that mattered most (per-hand dumbbell loads
versus the doubled value Hevy stores) was restated in eight documents and
still reached Hevy wrong. We decided that anything a script reads or
writes (the program, the exercise library, the overlay in force, rotation
state, the history cache) is JSON with a schema version, that human-edited
settings are TOML, and that the markdown views the athlete reads
(session pages, the brief, the dashboard, check-in tables) are rendered
from the data and checked for freshness, never hand-edited.

## Considered options

- **Keep markdown as the source and parse it.** Rejected: table shapes
  drifted three times in two months, and a parser over prose is the
  fragile part of every such system.
- **Structure everything, including prose.** Rejected: the goal
  narrative, coach's notes, check-in judgement and research notes are
  prose by nature and lose value as fields. The rule is "if a script reads
  it, data; if only a human reads it, prose; nothing is both".

## Consequences

- Hand edits to a rendered file fail validation and must be made in the
  data file or by re-rendering.
- Existing instances migrate once through a versioned, backed-up,
  reviewed migration; old check-ins stay as prose archive.
- The standard library reads TOML but cannot write it, so scripts never
  write config; all machine state is JSON even when humans read it.
