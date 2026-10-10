---
status: accepted
date: 2026-10-11
---

# Cardio and health data come through sanctioned exports, never unofficial Garmin clients or the Strava API

The obvious way to get an athlete's runs, sleep and scale weight into the
system is to call Garmin Connect or Strava directly. We decided not to.
Garmin's official API is for companies only and new applications are
paused; the unofficial Python clients broke when Garmin added bot
fingerprinting in March 2026 and have been intermittently blocked since;
Strava's API now requires a paid plan and its policy forbids feeding API
data into any AI context. The template therefore reads cardio and health
data through an activity-source layer whose first adapter is Apple
Health, exported by a phone app to a folder the script reads, with
Intervals.icu as optional enrichment, a run-plan calendar feed for planned
sessions, and manual entry always available. Every source is optional and
the check-in degrades to asking the athlete when data is missing.

## Considered options

- **Unofficial Garmin client as the primary source.** Rejected: terms risk
  and a breakage history measured in weeks.
- **Strava API with the athlete's own token.** Rejected: the policy bans
  the exact use (an agent reading the output), and Strava carries no
  sleep or scale data anyway.
- **Intervals.icu as the hub.** Rejected as the primary: its developer has
  said Garmin may require it to block Garmin data through its API, which
  is exactly the content that makes it rich.

## Consequences

- HRV is not available in the first version: Garmin does not write it to
  Apple Health. Given the measurement error of consumer HRV against the
  training signal it would detect, this is accepted.
- The phone export runs only while the phone is unlocked, so the sync
  must tolerate gaps and the cache is append-only.
- If Garmin opens individual API access, a new adapter slots in behind the
  same interface without touching the rest of the system.
