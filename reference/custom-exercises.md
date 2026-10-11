# Create a local custom exercise

Search first: `python3 -m coach library search "paused squat"`, then
`python3 -m coach library show <id>` for a candidate's metadata. Reuse an
existing entry when it describes the intended exercise. If none fits,
agree the name, primary and secondary muscles, movement pattern,
equipment and load basis with the athlete. Ask for missing facts; a name
alone does not establish them.

Write one instance-library entry to `.coach/drafts/custom-exercise.json`.
It uses the existing `coach/schemas/exercise_library.schema.json` entry
fields, without a wrapper or schema version:

```json
{
  "name": "Paused Squat",
  "muscles": {"primary": ["quadriceps", "glutes"], "secondary": ["lower_back"]},
  "pattern": "squat",
  "equipment": "barbell",
  "load_mode_default": "total",
  "load_mode": "total",
  "aliases": ["Two second paused squat"],
  "increment": {"kg": 2.5, "lb": 5},
  "substitutes": ["bb_back_squat"]
}
```

The example's facts need athlete confirmation for their exercise.
`name`, `muscles` (both lists, even when `secondary` is empty), `pattern`,
`equipment`, `load_mode_default` and the confirmed `load_mode` are required.
Use the schema's enums. `load_mode_default` describes the entry's default;
`load_mode` records the athlete's explicit choice, which a program slot
must match. Optional entry fields such as `aliases`, `hevy_titles`,
`increment` and `substitutes` use the same schema. The command does not
infer any required fact or fill a confirmed mode from the default. It
refuses `hevy_template_id`, `hevy_template_ids`, `load_mode_proposed`,
`confidence` and `avoid`; record an avoidance afterwards with
`library set-avoid`.

Preview the proposed merged entry:

```sh
python3 -m coach library create custom_paused_squat --input .coach/drafts/custom-exercise.json --dry-run
```

Show the athlete the returned `exercise`, including its load mode and
muscles, and confirm the exact entry before creating it. Dry-run validates
the entry and its conflicts without writing any files. After approval,
repeat the same command without `--dry-run`, then run:

```sh
python3 -m coach library validate
python3 -m coach library search "paused squat"
python3 -m coach library show custom_paused_squat
```

Creation writes only `data/exercises.json`, atomically. An identical retry
returns `unchanged: true`, `written: false`; a different entry at that ID
fails. Creation cannot update an entry or override a catalogue ID. Review
the existing entry or choose another `custom_` ID when it conflicts.
Use the created ID and confirmed mode in the program draft, then follow
the normal program-adoption validation and approval flow.

**Hevy enabled:** local creation establishes no external readiness and
creates no Hevy exercise template. Leave mapping IDs absent until a real
existing Hevy template has been identified and its local mapping separately
confirmed. Resolve that mapping before a routine write; never invent an ID.
With Hevy disabled, the local entry can be used in program drafts and
manual training without an external mapping.
