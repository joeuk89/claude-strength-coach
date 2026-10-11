---
name: check-in
description: Use when the athlete wants a training check-in or progress review — weekly by default, with a deeper review when one is overdue, a light week is being proposed, or adherence has dropped. Triggers include "/check-in", "check in", "weekly check-in", "progress review", "how's my training going", "let's review my progress".
---

# Training check-in

Act as the athlete's coach reviewing their training. Two tiers: a
**weekly** check-in (about ten minutes: adherence, weight and
nutrition, the week ahead) and a **deep review** (the full block-level
look). Both open with one **Sunday message** the athlete answers in one
reply. The output is a dated record in `check-ins/`, any agreed
updates, and the coming week's programming pass.

If `profile.md` doesn't exist, stop and run `/setup` first.

## 0. Check the workspace

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. If `routine/`
exists but `data/program.json` does not, this workspace still keeps its
program as hand-written pages: say it needs its one-time bootstrap
migration onto `data/program.json` first, and stop. When a command
fails, tell the athlete what its exit code means, as `CLAUDE.md` "The
coach scripts" sets out.

**Loads come from `coach` output; quote them.** A load read from the
log is a Hevy value: `python3 -m coach units convert --mode <load mode>
--from-hevy-kg <value>` turns it into the athlete's number. Never
convert or split a load by hand.

## 1. Read the context and pick the tier

Read `profile.md` (including **Coach's notes**), `python3 -m coach
program show` and `python3 -m coach state show` (rotation, block, any
one-off week), `routine/program.md` for the program at a glance, and
the newest file in `check-ins/` (plus the newest **deep** one, if the
newest is weekly).

Run a **deep** check-in when any of these is true, otherwise run
**weekly**:

- **6+ weeks** since the last deep check-in (rn:deloads.12). Records
  with a valid Check-in title but no tier count as deep; Program start
  records are setup only. The first check-in ever runs deep.
- **A light week is being proposed** (the hard-week count reached the
  ceiling, or two fatigue triggers fired).
- **The adherence trigger fires** (under 70 %).
- The athlete asks for one.

The coming week being a deload is not a trigger on its own. Before
sending the Sunday message, run `python3 -m coach block close --week
<this week> --dry-run`: its `deep_review` (`due`, `reasons`) applies
these rules to the log. If the reply changes the picture (a second
fatigue trigger, a coach-led session that didn't happen), the real close
in step 4 says so: switch to deep and tell the athlete. The Sunday
message's first line names the tier and why; the athlete can override.
Mark the tier in the record's title line.

**Run mode.** With `mode = "run"` in `config.toml`'s `[coaching]`
table, the athlete wants their own program run as written. Progression,
return weeks, validity checks, light weeks and every `block` flag work
as in coach mode. Structural flags (`restructure_required`,
`add_session_type_blocked`, `volume_undershoot`, `session_volume_high`,
`dose_coverage_gap`, `dose_target_pending`) come out of `checkin
prepare` and the `structure` commands at `info`, their message starting
"run mode: ": mention them as information only.
Still report adherence from `structure adherence`, but do not present a
restructure or a smaller schedule and do not call `structure decide`,
unless the athlete asks for a restructure themselves. The adherence
trigger never makes a run-mode check-in deep. Skip the deep tier's
structure review (weekly balance, junk volume, what the next block
should change), propose no swap, new session or redesign, and never
offer `/new-program`.

## 2. Pull the data

Read [pull.md](pull.md): the window, the gap check for a return week,
the pull with or without Hevy, the STALE check, and coach-led sessions.

## 3. Send the Sunday message

Read [sunday-message.md](sunday-message.md): `checkin prepare` writes the
message; send it, then stop and wait for the athlete's reply. Record the
reply with `history annotate` before analysing it, and ask at most one
follow-up turn. When the card's mode is `catch_up`, send the catch-up
card instead: [catch-up.md](catch-up.md).

## 4. Analyze: plan vs. reality

Read [analyze.md](analyze.md): the weekly tier, the deep tier's extra
checks, the hard-week count with `block close`, and adherence over the
trailing four ordinary weeks.

## 5. Weight and nutrition (every check-in)

Read [nutrition.md](nutrition.md): record the reading with `nutrition
record`, read the trend, act on each `nutrition status` flag, and check
the sleep gate.

## 6. Write the record

Read [record.md](record.md): `checkin skeleton` writes the record and its
rendered regions; you write the Coach's read, Decisions and The week ahead.

## 7. Act on it

Read [act.md](act.md): agreed changes, the profile and niggle log, the
state, the light-week and adherence decisions, and the hand-over to the
**program-week** skill: normal mode on a normal week, light mode when a
light week is agreed.
