# Midweek mode

Started partway through a trained week, first ask what prompted it: a
missed session, a change to a lift, an easy or hard day, a schedule
change.

**Mid-week?** For a missed session, run `python3 -m coach missed list`
and pass over rows with `recorded: true` (that miss is already on file),
or take the session and date the athlete names; then run `python3 -m
coach missed plan --session <id> --date <date>`. When it reports
`matched: true`, present its `summary` lines and end with its
`write_line` and the commit plan (brief.md, step 7, with `--missed`),
then stop and wait for the athlete's reply. Only after "go": run
`python3 -m coach missed apply --session <id> --date <date> --tag
<tag>` (the athlete's reason: `time`, `sleep`, `ill`, `family`,
`skipped` or `other`; leave `--tag` off when they gave none), then
`python3 -m coach overlay approve <overlay_id>` with the `overlay_id` it
reports and, for Hevy users, `python3 -m coach routines push --overlay
<overlay_id>`. A `skip` rule (`action: skip`) writes no overlay, so
nothing is published: its write line has no commit plan. Stop after
`missed apply` and tell the athlete the miss stays only on this computer
(uncommitted) until the next brief's commit plan names
`data/history/annotations.json`. When it reports `matched: false`
(`missed_rule_unmatched`), the athlete decides what happens to the
session: "No rule applies" below.

**No rule applies.** The missed session's lifts leave the week only when
the athlete chooses that. Show `missed plan`'s `reason` and its
`destinations` (each later day of the span: `free`, `occupied`,
`elapsed` or `unavailable`), and offer:

- **Move it** to a free day: `missed plan --session <id> --date <date>
  --move-to <day>`, presented like a matched rule (summary, write line).
- **Reshuffle**, when the move needs other sessions moved too: one-off.md's
  reshuffle mode. Record the miss with `python3 -m coach history annotate
  --kind miss --date <date> --session <id> --tag <tag> --reason
  "reshuffled to <day>"`.
- **Drop it**: `missed plan ... --drop`; the rest of the week stays as
  planned.

After "go", run `missed apply` with the same `--move-to <day>` or `--drop`
and the athlete's `--tag`; it records the choice with the miss, and a
second apply of the same miss is refused. An `unavailable` day is the
athlete's `[athlete] available_days` speaking: ask whether that day is
really free, and change the list only on their confirmed answer. Once
the miss is recorded, a change to the sessions left is compute.md's
proposal with `--kind midweek`, then the steps after it.

**A lift with no session left this week** ("bump my squat" the day after
its only session): its next exposure is next week's own session, so the
change goes to the next proposal. Read the lift's latest exposure with
`python3 -m coach stats e1rm --exercise <id>`, agree the change from it,
and record it with `python3 -m coach followups add --text "<lift>:
<agreed change>, from <latest exposure>" --review-at <the day next week
is planned> --source "mid-week request <date>"`. The next weekly
proposal raises it as `followup_due`: check its line against the latest
exposure again, apply it as that line's override (compute.md, step 5),
then `followups resolve` it.

After a matched rule's or a move's push, verify and close out as
write.md does. Without Hevy, skip the push and run `python3 -m coach
sheets render`.
