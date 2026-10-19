## MODIFIED Requirements

### Requirement: Page content

A Desktop page "Today" SHALL show the date and every enabled section in file order: its title, items (title, detail, badge, time with its time label, tone, progress), total and note, its status, when it was read, and its error when there is one. Source text SHALL be shown as plain text, never as HTML. A section with no items says so.

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

## ADDED Requirements

### Requirement: Tone and progress on the page

The page SHALL show an item's tone as the colour of its badge (`good` success, `warn` warning, `bad` destructive, `muted` muted) or, with no badge, as a dot of that colour before the title. `progress` SHALL be a bar under the title filled to that percent, in the tone's colour (the theme's primary colour when there is no tone). `time_label` is written before the time.

#### Scenario: Usage window

- **GIVEN** an item `Claude · Current session` with `progress` 68, tone `warn`, `time_label` `resets` and a time 40 minutes ahead
- **WHEN** the page shows it
- **THEN** a bar under the title is filled to 68% in the warning colour, and the time reads `resets in 40 min`

#### Scenario: Empty bar and no tone

- **GIVEN** an item with `progress` 0 and no tone, badge or time
- **WHEN** the page shows it
- **THEN** an empty bar is drawn in the primary colour, and there is no dot and no time
