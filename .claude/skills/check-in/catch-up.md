# Catch-up card

When `data.card.mode` is `catch_up`, this is a catch-up check-in: send
`data.text` as the whole message. It has no per-session fields: one
summary row per week since the newest review, the return week
(`card.catch_up.return_week`: band, days off, load and set change, RPE
cap, each session's lines and flags), the numbered questions (the gap,
now, Food, next week), then the write line and "Reply ok to accept all
of this, or answer any of 1–4." Then stop and wait for the athlete's
reply. A catch-up never runs deep; when one was due, the card has
`deep_deferred: true` and the next check-in runs deep, with the reason
"deferred from catch-up <date>". Write its record with `checkin
skeleton` as record.md says; its title says `(catch-up)`.

- **One tag for the whole gap:** run `python3 -m coach checkin tag-gap
  --tag <tag>`. It writes one `miss` annotation per untagged missed core
  session in the window. Tags per session go through `history annotate
  --input` as the Sunday message's reply does. Then run `checkin
  prepare` again: an `ill` tag brings in the illness rule
  (`return_after_illness`, the first session capped), so the return
  week changes and is presented again.
- **Food** is the Sunday message's Food field: the `nutrition status`
  questions and pre-fills, or, with nutrition off, **Bodyweight** (one
  morning scale weight). Food's readings cover the last 7 days only,
  and the question names those dates. Record them as nutrition.md says,
  as one reading dated the check-in date, and nothing for the earlier
  weeks of the gap. A reading the reply leaves out is "not supplied".
- **"ok" alone** is a complete check-in: misses stay untagged, nothing
  new to report, the Food readings not supplied, and the return week as
  shown, written to Hevy (no Hevy: approved only). Run `python3 -m
  coach propose week --week <return_week.week>` and compare its
  `data.lines_digest` with the card's `return_week.lines_digest`.
  Equal: run `python3 -m coach propose finalize --proposal <id>`, then
  `python3 -m coach overlay approve <id>` and `python3 -m coach routines
  push --overlay <id>` as program-week's write step describes, without
  asking again. Different: something changed since the card, so present
  the new return week and wait for the reply.
- **A reply that mentions illness, travel or no kit:** present `python3
  -m coach checkin return-brief` output as the coach's brief. Use
  `--proposal <id> --reason ill` (or `layoff`) for a proposed return
  week, or `--overlay <id> --reason travel|no_kit` for a one-off week
  you built with `overlay build`. Its `data.text` is the return brief:
  the gap, what the return week does, each session's lines, what
  happens after, and the write line; `ill` adds the illness rule's
  safety lines from `CLAUDE.md`. If it returns warnings, the lines do
  not carry the return band's change or the illness cap, and the brief
  leaves that claim out: fix the week as each warning says (propose it
  again, or rebuild the overlay), then run `checkin return-brief` again
  before presenting. Edit the words if you like, never the figures. One
  "go" approves it and every write its last line names.
