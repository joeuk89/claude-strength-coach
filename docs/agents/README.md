# Agent skills (template development only)

This file configures dev-tooling skills for work on the template itself.
The `docs/agents/` files are not synced to instances: in an instance
workspace, ignore them.

### Issue tracker

Issues live as GitHub issues in `joeuk89/claude-strength-coach`, managed
with the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

The five canonical triage roles, each label string equal to its name. See
`docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` and `docs/adr/` at the repo root. See
`docs/agents/domain.md`.

### Workspace identity

With neither `profile.md` nor `config.toml`, `coach status` and the
SessionStart hook treat a checkout as the template only when its own Git
config says so: `coach.workspace = template`, or no setting and an `origin`
on the canonical GitHub repository. A fork or local development copy runs
`git config --local coach.workspace template`. Any other copy gets the
`/setup` prompt. Contract C52 has the full rule.
