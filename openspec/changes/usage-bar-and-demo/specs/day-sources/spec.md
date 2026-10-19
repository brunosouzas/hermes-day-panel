## MODIFIED Requirements

### Requirement: Section result

Every read SHALL produce `items` (each with a text `title` and optional `url`, `detail`, `badge`, `time`, `time_label`, `tone`, `progress`), optional `total` (default the number of items before the cut) and `note`. Items beyond `max_items` are cut, text fields are cut to 300 characters, and a `url` that is not an absolute http(s) URL is dropped.

#### Scenario: Too many items

- **GIVEN** a source that returns 80 items and a section with `max_items: 5`
- **WHEN** the section is read
- **THEN** the result has 5 items and `total` is 80

#### Scenario: Unsafe link

- **GIVEN** a source item with `url: javascript:alert(1)`
- **WHEN** the section is read
- **THEN** the item is kept without a `url`

### Requirement: Kind options

Each kind SHALL accept only these options. `command`: `argv` (required, 1–50 strings, the program first). `github_prs`: `include` (list of `author` and/or `review_requested`, default both), `exclude_owners` (list of text, default empty), `merge` (see the today-page spec). `mcp_tool`: `server`, `tool`, `args`, `fields`, `list_key` (see its requirements). `ai_usage`: `providers`, `warn_percent`, `labels` (see AI usage options).

#### Scenario: Unknown option

- **GIVEN** a `command` section with `options: {argv: [date], shell: true}`
- **WHEN** the file is validated
- **THEN** the error says section `cmd` has an unknown option `shell` and lists `argv`

### Requirement: Command output limits

A `command` read SHALL fail when the program runs past `timeout_s` (it is killed), writes more than 256 KiB to standard output, or prints something that is not a JSON object with an `items` list. An item that is not an object or has no non-empty text `title` is dropped; an optional item field of the wrong type is dropped; a `total` that is not a whole number of 0 or more, or a `note` that is not text, is ignored.

#### Scenario: Timeout

- **GIVEN** a command that sleeps past `timeout_s: 1`
- **WHEN** the section is read
- **THEN** the program is killed and the read fails saying it timed out after 1 s

#### Scenario: Not JSON

- **GIVEN** a command that prints `hello`
- **WHEN** the section is read
- **THEN** the read fails saying the output is not the expected JSON

#### Scenario: Malformed optional fields

- **GIVEN** a command that prints `{"items": [{"title": "x", "detail": {}}, {"title": 3}], "total": "many", "note": []}`
- **WHEN** the section is read
- **THEN** the read succeeds with one item `x` without a detail, `total` 1 and no note

### Requirement: MCP tool field mapping

`options.fields` SHALL map item fields to keys of each list element: `title` (required) and optional `detail`, `badge`, `time`, `time_label`, `url`, `tone`, `progress`. Values that are not text are converted to text, except `progress`, which is kept only when it is a number; `tone` and `progress` then follow the item rules. An element that is not an object or has an empty title is skipped, and the note says how many were skipped.

#### Scenario: Element without title

- **GIVEN** a result list of three elements, one of them without the mapped title key
- **WHEN** the section is read
- **THEN** there are two items and the note says one entry was skipped

#### Scenario: Progress mapped from a number

- **GIVEN** `fields: {title: name, progress: pct}` and elements `{"name": "a", "pct": 55}` and `{"name": "b", "pct": "55"}`
- **WHEN** the section is read
- **THEN** item `a` has `progress` 55 and item `b` has no `progress`

### Requirement: AI usage source

An `ai_usage` section SHALL run `hermes usage --json --provider <name>` for each name in `providers`, in order (none listed: one run without `--provider`); `timeout_s` bounds the whole section. Each limit window becomes an item, as AI usage items says. Providers that fail or are not reached in time are named in the note.

#### Scenario: Two providers

- **GIVEN** providers `anthropic` and `openai-codex`, each reporting two windows, one of them at 85% used
- **WHEN** the section is read
- **THEN** there are four items, and only the 85% window has the badge `high`

#### Scenario: One provider fails

- **GIVEN** providers `a` and `b`, where `hermes usage` for `b` exits with status 1
- **WHEN** the section is read
- **THEN** `a`'s windows are items and the note says provider `b` could not be read

#### Scenario: Section deadline

- **GIVEN** providers `a` and `b` and `timeout_s: 5`, where `a` takes the whole 5 seconds
- **WHEN** the section is read
- **THEN** `a` is stopped, `b` is not run, and the read fails naming both as not read in time

#### Scenario: Every provider fails

- **GIVEN** a single provider whose `hermes usage` exits with status 1
- **WHEN** the section is read
- **THEN** the read fails with that provider's error

## ADDED Requirements

### Requirement: Item tone, progress and time label

An item's `tone` SHALL be one of `good`, `warn`, `bad` or `muted`, and its `progress` a number from 0 to 100 (a boolean is not a number). Any other value is dropped and the item is kept. `time_label` is text cut to 40 characters, shown before the item's time.

#### Scenario: Valid tone and progress

- **GIVEN** a command that prints `{"items": [{"title": "build", "tone": "bad", "progress": 40, "time_label": "finished"}]}`
- **WHEN** the section is read
- **THEN** the item keeps `tone` `bad`, `progress` 40 and `time_label` `finished`

#### Scenario: Out-of-range values dropped

- **GIVEN** a command that prints `{"items": [{"title": "x", "tone": "purple", "progress": 140}, {"title": "y", "progress": true}]}`
- **WHEN** the section is read
- **THEN** both items are kept, neither has a `tone` or a `progress`

### Requirement: AI usage options

`ai_usage` SHALL accept `providers` (list of 0–10 names, default empty), `warn_percent` (1–100, default 80) and `labels` (a mapping from a provider name to the text shown for it, 1–40 characters each, default empty).

#### Scenario: Label that is not text

- **GIVEN** an `ai_usage` section with `options: {labels: {openai-codex: 5}}`
- **WHEN** the file is validated
- **THEN** the error names the section and says each label must be text of 1 to 40 characters

### Requirement: AI usage items

Each window SHALL become an item titled `<label> · <window label>`, where the label is `labels[<provider>]` for the provider name `hermes usage` reports, else that name. Its detail is `NN% used` (followed by the plan when one is reported), `time` the reset time with `time_label` `resets`, and `progress` the percent used. At or above `warn_percent` it also gets the badge `high` and tone `warn`.

#### Scenario: Labelled window

- **GIVEN** `labels: {claude-x: Claude}` and provider `claude-x` reporting window `Current session` at 68% that resets at 16:00, with `warn_percent: 80`
- **WHEN** the section is read
- **THEN** the item is titled `Claude · Current session`, with detail `68% used`, `progress` 68, `time_label` `resets` and that reset time, and no badge or tone

#### Scenario: High window

- **GIVEN** a provider with no label reporting window `Weekly` at 92% and `warn_percent: 80`
- **WHEN** the section is read
- **THEN** the item is titled `<provider name> · Weekly`, has the badge `high` and tone `warn`
