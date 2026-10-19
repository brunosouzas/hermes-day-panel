# Spec Delta

## Purpose

The Hermes Desktop page "Today" that shows every enabled section of the sources file with its items, status and age, refreshes them, and lets the user merge a pull request after a preview and an explicit confirmation when the user's sources file allows it.

## ADDED Requirements

### Requirement: Page content

A Desktop page "Today" SHALL show the date and every enabled section in file order: its title, items (title, detail, badge, time), total and note, its status, when it was read, and its error when there is one. Source text SHALL be shown as plain text, never as HTML. A section with no items says so.

#### Scenario: Sections shown

- **GIVEN** a sources file with sections `prs` (2 items) and `usage` (status `error`)
- **WHEN** the user opens the page
- **THEN** both sections are shown in that order: `prs` with its 2 items, `usage` with its error

#### Scenario: Markup in source text

- **GIVEN** an item title `<img src=x onerror=alert(1)>`
- **WHEN** the page shows the item
- **THEN** the characters are displayed as text and no element is created

#### Scenario: Invalid sources file

- **GIVEN** a sources file that fails validation
- **WHEN** the user opens the page
- **THEN** the page shows the validation errors and no sections

### Requirement: Opening links

The page SHALL open an item's link only when it is an absolute http(s) URL, in the system browser. An item without a valid link shows no link control.

#### Scenario: Item without a link

- **GIVEN** an item with no `url`
- **WHEN** the page shows it
- **THEN** its title is plain text and nothing on it navigates

### Requirement: Refreshing

The page SHALL ask for the sections when it opens and every 60 seconds while it is open; the backend reads only sections whose results are older than their interval. A refresh control on each section and one for the whole page force a read. Routes take a section id, never a path or a program; an id not among the enabled sections answers 404.

#### Scenario: Refresh one section

- **WHEN** the user presses refresh on section `prs`
- **THEN** only `prs` is read again, and the page shows its new time

#### Scenario: Unknown section id

- **WHEN** the backend is asked to refresh section `../etc`
- **THEN** it answers 404 and nothing runs

### Requirement: Merge setting

A `github_prs` section MAY set `options.merge` to a mapping with `enabled` (boolean, default false) and `method` (`squash`, `merge` or `rebase`, default `squash`). Only when `enabled` is true SHALL the page offer "Merge…" on its non-draft items, and the backend accept a merge preview for that section; otherwise a preview answers 409.

#### Scenario: Merge off by default

- **GIVEN** a `github_prs` section without `options.merge`
- **WHEN** the page shows its items
- **THEN** no item offers "Merge…", and a preview request for that section answers 409

### Requirement: Merge preview

A merge preview for one item SHALL read the pull request now through `gh` and return repository, number, title, base branch, head commit and method, with a token bound to the section, the pull request, the head commit and the method, valid once for 120 seconds. A draft or closed pull request is refused with 409. The page shows the preview and asks for an explicit confirmation; cancelling sends nothing.

#### Scenario: Draft pull request

- **GIVEN** merge is enabled and the pull request is a draft
- **WHEN** a preview is asked for
- **THEN** it answers 409 with "draft pull requests are not merged"

#### Scenario: Preview shown and cancelled

- **GIVEN** a preview of `owner/repo#7`
- **WHEN** the page shows it and the user presses Cancel
- **THEN** the dialog closes and no confirm request is sent

### Requirement: Merge confirmation

Confirming SHALL consume the token, re-read the sources file and check that the section still exists, is enabled, is `github_prs`, has merge enabled and the same method; then run `gh pr merge` with that method and `--match-head-commit <previewed head>`, keeping the branch. Any failed check answers 409 without running `gh` (409, not the 404 of refresh routes). One merge runs at a time; another confirm meanwhile gets 409.

#### Scenario: Confirmed merge

- **GIVEN** a preview of `owner/repo#7` with head `abc123`, and a `gh` that merges successfully
- **WHEN** the user confirms within 120 seconds
- **THEN** `gh pr merge` runs once for that pull request with `--squash --match-head-commit abc123`, and the page shows it merged

#### Scenario: Token used twice

- **GIVEN** a token that was already confirmed
- **WHEN** it is confirmed again
- **THEN** the answer is 409 and `gh` does not run

#### Scenario: Token expired

- **GIVEN** a preview older than 120 seconds
- **WHEN** it is confirmed
- **THEN** the answer is 409 and `gh` does not run

#### Scenario: Section disabled after the preview

- **GIVEN** a preview, after which the sources file sets `enabled: false` for that section
- **WHEN** the user confirms
- **THEN** the answer is 409 and `gh` does not run

#### Scenario: Merge turned off after the preview

- **GIVEN** a preview, after which the sources file sets `merge.enabled: false` for that section
- **WHEN** the user confirms
- **THEN** the answer is 409, `gh` does not run, and the token cannot be used again

### Requirement: Merge failure

When `gh pr merge` fails (head moved, checks pending, no permission, network), the backend SHALL return its exit status and last line of standard error, and the page SHALL show them. The token stays used; another attempt needs a new preview.

#### Scenario: Head moved

- **GIVEN** a new commit was pushed after the preview, so `gh` exits non-zero
- **WHEN** the user confirms
- **THEN** the page shows `gh`'s error, and confirming the same token again answers 409
