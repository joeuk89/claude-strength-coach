# Write the record

Run `python3 -m coach history sync`, then `python3 -m coach checkin
skeleton --date <today>`. It writes `check-ins/<today>.md`, titled with
the card's tier (pass `--tier deep` when the block preview required
deep), holding:

- **Week in review:** a rendered region: the window, sessions n of m
  core, the `Missed:` line with each miss's tag, the sessions, results
  and e1RM tables, and the flags; on a deep record, the misses since the
  last deep check-in. It reads synced history only, so the command warns
  when a workout in the window is not synced yet.
- **Coach's read**, **Decisions** and **The week ahead**: empty, for your
  prose. Deep records add **Block planning** after Decisions.

Exit 1 means the record exists. Never edit inside a rendered region:
correct the data (`history annotate`), then run `checkin skeleton --date
<today> --refresh`, which re-renders the regions and leaves every other
byte as it was. Once the week's overlay is approved (act.md), run it
with `--refresh --overlay <id>` to put the prescription in a collapsed
appendix in **The week ahead**; it also collapses a region that
`overlay render --into` already wrote.

Add the cardio block with `python3 -m coach cardio render --week <the
week> --into check-ins/<today>.md`: in **Week in review**, the week's
numbers, the reconcile and the cardio flags. It is a snapshot, which no
check re-renders, so run it again only when the week's data changes
before the record is committed.

Write the prose, each section short. The hand-written lines' shapes are
in `reference/record-formats.md`.

- **Coach's read:** one or two sentences on the state of the week, then
  what the region can't say: adherence as the reply confirmed it,
  notable sets, anything off-plan; the athlete's read (sleep, runs,
  niggles, next week; a field the reply didn't answer reads "not
  supplied"); and the three weight and nutrition lines.
- **Decisions:** first the block status line, then what changed and why
  (or "stay the course"), anything deferred, and the adherence decision
  line when it applies.
- **The week ahead:** a Day / Session table, one-off changes called out, and
  one closing line: the focus of the week.

Keep the prose outside the regions under 600 words (1,000 on a deep
record); `python3 -m coach check` warns past that.

**The block status line** opens Decisions: copy `status_line` from the
last `block close` or `block decide` you ran (`python3 -m coach block
status` prints it again). Never write it by hand.

**The adherence decision line** goes in Decisions only when the
adherence trigger was presented or an under-80 % override was agreed,
as `structure decide` prints it, e.g. `Adherence trigger: 58 % over 4
weeks: deferred to 2026-11-02`. An override adds the session after the
outcome. A **declined** proposal isn't presented again until four
ordinary weeks have passed since the decision; a **deferred** one is
presented again at the first check-in on or after its date; an
**adopted** one goes to `/new-program`'s redesign path and isn't
presented again for four ordinary weeks. These rules and the hand-off
apply only to the smaller-schedule decision. An override line (one with
`(override: …)`) records the added session only: it never holds back or
starts the under-70 % trigger, and never goes to `/new-program`.

**Deep records** use the same skeleton titled `(deep)`, with **Coach's
read** expanded to the full analysis (e1RM trends per lift, drift,
balance, intensity honesty) and a **Block planning** section: the
light-week outlook from the hard-week count, whether the goals/phase
plan in `profile.md` is stale (if so, prompt `/goals`), what the next
block should emphasize, and the research line (analyze.md). When body
composition applies (the Sunday message asked it), Block planning ends
with the body composition line that says when the next reading is due;
the next check-in reads it.
