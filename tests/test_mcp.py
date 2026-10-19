"""Spec day-sources: the read-only MCP tool source, its child process and its result mapping."""

from __future__ import annotations

import io
import json
import sys
import time

import pytest

from day_panel import dp_mcp_child, dp_sources
from day_panel.dp_sources import ReadError
from helpers import script, section


class FakeHermes:
    """Hermes' MCP entry points: one configured server with a read-only and a write tool."""

    def __init__(self, result='[]'):
        self.result, self.dispatched = result, []

    def entry(self):
        tools = {"mcp__srv__get_today": True, "mcp__srv__create_task": False}
        return {
            "configured": lambda: {"srv": {"url": "https://x"}},
            "discover": lambda names: None,
            "tool_name": lambda server, tool: f"mcp__{server}__{tool}",
            "exists": lambda name: name in tools,
            "read_only": lambda server, tool: tools.get(f"mcp__{server}__{tool}") is True,
            "dispatch": self.dispatch,
        }

    def dispatch(self, name, args):
        self.dispatched.append((name, args))
        return json.dumps({"result": self.result})


def run_child(fake, server="srv", tool="get_today", args=None):
    out = io.StringIO()
    stdin = io.StringIO(json.dumps({"server": server, "tool": tool, "args": args or {}}))
    real = sys.stdout
    sys.stdout = out
    try:
        dp_mcp_child.main(stdin=stdin, entry=fake.entry())
    finally:
        sys.stdout = real
    line = out.getvalue().strip().splitlines()[-1]
    assert line.startswith(dp_mcp_child.RESULT_MARK)
    return json.loads(line[len(dp_mcp_child.RESULT_MARK):])


def through_child(fake):
    """A call_mcp_child stand-in that runs the child in-process with the fake Hermes."""
    def call(server, tool, args, timeout):
        answer = run_child(fake, server, tool, args)
        if answer["ok"]:
            return answer["text"]
        raise ReadError(answer["error"])
    return call


def mcp_section(tmp_path, **options):
    opts = {"server": "srv", "tool": "get_today", **options}
    return section(tmp_path, kind="mcp_tool", options=opts)


def test_read_only_tool(tmp_path):
    fake = FakeHermes(json.dumps([{"title": "Study", "note": "SOLID"}, {"title": "Gym", "note": ""}]))
    s = mcp_section(tmp_path, args={"timezone": "Europe/London"}, fields={"title": "title", "detail": "note"})
    out = dp_sources.read_mcp_tool(s, call=through_child(fake))
    assert out["items"] == [{"title": "Study", "detail": "SOLID"}, {"title": "Gym"}]
    assert fake.dispatched == [("mcp__srv__get_today", {"timezone": "Europe/London"})]


def test_write_tool_refused(tmp_path):
    fake = FakeHermes()
    with pytest.raises(ReadError, match="not read-only"):
        dp_sources.read_mcp_tool(mcp_section(tmp_path, tool="create_task"), call=through_child(fake))
    assert fake.dispatched == []


def test_unknown_server(tmp_path):
    fake = FakeHermes()
    s = section(tmp_path, kind="mcp_tool", options={"server": "nope", "tool": "get_today"})
    with pytest.raises(ReadError, match="'nope' is not configured"):
        dp_sources.read_mcp_tool(s, call=through_child(fake))


def test_text_after_heading(tmp_path):
    text = 'Tasks for 2026-10-19:\n[{"title": "Study", "note": "SOLID"}]'
    out = dp_sources.map_mcp_result(text, {"fields": {"title": "title", "detail": "note"}}, 10)
    assert out["items"] == [{"title": "Study", "detail": "SOLID"}]


def test_scalar_result():
    assert dp_sources.map_mcp_result('"nothing scheduled"', {}, 10)["items"] == [{"title": "nothing scheduled"}]
    assert dp_sources.map_mcp_result("null", {}, 10)["items"] == []


def test_plain_text_lines():
    assert [i["title"] for i in dp_sources.map_mcp_result("one\n\ntwo\n", {}, 10)["items"]] == ["one", "two"]


def test_object_without_list_key():
    with pytest.raises(ReadError, match="set options.list_key"):
        dp_sources.map_mcp_result('{"tasks": []}', {}, 10)


def test_list_key_not_a_list():
    with pytest.raises(ReadError, match="tasks is not a list"):
        dp_sources.map_mcp_result('{"tasks": 3}', {"list_key": "tasks"}, 10)
    with pytest.raises(ReadError, match="tasks is not a list"):
        dp_sources.map_mcp_result('{"other": []}', {"list_key": "tasks"}, 10)
    out = dp_sources.map_mcp_result('{"tasks": [{"title": "a"}]}', {"list_key": "tasks"}, 10)
    assert out["items"] == [{"title": "a"}]


def test_element_without_title():
    data = json.dumps([{"title": "a"}, {"note": "x"}, {"title": "c"}])
    out = dp_sources.map_mcp_result(data, {"fields": {"title": "title"}}, 10)
    assert [i["title"] for i in out["items"]] == ["a", "c"] and out["note"] == "1 entry skipped (no title)"


def test_mcp_child_timeout(tmp_path):
    sleeper = script(tmp_path, "import time; time.sleep(30)", name="child.py")
    started = time.monotonic()
    with pytest.raises(ReadError, match="timed out after 1 s"):
        dp_sources.call_mcp_child("srv", "t", {}, 1, child=[sys.executable, str(sleeper)])
    assert time.monotonic() - started < 10


def test_mcp_child_protocol_through_a_real_process(tmp_path):
    """The parent finds the result line among other output a real child prints."""
    child = script(tmp_path, """
        import json, sys
        req = json.loads(sys.stdin.read())
        print("noise from a library")
        print("DAY_PANEL_RESULT " + json.dumps({"ok": True, "text": req["tool"] + ":" + json.dumps(req["args"])}))
    """, name="child.py")
    text = dp_sources.call_mcp_child("srv", "get_today", {"a": 1}, 10, child=[sys.executable, str(child)])
    assert text == 'get_today:{"a": 1}'
