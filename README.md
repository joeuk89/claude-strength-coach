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

## The commands

- **`/setup`** — first-run onboarding. Re-runnable; picks up where it
  left off.
- **`/new-program`** — create your training program: import what you
  already run in Hevy, or design one from scratch with the coach. Also for
  block redesigns later.
- **`/check-in`** — run **weekly** (~10 minutes). Reviews the week's
  training and weight/nutrition against the plan, asks a few questions,
  writes a dated record to `check-ins/`, and ends with a plan for the week
  ahead. Every ~6 weeks it runs as a deeper block-level review.
- **`/goals`** — run when goals change or a phase decision is due
  ("should I bulk or cut?"). Ends with a recorded plan and, if you use
  MacroFactor, exact setup steps for it.
- **`/meal-plan`** — plan the week's meals and snacks around what's
  already covered (meal kit, canteen, eating out), to your targets, and
  get a shopping list for exactly what the plan needs.
- **`/recipes`** — manage your recipe bank: add a recipe from a link or
  an idea, have the coach source new ones online that fit your goals,
  or bench the ones you're bored of.
- **`/hevy-sync`** — run after editing routines in the Hevy app, or when
  the coach proposes routine changes here. Reconciles `routine/` and Hevy
  in either direction, one difference at a time.
- **`/framework-sync`** — update your copy to the latest version of the
  framework (skills, docs). Your personal files are never touched.

Anything else — an exercise swap, a question, advice — just ask in plain
words; no command needed.

## The weekly rhythm

1. Train your program and log every workout (in Hevy if you use it —
   including any PT/class sessions; unlogged sessions skew the check-ins).
2. If you use MacroFactor: log food daily, weigh in 2–3× a week (morning,
   before food).
3. Run `/check-in` once a week. It ends with the week-ahead plan — that's
   the plan until the next one.

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
