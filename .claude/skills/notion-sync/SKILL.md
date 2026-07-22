---
name: notion-sync
description: Use when the athlete wants coaching docs mirrored to Notion — first-time Notion setup, syncing or backfilling check-ins, meal plans, recipes, or the routine, or repairing the mapping. Triggers include "/notion-sync", "sync to notion", "set up notion", "put my meal plan in notion", "why isn't this in notion".
---

# Notion sync

Set up and maintain the optional **one-way** mirror of coaching docs
to Notion. The mechanics, map format, and sync contract live in
**`reference/notion-sync.md`** — follow it exactly. This skill owns
setup, backfill, scope changes, and repair; the writing skills
(`/check-in`, `/meal-plan`, `/recipes`) mirror their own output at
close-out.

## 1. Check the MCP

Look for connected Notion tools (per the reference doc). None → tell
the athlete they need to connect a Notion MCP (e.g. the claude.ai
Notion connector) first, and stop — there's nothing useful to do
without one.

## 2. First run — setup

No `notion-map.json` yet:

- State the contract in one breath: files in this repo stay the source
  of truth, Notion is a read-only view, and anything edited on the
  Notion side gets overwritten by the next sync.
- Ask which doc types to mirror: **check-ins** · **meal plans +
  recipes** · **routine**. (Routine earns its place mainly for
  non-Hevy athletes — Hevy users already carry the program in the
  app.)
- Pick the parent page: search their Notion, confirm the exact page
  with the athlete — never guess between similarly named pages.
- Create one section page per chosen doc type under the parent.
- Write `notion-map.json`, then **bulk-export** every existing doc of
  the chosen types, recording each page in the map as it lands.
- Close out: what synced where, and the one-way warning once more.

## 3. Later runs — backfill, scope changes, repair

Map exists:

- Find **stale** and **unsynced** files for the chosen doc types (per
  the reference doc) and re-mirror them. Report updated vs created.
- Spot-check that the parent, section, and a sample of mapped pages
  still exist; repair per the reference doc if not.
- Scope changes on request: add or remove doc types (update
  `doc_types`, create the section page, backfill), or move to a new
  parent page (recreate the structure, re-export, rewrite the map).

## Rules that always apply

- Local files first, always — a Notion failure never loses local work
  and never fails the task that wrote the file.
- Nothing is ever deleted in Notion; the map drops entries instead.
- Every page create/update updates `notion-map.json` in the same
  operation.
