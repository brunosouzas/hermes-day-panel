# Tasks

Tests: `.venv/bin/python -m pytest -q` (unit, offline: `gh`, `hermes usage` and the MCP child are replaced by fakes, except where a task says real child processes) and `node --import ./tests/desktop/register.mjs --test tests/desktop/` (page views and containers rendered in Node).

## 1. Plugin skeleton

- [ ] 1.1 `plugin.yaml` (setting `sources_file`), `__init__.py` registering the `day` CLI command, `dashboard/manifest.json`, `pyproject.toml` with dev dependencies, `AGENTS.md`. Check: `hermes plugins validate . --install-deps` exits 0 and prints no `dangerous` warning.

## 2. Sources file (`dp_config.py`)

- [ ] 2.1 Load the file and apply defaults. Scenarios "Sections in file order", "Missing file", "Defaults applied" → `tests/test_config.py::test_sections_in_file_order`, `::test_missing_file`, `::test_defaults_applied` (unit).
- [ ] 2.2 Validation of fields, kinds and options. Scenarios "Unknown kind", "Value out of bounds", "Unknown option" → `tests/test_config.py::test_unknown_kind`, `::test_value_out_of_bounds`, `::test_unknown_option`, plus repeated id, bad id, wrong types, 20-section limit and every kind's option bounds in `::test_validation_rules` (unit, parametrised).

## 3. Sources (`dp_sources.py`, `dp_mcp_child.py`)

- [ ] 3.1 Section result normalisation. Scenarios "Too many items", "Unsafe link" → `tests/test_sources.py::test_too_many_items`, `::test_unsafe_link` (unit).
- [ ] 3.2 `command`. Scenarios "Valid output", "Relative script with Hermes' Python", "Timeout", "Not JSON", "Malformed optional fields" → `tests/test_sources.py::test_command_valid_output`, `::test_command_relative_script_with_hermes_python`, `::test_command_timeout`, `::test_command_not_json`, `::test_command_malformed_optional_fields` (unit, real child processes running small Python scripts), plus the 256 KiB cap in `::test_command_output_cap`.
- [ ] 3.3 `github_prs`. Scenarios "Authored and review requested", "gh not available" → `tests/test_sources.py::test_prs_authored_and_review`, `::test_prs_without_gh` (unit, fake runner), plus `exclude_owners` and de-duplication in `::test_prs_exclude_and_dedupe`.
- [ ] 3.4 `mcp_tool` and its child. Scenarios "Read-only tool", "Write-capable tool refused", "Unknown server", "Text after a heading", "Scalar result", "Object without list key", "List key not a list", "Element without title" → `tests/test_mcp.py::test_read_only_tool`, `::test_write_tool_refused`, `::test_unknown_server`, `::test_text_after_heading`, `::test_scalar_result`, `::test_object_without_list_key`, `::test_list_key_not_a_list`, `::test_element_without_title` (unit: the child's functions run with a fake registry and discovery; the parent's timeout runs a real child that sleeps in `::test_mcp_child_timeout`).
- [ ] 3.5 `ai_usage` (blocked until the owner answers the proposal's open question at gate 1; the requirement changes with the answer). Scenarios "Two providers", "One provider fails", "Section deadline", "Every provider fails" → `tests/test_sources.py::test_usage_two_providers`, `::test_usage_one_provider_fails`, `::test_usage_section_deadline`, `::test_usage_every_provider_fails` (unit, fake runner and clock).

## 4. Refresh, cache, status and log (`dp_panel.py`)

- [ ] 4.1 Memory cache keyed by id and definition hash, joined reads, four at a time. Scenarios "Fresh result reused", "Concurrent refresh joins", "Definition changed" → `tests/test_panel.py::test_fresh_result_reused`, `::test_concurrent_refresh_joins`, `::test_definition_changed` (unit, fake sources and threads).
- [ ] 4.2 Status. Scenarios "Failure after success", "First read fails", "Command fails" → `tests/test_panel.py::test_failure_after_success`, `::test_first_read_fails`, `::test_command_fails` (unit; the last runs a real child process).
- [ ] 4.3 Failure log. Scenario "Output not logged" → `tests/test_panel.py::test_output_not_logged` (unit, `caplog`).

## 5. CLI (`dp_cli.py`)

- [ ] 5.1 `hermes day show [--json]` and `hermes day check`. Scenarios "Invalid file", "Show as JSON" → `tests/test_cli.py::test_check_invalid_file`, `::test_show_json` (unit).

## 6. Backend routes (`dashboard/plugin_api.py`)

- [ ] 6.1 `GET /sections`, `POST /sections/{id}/refresh`, `POST /refresh`. Scenarios "Refresh one section", "Unknown section id" → `tests/test_api.py::test_refresh_one_section`, `::test_unknown_section_id` (FastAPI TestClient).
- [ ] 6.2 Merge setting, preview, confirmation and failure. Scenarios "Merge off by default", "Draft pull request", "Confirmed merge", "Token used twice", "Token expired", "Section disabled after the preview", "Merge turned off after the preview", "Head moved" → `tests/test_api.py::test_merge_off_by_default`, `::test_merge_draft_refused`, `::test_merge_confirmed`, `::test_merge_token_used_twice`, `::test_merge_token_expired`, `::test_merge_section_disabled_after_preview`, `::test_merge_turned_off_after_preview`, `::test_merge_head_moved` (FastAPI TestClient, fake `gh` runner, fake clock), plus a second confirm while one runs in `::test_merge_one_at_a_time`.

## 7. Desktop page (`desktop/plugin.js`)

- [ ] 7.1 Page views. Scenarios "Sections shown", "Markup in source text", "Invalid sources file", "Item without a link" → `tests/desktop/page.test.mjs` tests of the same names (Node, rendered views).
- [ ] 7.2 Refresh controls and 60 s polling. Scenario "Refresh one section" (page side) → `tests/desktop/page.test.mjs` "refresh one section calls its route" (Node, container with a fake `rest`).
- [ ] 7.3 Merge dialog. Scenarios "Merge off by default" (no control), "Preview shown and cancelled", "Confirmed merge" and "Head moved" (page side) → `tests/desktop/page.test.mjs` "merge control only when enabled", "preview shown and cancelled", "confirm sends the token and shows merged", "merge error shown" (Node, fake `rest`).

## 8. Documentation and acceptance

- [ ] 8.1 README: install, the sources file with every field and option, each kind with an example, the command output format, the merge guard, "What it reads, sends and writes". Check: `tests/test_readme.py::test_every_option_documented` finds every field and option name from `dp_config.py` in the README.
- [ ] 8.2 Acceptance on the owner's Mac, with his sources from `hermes-personal`: the page shows real data from every section (screenshot in the pull request), and `hermes day show` prints the same sections.
