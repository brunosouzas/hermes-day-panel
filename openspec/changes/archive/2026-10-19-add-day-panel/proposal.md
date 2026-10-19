# Proposal

## Why

Hermes Desktop has dashboards, but none of them answers "what needs me today?" from the user's own tools without a model in the loop. The catalog was checked on 2026-10-19 (615 entries, pinned 2026-10-15):

- `home-dashboard`: a grid of 16 built-in widgets over Hermes' own data (sessions, cron, tokens, clock). A new data source means a new TypeScript widget and a rebuilt bundle.
- `boardstate`: a board the agent lays out through 19 tools, with a Node sidecar and MCP connectors behind operator grants. The agent builds the board, so every update goes through the model.
- `hermes-monitoring-dashboard`: host metrics plus static text, clock and calendar widgets from a JSON file. No external data sources.
- `ai-usage-tracker`, `usage-flame`, `provider-usage` and similar: provider quota only.
- `my-github`: a list of the user's repositories, not pull requests that wait for them.

None reads arbitrary sources on a schedule without the model. Card AB#77 asks for a public "Today" page with pluggable sources, while the owner's own sources stay private.

## What Changes

- New plugin `day-panel` (repository `hermes-day-panel`): Python, standard library plus the PyYAML Hermes ships, and a Desktop page.
- A sources file the user owns (YAML) lists the page's sections in order. Each section has a kind, options, a refresh interval and an on/off switch.
- Four source kinds, all read-only:
  - `command`: runs a program the user names, without a shell, and reads a small JSON document from its standard output. This is how anyone plugs in a source the plugin does not know (a board, a notes folder).
  - `github_prs`: open pull requests the user authored or was asked to review, through the `gh` CLI the user is already logged into.
  - `mcp_tool`: one tool of an MCP server already configured in Hermes, called only when the server marks that tool read-only (`readOnlyHint`).
  - `ai_usage`: the account limit windows that `hermes usage --json` reports for each provider listed.
- A Desktop page, **Today**, showing every enabled section with its items, when it was read and any error. Sections refresh on their interval while the page is open, and on demand.
- Pull request merge from the page, off by default. When a `github_prs` section turns it on, the user previews the merge and then confirms it. The merge runs only if the pull request's head commit is still the one shown.
- A CLI: `hermes day show` prints every section and `hermes day check` validates the sources file.
- README with installation, configuration, examples, and what the plugin reads, sends and writes. Tests, `hermes plugins validate` passing, MIT licence.

## Capabilities

### New Capabilities

- `day-sources`: the sources file, the four source kinds, their limits, refresh and caching, and the CLI.
- `today-page`: the Desktop page, its backend routes and the confirmed pull request merge.

### Modified Capabilities

None (new repository).

## Out of scope

- Notifications. The owner's watcher that posts changes to Slack lives in his private `hermes-personal` repository and does not use this plugin.
- Writing anywhere except the merge action: no edits to boards, notes, tasks or MCP servers.
- Calling a model. The page and the CLI never send anything to a model provider.
- Built-in kinds for Azure Boards, Jira, Linear, calendars or notes vaults. A `command` source covers them, and the owner's live in `hermes-personal`.
- Editing the sources file from the page. The user edits it by hand or asks Hermes to.
- Persisting results across restarts: the cache lives in memory, and the first page load after a restart reads every source again.
- Token and cost history (`hermes insights`); `ai_usage` shows only the provider's limit windows.
- Remote Hermes backends: commands, `gh` and `hermes usage` run on the machine that runs the Hermes backend.
- Submitting the plugin to the Hermes catalog, a separate step after the owner approves.

## Open questions

None open. Answered by the owner at gate 1 (2026-10-19):

1. "AI usage" means the provider limit windows that `hermes usage` reports (session and week, used percent, reset time) for the providers the user lists. Token and cost history (`hermes insights`) stays out of scope.
2. Merge is opt-in per section, needs a preview and a confirmation, and is guarded by the head commit.

## Implicit requirements

- **Errors and invalid input**: required. A sources file that fails validation is reported on the page and by `hermes day check`, naming the section and the rule. A section whose read fails shows its error, and keeps its last good items marked stale when it has them. One failing section never blocks the others.
- **Limits**: required. Per section: read timeout 1–120 s (default 30; for `ai_usage` it bounds all providers together), at most 50 items (default 10), refresh interval 1–1440 minutes (default 15). Command standard output at most 256 KiB, text fields cut to 300 characters, at most 20 sections. A merge confirmation expires after 120 s.
- **Repetition and idempotency**: required. A refresh request for a section already being read joins that read instead of starting another. A merge confirmation token works once, whatever the outcome; a second confirm is refused.
- **Concurrency**: required. At most one read per section definition at a time, and at most four reads in parallel. A changed section definition gets a fresh read, and a read finishing for the old definition is discarded. Only one merge runs at a time.
- **Security**: required. Programs come only from the sources file, run without a shell, and are never given anything from the page. Routes take section ids, never paths or arguments. Source output is untrusted: it is rendered as text, and only http(s) links open. `mcp_tool` refuses a tool that is not marked read-only. Merge is off unless the user's sources file turns it on, needs a confirmation bound to one preview, re-checks the sources file on confirmation, and checks the head commit.
- **Logs and observability**: required. Each section shows its status (ok, error, stale), when it was last read and how long the read took. The plugin logs one warning per failed read with the section id, kind and error, never the source's output.

## Impact

- New repository `brunosouzas/hermes-day-panel` (public, MIT).
- Writes nothing on disk. The sources file is the user's (default `$HERMES_HOME/day-panel/sources.yaml`); the plugin only reads it.
- Uses Hermes surfaces: `ctx.register_cli_command`, `ctx.get_config`, a Desktop plugin page and its `dashboard/plugin_api.py` backend, Hermes' MCP client (`tools.mcp_tool_discovery`, `tools.registry`) for `mcp_tool`, and the `hermes usage --json` command.
- The owner's sources (Azure Boards cards and pipelines, drafts waiting for him, his Structured routine) and his watcher live in the private `hermes-personal` repository.

## Documentation

- `README.md` of this repository: installation, the sources file, each kind with an example, the command output format, and "What it reads, sends and writes".
- `AGENTS.md` of this repository: project context for agents.
- Vault note `10-personal/projects/hermes-plugins/_index.md` (repository table and status), on the vault's `main` after this pull request is ready.
