## Decisions

- **`time_label` instead of folding the reset into `detail`.** The backend caches results for up to `refresh_minutes`. A "resets in 1 h" written there would go stale, while the page already turns `time` into a live relative time. A short label in front ("resets", "due", "updated") keeps the time live and works for any source.
- **`tone` is a closed set of four words, not a colour.** Sources stay independent of the theme. The page maps each word to the Desktop's own success, warning, destructive and muted styles, so a light or dark theme keeps working and no source value reaches CSS.
- **`labels` is keyed by the provider name that `hermes usage` reports** (its `provider` field). This also covers a section with no `providers` list, where the name is the configured provider's.
- **Compatibility.** Every new field and option is optional. Existing sources files, command and MCP producers, and the page's existing data keep working with no migration. The only visible change for an existing `ai_usage` section is the added bar and "resets" label; titles change only when `labels` is set or the reported name differs from the one asked for.
- **`progress` is dropped outside 0–100 instead of clamped.** A value out of range means the source is wrong, and showing 100% for 140 would hide that.
