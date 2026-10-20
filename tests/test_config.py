"""Spec day-sources: the sources file, its fields, kinds, options and validation."""

from __future__ import annotations

import pytest

from day_panel import dp_config
from helpers import write_sources


def errors_of(tmp_path, sections):
    with pytest.raises(dp_config.ConfigError) as info:
        dp_config.load(write_sources(tmp_path, sections))
    return info.value.errors


def test_sections_in_file_order(tmp_path):
    path = write_sources(tmp_path, [
        {"id": "prs", "kind": "github_prs"},
        {"id": "cards", "kind": "command", "enabled": False, "options": {"argv": ["true"]}},
        {"id": "usage", "kind": "ai_usage"},
    ])
    assert [s.id for s in dp_config.load(path).enabled] == ["prs", "usage"]


def test_missing_file(tmp_path):
    with pytest.raises(dp_config.ConfigError) as info:
        dp_config.load(tmp_path / "nope.yaml")
    assert str(tmp_path / "nope.yaml") in info.value.errors[0]


def test_defaults_applied(tmp_path):
    s = dp_config.load(write_sources(tmp_path, [{"id": "usage", "kind": "ai_usage"}])).sections[0]
    assert (s.title, s.enabled, s.refresh_minutes, s.max_items, s.timeout_s) == ("usage", True, 15, 10, 30)
    assert s.options == {"providers": [], "warn_percent": 80, "labels": {}}


def test_unknown_kind(tmp_path):
    [error] = errors_of(tmp_path, [{"id": "cal", "kind": "calendar"}])
    assert error.startswith("section cal:") and "unknown kind" in error
    assert all(k in error for k in dp_config.KINDS)


def test_value_out_of_bounds(tmp_path):
    [error] = errors_of(tmp_path, [{"id": "u", "kind": "ai_usage", "refresh_minutes": 0}])
    assert "refresh_minutes must be between 1 and 1440" in error


def test_label_that_is_not_text(tmp_path):
    errors = errors_of(tmp_path, [{"id": "usage", "kind": "ai_usage", "options": {"labels": {"openai-codex": 5}}}])
    assert any("usage" in e and "labels must map provider names to text of 1 to 40 characters" in e for e in errors)
    assert errors_of(tmp_path, [{"id": "usage", "kind": "ai_usage", "options": {"labels": {"x": "y" * 41}}}])
    ok = dp_config.load(write_sources(tmp_path, [{"id": "usage", "kind": "ai_usage",
                                                 "options": {"labels": {"claude-x": " Claude "}}}]))
    assert ok.sections[0].options["labels"] == {"claude-x": "Claude"}


def test_unknown_option(tmp_path):
    [error] = errors_of(tmp_path, [{"id": "cmd", "kind": "command", "options": {"argv": ["date"], "shell": True}}])
    assert error.startswith("section cmd:") and "unknown option 'shell'" in error and "argv" in error


@pytest.mark.parametrize("sections, needle", [
    ([{"id": "a", "kind": "ai_usage"}, {"id": "a", "kind": "ai_usage"}], "id appears twice"),
    ([{"id": "Bad_id", "kind": "ai_usage"}], "id must be"),
    ([{"id": "a", "kind": "ai_usage", "extra": 1}], "unknown key 'extra'"),
    ([{"id": "a", "kind": "ai_usage", "enabled": "yes"}], "enabled must be true or false"),
    ([{"id": "a", "kind": "ai_usage", "max_items": 51}], "max_items must be between 1 and 50"),
    ([{"id": "a", "kind": "ai_usage", "timeout_s": True}], "timeout_s must be a whole number"),
    ([{"id": "a", "kind": "ai_usage", "title": ""}], "title must be non-empty text"),
    ([{"id": "a", "kind": "ai_usage", "options": None}], "options must be a mapping"),
    ([{"id": "a", "kind": "github_prs", "options": None}], "options must be a mapping"),
    ([{"id": "a", "kind": "command"}], "option argv is required"),
    ([{"id": "a", "kind": "command", "options": {"argv": []}}], "argv must have between 1 and 50"),
    ([{"id": "a", "kind": "command", "options": {"argv": "date"}}], "argv must be a list"),
    ([{"id": "a", "kind": "command", "options": {"argv": ["date", 3]}}], "argv must be a list of strings"),
    ([{"id": "a", "kind": "github_prs", "options": {"include": ["mine"]}}], "mine not allowed"),
    ([{"id": "a", "kind": "github_prs", "options": {"merge": {"enabled": "on"}}}], "merge.enabled must be true or false"),
    ([{"id": "a", "kind": "github_prs", "options": {"merge": {"method": "ff"}}}], "merge.method must be one of"),
    ([{"id": "a", "kind": "github_prs", "options": {"merge": {"delete": True}}}], "unknown merge key 'delete'"),
    ([{"id": "a", "kind": "mcp_tool", "options": {"server": "s"}}], "option tool is required"),
    ([{"id": "a", "kind": "mcp_tool", "options": {"server": "s", "tool": "t", "fields": {"detail": "note"}}}],
     "fields must map title"),
    ([{"id": "a", "kind": "mcp_tool", "options": {"server": "s", "tool": "t", "fields": {"title": "t", "x": "y"}}}],
     "unknown fields key 'x'"),
    ([{"id": "a", "kind": "mcp_tool", "options": {"server": "s", "tool": "t", "args": []}}], "args must be a mapping"),
    ([{"id": "a", "kind": "ai_usage", "options": {"providers": ["p"] * 11}}], "providers must have between 0 and 10"),
    ([{"id": "a", "kind": "ai_usage", "options": {"warn_percent": 101}}], "warn_percent must be between 1 and 100"),
])
def test_validation_rules(tmp_path, sections, needle):
    assert any(needle in e for e in errors_of(tmp_path, sections)), errors_of(tmp_path, sections)


def test_argv_later_arguments_may_be_empty(tmp_path):
    s = dp_config.load(write_sources(tmp_path, [{"id": "c", "kind": "command", "options": {"argv": ["echo", "", " "]}}])).sections[0]
    assert s.options["argv"] == ["echo", "", " "]
    assert "argv must start with a program name" in errors_of(tmp_path, [{"id": "c", "kind": "command", "options": {"argv": [" "]}}])[0]


def test_section_limit_and_top_level(tmp_path):
    many = [{"id": f"s{i}", "kind": "ai_usage"} for i in range(21)]
    assert "at most 20 sections" in errors_of(tmp_path, many)[0]
    path = tmp_path / "x.yaml"
    path.write_text("sections: []\nother: 1\n")
    with pytest.raises(dp_config.ConfigError, match="unknown top-level key 'other'"):
        dp_config.load(path)
    path.write_text("sections: [\n")
    with pytest.raises(dp_config.ConfigError, match="not valid YAML"):
        dp_config.load(path)


def test_yaml_follows_the_hermes_policy(tmp_path):
    path = tmp_path / "x.yaml"
    path.write_text("sections: []\nsections: []\n", encoding="utf-8")
    with pytest.raises(dp_config.ConfigError, match=r"x\.yaml is not valid YAML \(line 2\)"):
        dp_config.load(path)
    path.write_text("sections:\n  - id: c\n    kind: ai_usage\n    enabled: n\n", encoding="utf-8")
    assert dp_config.load(path).sections[0].enabled is False


def test_definition_key_changes_with_the_definition(tmp_path):
    a = dp_config.parse({"sections": [{"id": "c", "kind": "command", "options": {"argv": ["a"]}}]}, tmp_path / "f")
    b = dp_config.parse({"sections": [{"id": "c", "kind": "command", "options": {"argv": ["b"]}}]}, tmp_path / "f")
    c = dp_config.parse({"sections": [{"id": "c", "kind": "command", "title": "New", "options": {"argv": ["a"]}}]},
                        tmp_path / "f")
    assert a.sections[0].key != b.sections[0].key and a.sections[0].key == c.sections[0].key


def test_sources_path_setting(tmp_path):
    assert dp_config.sources_path("", tmp_path) == tmp_path / "day-panel" / "sources.yaml"
    assert dp_config.sources_path("$HERMES_HOME/x.yaml", tmp_path) == tmp_path / "x.yaml"
