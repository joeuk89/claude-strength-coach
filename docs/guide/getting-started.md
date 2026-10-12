# Getting started

How to make your own copy of the template and take it from an empty repo
to an approved first training week with `/setup`. Read this once, before
your first session.

## Requirements

- [Claude Code](https://claude.com/claude-code) with a Claude
  subscription. The coach is Claude; the skills in `.claude/skills/` are
  its playbooks.
- **Python 3.11 or newer.** The coach scripts (`python3 -m coach ...`)
  use only the standard library, so there is nothing to install. An
  older Python stops them with exit code 5.
- **git**, and a GitHub account so your copy can be private and your
  phone can read the pages the coach publishes.
- Optional: **Hevy Pro**. The coach reads your logs and writes your
  routines through Hevy's API, which only Pro accounts have. With the
  free app, or no Hevy, you train from rendered session sheets and
  report workouts in chat (see [Training without Hevy](training-without-hevy.md)).
- Optional: **MacroFactor**, or another nutrition app you log in. The
  coach sets the strategy; the app sets the daily calories.

Check Python first:

```bash
python3 --version
```

## Make your copy

1. On GitHub, click **Use this template** and create a **private** repo.
   Your profile, check-ins and every training record will live in it.
2. Clone it, mark the clone as your training workspace, and open Claude
   Code inside it:

   ```bash
   git clone <your-repo-url> my-training && cd my-training
   git config --local coach.workspace athlete
   claude
   ```

The git setting tells the coach scripts that this checkout is an
athlete's workspace, not the template itself. Git never commits or
clones local config, so set it in every new clone. Without it, and with
no `profile.md` or `config.toml` yet, the coach cannot tell your copy
from a development checkout. For a copy that is not on GitHub, run
`git init` and the same `git config` line inside it before opening
Claude.

Keep the `tests/` folder. It is the template's own test suite and does
no harm in your copy; `/framework-sync` never touches it.

## Run `/setup`

When Claude Code opens, a SessionStart hook runs `python3 -m coach
status` and puts a few status lines in the coach's context. On a fresh
copy those lines say the workspace needs `/setup`. Type `/setup` (or
"get me set up"). It takes about ten replies and resumes wherever it
left off, so you can stop and come back.

The coach asks each step's questions together, in one message, and
writes every answer a script needs into `config.toml` or a data file,
not into prose.

### 1. Three questions, then `config.toml`

- **Hevy:** Pro, free, or not at all?
- **Units:** kg or lb?
- **Nutrition coaching:** yes, no, or later?

From the answers the coach runs `python3 -m coach config suggest` and
writes `config.toml` from `config.example.toml`: the athlete table, the
equipment table and the Hevy switch. Nutrition stays out of the file
until step 6 (a "no" records `enabled = false`). `python3 -m coach
config validate` must exit 0 before the step ends; an exit 5 names the
file and key to fix. Every setting is explained in
[Configuration](configuration.md).

### 2. The Hevy key (Pro only)

Generate a key at hevy.com → Settings → Developer, and put it in `.env`
at the repo root as `HEVY_API_KEY=...` (copy `.env.example`). `.env` is
gitignored and the coach never prints the key. `python3 -m coach hevy
status` then shows `key: present`, and the first `hevy pull` fills the
local cache with your workouts and routines. See [Hevy](hevy.md).

### 3. Your profile: six questions

Asked in two messages, reusing anything already known:

1. Name, and birth year if you want age-aware advice.
2. Your goal, in your own words.
3. Training history and current level: past training, recent
   consistency, time off, current working weights you know, and which
   strict pull-ups or dips you can do now. The coach confirms today's
   level (beginner, intermediate, advanced) with you rather than
   inferring it from history.
4. The training week: how many sessions you want, which weekdays you
   can train, minutes per session, any PT or team sessions and their
   days, classes, runs and whether an outside plan sets them.
5. Equipment, per place you train: the kit, plus benches, bars and
   supports, and anything `config suggest` asked you to confirm.
6. Injuries and limitations: anything that hurts or limits training now
   or keeps coming back, and any exercise you cannot or will not do.

Bodyweight and recovery wait for your first check-in.

### 4. Facts into config and data, then `profile.md`

Answers that scripts read go where scripts read them: the training week
and demonstrated skill exercises into `[athlete]`, each place's kit into
`[equipment]` and `[equipment.locations.<name>]`, a lasting limitation
into the niggle log (`niggles add`), an exercise you avoid into the
exercise library (`library set-avoid`). Runs or classes switch on the
activity layer and set the cardio tier. Then the coach writes
`profile.md`: your goal, week, equipment and limits in words, plus a
Coach's notes section it keeps current from here on. You see it before
it is written.

### 5. Your program, then week one

The coach offers three paths and recommends one:

- **Import**: you already run a program in Hevy or on paper. It pulls
  your routines, confirms how each exercise is loaded, and imports them
  as they are. It asks once whether to run your program as written
  ("run mode") or coach it.
- **Design**: the week or goal needs a program built for it. A coaching
  conversation with two or three structure options.
- **Starter**: a tested program that ships with the template (full body,
  upper/lower, push/pull/legs, a 3-week wave, full body by RPE), fitted
  to your days and kit.

Every path ends in a program draft you review: the report of what the
source could not settle, a table of each exercise's load mode (one
total, per hand, or one dumbbell), and optional missed-day rules. Your
yes adopts it: `program adopt` writes `data/program.json` and
`data/state.json` and renders `routine/program.md` and one page per
session. Details: [Programs](programs.md).

The coach then offers a reviewed commit of the setup files, and runs
the first programming pass: `/program-week` proposes week one, exercise
by exercise, and presents the coach's brief. Your "go" writes the week
to your Hevy routines (or to `this-week-sheets.md` without Hevy),
records a Program start record in `check-ins/`, and publishes the
pages. See [Programming the week](programming-the-week.md).

### 6. Nutrition (only if you said yes)

After week one is approved, the coach invokes `/goals`: a weigh-in, your
goal in words, phase and rate, protein numbers, two or three protein
anchors, and exact MacroFactor setup if you use it. A "later" is noted
and `/goals` sets it up whenever you want. See [Nutrition](nutrition.md).

### 7. Close-out

The coach recaps settings, profile, program and the approved week, and
names what was deferred (the first `/check-in` asks bodyweight and
recovery). The rhythm from here: train and log everything, PT sessions
included, and `/check-in` once a week.

## What you have at the end

| File | What it is |
|---|---|
| `config.toml` | Your settings: units, equipment, Hevy, nutrition. |
| `.env` | Your Hevy key, gitignored. |
| `profile.md` | You, in words: goal, week, limits, Coach's notes. |
| `data/program.json`, `routine/` | Your program and its rendered pages. |
| `data/overlays/<date>-weekly.json` | Week one's prescription. |
| `this-week.md`, `README.md`, `progress.md` | The brief, the dashboard and the progress page, rendered. |
| `check-ins/<date>.md` | The Program start record. |
| `this-week-sheets.md` | Session sheets, only without Hevy. |

[Files](files.md) describes everything else.

## Running Claude Code in the cloud

Claude Code on the web clones your repo without `.env`. Put
`HEVY_API_KEY` in the cloud environment's variables and set its network
access to **Custom** with `api.hevyapp.com` allowed, as
[Hevy](hevy.md) describes. The `coach.workspace` git setting is also
local, so a cloud session without `profile.md` would see the template;
once setup has written `profile.md` and `config.toml` the files
themselves identify the workspace.

## Adding things later

`/setup` is re-runnable. On an existing workspace it reports each step's
state and asks what to change: add a Hevy key, switch on nutrition,
refresh your profile or your equipment. Changes to goals go through
`/goals`; a new program through `/new-program`.
