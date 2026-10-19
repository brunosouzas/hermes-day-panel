"""Spec day-sources: `hermes day check` and `hermes day show`."""

from __future__ import annotations

import argparse
import json

from day_panel import dp_cli
from day_panel.dp_panel import Panel
from helpers import write_sources


def run(argv, path, reader=None):
    parser = argparse.ArgumentParser()
    dp_cli.setup_parser(parser)
    args = parser.parse_args(argv)
    panel = Panel(reader or (lambda s: {"items": [{"title": "Card 42", "badge": "new"}], "total": 1}))
    return dp_cli.make_handler(lambda: path, lambda: panel)(args)


def test_check_invalid_file(tmp_path, capsys):
    path = write_sources(tmp_path, [{"id": "a", "kind": "ai_usage"}, {"id": "a", "kind": "ai_usage"}])
    assert run(["check"], path) == 2
    assert "section a: id appears twice" in capsys.readouterr().out


def test_check_valid_file(tmp_path, capsys):
    path = write_sources(tmp_path, [{"id": "a", "kind": "ai_usage"}])
    assert run(["check"], path) == 0 and "ok:" in capsys.readouterr().out


def test_show_json(tmp_path, capsys):
    path = write_sources(tmp_path, [{"id": "cmd", "kind": "command", "options": {"argv": ["x"]}}])
    assert run(["show", "--json"], path) == 0
    [view] = json.loads(capsys.readouterr().out)
    assert view["id"] == "cmd" and view["status"] == "ok" and view["items"] == [{"title": "Card 42", "badge": "new"}]


def test_show_text(tmp_path, capsys):
    path = write_sources(tmp_path, [{"id": "cmd", "kind": "command", "title": "Cards", "options": {"argv": ["x"]}}])
    assert run(["show"], path) == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["## Cards [ok]", "- Card 42 (new)"]
