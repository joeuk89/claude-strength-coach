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
- **Sleep gate:** passed | recomp | pending measurement | not evaluated
  — <assessment date; supported 14-day average; covered dates; source; nightly / self-reported period mean; missing coverage>

_Revised: YYYY-MM-DD_
```

## profile.md: Food & eating

`/recipes` collects this section for first-bank setup or a requested
refresh; `/meal-plan` reads it for standing-template setup. Reuse facts
already in profile prose, config or the conversation, even with older
labels. In one first message ask for every missing field below; after a
partial reply ask only what is still needed. Explain the two plan styles
in that question. A complete section has an answer for each field:
"none" is an answer; missing, "not supplied" or "to decide" is unresolved.
Confirm a complete section is current, then seed recipes without another
interview. A specific recipe request needs only relevant missing facts.

Show the proposed section before writing; write only after the athlete
confirms it. Retain known answers and mark deferred fields "not supplied"
rather than guessing, including allergies. If unresolved facts affect
safe recipe selection or a planning decision, resolve those before
proceeding. An unchanged complete section needs no rewrite.

```markdown
## Food & eating

- **Likes:** <foods, meals and cuisines enjoyed>
- **Dislikes:** <foods to avoid, or none>
- **Allergies/intolerances:** <restrictions, or none reported>
- **Household staples:** <ingredient names always stocked, or none>
- **Cooking appetite:** <assemble-only, batch-cook or cook most days; time/effort limits>
- **Shopping pattern:** <when/how groceries arrive and usual top-ups>
- **Office-day pattern:** <usual weekdays at the office, or none; variable days still to confirm>
- **Meal responsibility/standing coverage:** <who decides each meal, its slot and days; meals self-managed>
- **Plan style:** <loose: a weekly recipe pool with suggested days | strict: a dated menu | no preference>

_Revised: YYYY-MM-DD_
```

A synthetic complete example:

```markdown
## Food & eating

- **Likes:** Rice bowls and eggs.
- **Dislikes:** Mushrooms.
- **Allergies/intolerances:** Peanuts.
- **Household staples:** Eggs, rice, olive oil.
- **Cooking appetite:** Batch-cook Sunday; assemble weekday lunches.
- **Shopping pattern:** Weekly online shop with fresh-food top-ups.
- **Office-day pattern:** Tuesday and Thursday; other weekdays at home.
- **Meal responsibility/standing coverage:** Partner decides dinner Monday to Thursday; other meals self-managed.
- **Plan style:** Loose — weekly recipe pool with suggested days.

_Revised: 2026-10-11_
```

### After the standing template exists

Household staples, Office-day pattern, Meal responsibility/standing
coverage and Plan style are the **planning fields**. Until `/meal-plan`
writes `[nutrition.template]`, no script reads them, so they stay prose
here. The approval that writes the template also replaces those four
lines with one pointer line, so each fact lives in one place (ADR-0001):

```markdown
- **Standing week:** staples, office days, standing coverage and plan style are in `config.toml` → `[nutrition.template]`.
```

The pointer answers all four planning fields for completeness. From then
on a change to one of them is a `/meal-plan` template edit, never a
profile edit, and slot notes derive from the template.

### Standing-template and slot-note consumers

| Food & eating field | Consumer |
|---|---|
| Likes; Dislikes; Allergies/intolerances | `/recipes` selection and sourcing filters; retain restrictions in every draft. |
| Household staples | `[nutrition.template] staples`, using the bank's ingredient names. Staples are stock, not daily protein anchors. |
| Cooking appetite; Shopping pattern | Recipe effort, batch choices and shopping timing; derive relevant per-slot priorities for `[nutrition.bank.slot_notes]`. |
| Office-day pattern | `[nutrition.template] office_days`. Ask about a variable pattern before selecting standing weekdays; an explicit none gives `[]`. |
| Meal responsibility/standing coverage | `[[nutrition.template.standing]]`: `slot`, `days` and `cover` when someone else decides. Self-managed slots stay open unless an approved bank recipe or pool fills them. |
| Plan style | `[nutrition.template] plan_style`: `loose` or `strict`; no preference leaves it unset, so the default applies. |

The example maps to this TOML; the slot notes come from Cooking appetite,
Office-day pattern and Meal responsibility/standing coverage:

```toml
[nutrition.template]
office_days = ["tue", "thu"]
staples = ["eggs", "rice", "olive oil"]
plan_style = "loose"

[[nutrition.template.standing]]
days = ["mon", "tue", "wed", "thu"]
slot = "dinner"
cover = "partner"
kcal = 700        # estimate, shown to the athlete for approval
protein_g = 35    # estimate, shown to the athlete for approval

[nutrition.bank.slot_notes]
lunch = "Assemble weekday lunches; portable on Tuesday and Thursday"
dinner = "Partner decides Monday to Thursday"
```

Cover rows also need `kcal` and `protein_g`: use known values or show
clearly labelled estimates for approval, never as the athlete's answers.
Resolve only missing planning details (such as a cover's days or an
agreed recipe/pool); do not repeat the food interview. Show exact TOML
and each row's meaning, then wait for approval before writing config.

Slot notes are prose under configured slot names. They explain
priorities and coverage in the index; only standing rows create plan
coverage. Show slot-note changes for approval, preserve unrelated
existing notes and run `python3 -m coach recipes render` afterward.
