---
name: setup
description: Use for first-run onboarding of this training workspace — when profile.md doesn't exist, the user is new, or they ask to get set up. Triggers include "/setup", "get me set up", "set up hevy", "initialise this", or any session in a copy of the template where profile.md is missing.
---

# First-run setup

Take a fresh copy of the template to an approved first week in about ten
replies. Each step skips itself when done, so `/setup` resumes after a
partial run; on a set-up workspace it is how the athlete
**reconfigures**: report each step's state and ask what to change. Ask
each step's questions together, never one at a time. Every answer a
script reads goes into `config.toml` or a `coach` command, not prose.

## 0. State check

Run `python3 -m coach check` and report every `fail` result to the
athlete, with its message, before doing anything else. On a first run
the `config` check fails because there is no `config.toml` yet; step 1
creates it. If `routine/` exists but `data/program.json` does not, this
workspace still keeps its program as hand-written pages: say it needs
its one-time bootstrap migration onto `data/program.json` first, and
stop. When a command fails, tell the athlete what its exit code means,
as `CLAUDE.md` "The coach scripts" sets out.

Then look at what exists — `config.toml`, `profile.md`,
`data/program.json`, an approved overlay (`python3 -m coach overlay
current`) — and continue from the first step that isn't done.

## 1. Three questions, then `config.toml`

Skip when `config.toml` exists and `python3 -m coach config validate`
exits 0; on a re-run, report the three answers from `python3 -m coach
config show` and ask what to change. A `config.toml` without a
`[nutrition]` table means a yes not yet set up, or a later; step 6
settles which.

Welcome the athlete in two lines: this repo plans and reviews their
training, their logging app records it, and a weekly `/check-in` keeps
it on track. Then ask, in one message:

- **Hevy:** Pro, free, or not at all? The coach reads logs and writes
  routines only through Hevy Pro's API.
- **Units:** kg or lb?
- **Nutrition coaching:** yes, no, or later?

With the reply, write `config.toml` as [config.md](config.md) says:
`python3 -m coach config suggest`, then the athlete, equipment and Hevy
keys copied from `config.example.toml`. Nutrition: on a yes or a later,
leave `[nutrition]` out (step 6 sets up a yes after week one); on a no,
add a `[nutrition]` table holding only `enabled = false`. For a no or a
later, note "`/goals` sets up nutrition coaching whenever you want it"
for the close-out. Run `python3 -m coach config validate` until it
exits 0; exit 5 names the file and key to fix.

## 2. Hevy key (Pro only)

Skip without Hevy Pro, or when `python3 -m coach hevy status` already
reads `key` `present`. Otherwise follow [hevy-key.md](hevy-key.md): where
the key comes from, where it goes, and the checks that prove it works.

## 3. Profile: six questions

Skip when `profile.md` exists (offer a refresh instead). Ask these six,
named in one list, in at most two messages: 1 to 3, then 4 to 6.

1. **Name.** Units are known from step 1.
2. **Goal:** what they want from training, in their own words.
3. **Training experience and known working weights:** how long they've
   trained consistently, and any working weights they know for their
   main lifts (weight and reps).
4. **The training week:** which days, about how many minutes per
   session, any coach-led sessions (PT, team training) and their days,
   any classes, any runs.
5. **Equipment, per place they train:** the main place and what it has,
   and each other place with what differs; plus whatever
   `config suggest`'s notes said to confirm.
6. **Injuries and limitations:** anything that hurts or limits training
   now or keeps coming back, and any exercise they cannot or will not
   do.

Don't ask bodyweight, height, age, sleep or recovery here: the first
`/check-in` asks.

## 4. Profile facts into config and data, then `profile.md`

Map answers 3 to 6 onto `config.toml` and `coach` commands as
[profile-facts.md](profile-facts.md) says, run `python3 -m coach config
validate` until it exits 0, then write `profile.md` from its skeleton.
Show it in step 5's message, so a correction rides along.

## 5. Program, then week one

Skip the program when `data/program.json` exists. Otherwise follow
[program.md](program.md): `python3 -m coach starters list`, the
**new-program** skill's three-path offer, the chosen path, `python3 -m
coach program adopt`, and the one load-mode confirmation.

Then run week one through the **program-week** skill: `python3 -m coach
propose week`, the overlay, the coach's brief, and the approval gate,
where the athlete's "go" approves the week and its writes.

## 6. Nutrition (only when the athlete wants it now)

Skip when `config.toml` has a `[nutrition]` table, or the athlete said
no or later in step 1 of this run. It runs only after week one is
approved. On a resumed run with the step 1 answer not in this
conversation and `[nutrition]` absent, ask once: now, or later? A later
goes into the close-out's deferred list.

Invoke the **goals** skill (`/goals`) on a yes: it asks the nutrition
questions, sets `[nutrition]` in `config.toml` and adds the "Nutrition &
goals" section to `profile.md`.

## 7. Close out

Recap settings, profile, program and the approved week one in a few
lines. Name what was deferred: anything step 1 noted, any step the
athlete postponed, and that the first `/check-in` asks bodyweight and
recovery. State the weekly rhythm: train and log everything (coach-led
sessions too), `/check-in` weekly. With a Hevy key, `.env` stays
uncommitted (gitignored). Offer to commit: `git add -A`, show
what's staged, and commit with message `Initial setup: settings,
profile and program` once they approve.
