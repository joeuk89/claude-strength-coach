# Notion sync — mechanics

How the optional Notion mirror works. `/notion-sync` owns setup,
backfill, and repair; `/check-in`, `/meal-plan`, and `/recipes` mirror
their own writes at close-out. Read this before any Notion write.

## The contract

- **One-way.** Repo files are the source of truth; Notion is a read
  view. Local writes always happen first and never depend on Notion.
  Notion-side edits are unsupported — the next sync of that doc
  overwrites them (the athlete is told this at setup).
- **Optional.** No `notion-map.json` → no Notion behaviour anywhere.
- **Never block.** If no Notion MCP is connected in a session, say the
  sync is pending and continue; `/notion-sync` backfills later. A
  failed Notion write never fails the local task.

## The MCP

Notion access comes from whatever Notion MCP the user connected (the
claude.ai Notion connector, the official Notion MCP server, …). Tool
names differ; the needed capabilities are the same: search, fetch,
create page, update page. Discover what's available at runtime (e.g.
ToolSearch for "notion") — never hardcode tool names. No Notion tools
in this session → sync is pending.

## notion-map.json (repo root)

```json
{
  "_comment": "Notion mirror mapping. One-way: repo -> Notion. Managed by /notion-sync; writing skills append page entries when they mirror their own output.",
  "parent_page_id": "…",
  "parent_page_title": "Training",
  "doc_types": ["check-ins", "meal-plans", "recipes"],
  "sections": {
    "check-ins": "…page id…",
    "meal-plans": "…page id…",
    "recipes": "…page id…"
  },
  "pages": {
    "check-ins/2026-07-19.md": { "page_id": "…", "synced_at": "2026-07-22" }
  }
}
```

`doc_types` is the athlete's choice from: `check-ins`, `meal-plans`,
`recipes`, `routine` (`meal-plans` and `recipes` normally travel
together). File coverage per type: `check-ins/*.md` · dated
`nutrition/*.md` plans · `nutrition/menu/*.md` cards (including
`index.md`) · `routine/*.md`. Any write that creates or updates a
Notion page updates `pages` in the same operation (hevy-map rule).

## Syncing one file

1. Path in `pages` → **update** that page (replace content). Not
   there → **create** under its doc type's section page, then record
   it.
2. Page title = the file's H1 (filename if there's no H1).
3. Content = the file's markdown, with three adjustments:
   - **Links** to repo files that are in `pages` become Notion links
     to those pages; other repo-relative links are flattened to plain
     text — never ship a broken link.
   - **Shopping list tables** (meal plans) become checkable to-do
     items — one per Buy row and per staple row, quantity included.
   - Tables stay tables. Keep formatting simple: when something won't
     render cleanly, prefer plain over clever.
4. Update `pages` (`page_id`, `synced_at`) in the same operation.

## Staleness (what backfill re-syncs)

- **Stale:** a mapped file changed after its `synced_at` — last commit
  date (`git log -1 --format=%cs -- <file>`) is newer, or the file has
  uncommitted changes.
- **Unsynced:** a file of a chosen doc type with no map entry.

## Repair

- Mapped page fetch fails (deleted/moved in Notion) → recreate it,
  update the map.
- Parent or section page missing → offer to recreate the structure,
  then re-link or re-export as needed.
- Local file deleted or archived → drop its map entry; leave the
  Notion page for the athlete to tidy. **Nothing is ever deleted in
  Notion by this system.**
