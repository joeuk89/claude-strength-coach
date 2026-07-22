# Claude Strength Coach

A training system where **Claude Code acts as your strength coach**. Your
plan, athlete profile, goals, and progress history live in this repo;
Claude programs your training, reviews your progress weekly, and manages
your nutrition strategy — collaboratively, with you approving every change.

## The three pieces

| Piece | Job |
|---|---|
| **This repo** | The brain: routine, athlete profile, goals, check-in history. Everything is planned and reviewed here. |
| **Hevy** (app, optional) | The training logbook. You train from Hevy routines that mirror `routine/`, and log every workout there. The coach reads logs back via the API (needs Hevy Pro). |
| **MacroFactor** (app, optional) | The nutrition engine. You log food and weigh-ins there; it works out your calorie/macro targets and adjusts them weekly. The strategy it runs (bulk/cut/maintain, rate) is decided here via `/goals`. |

Both apps are optional — without Hevy you describe your training at
check-ins; without MacroFactor the coach tracks scale weight against plain
targets. With them, the loop is much tighter.

## Requirements

- [Claude Code](https://claude.com/claude-code) (a paid Claude
  subscription).
- Optional: **Hevy Pro** (for API access) and **MacroFactor**.

## Getting started

1. Click **"Use this template"** on GitHub and create your own **private**
   repo (your training data will live in it).
2. Clone it and open Claude Code inside:
   ```bash
   git clone <your-repo-url> my-training && cd my-training
   claude
   ```
3. Run **`/setup`**. It walks you through connecting Hevy (if you have
   it), building your athlete profile, setting your goals, and creating
   your program.

## The weekly rhythm

The heartbeat is one check-in a week. Around it:

1. **Train and log.** Train your program and log every workout in Hevy if
   you use it — including any PT or class sessions (unlogged sessions skew
   the review).
2. **Log food** (MacroFactor users): daily, with 2–3 morning weigh-ins a
   week.
3. **`/check-in`** once a week (~10 min). It reviews the week against the
   plan, asks a few questions, saves a dated record to `check-ins/`, and
   hands you the plan for the week ahead. Every ~6 weeks it runs deeper,
   as a block-level review.

That loop is most of it. The flows below are for when something changes.

## The flows

**You never need a command for the small stuff** — an exercise swap, "why
this rep range?", a form check, "what should I eat post-workout?" Just ask
in plain words. The commands are for the bigger moves.

### Getting set up
- **`/setup`** — first-run onboarding: apps, profile, goals, first
  program. Re-runnable — it's also how you add an integration (like
  Notion) or refresh your profile later.

### Your training
- **`/new-program`** — build your program (import from Hevy or design from
  scratch with the coach), or redesign it at a block boundary.
- **`/one-off-week`** — a week that breaks the pattern: a deload, or a
  disrupted one (travel, illness, limited kit). Concrete sessions for the
  blip; your program stays untouched.
- **`/hevy-sync`** — reconcile `routine/` with your Hevy app after editing
  routines in either place, one difference at a time. (Hevy users.)

### Goals & nutrition strategy
- **`/goals`** — set or revise the big picture: bulk / cut / maintain,
  target weight, trend rate, protein. Run it when goals change or a phase
  decision is due ("should I bulk or cut?"). Ends with a recorded plan —
  and exact MacroFactor setup, if you use it.

### Food & meals
- **`/recipes`** — build and manage your recipe bank: add from a link or
  an idea, have the coach source new ones that fit your goals, or bench
  the ones you're bored of.
- **`/meal-plan`** — turn your targets into meals and snacks for the week
  around what's already covered (meal kit, canteen, eating out), with a
  shopping list for exactly what's needed.

### System & extras
- **`/framework-sync`** — update your copy to the latest framework
  (skills, docs); your personal files are never touched (see "Updating
  your copy" below).
- **`/notion-sync`** — optionally mirror your check-ins, meal plans, and
  recipes to Notion, to read on your phone. Files here stay the source of
  truth.

## Ground rules the coach follows

- Nothing is edited without your approval — routine changes show
  before/after and rationale first.
- Routine changes agreed here get offered to Hevy so the app and plan
  don't drift silently.
- Advice is evidence-based and cited when it depends on current research.
- No extreme cuts or bulks; a coach, not a doctor — pain or suspected
  injury goes to a professional.

## Updating your copy

Run **`/framework-sync`**. It fetches the template's latest `main` and
updates your framework files (skills, CLAUDE.md, reference docs) in one
commit. Your personal files — profile, routine, check-ins, nutrition —
are never touched, and it warns you first if you've edited a framework
file locally.
