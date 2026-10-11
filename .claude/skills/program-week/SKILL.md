---
name: program-week
description: Use when a span of days needs programming — the coming week, the rest of this week, or a week that breaks the pattern (a deload, travel, illness recovery, limited kit, a compressed schedule) — with coach-set loads, rep targets, RPE and per-exercise notes written to Hevy. Triggers include "/program-week", "program my week", "set my weights for this week", "bump my squat", "reprogram the rest of the week", "deload week", "plan my deload", "I'm traveling next week", "next week is disrupted", "plan me a fallback week", /check-in finishing its decisions or agreeing a light week, or /new-program finishing a first-time program (the opening week).
---

# Programming pass

One run of this skill is one **programming pass**: one mode, one
overlay, one approval. It turns the plan and the latest review into the
prescription for a span of days — per session, per exercise: load,
reps, RPE, a focus where warranted, and the standing cues — records it
as an **overlay** (`data/overlays/<id>.json`), the prescription the next
check-in judges adherence against, and writes it into the athlete's
Hevy routines.

The program (`data/program.json`, rendered to `routine/` by `program
render`) stays the block-level plan: weekly numbers never go into it. A
structural change (a swap, an added exercise, a set count, an execution
change) edits `data/program.json`, plan first, then Hevy. A one-off week
(light, constrained or reshuffle mode) never changes the program: its
temporary sessions live in the overlay and in temporary Hevy routines,
and the normal weeks resume from the untouched program.

Requires `profile.md` and `data/program.json`: if either is missing, run
`/setup` or `/new-program` first.

**Loads come from `coach` output; quote them.** Never convert kg and
lb, split a dumbbell total or round a load by hand: `units convert`,
`units format` and `units round` do it, and the overlay's rendered
tables are the only loads the brief shows.

**One approval per pass.** Every mode ends with the same coach's brief
and write line (step 4); only a missed-day rule that matches presents
`missed plan`'s own summary and write line instead. Then stop and wait
for the athlete's reply: only "go" (or a clear yes) lets the pass write,
and it approves every write the line names.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

## 1. Read the context and pick the mode

Read [context.md](context.md) on every run: what to read, the logged
workouts, the rotation position, the days off, Hevy freshness and the
first-run cue backfill. Then pick the mode from what the athlete says,
the session-start status, `state show` and `overlay current`, and name
it in the brief's first line:

| Mode | When | Overlay kind | How |
| --- | --- | --- | --- |
| normal | the coming program week | `weekly` | [compute.md](compute.md): `propose week`, settle each line, `propose finalize` |
| midweek | a missed session, or a change partway through a trained week | `midweek` | [midweek.md](midweek.md): `missed plan`; no matching rule → compute.md with `--kind midweek` |
| light | a deload, light or return week the check-in agreed, or a return after illness | `deload` | compute.md: the `command` that `block decide` printed, or `--kind deload` |
| minimum | short on time at the usual kit, with a configured `minimum_week` | `weekly` | [short-week.md](short-week.md): configure and validate, then `structure minimum` and `--plan` |
| constrained | travel, limited kit, or short on time without a valid minimum | `one_off` | [one-off.md](one-off.md): a coach-built draft through `overlay build` |
| reshuffle | the same sessions on different days | `one_off` | one-off.md: the overlay in force, re-dated; `routines diff` is empty, so nothing goes to Hevy |

A span can mix a reshuffle and a constrained week (two days moved, two
on hotel kit): one overlay, one brief.

**An active one-off week.** When `state.one_off` in `state show` covers
the span, continue in that one-off's mode rather than starting a normal
week: `overlay current` shows its kind, `deload` for light mode and
`one_off` for constrained (temporary sessions) or reshuffle (none).

**Run mode** (every mode). With `mode = "run"` in `config.toml`'s
`[coaching]` table, the athlete wants their own program run as written:
propose no structural change, and make only the ones the athlete asks
for. Loads and checks work as in coach mode: `propose week` gives the
same lines in both.

**No Hevy** (every mode). With `[hevy] enabled = false`, `overlay
approve` is the last write of the pass: skip every Hevy command and run
`python3 -m coach sheets render`, which writes `this-week-sheets.md`, the
per-set sheets the athlete trains from. Never run `routines push`: with
Hevy off it exits 5.

## 2. Compute or build the week

- **normal, midweek, light, minimum:** the scripts propose each line and
  you coach it — [compute.md](compute.md). Mid-week starts with
  [midweek.md](midweek.md).
- **constrained, reshuffle:** you design the span and write the draft —
  [one-off.md](one-off.md).

Both end with an overlay id.

## 3. Build and check the overlay

Read [build.md](build.md): where the overlay renders, its validation,
the check of every prescription before the brief, and the routines
"go" would write.

## 4. Present the coach's brief, and stop

Read [brief.md](brief.md): the brief's parts, the hold-steady short
brief, and the write line with its approval sentence. Never present and
write in the same turn.

## 5. Write, then close out

Only after "go": read [write.md](write.md). It writes exactly what the
write line named, records a one-off week in `data/state.json`, verifies
every routine, publishes the week and recaps it.
