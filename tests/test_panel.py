"""Spec day-sources: refresh and cache, section status and the failure log."""

from __future__ import annotations

import logging
import sys
import threading

from day_panel import dp_config, dp_sources
from day_panel.dp_panel import Panel
from day_panel.dp_sources import ReadError
from helpers import Clock, py, script


def sources(tmp_path, *sections):
    return dp_config.parse({"sections": list(sections)}, tmp_path / "sources.yaml")


def cmd(sid="cmd", argv=("a",), **raw):
    return {"id": sid, "kind": "command", "options": {"argv": list(argv)}, **raw}


class Reader:
    def __init__(self):
        self.calls, self.answers = [], {}

    def __call__(self, section):
        self.calls.append((section.id, tuple(section.options.get("argv") or ())))
        answer = self.answers.get(section.id, {"items": [{"title": "x"}], "total": 1})
        if isinstance(answer, BaseException):
            raise answer
        return answer


def test_fresh_result_reused(tmp_path):
    clock, reader = Clock(), Reader()
    panel = Panel(reader, clock=clock)
    src = sources(tmp_path, cmd(refresh_minutes=15))
    panel.sections(src)
    clock.now += 120
    [view] = panel.sections(src)
    assert len(reader.calls) == 1 and view["status"] == "ok"
    clock.now += 15 * 60
    panel.sections(src)
    assert len(reader.calls) == 2


def test_concurrent_refresh_joins(tmp_path):
    gate, started = threading.Event(), threading.Event()
    calls = []

    def slow(section):
        calls.append(section.id)
        started.set()
        gate.wait(5)
        return {"items": [{"title": "done"}], "total": 1}
    panel = Panel(slow)
    src = sources(tmp_path, cmd("prs"))
    results = []
    first = threading.Thread(target=lambda: results.append(panel.sections(src, force=["prs"])))
    first.start()
    started.wait(5)
    second = threading.Thread(target=lambda: results.append(panel.sections(src, force=["prs"])))
    second.start()
    gate.set()
    first.join(5)
    second.join(5)
    assert calls == ["prs"] and [r[0]["items"] for r in results] == [[{"title": "done"}]] * 2


def test_definition_changed(tmp_path):
    reader = Reader()
    panel = Panel(reader)
    panel.sections(sources(tmp_path, cmd(argv=["a"])))
    reader.answers["cmd"] = {"items": [{"title": "from b"}], "total": 1}
    [view] = panel.sections(sources(tmp_path, cmd(argv=["b"])))
    assert reader.calls == [("cmd", ("a",)), ("cmd", ("b",))] and view["items"] == [{"title": "from b"}]


def test_read_for_an_old_definition_is_discarded(tmp_path):
    gate, started = threading.Event(), threading.Event()

    def reader(section):
        if section.options["argv"] == ["a"]:
            started.set()
            gate.wait(5)
            return {"items": [{"title": "old"}], "total": 1}
        return {"items": [{"title": "new"}], "total": 1}
    panel = Panel(reader)
    old = threading.Thread(target=lambda: panel.sections(sources(tmp_path, cmd(argv=["a"]))))
    old.start()
    started.wait(5)
    [view] = panel.sections(sources(tmp_path, cmd(argv=["b"])))
    gate.set()
    old.join(5)
    [again] = panel.sections(sources(tmp_path, cmd(argv=["b"])), wait=False)
    assert view["items"] == again["items"] == [{"title": "new"}]


def test_failure_after_success(tmp_path):
    reader = Reader()
    reader.answers["cmd"] = {"items": [{"title": "1"}, {"title": "2"}, {"title": "3"}], "total": 3}
    panel = Panel(reader)
    src = sources(tmp_path, cmd())
    panel.sections(src)
    reader.answers["cmd"] = ReadError("exited with status 1")
    [view] = panel.sections(src, force=["cmd"])
    assert view["status"] == "stale" and len(view["items"]) == 3 and view["error"] == "exited with status 1"


def test_first_read_fails(tmp_path):
    reader = Reader()
    reader.answers["cmd"] = ReadError("boom")
    [view] = Panel(reader).sections(sources(tmp_path, cmd()))
    assert view["status"] == "error" and view["items"] == [] and view["error"] == "boom"


def test_command_fails(tmp_path):
    path = script(tmp_path, "import sys; sys.stderr.write('boom\\n'); sys.exit(2)")
    [view] = Panel(dp_sources.read).sections(sources(tmp_path, cmd(argv=py(path))))
    assert view["status"] == "error" and "status 2" in view["error"] and "boom" in view["error"]


def test_output_not_logged(tmp_path, caplog):
    path = script(tmp_path, "print('secret-output'); import sys; sys.exit(1)")
    with caplog.at_level(logging.WARNING, logger="hermes.plugins.day_panel"):
        Panel(dp_sources.read).sections(sources(tmp_path, cmd(argv=py(path))))
    warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and "cmd" in warnings[0] and "status 1" in warnings[0]
    assert not any("secret-output" in r.getMessage() for r in caplog.records)


def test_one_failing_section_does_not_block_others(tmp_path):
    reader = Reader()
    reader.answers["bad"] = RuntimeError("bug")
    views = Panel(reader).sections(sources(tmp_path, cmd("bad"), cmd("good")))
    assert [(v["id"], v["status"]) for v in views] == [("bad", "error"), ("good", "ok")]
    assert views[0]["error"] == "the read failed (RuntimeError)"
