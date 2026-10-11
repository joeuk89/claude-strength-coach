# Research notes

A research note answers one coaching question with dated, sourced,
numbered claims. Skills, schemes, flag thresholds and check-ins cite a
claim by its id instead of citing sources inline, so every number the coach
uses traces back to the evidence behind it and to the date that evidence
was last reviewed.

Use this doc whenever you research something, refresh a note, or hand note
writing to a subagent. The format is fixed by contract section C28
(`docs/design/coach-contract.md` in the template).

## The two kinds

| Kind | Path | Id | Who writes it | Synced |
|---|---|---|---|---|
| Template note | `research/<id>.md` | lowercase words joined by `-`, never starting `local-` | a template PR | yes, by `/framework-sync` |
| Local note | `research/local/<id>.md` | starts `local-`, e.g. `local-knee-pain` | the coach, in an instance | never: sync does not touch it |

- The id equals the file name without `.md`.
- **In an instance, write local notes only.** Never edit a template note
  there: `/framework-sync` would overwrite the edit. To change what a
  template claim says for this athlete, supersede it with a local note
  (below).
- **Write a local note whenever you research something**: a new program,
  a niggle, an athlete question. Findings that live only in the
  conversation are lost when it ends.

## Citing a claim

A claim is cited as `rn:<note-id>.<n>`, in brackets after the statement it
supports: "default ceiling of 6 hard weeks (rn:<note-id>.<n>)". Python code
carries the ref in a string, such as a `CITES` tuple, never in a comment.

- **Framework files** (`CLAUDE.md`, skills, `reference/`, template notes,
  `coach/`) cite template claims only. A missing, retired or local claim
  there fails `coach check`.
- **Instance files** (`profile.md`, check-ins, `data/`, local notes,
  `plugins/`) may cite both kinds. A missing claim there warns. A retired
  claim warns, except in a check-in: check-ins are history and keep the
  ref they were written with.

## The file

A note has three parts, in this order:

1. **The data block**: TOML inside an HTML comment, so GitHub hides it.
   The first line is exactly `<!-- coach:note` and the block ends at the
   first line that is exactly `-->`. The TOML must not contain `-->`
   anywhere.
2. **The rendered region**: a status line, the claims table and the
   sources table, between `<!-- coach:begin research <id> -->` and
   `<!-- coach:end research <id> -->`. Only `research render` writes it.
   Never edit it by hand: `coach check` fails a region that differs from
   a fresh render.
3. **The prose**: `## Answer` (three sentences at most), `## Evidence`
   (discussion keyed to claim numbers), `## Applying it`, and
   `## Open questions`. Nothing parses the prose.

```
<!-- coach:note
schema_version = 1
id = "local-knee-pain"
topic = "Knee pain and squat volume"
question = "How should knee pain change this athlete's squat volume?"
written = 2026-10-11
review_by = 2027-10-11
confidence = "low"
applies_to = ["rehab", "exercise_selection"]
tags = ["knee"]
updates = ["rn:<template-note-id>.<n>"]

[[sources]]
id = "smith-2024"
citation = "Smith A, Jones B. Title of the paper. Journal. 2024;10:100-110."
url = "https://<the paper's DOI link>"
type = "systematic-review"
year = 2024

[[claims]]
n = 1
text = "One sentence that states the claim, with the exact numbers the coach will use."
basis = "evidence"
sources = ["smith-2024"]
status = "current"
-->

## Answer

This note does not replace assessment by a qualified professional.

...
```

### Keys

- `written`: the date of the last full review. `review_by`: when the note
  needs its next one. Set it to `written` plus **18 months**, or plus
  **12 months** when `confidence` is `low`. It may never be more than
  24 months after `written`.
- `confidence`: `high` when several meta-analyses agree; `moderate` for
  one meta-analysis or consistent trials; `low` for few or indirect
  trials, expert opinion alone, or a claim resting on a preprint.
- `applies_to`: the areas the note informs. Pick from `volume`,
  `frequency`, `proximity_to_failure`, `progression`, `deload`,
  `autoregulation`, `concurrent_training`, `return_to_training`,
  `minimum_dose`, `bodyweight_skills`, `protein`, `energy_balance`,
  `sleep`, `rehab`, `exercise_selection`. A template note needs at least
  one. A local note may have none if it has a tag.
- `tags`: optional free-form labels (`knee`, `travel`), lowercase words
  joined by `-`.
- `updates`: local notes only. The template claims this note supersedes
  in this instance.
- Each source: `id` (unique in the note), `citation`, `url` (https; the
  DOI URL when one exists), `type`, `year`, and `accessed` (a date) for
  educator pages. `type` is one of `meta-analysis`, `systematic-review`,
  `rct`, `observational`, `consensus`, `position-stand`,
  `narrative-review`, `preprint`, `educator`.
- Each claim: `n`, `text`, `basis`, `sources`, `status`, and optionally
  `confidence` when the claim is weaker than the note. A retired claim
  also has `retired_on` and may have `superseded_by` (a claim ref).

## Writing a note

1. **Find the evidence.** Rank sources by evidence quality:
   peer-reviewed research and meta-analyses first, then established
   evidence-based educators and professional bodies, then general
   content. Reputable evidence-based outlets include Stronger By Science
   and the MASS Research Review, Renaissance Periodization, Barbell
   Medicine, the published research of scientists like Brad Schoenfeld,
   and NSCA and ACSM position stands. Prefer recent sources: best
   practice shifts as research accrues. Be sceptical of influencer
   marketing, anecdote and bro-science.
2. **Write the claims.**
   - One sentence per claim.
   - Numbers in a claim's text are the numbers the code and the skills
     use. If the code uses 6, the claim says 6, not "about 5 to 7".
   - `basis = "evidence"` for a claim the sources support directly,
     `"consensus"` for an expert-consensus or position-stand claim, and
     `"heuristic"` for a coaching rule of thumb. Only a heuristic claim
     may have no sources.
   - Number claims from 1. A number is never reused, even after its claim
     is retired.
3. **Write the data block with the Write tool.** Scripts never write the
   TOML.
4. **Render the region**: `python3 -m coach research render <id>`. It
   inserts the region after the data block, or replaces the one there,
   and changes nothing else.
5. **Check it**: `python3 -m coach check --only research_notes,research_citations,research_render_fresh`.
   Fix every `fail`.

**Rehab notes.** A note whose `applies_to` includes `rehab` must carry this
exact line in its prose, on a line of its own:

```
This note does not replace assessment by a qualified professional.
```

## Refreshing a template note (in the template)

Template notes are refreshed in the template repo, never in an instance.

1. Search for evidence newer than the note's `written` date.
2. Keep every claim number. Change a claim's text or sources in place
   when the evidence still supports the same claim with new detail.
3. **Retire, don't delete.** When a claim no longer holds, set
   `status = "retired"` and `retired_on`, and add a new claim with the
   next free number. Point the old one at it with `superseded_by`.
4. Update `written` to today and `review_by` by the rule above.
5. Run `python3 -m coach research render <id>`, then
   `python3 -m coach research cites` and list, in the PR, every place
   that cites a changed or retired claim. A framework file citing a
   retired claim fails `coach check`, so update those citations in the
   same PR.

## Local notes (in an instance)

- **Write one whenever you research something** for this athlete, using
  the steps under "Writing a note".
- **Refresh one** the same way as a template note: keep numbers, retire
  instead of delete, update `written` and `review_by`.
- **When a template note in an area has expired** (`research status`
  shows the area as `expired`, and `coach check` warns), research the
  question again and write a local note that covers the area in
  `applies_to`. A local note that is current or due soon keeps the area
  current.
- **To supersede a template claim for this athlete**, list its ref in the
  local note's `updates` and state the replacement as a local claim.
  `research status` then reports the template claim under
  `superseded_locally`, and `research show` names the local note. If the
  template later retires a claim your note updates, `coach check` warns:
  re-read the template note and refresh yours.

## Commands

| Command | What it does |
|---|---|
| `python3 -m coach research status [--area A] [--kind template\|local] [--expired]` | Every note with its kind and review status (`current`, `due_soon` within 60 days of `review_by`, `expired` after it), template claims superseded locally, and each area's status |
| `python3 -m coach research show <id or ref>` | One note's data block, or one claim with its sources in full and the local note superseding it, if any |
| `python3 -m coach research cites [--unresolved]` | Every claim reference in the framework and instance files, and whether it resolves |
| `python3 -m coach research validate` | Validate every note; exit 1 if any is invalid |
| `python3 -m coach research render [id] [--dry-run]` | Rewrite the rendered region of one note, or of every note |

## Handing note writing to a subagent

Give the subagent the question, the note kind and id, this doc's path, and
the areas the note should cover. Ask it to return the note file it wrote
and the output of `research render` and `coach check`. Read the claims
before citing them: you own every number the coach uses.
