## 1. Item fields (day-sources)

- [ ] 1.1 Item normalisation keeps `tone` (four words), `progress` (number 0–100, not boolean) and `time_label` (text, cut to 40) and drops anything else. Tests in `tests/test_sources.py`: "Valid tone and progress", "Out-of-range values dropped", and "Malformed optional fields" still passing.
- [ ] 1.2 `mcp_tool` field mapping accepts `time_label`, `tone` and `progress`, and keeps `progress` only when it is a number. Test in `tests/test_mcp.py`: "Progress mapped from a number".

## 2. AI usage (day-sources)

- [ ] 2.1 `ai_usage` option `labels` is validated (a mapping of text to text of 1–40 characters). Test in `tests/test_config.py`: "Label that is not text"; "Unknown option" and "Defaults applied" still pass.
- [ ] 2.2 Window items: title from `labels` or the reported provider name; detail `NN% used` plus plan; `time` and `time_label` `resets`; `progress`; badge `high` and tone `warn` at or above `warn_percent`. Tests in `tests/test_sources.py`: "Labelled window", "High window"; "Two providers", "One provider fails", "Section deadline" and "Every provider fails" still pass.

## 3. Page (today-page)

- [ ] 3.1 Badge coloured by tone; a dot before the title for a tone without a badge; a progress bar under the title (width from the validated number only, tone colour or primary); `time_label` before the short time. Tests in `tests/desktop/page.test.mjs`: "Usage window", "Empty bar and no tone"; "Sections shown", "Markup in source text" and "Invalid sources file" still pass.

## 4. Demo and docs

- [ ] 4.1 `examples/demo/sources.yaml` and `examples/demo/demo_source.py` (standard library only, no network). The sections cover cards, pull-request-like items with badges, pipelines with tones, a routine, and usage windows with progress. Test in `tests/test_demo.py`: the file validates, and every section reads `ok` offline through the real readers.
- [ ] 4.2 README: item fields table (`time_label`, `tone`, `progress`), `ai_usage` `labels`, "The page" (tone, bar, time label), and a "Try it" section with the demo, plus a screenshot of the demo in Desktop (`docs/today.png`). `tests/test_readme.py` passes.

## 5. Checks

- [ ] 5.1 `.venv/bin/python -m pytest -q`, `node --import ./tests/desktop/register.mjs --test tests/desktop/` and `hermes plugins validate . --install-deps` with no `dangerous` warning; `openspec validate usage-bar-and-demo --strict`.
