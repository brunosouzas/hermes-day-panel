Test levels: **unit (pytest)** runs the Python readers with fakes or a real subprocess; **page (node)** renders the Desktop views in Node with SDK stubs. Every scenario of the change's MODIFIED and ADDED requirements is listed with its test.

## 1. Item fields (day-sources)

- [x] 1.1 Item normalisation keeps `tone` (four words), `progress` (number 0–100, not boolean) and `time_label` (text, cut to 40) and drops anything else. Unit (pytest), `tests/test_sources.py`: "Valid tone and progress" → `test_valid_tone_and_progress`; "Out-of-range values dropped" → `test_out_of_range_values_dropped`; kept passing: "Too many items" → `test_too_many_items`, "Unsafe link" → `test_unsafe_link`, "Timeout" → `test_command_timeout`, "Not JSON" → `test_command_not_json`, "Malformed optional fields" → `test_command_malformed_optional_fields`.
- [x] 1.2 `mcp_tool` field mapping accepts `time_label`, `tone` and `progress`, and keeps `progress` only when it is a number. Unit (pytest), `tests/test_mcp.py`: "Progress mapped from a number" → `test_progress_mapped_from_a_number`; kept passing: "Element without title" → `test_element_without_title`.

## 2. AI usage (day-sources)

- [x] 2.1 `ai_usage` option `labels` is validated (a mapping of text to text of 1–40 characters). Unit (pytest), `tests/test_config.py`: "Label that is not text" → `test_label_that_is_not_text`; kept passing: "Unknown option" → `test_unknown_option`.
- [x] 2.2 Window items: title from `labels` and the provider name (reported, else asked for, else `provider`); detail `NN% used` plus plan; `time` and `time_label` `resets`; `progress`; badge `high` and tone `warn` at or above `warn_percent`. Unit (pytest), `tests/test_sources.py`: "Labelled window" → `test_usage_labelled_window`; "Window exactly at the warning level" → `test_usage_window_exactly_at_the_warning_level`; "No provider name reported" → `test_usage_no_provider_name_reported`; kept passing: "Two providers" → `test_usage_two_providers`, "One provider fails" → `test_usage_one_provider_fails`, "Section deadline" → `test_usage_section_deadline`, "Every provider fails" → `test_usage_every_provider_fails`.

## 3. Page (today-page)

- [x] 3.1 Badge coloured by tone; a dot before the title for a tone without a badge; a progress bar under the title (width from the validated number only, tone colour or primary); `time_label` before the short time. Page (node), `tests/desktop/page.test.mjs`: "Usage window", "Badge coloured by tone", "Tone without a badge", "Empty bar and no tone"; kept passing: "Sections shown", "Markup in source text", "Invalid sources file".

## 4. Demo and docs

- [x] 4.1 `examples/demo/sources.yaml` and `examples/demo/demo_source.py` (standard library only, no network): cards, pull-request-like items with badges, pipelines with tones, a routine, and usage windows with progress. Unit (pytest), `tests/test_demo.py`: the file validates, and every section reads `ok` offline through the real readers.
- [x] 4.2 README: item fields table (`time_label`, `tone`, `progress`), `ai_usage` `labels`, "The page" (tone, bar, time label), and a "Try it" section with the demo, plus a screenshot of the demo in Desktop (`docs/today.png`). Check: `tests/test_readme.py` passes.

## 5. Checks

- [x] 5.1 `.venv/bin/python -m pytest -q`, `node --import ./tests/desktop/register.mjs --test tests/desktop/` and `hermes plugins validate . --install-deps` with no `dangerous` warning; `openspec validate usage-bar-and-demo --strict`.
