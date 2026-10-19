# Spec Delta

## Purpose

The sources behind the Today page: a user-owned YAML file that lists sections in order, four read-only source kinds (command, GitHub pull requests, read-only MCP tool, AI usage windows), their limits, how results are refreshed and cached, and the CLI that shows and checks them.

## ADDED Requirements

### Requirement: Sources file

The plugin SHALL read the sources file named by the `sources_file` setting, or `$HERMES_HOME/day-panel/sources.yaml` when the setting is empty, on every read of the page or CLI. The file is a mapping with a `sections` list. Each section has `id` (lowercase letters, digits and hyphens, unique), `kind`, and optional `title`, `enabled` (default true), `refresh_minutes` and `options`.

#### Scenario: Sections in file order

- **GIVEN** a sources file with sections `prs`, `cards` and `usage`, where `cards` has `enabled: false`
- **WHEN** the sections are listed
- **THEN** `prs` and `usage` are returned, in that order, and `cards` is not

#### Scenario: Missing file

- **GIVEN** no file at the configured path
- **WHEN** the sections are listed
- **THEN** the result is a configuration error naming the path, and no source runs

### Requirement: Sources file validation

The plugin SHALL refuse a sources file that is not valid YAML, has more than 20 sections, repeats an id, names an unknown kind, an unknown option or a value outside its bounds. The error names the section and the rule broken. A refused file runs no source.

#### Scenario: Unknown kind

- **GIVEN** a section `id: cal`, `kind: calendar`
- **WHEN** the file is validated
- **THEN** the error says that section `cal` has an unknown kind and lists the four allowed kinds

#### Scenario: Value out of bounds

- **GIVEN** a section with `refresh_minutes: 0`
- **WHEN** the file is validated
- **THEN** the error says `refresh_minutes` must be between 1 and 1440

### Requirement: Section result

Every source kind SHALL produce a section result: `items` (each with `title`, optional `url`, `detail`, `badge` and `time`), optional `total` and `note`, the status (`ok`, `error` or `stale`), when it was read and how long the read took. At most `max_items` items are kept (1–50, default 10), and each text field is cut to 300 characters. A `url` that is not absolute http(s) is dropped.

#### Scenario: Too many items

- **GIVEN** a source that returns 80 items and a section with `max_items: 5`
- **WHEN** the section is read
- **THEN** the result has 5 items and `total` is 80

#### Scenario: Unsafe link

- **GIVEN** a source item with `url: javascript:alert(1)`
- **WHEN** the section is read
- **THEN** the item is kept without a `url`

### Requirement: Command source

A `command` section SHALL run `options.argv` (a non-empty list of strings, the program first) without a shell, with no standard input, and read one JSON object from standard output with `items` and optional `total` and `note`. Item fields are as in the section result. `options.timeout_s` is 1–120 (default 30).

#### Scenario: Valid output

- **GIVEN** a command that prints `{"items": [{"title": "Card 42", "url": "https://example.com/42"}], "total": 1}`
- **WHEN** the section is read
- **THEN** the result is `ok` with that one item

#### Scenario: Command fails

- **GIVEN** a command that exits with status 2 and prints `boom` on standard error
- **WHEN** the section is read
- **THEN** the result is `error` with a message containing the exit status and `boom`

### Requirement: Command output limits

A `command` read SHALL fail with an error when the program runs past its timeout (the program is killed), writes more than 256 KiB to standard output, or prints something that is not a JSON object with an `items` list. An item without a text `title` is dropped.

#### Scenario: Timeout

- **GIVEN** a command that sleeps past `timeout_s: 1`
- **WHEN** the section is read
- **THEN** the program is killed and the result is `error` saying it timed out after 1 s

#### Scenario: Not JSON

- **GIVEN** a command that prints `hello`
- **WHEN** the section is read
- **THEN** the result is `error` saying the output is not the expected JSON

### Requirement: GitHub pull requests source

A `github_prs` section SHALL list open pull requests through the `gh` CLI: those the user authored and those where their review is requested (`options.include`, either or both, default both), minus repositories whose owner is in `options.exclude_owners`. Each item shows `owner/repo#number`, the title, the link, and a `draft` or `review requested` badge.

#### Scenario: Authored and review requested

- **GIVEN** `gh` returns one pull request the user authored (a draft) and one where their review is requested
- **WHEN** the section is read
- **THEN** both are items, with badges `draft` and `review requested`

#### Scenario: gh not available

- **GIVEN** no `gh` program on the path
- **WHEN** the section is read
- **THEN** the result is `error` saying the `gh` CLI was not found

### Requirement: Read-only MCP tool source

An `mcp_tool` section SHALL call `options.tool` on the Hermes MCP server `options.server` with `options.args` (a mapping, default empty), in a separate process limited by `options.timeout_s` (1–120, default 30). The call SHALL be refused, without calling the tool, unless the server reports the tool as read-only (`readOnlyHint: true`).

#### Scenario: Read-only tool

- **GIVEN** a configured server whose tool `get_today` is marked read-only and returns a JSON list of tasks
- **WHEN** the section is read with `options.fields: {title: title, detail: note}`
- **THEN** each task becomes an item with its title and note

#### Scenario: Write-capable tool refused

- **GIVEN** a tool `create_task` that is not marked read-only
- **WHEN** the section is read
- **THEN** the result is `error` saying the tool is not read-only, and the tool is never called

### Requirement: MCP tool result mapping

The `mcp_tool` source SHALL take the first JSON array or object in the tool's text result. With an object, `options.list_key` names the list inside it. Each element becomes an item through `options.fields`, mapping `title`, `detail`, `badge`, `time` and `url` to element keys (`title` required). A result with no JSON shows each non-empty line as an item.

#### Scenario: Text after a heading

- **GIVEN** a tool result `Tasks for 2026-10-19:\n[{"title": "Study", "note": "SOLID"}]`
- **WHEN** the section is read with `fields: {title: title, detail: note}`
- **THEN** there is one item, title `Study`, detail `SOLID`

#### Scenario: Unknown server

- **GIVEN** `options.server` names a server that is not in the Hermes configuration
- **WHEN** the section is read
- **THEN** the result is `error` saying the MCP server is not configured

### Requirement: AI usage source

An `ai_usage` section SHALL run `hermes usage --json --provider <name>` for each name in `options.providers` (default: one run without `--provider`, the configured provider). Each limit window becomes an item: the provider's title and window label, `NN% used` and the reset time. A window at or above `options.warn_percent` (1–100, default 80) gets the badge `high`.

#### Scenario: Two providers

- **GIVEN** providers `anthropic` and `openai-codex`, each reporting two windows, one of them at 85% used
- **WHEN** the section is read
- **THEN** there are four items, and only the 85% window has the badge `high`

#### Scenario: One provider fails

- **GIVEN** providers `a` and `b`, where `hermes usage` for `b` exits with status 1
- **WHEN** the section is read
- **THEN** `a`'s windows are items and the `note` says provider `b` could not be read

### Requirement: Refresh and cache

The plugin SHALL keep each section's last result in memory and read a section again when its result is older than `refresh_minutes` (default 15), or when a refresh is asked for. A read already running for a section is joined, never repeated. At most four sections are read at once. A failed read keeps the previous items and marks the section `stale`.

#### Scenario: Fresh result reused

- **GIVEN** a section read 2 minutes ago with `refresh_minutes: 15`
- **WHEN** the page asks for the sections
- **THEN** the cached result is returned and the source does not run

#### Scenario: Failure after success

- **GIVEN** a section whose last read returned 3 items
- **WHEN** the next read fails
- **THEN** the section is `stale`, still shows the 3 items, and shows the error

### Requirement: Command line

The plugin SHALL register `hermes day show`, which reads every enabled section now and prints each title, status and items (`--json` prints the results as JSON), and `hermes day check`, which validates the sources file and exits 0 when it is valid, or 2 with the errors.

#### Scenario: Invalid file

- **GIVEN** a sources file with a repeated id
- **WHEN** the user runs `hermes day check`
- **THEN** it prints the error and exits with status 2
