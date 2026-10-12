# Research notes

This page explains where the coach's numbers come from: the research
notes in `research/`, the claims inside them and the `rn:` citations
that tie every threshold back to its evidence. Read it when you want to
know why a rule is what it is, when a note has expired, or when the
coach researches something for you.

## Every number traces to a claim

Each number the coach uses, from the 6-hard-week ceiling to the 24-hour
gap before a heavy lower session, cites a claim in a **research note**
(see [the glossary](../../CONTEXT.md) under "Research note"). The
citation looks like `(rn:deloads.3)`: the note id, then the claim
number. The coaching principles in [`CLAUDE.md`](../../CLAUDE.md) cite
them line by line, the skills and the shipped progression schemes cite
them, and the comments in
[`config.example.toml`](../../config.example.toml) cite the claim behind
each cardio threshold.

To read any claim with its sources in full:

```bash
python3 -m coach research show rn:running-load.1
```

```json
{"ref": "rn:running-load.1",
 "claim": {"n": 1,
   "text": "A run more than 1.10 × the longest run in the previous 30 days is linked to a higher risk of an overuse running injury.",
   "basis": "evidence", "sources": ["frandsen-2025"], "status": "current"},
 "sources": [{"id": "frandsen-2025",
   "citation": "Frandsen JSB, Hulme A, Parner ET, ... How much running is too much? Identifying high-risk running sessions in a 5200-person cohort study. Br J Sports Med. 2025;59(17):1203-1210.",
   "url": "https://doi.org/10.1136/bjsports-2024-109380",
   "type": "observational", "year": 2025}],
 "note": {"id": "running-load", "kind": "template", "status": "current",
   "written": "2026-10-11", "review_by": "2027-10-11", "confidence": "low"},
 "superseded_locally_by": null}
```

`research show` also takes a note id, and prints the whole note's data
block with its status.

## Two kinds of note, one format

| Kind | Path | Who writes it | Framework sync |
|---|---|---|---|
| Template note | `research/<id>.md` | the template's authors | refreshed from the template |
| Local note | `research/local/local-<slug>.md` | the coach, in your workspace | never touched |

The id is the file name without `.md`, and a local note's id always
starts with `local-`. In your workspace the coach writes local notes
only. It never edits a template note, because `/framework-sync` would
overwrite the edit. To change what a template claim says for you, the
coach writes a local note that supersedes it (below).

### The note format in plain words

A note has three parts:

1. **The data block**: settings and claims in TOML, hidden inside an
   HTML comment so GitHub does not show it. It holds the topic, the one
   question the note answers, when it was written, its `review_by`
   date, its `confidence` (`high`, `moderate` or `low`), the areas it
   `applies_to`, optional tags, and for a local note the template claims
   it `updates`. Then the sources, each with an id, a full citation, a
   URL (the DOI link when one exists), its type and year. Then the
   claims: each a number, one sentence with the exact figures the coach
   uses, a `basis` of `evidence` (the sources support it directly),
   `consensus` (a position stand or expert consensus) or `heuristic` (a
   coaching rule of thumb, the only kind allowed no sources), its
   sources, and a `status` of `current` or `retired`.
2. **The rendered region**: a status line, the claims table and the
   sources table, between `coach:begin research` and `coach:end
   research` markers. Only `research render` writes it, and `coach check`
   fails a region edited by hand.
3. **The prose**: an Answer of at most three sentences, Evidence keyed to
   the claim numbers, Applying it, and Open questions.

The opening of the shipped deloads note, with one source and the first
claim:

```toml
<!-- coach:note
schema_version = 1
id = "deloads"
topic = "Deloads"
question = "When should a lifter take a lighter week, and what should it contain?"
written = 2026-10-12
review_by = 2027-10-12
confidence = "low"
applies_to = ["deload", "autoregulation"]
tags = ["fatigue", "adherence"]

[[sources]]
id = "bell-2023"
citation = "Bell L, Strafford BW, Coleman M, Androulakis Korakakis P, Nolan D. Integrating Deloading into Strength and Physique Sports Training Programmes: An International Delphi Consensus Approach. Sports Med Open. 2023;9:87."
url = "https://doi.org/10.1186/s40798-023-00633-0"
type = "consensus"
year = 2023

[[claims]]
n = 1
text = "Deloads may be pre-planned or triggered by fatigue at any point in a block; this framework triggers them by fatigue, with a ceiling on how long a block runs without one."
basis = "consensus"
sources = ["bell-2023", "coleman-2024"]
status = "current"
-->
```

A claim's number is never reused. A claim that no longer holds is
retired, not deleted, and may point at the claim that replaced it.

### The rehab line

A note whose areas include `rehab` must carry this line in its prose,
on a line of its own:

```text
This note does not replace assessment by a qualified professional.
```

The coach still recommends a qualified professional for pain or a
suspected injury, whatever a note says.

## Review status and expiry

`review_by` is the date a note needs its next full review: 18 months
after it was written, 12 months when confidence is low, never more than
24 months. `research status` gives every note one of three statuses:

| Status | Meaning |
|---|---|
| `current` | before its review date |
| `due_soon` | within 60 days of its review date |
| `expired` | past its review date |

Each area the notes cover gets a status too, and `research status` lists
template claims that a local note supersedes under
`superseded_locally`. From the template today, the summary reads
`"summary": {"current": 15, "due_soon": 0, "expired": 0}`.

**An expired note is not cited.** Its claims and its sources stay out of
new recommendations until the area is researched again. In practice:

- `coach check` warns per expired area (`research_expiry`).
- A proposal line whose scheme cites a claim in an expired area says
  "evidence under review (<note id> expired <date>)" instead of citing
  it, and carries an `evidence_expired` flag. Nothing is blocked.
- The deep check-in lists every expired area in its Block planning
  section, as `Research: expired <area> (<note id>)` or `Research:
  nothing expired`, and offers to refresh an area the coming block
  depends on.

A local note that is current or due soon keeps its area current even
when the template note behind it has expired.

## How the coach researches

When a recommendation depends on evidence, or you ask for best practice,
the coach follows `reference/research-notes.md`:

1. **Check what exists** with `python3 -m coach research status`
   (`--area <area>` narrows it). A current or due-soon note that answers
   the question is enough: the coach cites its claim and stops. A claim
   listed under `superseded_locally` is cited from the local note.
2. **Otherwise research online**, never from memory: peer-reviewed
   research and meta-analyses first, then established evidence-based
   educators and professional bodies, recent sources preferred.
3. **Save a local note** at `research/local/local-<slug>.md`, then
   render its region and check it:

   ```bash
   python3 -m coach research render local-<slug>
   python3 -m coach check --only research_notes,research_citations,research_render_fresh
   ```

4. **Cite the claim** as `(rn:local-<slug>.<n>)` in the conversation and
   in the record the decision lands in.

The coach writes a local note whenever it researches something for you:
a new program, a niggle, a question you asked. Findings that live only in
the conversation are lost when it ends.

### Newer evidence against a template claim

A local note can list template claims in its `updates` and state the
replacement as its own claim. `research status` then reports the
template claim under `superseded_locally`, `research show` on that claim
names the local note, and the proposal's rationale may cite the local
note instead. If the template later retires a claim your note updates,
`coach check` warns so the coach re-reads the template note and refreshes
yours.

### Deciding against a current claim

Sometimes you and the coach decide against a current claim with no newer
evidence, say a shorter gap before a heavy session because your week
leaves no other slot. That is recorded in the check-in record's Decisions
section as `contradicts rn:<note>.<n>: <reason>`, so the departure is
dated and explained rather than silent.

## The citation check

Every `rn:` reference in the workspace is scanned, and whether it
resolves is checked.

| Command | What it does |
|---|---|
| `research status [--area A] [--kind template\|local] [--expired]` | every note with its review status, local supersessions and each area's status |
| `research show <id or ref>` | one note's data block, or one claim with its sources and the local note superseding it |
| `research cites [--unresolved]` | every claim reference in the framework and your files, and whether it resolves |
| `research validate` | validates every note; exit 1 naming each problem |
| `research render [id] [--dry-run]` | rewrites the rendered region of one note, or of every note, and nothing else |

The `coach check` items are `research_notes` (an invalid note fails;
an `updates` entry that no longer resolves warns), `research_citations`,
`research_render_fresh` (a region that differs from a fresh render
fails) and `research_expiry` (an expired area warns). Framework files
such as `CLAUDE.md`, the skills and `reference/` may cite template claims
only, and a missing, retired or local claim there fails the check. Your
own files, `profile.md`, the check-ins, `data/` and local notes, may
cite both kinds; a missing or retired claim there warns, except in a
check-in record, which is history and keeps the reference it was
written with.

One broken note never stops a proposal: the readers use only the notes
that pass validation, and `coach check` names the broken one. From a
fixture with a note that numbers two claims `1`:

```text
coach: 1 research note(s) are invalid; see python3 -m coach research validate
research/fixture-broken.md: more than one claim numbered 1
```

## The template notes that ship

`ls research/` lists them. Each answers one question.

| Note | Topic | Areas | The question it answers |
|---|---|---|---|
| `autoregulation` | Autoregulation with RPE and reps in reserve | autoregulation | Can RPE and reps-in-reserve ratings set and adjust training loads, and when does a rising RPE mean fatigue? |
| `bodyweight-skill-progression` | Bodyweight-skill progression | bodyweight_skills, progression, exercise_selection | How do progressive calisthenics compare with loaded training, and how should assistance and leverage be progressed? |
| `concurrent-training` | Concurrent training | concurrent_training | How much does running or other cardio interfere with lifting, and how should the two be spaced? |
| `deloads` | Deloads | deload, autoregulation | When should a lifter take a lighter week, and what should it contain? |
| `detraining-return` | Detraining and return after a layoff | return_to_training | How much strength and size does a lifter lose during a layoff, and how should training restart afterwards? |
| `endurance-fuelling` | Fuelling endurance training and events | energy_balance, concurrent_training | What should a coach review about fuelling an outside endurance plan or event? |
| `minimum-effective-dose` | Minimum and maintenance dose | minimum_dose | What is the least training that keeps size and strength, and the least that still builds strength? |
| `progression-training-age` | Progression by training age | progression, autoregulation | How fast can load rise for beginner, intermediate and advanced lifters, and which progression scheme suits each? |
| `protein-energy-deficit` | Protein and the energy deficit | protein, energy_balance | How much protein should a lifter eat, per kg of which mass, and how fast should they lose or gain weight to keep or build muscle? |
| `proximity-to-failure` | Proximity to failure, load and rep ranges | proximity_to_failure, autoregulation | How close to failure, and with what loads and rep ranges, should working sets be taken for hypertrophy and for strength? |
| `resting-hr` | Resting heart rate as a fatigue and illness signal | deload, return_to_training | Is a rise in resting heart rate above the athlete's own baseline worth flagging, and how should the baseline, threshold and minimum data be set? |
| `running-load` | Running load | concurrent_training | How should the coach watch an athlete's running load for overuse-injury risk, and what load measure should it report? |
| `sleep-dieting` | Sleep and dieting | sleep, energy_balance | How much sleep does an adult lifter need, and should short sleep stop them from eating in a deficit? |
| `strength-for-running` | Strength training for runners | concurrent_training, exercise_selection | What can strength training contribute to an outside running plan? |
| `volume-frequency` | Weekly sets and training frequency | volume, frequency | How many hard sets should each muscle get per week and per session, and how many sessions should they be spread across? |

The coaching principles in `CLAUDE.md` cite these notes claim by claim:
progressive overload and load increases from `progression-training-age`,
volume and frequency from `volume-frequency`, intensity from
`proximity-to-failure`, RPE targets and drift from `autoregulation`,
the block rules from `deloads`, the return bands
and illness rule from `detraining-return`, the spacing rules from
`concurrent-training`, protein from `protein-energy-deficit`, the sleep
gate from `sleep-dieting`, and the minimum week from
`minimum-effective-dose`. The cardio thresholds in `config.example.toml`
cite `running-load` and `sleep-dieting`.

## Framework sync and your notes

Template notes are framework files. `/framework-sync` refreshes them
from the template, so a note the template's authors re-reviewed arrives
with its new `written` and `review_by` dates and any retired or added
claims, and `coach check` then flags any framework file that cites a
retired claim. `research/local/` is yours: sync never writes there, and a
local note's `updates` keep superseding the template claims they name
after every sync.
