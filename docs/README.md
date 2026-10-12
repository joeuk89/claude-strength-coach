# Documentation

User guides for athletes using the system, plus the design and development
docs behind it. The guides describe the system as it is in this template;
your own copy reads them from here on GitHub, since `/framework-sync` does
not copy `docs/`.

## Start here

| Guide | Read it when |
|---|---|
| [Getting started](guide/getting-started.md) | Making your copy and running `/setup`. |
| [Concepts](guide/concepts.md) | You want the mental model: program, session, overlay, block, brief, the approval gate, the two dumbbell numbers. |
| [The weekly rhythm](guide/weekly-rhythm.md) | A full week with the coach, with example messages. |

## Training

| Guide | Covers |
|---|---|
| [Check-in](guide/check-in.md) | `/check-in`: the Sunday message, the weekly and deep tiers, catch-ups after a gap, the record. |
| [Programming the week](guide/programming-the-week.md) | `/program-week`: modes, the proposal, the coach's brief, missed days, what "go" writes. |
| [Programs](guide/programs.md) | `/new-program`: import, design or starter; what a program contains; redesigns; run mode. |
| [Blocks and light weeks](guide/blocks-and-light-weeks.md) | Hard weeks, fatigue triggers, deloads, returning after time off or illness. |
| [Hevy](guide/hevy.md) | The API key, load modes, routines, the approval gate, `/hevy-sync`. |
| [Training without Hevy](guide/training-without-hevy.md) | Session sheets and reporting workouts in chat. |
| [Niggles, follow-ups and status days](guide/niggles-and-followups.md) | What the coach tracks between check-ins. |
| [Cardio and activity](guide/cardio-and-activity.md) | Runs, conditioning, Apple Health, sleep, goal events, interference with lifting. |

## Nutrition

| Guide | Covers |
|---|---|
| [Nutrition](guide/nutrition.md) | `/goals`: phases, protein, MacroFactor, overrides, the sleep gate. |
| [Recipes and meal plans](guide/recipes-and-meal-plans.md) | `/recipes` and `/meal-plan`: the bank, the standing week, shopping lists. |

## Reference

| Guide | Covers |
|---|---|
| [Pages and publishing](guide/pages-and-publishing.md) | The dashboard, the brief, progress and sheets, and how they reach your phone. |
| [Configuration](guide/configuration.md) | Every `config.toml` setting, `.env`, the permission allowlist and hooks. |
| [Files](guide/files.md) | What every file and folder is, and which are rendered or local. |
| [Command reference](guide/cli.md) | The coach scripts: envelope, exit codes, every command. |
| [Research](guide/research.md) | The evidence behind the numbers and how it is cited. |
| [Updating](guide/updating.md) | `/framework-sync` and data migrations. |
| [Troubleshooting](guide/troubleshooting.md) | Exit codes, `coach check` failures, common situations. |

## Design and development

- [Development](development.md): architecture, tests, how to change the
  template.
- [`CONTEXT.md`](../CONTEXT.md): the glossary every doc and skill uses.
- [`design/coach-contract.md`](design/coach-contract.md): the package
  contract.
- [`adr/`](adr/): architecture decision records.
- [`roadmap/`](roadmap/): the system review the rewrite came from.
- [`agents/`](agents/): tooling notes for agents working on the template.
