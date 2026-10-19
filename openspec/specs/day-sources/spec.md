# day-sources Specification

## Purpose
The sources behind the Today page: a user-owned YAML file that lists sections in order, four read-only source kinds (command, GitHub pull requests, read-only MCP tool, AI usage windows), their limits, how results are refreshed and cached, and the CLI that shows and checks them.

## Requirements

### Requirement: Sources file

The plugin SHALL read the sources file named by the `sources_file` setting, or `$HERMES_HOME/day-panel/sources.yaml` when the setting is empty, on every request from the page or CLI. The file is a mapping whose only key is `sections`, a list of 1–20 section mappings, kept in file order.

#### Scenario: Sections in file order

- **GIVEN** a sources file with sections `prs`, `cards` and `usage`, where `cards` has `enabled: false`
- **WHEN** the sections are listed
- **THEN** `prs` and `usage` are returned, in that order, and `cards` is not

#### Scenario: Missing file

- **GIVEN** no file at the configured path
- **WHEN** the sections are listed
- **THEN** the result is a configuration error naming the path, and no source runs

### Requirement: Section fields

Each section SHALL have: `id` (required; 1–40 lowercase letters, digits and hyphens, starting with a letter; unique), `kind` (required; `command`, `github_prs`, `mcp_tool` or `ai_usage`), `title` (text, default the id), `enabled` (boolean, default true), `refresh_minutes` (1–1440, default 15), `max_items` (1–50, default 10), `timeout_s` (1–120, default 30) and `options` (a mapping, default empty).

#### Scenario: Defaults applied

- **GIVEN** a section with only `id: usage` and `kind: ai_usage`
- **WHEN** the file is validated
- **THEN** its title is `usage`, it is enabled, and its refresh, item and timeout limits are 15, 10 and 30

### Requirement: Kind options

Each kind SHALL accept only these options. `command`: `argv` (required, 1–50 strings, the program first). `github_prs`: `include` (list of `author` and/or `review_requested`, default both), `exclude_owners` (list of text, default empty), `merge` (see the today-page spec). `mcp_tool`: `server`, `tool`, `args`, `fields`, `list_key` (see its requirements). `ai_usage`: `providers`, `warn_percent`, `labels` (see AI usage options).

#### Scenario: Unknown option

- **GIVEN** a `command` section with `options: {argv: [date], shell: true}`
- **WHEN** the file is validated
- **THEN** the error says section `cmd` has an unknown option `shell` and lists `argv`

### Requirement: Sources file validation

The plugin SHALL refuse a whole sources file that is not valid YAML or breaks any field, kind or option rule: wrong type, missing required value, value outside its bounds, repeated id, unknown key, more than 20 sections. Each error names the section and the rule broken. A refused file runs no source.

#### Scenario: Unknown kind

- **GIVEN** a section `id: cal`, `kind: calendar`
- **WHEN** the file is validated
- **THEN** the error says that section `cal` has an unknown kind and lists the four allowed kinds

#### Scenario: Value out of bounds

- **GIVEN** a section with `refresh_minutes: 0`
- **WHEN** the file is validated
- **THEN** the error says `refresh_minutes` must be between 1 and 1440

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

### Requirement: Section status

A section SHALL be `ok` after a successful read, `error` when its latest read failed and it has no earlier successful read for its current definition, and `stale` when its latest read failed after an earlier success: it keeps those items and shows the new error. Each section also reports when it was last read and how long the read took.

#### Scenario: Failure after success

- **GIVEN** a section whose last read returned 3 items
- **WHEN** the next read fails
- **THEN** the section is `stale`, still shows the 3 items, and shows the error

#### Scenario: First read fails

- **GIVEN** a section never read successfully
- **WHEN** its read fails
- **THEN** the section is `error`, with no items and the error message

### Requirement: Command source

A `command` section SHALL run `options.argv` without a shell, with no standard input, within `timeout_s`, and read one JSON object from standard output: `items` (a list) and optional `total` (a whole number) and `note` (text). Items follow the section result rules. A non-zero exit fails the read with the exit status and the last line of standard error.

#### Scenario: Valid output

- **GIVEN** a command that prints `{"items": [{"title": "Card 42", "url": "https://example.com/42"}], "total": 1}`
- **WHEN** the section is read
- **THEN** the read succeeds with that one item

#### Scenario: Command fails

- **GIVEN** a section never read successfully, whose command exits with status 2 and prints `boom` on standard error
- **WHEN** the section is read
- **THEN** the section is `error` with a message containing the exit status and `boom`

### Requirement: Command environment

A `command` program SHALL run with the sources file's folder as its working directory, so `argv` may name files relative to it. An `argv` element that is exactly `{python}` SHALL be replaced by the path of the Python interpreter running Hermes. No other placeholder is expanded, and the environment is the Hermes backend's own.

#### Scenario: Relative script with Hermes' Python

- **GIVEN** `argv: ["{python}", source.py]` and a `source.py` next to the sources file that prints `{"items": []}`
- **WHEN** the section is read
- **THEN** the script runs with Hermes' Python in that folder and the read succeeds with no items

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

### Requirement: GitHub pull requests source

A `github_prs` section SHALL list open pull requests through `gh search prs` within `timeout_s`: authored by the user (`author`) and those requesting their review (`review_requested`), as `include` says, minus repositories whose owner is in `exclude_owners`, without duplicates. Each item shows `owner/repo#number` and title, the link, and badges `draft` or `review requested`.

#### Scenario: Authored and review requested

- **GIVEN** `gh` returns one pull request the user authored (a draft) and one where their review is requested
- **WHEN** the section is read
- **THEN** both are items, with badges `draft` and `review requested`

#### Scenario: gh not available

- **GIVEN** no `gh` program on the path
- **WHEN** the section is read
- **THEN** the read fails saying the `gh` CLI was not found

### Requirement: Read-only MCP tool source

An `mcp_tool` section SHALL call `options.tool` (required text) on the Hermes MCP server `options.server` (required text) with `options.args` (a mapping, default empty), in a separate process killed at `timeout_s`. The call SHALL be refused, without calling the tool, unless the server marks the tool read-only (`readOnlyHint: true`).

#### Scenario: Read-only tool

- **GIVEN** a configured server whose tool `get_today` is marked read-only and returns a JSON list of tasks
- **WHEN** the section is read with `options.fields: {title: title, detail: note}`
- **THEN** each task becomes an item with its title and note

#### Scenario: Write-capable tool refused

- **GIVEN** a tool `create_task` that is not marked read-only
- **WHEN** the section is read
- **THEN** the read fails saying the tool is not read-only, and the tool is never called

#### Scenario: Unknown server

- **GIVEN** `options.server` names a server that is not in the Hermes configuration
- **WHEN** the section is read
- **THEN** the read fails saying the MCP server is not configured

### Requirement: MCP tool JSON extraction

The `mcp_tool` source SHALL decode the tool's text result as JSON when the whole text is JSON; otherwise it SHALL decode from the first line that starts with `[` or `{`. A list is the item list. An object needs `options.list_key` naming a list inside it. JSON `null` gives no items; another scalar gives one item with the value as its title. Text with no decodable JSON gives one item per non-empty line.

#### Scenario: Text after a heading

- **GIVEN** a tool result `Tasks for 2026-10-19:\n[{"title": "Study", "note": "SOLID"}]`
- **WHEN** the section is read with `fields: {title: title, detail: note}`
- **THEN** there is one item, title `Study`, detail `SOLID`

#### Scenario: Scalar result

- **GIVEN** a tool result `"nothing scheduled"` (a JSON string)
- **WHEN** the section is read
- **THEN** there is one item titled `nothing scheduled`

#### Scenario: Object without list key

- **GIVEN** a tool result that is a JSON object and no `options.list_key`
- **WHEN** the section is read
- **THEN** the read fails saying the result is an object and `options.list_key` must name its list

#### Scenario: List key not a list

- **GIVEN** `options.list_key: tasks` and a result object whose `tasks` is missing or is not a list
- **WHEN** the section is read
- **THEN** the read fails saying `tasks` is not a list in the result

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

### Requirement: Refresh and cache

The plugin SHALL keep each section's last result in memory, keyed by its id and a hash of its definition (kind, options and limits), and read it again when older than `refresh_minutes` or when asked. A running read with the same key is joined, not repeated. At most four reads run at once. A section whose definition changed starts with no result; a read finishing for an old definition is discarded.

#### Scenario: Fresh result reused

- **GIVEN** a section read 2 minutes ago with `refresh_minutes: 15`
- **WHEN** the page asks for the sections
- **THEN** the cached result is returned and the source does not run

#### Scenario: Concurrent refresh joins

- **GIVEN** a read of section `prs` is running
- **WHEN** a second refresh of `prs` is asked for
- **THEN** both get the same result and the source ran once

#### Scenario: Definition changed

- **GIVEN** section `cmd` was read with `argv: [a]`, and the file now says `argv: [b]`
- **WHEN** the page asks for the sections
- **THEN** `cmd` is read again with `[b]`, and the old result is not shown

### Requirement: Failure log

Each failed read SHALL log one warning line with the section id, the kind and the error message, and never the source's standard output or tool result.

#### Scenario: Output not logged

- **GIVEN** a command that prints `secret-output` and then exits with status 1
- **WHEN** the section is read
- **THEN** one warning names the section and the exit status, and no log line contains `secret-output`

### Requirement: Command line

The plugin SHALL register `hermes day show`, which reads every enabled section now and prints each title, status and items (`--json` prints the results as JSON), and `hermes day check`, which validates the sources file and exits 0 when it is valid, or 2 with the errors.

#### Scenario: Invalid file

- **GIVEN** a sources file with a repeated id
- **WHEN** the user runs `hermes day check`
- **THEN** it prints the error and exits with status 2

#### Scenario: Show as JSON

- **GIVEN** a valid sources file with one `command` section
- **WHEN** the user runs `hermes day show --json`
- **THEN** it prints a JSON list with that section's id, status and items

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

Each window SHALL become an item titled `<label> · <window label>`. The provider name is the `provider` text `hermes usage` reports, else the name asked for, else `provider`; the label is `labels[<that name>]`, else the name. Detail `NN% used` (plus the plan when reported), `time` the reset time with `time_label` `resets`, `progress` the percent used. At or above `warn_percent`: badge `high` and tone `warn`.

#### Scenario: Labelled window

- **GIVEN** `labels: {claude-x: Claude}` and provider `claude-x` reporting window `Current session` at 68% that resets at 16:00, with `warn_percent: 80`
- **WHEN** the section is read
- **THEN** the item is titled `Claude · Current session`, with detail `68% used`, `progress` 68, `time_label` `resets` and that reset time, and no badge or tone

#### Scenario: Window exactly at the warning level

- **GIVEN** provider `openai-codex` with no label reporting window `Weekly` at exactly 80% and `warn_percent: 80`
- **WHEN** the section is read
- **THEN** the item is titled `openai-codex · Weekly`, has the badge `high` and tone `warn`

#### Scenario: No provider name reported

- **GIVEN** `providers: [codex]`, `labels: {codex: Codex}`, and `hermes usage` output without a `provider` field
- **WHEN** the section is read
- **THEN** the items are titled `Codex · <window label>`
