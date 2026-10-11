# Writing `config.toml`

1. Run `python3 -m coach config suggest --unit <kg|lb>`. Its
   `data.values` are the settings to write; fold what its `data.notes`
   say to confirm (such as the heaviest dumbbell) into profile question 5.
2. Copy `config.example.toml` to `config.toml` and set, with the Edit
   tool:
   - `[athlete]`: `units` and `bodyweight_units` from `data.values`.
     Leave `week_starts` and `timezone` as the example has them (Monday;
     this computer's local time) unless the athlete says otherwise.
   - `[equipment]`: every key in `data.values`, uncommenting it. Step 4
     sets `available` and `dumbbells`.
   - `[hevy]`: `enabled` — `true` for Pro, `false` for free or none
     (free has no API, so the coach works as if there were no Hevy).
