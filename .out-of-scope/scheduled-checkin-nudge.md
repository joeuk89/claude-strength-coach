# Scheduled check-in draft and nudge

This project does not run anything on a schedule outside a Claude Code
session. There is no daily job that pulls Hevy, drafts the Sunday check-in
card, or sends a reminder when a check-in is overdue.

## Why this is out of scope

The coach works inside a session the athlete opens. When they open one, the
SessionStart status line (`coach status`) already says when a check-in is
due and which tier it will run, and `checkin prepare` builds the card
quickly from the local cache. A scheduled job would add value only by
reaching the athlete when they haven't opened Claude. That isn't worth the
cost:

- **Unattended runs can't be approved.** The approval gate denies Hevy
  writes and pushes when nobody can see a prompt. A scheduled run would
  need its own read-only mode, enforced in every writing command and in the
  Hevy client, just to stay safe.
- **Machine setup the athlete has to maintain.** A launchd or cron job
  has to be installed, kept working across OS updates, and debugged
  through log files, all outside the coach's view.
- **Remote channels move training data off the machine.** A reminder you
  can answer from your phone (for example a GitHub issue carrying the card)
  means an unattended job writing to an external service.

A calendar reminder does the same job for nothing.

## Prior requests

- #33: "R-45 Scheduled Sunday draft and nudge"
- #50: "R-45 follow-up: install and verify the scheduled run on a real instance"
