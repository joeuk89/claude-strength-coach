# Record formats

The record lines and page skeletons the coach writes by hand. Every
other part of a check-in record, overlay or rendered page comes from a
`coach` command: correct the data and re-run the command, never edit a
rendered region.

## Check-in record: Coach's read, weight and nutrition

Three lines at the end of the Coach's read, from `nutrition status` and
the reply's Food field:

```markdown
Weight (trend or scale) · targets · adherence. Trend vs. target rate — on track?
Protein: <7-day avg> g vs floor <g> (<n> of 2 toward a raise | raised to <g> | under) · days logged <n>/7 · anchors most days: y/n
Override: none | active, expires <date> | expired <date> | renewal flagged · Sleep gate: <status> (deficit only)
```

A field the reply didn't answer reads "not supplied".

## Check-in record: Decisions

Decisions opens with the block status line, copied from the
`status_line` that `block close` or `block decide` printed (`block
status` prints it again). The adherence decision line follows only when
the adherence trigger was presented or an under-80 % override was
agreed; `structure decide` prints it:

```markdown
Block <n> · <count> of <ceiling> hard weeks · triggers <k> of 4 (<names>) · light week: <state>
Adherence trigger: <n> % over 4 weeks: adopted | declined: <reason> | deferred to <date>
```

An override adds the session after the outcome: `Adherence trigger: 76 %
over 4 weeks: adopted (override: adds Sat conditioning)`.

## Deep check-in record: body composition

When body composition applies, Block planning ends with one line that
says when the next reading is due:

```markdown
**Body composition:** waist <reading, "not supplied" or "not due"> · body fat <reading, "not supplied" or "not due"> · photos: <"athlete's one-line read", "not supplied" or "not due"> · **Last reading:** <date> · **Next reading due:** first deep check-in on or after <last reading + 4 weeks>
```

A reading taken today makes today the **Last reading** date. "Not
supplied" means it was asked and the reply left it out; "not due" means
it wasn't asked. Either way, carry the previous **Last reading** date
forward; with no reading ever, write "none" and make the next deep
check-in the due one. Photos stay with the athlete: record only their
one-line read.

## Standalone reprogram or one-off week

A programming pass that `/check-in` didn't start adds a section to the
newest check-in record, with the overlay's two region markers on their
own lines below it, filled by `overlay render --into`:

```markdown
## Week reprogrammed — YYYY-MM-DD

**Span:** <start> → <end> · **Reason:** <missed session / deload / travel / …> · **Mode:** <mode>

<!-- coach:begin overlay <id> -->
<!-- coach:end overlay <id> -->
```

A one-off week ends the section with "Normal program resumes <date>."
With no check-in record yet (a brand-new program), the pass creates
`check-ins/YYYY-MM-DD.md`: a header noting the program's start date and
structure, then `## The week ahead` holding the region.

## profile.md: the first version

`/setup` writes it from this skeleton. It holds prose only a human
reads; units, training days, equipment, niggles and avoided exercises
live in `config.toml` and `data/`.

```markdown
# <Name> — Athlete Profile

The goal, the week and the limits in words. Units, training days,
session length, equipment, niggles and avoided exercises live in
`config.toml` and `data/`.

_Last reviewed: YYYY-MM-DD_

## Goal

(In the athlete's words, plus what it means for the program.)

## Training week

(The weekly shape in words: coach-led sessions and who runs them,
classes, runs, which days are fixed and which can move.)

## Equipment

(Where they train and anything about the kit the config can't say.)

## Injuries / limitations

(Each limitation's story in a line or two. "None currently" is an
answer.)

## Coach's notes

(Historical training, recent consistency and time off; confirmation of the
current programming level, and unresolved/deferred setup answers. Later,
per-athlete patterns. Machine-owned numeric facts stay in config/data.)
```

## profile.md: Nutrition & goals

`/goals` writes this section. The numbers live in `config.toml`'s
`[nutrition]` table; the section holds what only a human reads:

```markdown
## Nutrition & goals

The numbers (phase, trend rate, protein, anchors, any override) are in `config.toml` → `[nutrition]`.

- **Apps:** Hevy: … · MacroFactor: yes / no
- **Goal:** <in the athlete's words> → <phase sequence, with the trigger for each next phase>
- **Calories:** set by MacroFactor (<goal type, rate, calorie shifting>)
  — or, no app: starting estimate (<method>, <date>); trend changes since: <date: reason>, …
- **Protein basis:** <why this reference mass: the body-fat reading, its method and date>
- **Anchors:** <how they were chosen; what the athlete likes>
- **Override:** <the story behind an active one, if any>
- **Sleep gate:** passed (<14-day avg>, <date>) | recomp (<14-day avg>, <date>) | pending measurement (<what was reported>) | not evaluated

_Revised: YYYY-MM-DD_
```
