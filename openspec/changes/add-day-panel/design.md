# Design

## Context

Observed (DES-4):
- The Desktop plugin SDK loads uncompiled ESM from `desktop/plugin.js`, and `dashboard/plugin_api.py` is mounted at `/api/plugins/<name>/` while the plugin is enabled (the same shape as `hermes-daily-reading`, `dashboard/plugin_api.py` and `desktop/plugin.js`).
- Hermes records each MCP tool's `readOnlyHint` at discovery (`tools/mcp_tool_handlers.py`, `_tool_is_read_only`) and registers the tool as `mcp__<server>__<tool>` (`tools/mcp_tool_schema.py`, `mcp_prefixed_tool_name`). A standalone process can call `discover_mcp_tools([server])` and then `registry.dispatch(name, args)`. This was tried on 2026-10-19 against a remote OAuth server, Structured, in about 7 s.
- `hermes usage --json [--provider P]` prints `{provider, title, plan, windows: [{label, used_percent, resets_at}], details, unavailable_reason}` and exits 1 when the fetch fails (`hermes usage --help`, run on 2026-10-19).

## Decision 1: how a source plugs in

| Option | Fit | Cost |
|---|---|---|
| A. A program that prints JSON (`command`), plus a few built-in kinds | Any language; the private sources stay in the user's own repository; nothing to register | One process per read |
| B. Python entry points or modules the plugin imports | Faster | The user's code runs inside the Hermes backend. A bad source can hang or crash the server, and the trust boundary blurs |
| C. Other Hermes plugins register providers through a hook | Clean for plugin authors | Needs an API in Hermes core that does not exist |

Choice: **A**. Rejected B: it would run user code in the server process. Rejected C: it depends on Hermes core. Built-in kinds exist only where a generic tool is already on most machines (`gh`, Hermes' own MCP client, `hermes usage`).

## Decision 2: where the MCP call runs

In-process dispatch would reuse a connection the backend may already hold. But a stuck remote server would tie up a worker thread, and the plugin cannot kill a thread. A child process running Hermes' own Python (`sys.executable -I`, with the Hermes source root on its path) can be killed at the timeout. It costs one MCP connection per read (about 7 s for Structured), which the cache absorbs. Choice: **child process**.

## Decision 3: cache

The cache lives in memory, so the plugin writes nothing to disk. The first load after a restart reads every section; reads run four at a time. A file cache would add a write path, stale-file handling and its own entry in the README's "writes", for little gain.

## Merge guard

Merge needs three things: the owner's opt-in in the sources file (the page cannot turn it on), a preview that returns a single-use token bound to the section, pull request and head commit, and `gh pr merge --match-head-commit`. With the last one, GitHub refuses the merge if the branch moved after the preview.

## Compatibility (DES-3)

Public contracts introduced: the sources file format (`sections` list) and the `command` output JSON. Both are new and versioned by the plugin version. A later breaking change needs a new major version and a README migration note.
