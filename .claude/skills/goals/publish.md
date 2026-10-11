# Publish the pages after a goals change

The brief and the dashboard show the phase, and the brief's food line
shows the protein floor, so step 9's edits leave the athlete's pages
stale until they are rendered and published again. Start once step 9's
edits pass `python3 -m coach config validate`.

1. **No pages yet?** When `this-week.md` does not exist, the first
   programming pass publishes the pages; say so and stop here.
2. Run `python3 -m coach pages render`. Its `brief_overlay` names the
   overlay the brief shows and whether it is `approved`.
3. When `brief_overlay.approved` is true, run `python3 -m coach pages
   publish --overlay <brief_overlay.id>`. That week's "go" already
   approved publishing it. The publish commits exactly the pages, that
   overlay, the newest check-in record and, without Hevy, the session
   sheets, then pushes them.
4. Run `python3 -m coach check --only pages_fresh` and quote it.

Done means step 3's publish reported `pushed: true` and step 4 reports
`pass` for every page.

**Anything short of that is reported as not done**, in the close-out,
with what fixes it:

- `brief_overlay` null or not approved: the pages here are current,
  and the phone keeps the old ones until the next approved week
  publishes.
- A publish that exits 3 (no upstream, another file already staged,
  `README.md` not coach's) or exits 4 (the push failed; the commit is
  kept): quote its message and the fix it names, as
  `program-week/write.md` → "Close out" handles them. Leave the index
  and the files as the refusal left them.

`config.toml` and `profile.md` stay out of the publish. Commit them only
when the athlete asks: show the diff, then stage those two paths by name
(`git add -- config.toml profile.md`), never `git add -A`.
