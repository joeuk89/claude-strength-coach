# Midweek mode

Started partway through a trained week, first ask what prompted it: a
missed session, an easy or hard day, a schedule change.

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
(`missed_rule_unmatched`), or for any other reason, reprogram only the
remaining days: compute.md's proposal with `--kind midweek`, then the
steps after it.

After a matched rule's push, verify and close out as write.md does.
Without Hevy, skip the push and run `python3 -m coach sheets render`.
