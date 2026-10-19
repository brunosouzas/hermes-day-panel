# Spec Delta

## Purpose

The Hermes Desktop page "Today" that shows every enabled section of the sources file with its items, status and age, refreshes them, and lets the user merge a pull request after a preview and an explicit confirmation when the user's sources file allows it.

## ADDED Requirements

### Requirement: Page content

A Desktop page "Today" SHALL show the date and every enabled section in file order: its title, items (title, detail, badge, time), total and note, its status, when it was read, and its error when there is one. Source text SHALL be shown as plain text, never as HTML. A section with no items says so.

#### Scenario: Sections shown

- **GIVEN** a sources file with sections `prs` (2 items) and `usage` (an error)
- **WHEN** the user opens the page
- **THEN** both sections are shown in that order: `prs` with its 2 items, `usage` with its error

#### Scenario: Markup in source text

- **GIVEN** an item title `<img src=x onerror=alert(1)>`
- **WHEN** the page shows the item
- **THEN** the characters are displayed as text and no element is created

#### Scenario: Invalid sources file

- **GIVEN** a sources file that fails validation
- **WHEN** the user opens the page
- **THEN** the page shows the validation error and no sections

### Requirement: Opening links

The page SHALL open an item's link only when it is an absolute http(s) URL, in the system browser. An item without a valid link shows no link control.

#### Scenario: Item without a link

- **GIVEN** an item with no `url`
- **WHEN** the page shows it
- **THEN** its title is plain text and nothing on it navigates

### Requirement: Refreshing

The page SHALL ask for the sections when it opens and every 60 seconds while it is open; the backend reads only sections whose results are older than their interval. A refresh control on each section and one for the whole page force a read. Routes take a section id, never a path or a program.

#### Scenario: Refresh one section

- **WHEN** the user presses refresh on section `prs`
- **THEN** only `prs` is read again, and the page shows its new time

#### Scenario: Unknown section id

- **WHEN** the backend is asked to refresh section `../etc`
- **THEN** it answers 404 and nothing runs

### Requirement: Merge preview

When a `github_prs` section has `options.merge.enabled: true` (default false), each non-draft item SHALL offer "Merge…". A preview reads the pull request now and shows repository, number, title, base branch, head commit and merge method (`options.merge.method`: `squash`, `merge` or `rebase`, default `squash`), with a confirmation token valid once, for 120 seconds.

#### Scenario: Merge off by default

- **GIVEN** a `github_prs` section without `options.merge`
- **WHEN** the page shows its items
- **THEN** no item offers "Merge…", and a preview request for that section answers 409

#### Scenario: Draft pull request

- **GIVEN** merge is enabled and the pull request is a draft
- **WHEN** a preview is asked for
- **THEN** it is refused with "draft pull requests are not merged"

### Requirement: Merge confirmation

Confirming a valid token SHALL run `gh pr merge` with the previewed method and `--match-head-commit <previewed head>`, without deleting the branch, and show the outcome. An expired, unknown or used token, or a merge already running, is refused without running anything.

#### Scenario: Confirmed merge

- **GIVEN** a preview of `owner/repo#7` with head `abc123`
- **WHEN** the user confirms within 120 seconds
- **THEN** `gh pr merge` runs once for that pull request with `--squash --match-head-commit abc123`, and the page shows it merged

#### Scenario: Token used twice

- **GIVEN** a token that was already confirmed
- **WHEN** it is confirmed again
- **THEN** the answer is 409 and `gh` does not run

#### Scenario: Head moved

- **GIVEN** a new commit was pushed after the preview
- **WHEN** the user confirms
- **THEN** `gh` refuses the merge, and the page shows its error
