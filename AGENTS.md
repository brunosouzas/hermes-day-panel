# hermes-day-panel: project context

## Purpose

A public Hermes Agent plugin: a **Today** page in Hermes Desktop built from sections listed in a user-owned YAML file, each read from a read-only source (`command`, `github_prs`, `mcp_tool`, `ai_usage`). Pull request merge from the page is opt-in, previewed, confirmed once and guarded by the head commit. No model calls, nothing written to disk.

## Technology declarations

Stack: Python, pytest, Hermes plugin API, FastAPI (Hermes dashboard backend), Hermes Desktop plugin SDK (plain ESM)
Delivery: D this Mac
Integration branch: `main`
Trivial: none
Deliver and verify: `hermes plugins update day-panel`; a gateway restart only with Bruno around; verify with `hermes plugins check-updates` (Current is the merge commit, up to date) and `hermes plugins list` (enabled) and `hermes day check`

- Plugin code (`__init__.py`, `dp_*.py`) runs inside Hermes and uses the standard library plus core's `hermes_yaml`. Import no YAML library directly, and never add a runtime dependency. Any exception from `hermes_yaml.safe_load` means "not valid YAML" (ruamel raises more than `YAMLError`). Outside Hermes, the root `conftest.py` puts `tests/stubs/hermes_yaml.py` in its place.
- `dashboard/plugin_api.py` is mounted by Hermes at `/api/plugins/day-panel/`; it imports the plugin modules through its own package loader.
- `dp_mcp_child.py` runs as a separate process (Hermes' Python with `-I`, the backend's `sys.path` passed in) so an MCP call can be killed at its timeout.
- `desktop/plugin.js` is uncompiled ESM: `jsx()` calls, not JSX syntax; only `@hermes/plugin-sdk`, `react` and `react/jsx-runtime` resolve. Views stay pure functions of their props so `tests/desktop/` can render them in Node.
- Tests: `.venv/bin/python -m pytest -q` and `node --import ./tests/desktop/register.mjs --test tests/desktop/`; validation: `hermes plugins validate . --install-deps` (delete `tests/__pycache__` first). Run pytest with `PYTHONPATH` unset: a Hermes terminal exports one that breaks the venv.

## Rules

- Repository language: English.
- Board: Azure Boards `brunosouzas`, area `jarvis`; branches `ab<card>-<slug>`; pull requests end with `Fixes AB#<card>`; pull requests from outside contributors are merged by the owner; the owner's own changes follow the gates of the kit's `engineering` playbook.
- Specs live in `openspec/`; change behaviour through an OpenSpec change, and keep tests mapped to its scenarios.
- Nothing personal in the code: sections, programs, servers and providers come from the sources file. The owner's sources live in his private `hermes-personal` repository.
- Source output is untrusted: cut and typed in Python, rendered as text on the page, never passed to a shell, never logged.
- Programs run only from the sources file, without a shell. Routes take section ids and pull request references, never paths, programs or arguments.
- `mcp_tool` calls a tool only when its server marks it `readOnlyHint: true`.
- Keep the README's settings tables and "What it reads, sends and writes" true after every change (`tests/test_readme.py` checks the names).
- No self-updating code (Hermes plugin catalog rule 3).
