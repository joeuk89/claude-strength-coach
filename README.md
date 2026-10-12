# Claude Strength Coach

A training system where **Claude Code is your strength coach**. Your
program, profile, goals, check-ins and nutrition plan live in a private
copy of this repo. Claude plans your training week, reviews it with you
every Sunday, and manages your nutrition strategy, and nothing is written
to your training app or your plan until you say "go".

You train from **Hevy** (or printed session sheets), log food in
**MacroFactor** (or just weigh in), and spend about ten minutes a week
answering one message. Everything else is the coach's job.

## Your week, in short

| When | You | The coach |
|---|---|---|
| Training days | Train the session in Hevy (or from your sheets) and log it, PT sessions and runs included | Nothing to do; it reads the log later |
| Any day | Say what changed: "I missed Tuesday", "travelling next week", "my knee's sore", "swap the leg press" | Reprograms the rest of the week, proposes a fallback, logs the niggle, or makes the swap, and shows you before writing |
| Sunday | Run `/check-in`. Answer one message by number: missed-session reasons, how the PT session went, sleep, niggles, your food numbers | Reviews the week against the plan, saves a dated record, then proposes next week: loads, reps, RPE and notes per exercise |
| Sunday, one reply | Read the brief. Reply "go", or say what to change | Writes the week to your Hevy routines (or your sheets), commits the records, and pushes, so your phone shows the week |
| Every ~6 weeks | Same check-in, a few more questions | A deeper block review: balance, progress, what the next block changes, a light week if the signs call for one |

## A training day

Open the day's Hevy routine. Every exercise carries the coach's note for
this week, and the first one carries the week's focus:

```text
Wk of 12 Oct: heavier top sets, stop 1–2 reps short of failure
Target: 3×8 @ 25/hand (Hevy: 50) @ RPE 8
Focus: pause 1s on the chest this week
Cues: narrow grip · elbows tucked · feet planted
```

Dumbbell loads always show both numbers: what you put in each hand, and
the total Hevy stores. Log every set, with RPE where you can. On your
phone, `this-week.md` in your repo is the week on one page: focus, every
session including PT and runs, what changed, what to watch, and what to
do if you miss a day; `README.md` is your dashboard.

## A Sunday

Run `/check-in`. The coach pulls your log and sends one message that
states what it can see and numbers what it cannot (illustrative; the
fields that cannot apply are left out):

```text
Check-in for 5–11 Oct (weekly: last deep review 3 weeks ago).

1. Sessions — Upper A Mon ✔, Lower A Tue ✔, Upper B Thu ✔, Lower B Sat:
   no workout logged. Tag the miss: time / sleep / ill / family /
   skipped / other. Anything trained but not logged?
2. Coach-led — PT Wed: what did it cover, how long, how hard (RPE), or
   did the trainer cancel? Next week lands on Week B: confirm.
3. Sleep — hours asleep each night (diary or tracker), and how it felt?
4. Niggles — anything new? Open: left knee (watching): quiet, or still
   there?
5. Food — readings: trend weight · expenditure · targets (kcal/protein)
   · 7-day average (kcal/protein) · days logged. Anchors most days?
   Anything different about food next week?
6. Next week — anything different: travel, schedule, kit, illness?
```

You answer in one reply ("1 time. 2 lower body, 50 min, RPE 7, Week B
yes. 3 about 7 h, fine. 4 quiet. 5 78.4 · 2650 · 2300/160 · 2280/152 · 7;
anchors yes; Thursday out. 6 no."). The coach reviews the week against
the plan, writes a dated record to `check-ins/`, and presents next week
as a brief: the focus, what is changing and why, a table per session,
and one closing line naming exactly what "go" will write:

```text
Reply "go" to train this and write: Upper A, Lower A, Upper B, Lower B
(Hevy). Commit: data/state.json, data/history/annotations.json.
```

Reply "go", or say what to change and get a revised brief. On "go" the
coach writes each routine, reads it back to verify, re-renders your pages
and pushes them. On a week where nothing needs deciding the whole thing
is three sentences and the write line. The
[weekly rhythm](docs/guide/weekly-rhythm.md) walks through all of this
with fuller examples.

## Things you can just say

The slash commands below are for the bigger moves. Day to day you talk to
the coach in plain words, and it knows which flow applies:

- "I missed Thursday's lower session" → the program's missed-day rule, or
  a move, reshuffle or drop you choose, with the rest of the week redone.
- "Today felt heavy" or "bump my squat" → a mid-week change to the lines
  that are left, or a note for next week's proposal.
- "I'm away Tuesday to Friday with hotel dumbbells" → a constrained week
  that keeps your priority lifts at a maintainable dose, on the kit you
  name.
- "My shoulder's been niggly on presses" → a tracked niggle with load
  limits the proposals respect, and a professional recommended if it
  keeps coming back.
- "What should I eat after training?", "why this rep range?", "check my
  form on RDLs" → coaching, no files touched.
- "I did a 10 k on Saturday" → counted in the week's load, and checked
  against the lifting it sits next to.

## The commands

| Command | Use it when |
|---|---|
| `/setup` | First run, or to add Hevy or nutrition later, or refresh your profile. |
| `/check-in` | Weekly. Also for a progress review, and after a gap of any length. |
| `/program-week` | The weekly pass `/check-in` runs for you. Run it yourself to reprogram mid-week, plan a deload, or plan a travel, illness-recovery or short week. |
| `/new-program` | Build your program (import, design, or starter) or redesign it at a block boundary. |
| `/hevy-sync` | You changed routines in the Hevy app, or want to check the app and the plan agree. |
| `/goals` | Set or revise the big picture: bulk, cut or maintain, target weight, protein, MacroFactor setup. |
| `/recipes` | Build and manage your recipe bank. |
| `/meal-plan` | Turn your targets into the week's meals and a shopping list. |
| `/framework-sync` | Update your copy to the latest version of the system. |

## The three pieces

| Piece | Job |
|---|---|
| **This repo** | The brain: program, athlete profile, goals, check-in history, nutrition plan, the pages you read on your phone. Planning and review happen here. |
| **Hevy** (app, optional) | The training logbook. You train from Hevy routines the coach writes and log every workout there. The coach reads the logs back through the API, which needs Hevy Pro. |
| **MacroFactor** (app, optional) | The nutrition engine. You log food and weigh-ins there; it sets your calories and macros. The strategy it runs (bulk, cut, maintain, how fast) is decided here with `/goals`. |

Both apps are optional. Without Hevy you train from rendered session
sheets and report workouts in chat. Without MacroFactor the coach tracks
scale weight and protein against plain targets. With them the loop is
tighter and asks you less.

## Requirements

- [Claude Code](https://claude.com/claude-code) with a Claude subscription.
- Python 3.11 or newer (the coach scripts use only the standard library).
- git, and a GitHub account for your private copy.
- Optional: **Hevy Pro** (for the API) and **MacroFactor**.

## Get started

1. Click **Use this template** on GitHub and create a **private** repo:
   your training data will live in it.
2. Clone it, mark the clone as your training workspace, and open Claude
   Code inside it:

   ```bash
   git clone <your-repo-url> my-training && cd my-training
   git config --local coach.workspace athlete
   claude
   ```

3. Run **`/setup`**. In about ten replies it asks three settings
   questions (Hevy, units, nutrition), connects Hevy if you have Pro,
   builds your profile, creates your program (import your Hevy routines,
   design one with the coach, or start from a tested starter), and
   programs your first week.

The git setting tells the coach this clone is your workspace rather than
the template. Git never copies it, so set it in every new clone. Keep the
`tests/` folder; nothing needs deleting. Full walkthrough:
[Getting started](docs/guide/getting-started.md).

## What the coach never does without you

- Nothing reaches Hevy, and no program or profile change lands, without
  your approval. Every programming pass ends in one brief with one line
  naming exactly what "go" will write. A permission hook shows the exact
  Hevy write before it runs, so even a mistaken "go" cannot write
  unseen.
- Every load, conversion and progression is computed by a script, never
  in the coach's head. Dumbbell loads always show both numbers:
  `25/hand (Hevy: 50)`.
- Advice is evidence-based: each number in the coaching rules cites a
  research note you can read (`python3 -m coach research show <ref>`).
- No extreme cuts or bulks. The coach is a coach, not a doctor: pain or
  suspected injury goes to a professional.

## Documentation

The full guide is in [`docs/`](docs/README.md). Start with:

- [Getting started](docs/guide/getting-started.md): setup, step by step.
- [Concepts](docs/guide/concepts.md): the mental model in plain words.
- [The weekly rhythm](docs/guide/weekly-rhythm.md): a week with the
  coach, with examples.
- [Check-in](docs/guide/check-in.md), [Programming the week](docs/guide/programming-the-week.md),
  [Programs](docs/guide/programs.md), [Hevy](docs/guide/hevy.md),
  [Nutrition](docs/guide/nutrition.md).
- [Troubleshooting](docs/guide/troubleshooting.md) and the
  [command reference](docs/guide/cli.md).

In your own copy this page is replaced by your training dashboard; the
dashboard's "How this works" link brings you back here.

## Updating your copy

Run **`/framework-sync`**. It fetches the template's latest `main` and
updates the framework files (skills, coaching rules, reference docs, the
coach scripts) in one commit, migrating your data files if a schema moved.
Your personal files (profile, program, check-ins, nutrition) are never
touched, and it warns first if you edited a framework file locally. See
[Updating](docs/guide/updating.md).

## Working on the template

If you want to change the system itself rather than use it, read
[docs/development.md](docs/development.md).
