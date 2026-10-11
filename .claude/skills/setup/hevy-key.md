# Hevy key (Pro only)

- Send the athlete to **hevy.com → Settings → Developer → generate API
  key** (or in the app: Profile → Settings → Developer). Have them create
  `.env` (copy `.env.example`) and paste the key as `HEVY_API_KEY=...`
  themselves; never echo the key back.
- If they also want to coach from **Claude Code on the web**: the key
  goes in the cloud environment's variables (never in git), and the
  Hevy API's host must be on a **Custom** network allowlist or every
  call fails.
- Once they say it's in: `python3 -m coach hevy status` — `key` must
  read `present` (else the key isn't in `.env` yet). Then `python3 -m
  coach hevy pull` checks the key works: exit 0 is success, exit 5
  means Hevy rejected the key (re-copy it), exit 4 means Hevy couldn't
  be reached (try again shortly).
