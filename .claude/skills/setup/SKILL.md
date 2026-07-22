---
name: setup
description: Use for first-run onboarding of this training workspace — when profile.md doesn't exist, the user is new, or they ask to get set up. Triggers include "/setup", "get me set up", "set up hevy", "initialise this", or any session in a copy of the template where profile.md is missing.
---

# First-run setup

Turn a fresh copy of the template into this athlete's training workspace.
A thin orchestrator: each step checks whether it's already done and skips
or offers to redo it, so `/setup` is safe to re-run and resumes cleanly
after a partial run. It's also how the athlete **reconfigures** later —
on a fully set-up workspace, report each area's state and ask what they
want to change (add an integration like Notion, refresh the profile),
rather than declaring everything done.

Work conversationally — this is the athlete's first contact with the
coach. One question at a time.

## 0. State check

Look at what exists: `profile.md`? `.env` with a key? `routine/program.md`?
A "Nutrition & goals" section with real content? `notion-map.json`?
Report what's already done, then continue from the first missing piece —
or, if nothing is missing, ask what the athlete wants to change.

## 1. Welcome

Briefly explain the three pieces: **this repo** is the brain (plan,
profile, goals, history — everything reviewed and decided here), **Hevy**
is the training logbook (optional), **MacroFactor** is the nutrition
engine (optional). And the rhythm: train and log, then a weekly
`/check-in` keeps everything on track.

## 2. Integrations

**Hevy:**
- Ask whether they use Hevy. API access needs **Hevy Pro** — if they use
  Hevy free, note they can still mirror routines manually but the coach
  can't read logs; record that and move on.
- With Pro: send them to **hevy.com → Settings → Developer → generate API
  key** (or in the app: Profile → Settings → Developer). Have them create
  `.env` (copy `.env.example`) and paste the key as `HEVY_API_KEY=...` —
  they paste it into the file themselves if they prefer; never echo the
  key back.
- Verify it works:
  ```bash
  set -a && source .env && set +a
  curl -s -H "api-key: $HEVY_API_KEY" "https://api.hevyapp.com/v1/user/info"
  ```
  A username back = success. A 401 = bad key; retry.

**MacroFactor:**
- Ask whether they use it (or want to — it's paid, and the best-in-class
  option for this loop). No API either way: its numbers are read off the
  dashboard at check-ins. Record yes/no.

**Notion (optional):**
- Ask whether they want their coaching docs (check-ins, meal plans,
  recipes, routine) mirrored to Notion for reading on the go. If yes,
  invoke the **notion-sync** skill's setup flow — it checks for a
  Notion MCP connection and explains how to connect one if it's
  missing. Easy to skip and add later: re-running `/setup` or
  `/notion-sync` sets it up any time.

## 3. Profile interview

Skip if `profile.md` exists (offer a refresh instead). Interview one
question at a time — group related items, don't fire twenty questions —
then create `profile.md` from this skeleton, filling every section (write
"None" / "TBD" only where the athlete genuinely doesn't know):

```markdown
# <Name> — Athlete Profile

The single source of truth for who <Name> is as an athlete. All
programming decisions key off this file. Check-ins refresh the numbers —
if something here looks stale, confirm it and update it.

_Last reviewed: YYYY-MM-DD_

## Goal & phase

(Filled by /goals — goal in one line, current phase, experience level.)

## Body & key lifts

- **Born:** … · **Height:** …
- **Preferred units:** kg / lb (loads), kg / lb (bodyweight)
- **Daily activity outside training:** …
- **Bodyweight:** … (date, conditions)
- **Est. 1RMs / key lift numbers:** … (or "establishing — first block")

## Equipment

(What they train with, where. Home kit with load limits; gym access and
what it has. Exercise selection must stay inside this.)

## Training week

(The real weekly shape: which days can they train, how long per session,
any coach-/PT-led or class sessions and who controls those, cardio
commitments, rest days. A Mon–Sun table works well.)

## Cardio / other activity

(Runs, sports, classes — frequency, intensity, caps. Counts toward total
training stress.)

## Injuries / limitations

(Current and historical-but-relevant. "None currently" is an answer.
Check-ins keep a dated "Niggle log" table here — minor aches worth
watching for recurrence; it's created when the first one appears.)

## Nutrition & goals

(Filled by /goals — phase sequence, targets, trend rate, app config.)

- **Apps:** Hevy: yes-Pro / yes-free / no · MacroFactor: yes / no

## Food & eating

(Filled by /recipes — food preferences and allergies, staples, cooking
appetite, shopping style, standing meal coverage, plan-style preference.)

## Recovery

(Sleep quality, stress, anything that gates volume right now.)

## Coach's notes

(Per-athlete patterns the coach learns over time — logging habits, drift
tendencies, exercise preferences. Check-ins read and maintain this
section. Starts empty.)
```

Confirm the drafted profile with the athlete before writing the file.

## 4. Goals

Invoke the **goals** skill (`/goals`) to set phase, targets, and — for
MacroFactor users — its configuration. This fills "Goal & phase" and
"Nutrition & goals".

## 5. Program

Offer the **new-program** skill (`/new-program`): import what they already
run in Hevy, or design a program from scratch. It's fine to defer this to
another session — if deferred, say plainly that the workspace isn't
trainable until it runs.

## 6. Close out

- Recap what was set up and what (if anything) was deferred.
- State the weekly rhythm: train and log everything (including coach-led
  sessions), weigh-ins 2–3×/week if cutting/bulking, `/check-in` weekly.
- Remind: `.env` stays uncommitted (already gitignored).
- Offer to commit: `git add -A` and show what's staged; commit with
  message `Initial setup: profile and goals` after they approve.
