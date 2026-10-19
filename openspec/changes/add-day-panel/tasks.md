# Tasks

Tests: `.venv/bin/python -m pytest -q` (unit, offline: `gh`, `hermes usage` and the MCP child are replaced by fakes) and `node --import ./tests/desktop/register.mjs --test tests/desktop/` (page views rendered in Node).

## 1. Plugin skeleton

- [ ] 1.1 `plugin.yaml` (setting `sources_file`), `__init__.py` registering the `day` CLI command, `dashboard/manifest.json`, `pyproject.toml` with dev dependencies, `AGENTS.md`. Check: `hermes plugins validate .` passes.

## 2. Sources file (`dp_config.py`)

- [ ] 2.1 Load and validate the file. Scenarios "Sections in file order", "Missing file" → `tests/test_config.py::test_sections_in_file_order`, `::test_missing_file` (unit).
- [ ] 2.2 Validation rules and messages. Scenarios "Unknown kind", "Value out of bounds" → `tests/test_config.py::test_unknown_kind`, `::test_value_out_of_bounds`, plus the repeated id and 20-section limit in `::test_limits` (unit).

## 3. Sources (`dp_sources.py`)

- [ ] 3.1 Section result normalisation. Scenarios "Too many items", "Unsafe link" → `tests/test_sources.py::test_too_many_items`, `::test_unsafe_link` (unit).
- [ ] 3.2 `command`. Scenarios "Valid output", "Command fails", "Timeout", "Not JSON" → `tests/test_sources.py::test_command_valid_output`, `::test_command_fails`, `::test_command_timeout`, `::test_command_not_json` (unit, real child processes running small Python scripts), plus the 256 KiB cap in `::test_command_output_cap`.
- [ ] 3.3 `github_prs`. Scenarios "Authored and review requested", "gh not available" → `tests/test_sources.py::test_prs_authored_and_review`, `::test_prs_without_gh` (unit, fake runner).
- [ ] 3.4 `mcp_tool` and its child (`dp_mcp_child.py`). Scenarios "Read-only tool", "Write-capable tool refused", "Text after a heading", "Unknown server" → `tests/test_mcp.py::test_read_only_tool`, `::test_write_tool_refused`, `::test_text_after_heading`, `::test_unknown_server` (unit, fake registry and discovery injected into the child's functions).
- [ ] 3.5 `ai_usage`. Scenarios "Two providers", "One provider fails" → `tests/test_sources.py::test_usage_two_providers`, `::test_usage_one_provider_fails` (unit, fake runner).

## 4. Refresh and cache (`dp_panel.py`)

- [ ] 4.1 Memory cache, joined reads, four at a time, stale on failure. Scenarios "Fresh result reused", "Failure after success" → `tests/test_panel.py::test_fresh_result_reused`, `::test_failure_after_success`, plus `::test_concurrent_refresh_joins` (unit, fake sources).

## 5. CLI (`dp_cli.py`)

- [ ] 5.1 `hermes day show [--json]` and `hermes day check`. Scenario "Invalid file" → `tests/test_cli.py::test_check_invalid_file` and `::test_show_json` (unit).

## 6. Backend routes (`dashboard/plugin_api.py`)

- [ ] 6.1 `GET /sections`, `POST /sections/{id}/refresh`, `POST /refresh`. Scenarios "Refresh one section", "Unknown section id" → `tests/test_api.py::test_refresh_one_section`, `::test_unknown_section_id` (FastAPI TestClient).
- [ ] 6.2 Merge preview and confirm. Scenarios "Merge off by default", "Draft pull request", "Confirmed merge", "Token used twice", "Head moved" → `tests/test_api.py::test_merge_off_by_default`, `::test_merge_draft_refused`, `::test_merge_confirmed`, `::test_merge_token_used_twice`, `::test_merge_head_moved` (FastAPI TestClient, fake `gh` runner), plus `::test_merge_token_expired`.

## 7. Desktop page (`desktop/plugin.js`)

- [ ] 7.1 Page views and containers. Scenarios "Sections shown", "Markup in source text", "Invalid sources file", "Item without a link" → `tests/desktop/page.test.mjs` tests of the same names (Node, rendered views).
- [ ] 7.2 Refresh controls and 60 s polling. Scenario "Refresh one section" (page side) → `tests/desktop/page.test.mjs::refresh one section calls its route` (Node).

## 8. Documentation and acceptance

- [ ] 8.1 README: install, the sources file, each kind with an example, command output format, merge guard, "What it reads, sends and writes". Check: each setting and option in the code appears in the README (`tests/test_readme.py::test_every_option_documented`).
- [ ] 8.2 Acceptance on the owner's Mac, with his sources from `hermes-personal`: the page shows real data from every section (screenshot in the pull request), and `hermes day show` prints the same sections.
