"""The README documents every section field, kind and option the code accepts."""

from __future__ import annotations

from pathlib import Path

from day_panel import dp_config

README = (Path(__file__).resolve().parent.parent / "README.md").read_text(encoding="utf-8")


def test_every_option_documented():
    names = set(dp_config.SECTION_KEYS) | set(dp_config.KINDS) | set(dp_config.MERGE_METHODS) | set(dp_config.PR_INCLUDE)
    for options in dp_config.KIND_OPTION_NAMES.values():
        names |= set(options)
    names |= {"sources_file", "{python}", "readOnlyHint"}
    missing = sorted(n for n in names if f"`{n}`" not in README)
    assert missing == []


def test_limits_documented():
    for name, (default, lo, hi) in dp_config.LIMITS.items():
        row = next(line for line in README.splitlines() if line.startswith(f"| `{name}` |"))
        assert str(default) in row and f"{lo}-{hi}" in row
