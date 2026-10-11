# A short week

Use a configured minimum when it fits the athlete's available days, kit and
time. Otherwise offer constrained mode in [one-off.md](one-off.md) now;
its temporary sessions leave the ordinary program intact. A minimum variant
is optional, and setting one up need not delay this week's training.

## Configure a reusable minimum

When the athlete wants a reusable short week, agree the structural change
through the normal brief and approval before editing `data/program.json`:

1. Copy suitable ordinary sessions with new ids and `status: standby`.
   Keep usable exercises, load modes, progression schemes, working loads and
   effort; reduce sets to fit the available time while retaining priority
   lift floors. Standby sessions stay out of the ordinary schedule.
2. Set `minimum_week.sessions` to those ids and `minimum_week.schedule`
   to the rule and params that place them on the available days. For
   `fixed_weekdays`, for example, use
   `{"rule":"fixed_weekdays","params":{"days":{"tue":"min-a","fri":"min-b"}}}`.
   A fixed minimum is compared with every ordinary rotation position. If
   both schedules rotate, use the same position names so each comparison
   has the corresponding ordinary reference.
3. List only coach-led sessions that will still happen in
   `minimum_week.external_sessions`, using their ids from the program's
   `external_sessions`. Each retained session needs a `weekday`; it keeps
   that day. An omitted or empty list credits no coach-led dose to the
   minimum. Confirm that the retained sessions also fit the short week.
4. Run `python3 -m coach program validate`, then `python3 -m coach program
   render`, then `python3 -m coach structure balance --variant minimum`.
   Resolve every failure before offering this minimum for use; otherwise
   use constrained mode for the immediate week.

## Check and use the minimum

Run `python3 -m coach structure balance --variant minimum` each time.
Read each position's ordinary reference, planned dose, priority floors and
session duration separately. The check permits at most two self-programmed
minimum sessions and applies the existing time caps; retained coach-led
work is listed separately and still matters to the athlete's available time.

The approximate one-third comparison uses ordinary programmed weekly dose,
including scheduled coach-led estimates, rather than a hypertrophy target.
This fractional-muscle calculation is application policy
(rn:minimum-effective-dose.6), not a universal maintenance guarantee.
Older lifters can need more work to retain muscle size
(rn:minimum-effective-dose.2); discuss that before reducing their program.

When the check passes, run `python3 -m coach structure minimum --week
<label> --write`, then `python3 -m coach propose week --week <label>
--plan <the path it printed>`. Review its retained coach-led sessions as
well as its lifting sessions. Continue with compute.md's line review and
finalize, then build.md and the usual brief and approval. The overlay stays
`weekly`; the minimum plan marks the week so the hard-week count neither
counts nor resets it.
