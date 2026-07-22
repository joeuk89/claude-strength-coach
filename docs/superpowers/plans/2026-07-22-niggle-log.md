# Niggle Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Joe's standing rule overrides everything:** after each task, stage the
> changes and STOP for his review. Never commit until he approves that
> task's diff. Never push without asking.
>
> **Sequencing:** build after the `/framework-sync` plan
> (`2026-07-22-framework-sync.md`). Intended to ride the same publish +
> sync as the `/one-off-week` plan (`2026-07-22-one-off-week-skill.md`,
> Task 6) — see Task 3.

**Goal:** A dated niggle watch-list in `profile.md` that `/check-in` maintains, so recurring minor aches surface as patterns instead of vanishing into individual check-in records.

**Architecture:** A convention plus two template skill edits — no new skill, no new file. The log is a `### Niggle log` table inside `profile.md`'s existing "Injuries / limitations" section, created on first entry. `/check-in` writes to it (section 7) and follows up from it (section 5); `/setup`'s profile skeleton mentions it so fresh instances inherit the convention.

**Tech Stack:** Markdown only.

**Design decisions already agreed with Joe (don't relitigate):**

- Location: `profile.md` → Injuries / limitations → `### Niggle log` subsection, created when the first niggle appears (no empty table in a clean profile).
- Columns: `Area · First noted · Last noted · Mentions · Status · Notes`; statuses `watching` / `easing` / `resolved`.
- **Resolved rows stay** — recurrence detection is the whole point.
- Escalation rule: ~3 consecutive check-in mentions, worsening, or interfering with prescribed training → recommend a qualified professional and program around it meanwhile; never diagnose.
- Active niggles inform routine changes proposed at that check-in (no added load on an aggravated pattern).
- Joe's own profile is untouched now — he has no current niggles; the subsection appears with the first one.
- YAGNI: no separate file, no pain scores, no body map, no trend automation.

---

### Task 1: Teach `/check-in` to maintain the log

**Files:**
- Modify: `~/personal/workout-template/.claude/skills/check-in/SKILL.md` (section 5 interview list; section 7 bullets)

- [ ] **Step 1: Section 5 — follow up from the log.** In "## 5. Interview the athlete", change:

```markdown
One question at a time, only what the data can't show: sleep, recovery,
joints/aches, cardio, how any coach-led sessions felt, **anything unusual
```

to:

```markdown
One question at a time, only what the data can't show: sleep, recovery,
joints/aches (follow up on any `watching` rows in the profile's niggle
log, even if the athlete doesn't raise them), cardio, how any coach-led
sessions felt, **anything unusual
```

- [ ] **Step 2: Section 7 — the write-back.** In "## 7. Act on it", directly after the bullet ending "…Add or retire **Coach's notes** as patterns emerge or resolve — with the athlete's confirmation.", add:

```markdown
- **Maintain the niggle log** in `profile.md` (Injuries / limitations →
  a `### Niggle log` table: `Area · First noted · Last noted · Mentions
  · Status · Notes`; statuses `watching` / `easing` / `resolved`;
  create the subsection on its first entry). New complaint → new row;
  repeat mention → bump Last noted and Mentions; confirmed gone →
  `resolved`, but **keep the row** — recurrence is the signal this log
  exists to catch. Escalate — recommend a qualified professional and
  program around it meanwhile, never diagnose — when a niggle runs ~3
  consecutive check-ins, worsens, or interferes with prescribed
  training. Active niggles inform any routine change proposed today:
  no added load on an aggravated pattern.
```

- [ ] **Step 3: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/check-in/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "check-in: maintain a niggle log in profile.md"
```

---

### Task 2: Mention the log in `/setup`'s profile skeleton

**Files:**
- Modify: `~/personal/workout-template/.claude/skills/setup/SKILL.md` (profile skeleton, "Injuries / limitations" section)

- [ ] **Step 1:** In the skeleton, change:

```markdown
## Injuries / limitations

(Current and historical-but-relevant. "None currently" is an answer.)
```

to:

```markdown
## Injuries / limitations

(Current and historical-but-relevant. "None currently" is an answer.
Check-ins keep a dated "Niggle log" table here — minor aches worth
watching for recurrence; it's created when the first one appears.)
```

- [ ] **Step 2: Stage and stop for review**

```bash
cd ~/personal/workout-template
git add .claude/skills/setup/SKILL.md
git diff --staged   # show Joe
# After approval: git commit -m "setup: note the niggle log in the profile skeleton"
```

---

### Task 3: Publish and sync

- [ ] **Step 1:** If executing in the same session as the `/one-off-week` plan, fold these commits into that plan's Task 6 (one push, one `/framework-sync` run — with Joe's approval as specified there) and skip the rest of this task. Otherwise:

```bash
cd ~/personal/workout-template
git log origin/main..main --oneline   # show Joe what's about to publish
git push origin main                  # only after Joe approves
```

Then run `/framework-sync` in `~/personal/workout` (per Joe's standing rule: stage and show instead of auto-commit; Joe approves the commit).

---

## Done when

- `/check-in` follows up on `watching` niggles in the interview and writes the log in its close-out, with the escalation and no-load-on-aggravated-pattern rules stated.
- `/setup`'s skeleton tells fresh instances the convention.
- Changes published and synced into Joe's instance.
- Joe's profile is unchanged (no current niggles — first entry creates the subsection).

**Anchor-conflict note:** the `/one-off-week` plan also adds a bullet to check-in's section 7, anchored after the `/hevy-sync` bullet; this plan's bullet anchors after the Coach's-notes bullet. Different anchors — both edits apply cleanly in either order.
