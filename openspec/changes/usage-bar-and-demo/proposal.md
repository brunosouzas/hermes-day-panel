## Why

The AI usage section is hard to read. Each item shows the provider's internal name (for example `claude-subscription-directsdk-experimental · Current session`), and a bare time such as "in 1 h" does not say it is the reset. Nothing in an item can carry a colour or a fill level either. A pipeline that failed looks the same as one that passed, and a usage window at 90% looks the same as one at 5%.

The plugin is about to go to the Hermes plugin catalog. A first-time user also needs a way to see the page working before writing any source, and the README needs a screenshot that holds no personal data.

## What Changes

- Items get three optional fields that any source can set:
  - `tone`: `good`, `warn`, `bad` or `muted`;
  - `progress`: a number from 0 to 100;
  - `time_label`: a short word shown before the time, for example "resets in 1 h".
- Invalid values are dropped and the item is kept.
- `mcp_tool` can map these three fields like the others. `progress` must be a number.
- `ai_usage`:
  - New option `labels` maps a provider name to the text shown, for example `{claude-subscription-directsdk-experimental: Claude}`.
  - Each window item carries `progress` (the percent used), `time_label` "resets" and tone `warn` at or above `warn_percent`.
  - The badge `high` stays.
- The page:
  - colours a badge by its item's tone;
  - shows a coloured dot before the title when an item has a tone but no badge;
  - draws a bar under the title for `progress`;
  - writes `time_label` before the time.
- `examples/demo/`: a sources file and a script that run with no login, network or MCP server and show every kind of item. The README's "Try it" points at it, and its screenshot comes from it.

## Out of scope

- Other colours, icons or free CSS colours in items.
- A chart or history of usage over time.
- Changing `github_prs`, which has no tone source.
- The catalog submission itself, which is a separate pull request to the Hermes repository after this merges.
- Bruno's own sources. His pipelines script and `labels` live in his private repository.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `day-sources`: the item shape (`tone`, `progress`, `time_label`), command output limits, MCP field mapping, the `ai_usage` options and items.
- `today-page`: how tone, progress and time label are shown.

## Implicit requirements

1. **Errors and invalid input:** a wrong `tone` or `progress` is dropped from the item, not an error. A wrong `labels` value fails file validation with the section named, like every other option.
2. **Limits:** `time_label` is cut to 40 characters and each `labels` value is 1–40 characters. `progress` outside 0–100 is dropped, not clamped.
3. **Repetition and idempotency:** n/a. Reads are unchanged, and the new fields are part of the same cached result.
4. **Concurrency:** n/a. No new reads or shared state.
5. **Security:** the new fields are shown as text or as a CSS width computed from a validated number. No source value reaches markup or a style string unchecked.
6. **Logs and observability:** n/a. Nothing new is logged.

## Documentation

- README:
  - item fields in the `command` and `mcp_tool` sections;
  - `ai_usage` `labels`;
  - "The page" (tone, bar, time label);
  - a new "Try it" section with the demo and the screenshot.
- `examples/demo/README` lines inside `sources.yaml` comments.
- Brain: `10-personal/projects/hermes-plugins/_index.md`, after merge.
