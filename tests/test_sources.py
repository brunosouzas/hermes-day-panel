"""Spec day-sources: section results, the command, GitHub pull requests and AI usage sources."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

from day_panel import dp_sources
from day_panel.dp_sources import ReadError
from helpers import FakeRunner, ok, py, script, section


# ---------------------------------------------------------------- section result

def test_too_many_items():
    out = dp_sources.result([{"title": f"t{i}"} for i in range(80)], max_items=5)
    assert len(out["items"]) == 5 and out["total"] == 80


def test_unsafe_link():
    out = dp_sources.result([{"title": "x", "url": "javascript:alert(1)"}], 10)
    assert out["items"] == [{"title": "x"}]


def test_text_is_cut_and_whitespace_folded():
    out = dp_sources.result([{"title": "a\n  b" + "c" * 400, "detail": "d"}], 10)
    assert out["items"][0]["title"].startswith("a b") and len(out["items"][0]["title"]) == 300


# ---------------------------------------------------------------- command (real child processes)

def cmd(tmp_path, body, **raw):
    path = script(tmp_path, body)
    return section(tmp_path, kind="command", options={"argv": py(path)}, **raw)


def test_command_valid_output(tmp_path):
    s = cmd(tmp_path, """
        import json; print(json.dumps({"items": [{"title": "Card 42", "url": "https://example.com/42"}], "total": 1}))
    """)
    assert dp_sources.read_command(s) == {"items": [{"title": "Card 42", "url": "https://example.com/42"}], "total": 1}


def test_command_relative_script_with_hermes_python(tmp_path):
    script(tmp_path, """
        import json, os, sys
        print(json.dumps({"items": [], "note": os.getcwd() + "|" + sys.executable}))
    """, name="source.py")
    s = section(tmp_path, kind="command", options={"argv": ["{python}", "source.py"]})
    out = dp_sources.read_command(s)
    cwd, python = out["note"].split("|")
    assert out["items"] == [] and Path(cwd).resolve() == tmp_path.resolve() and python == sys.executable


def test_command_fails_message(tmp_path):
    s = cmd(tmp_path, "import sys; sys.stderr.write('boom\\n'); sys.exit(2)")
    with pytest.raises(ReadError, match=r"status 2: boom"):
        dp_sources.read_command(s)


def test_command_timeout(tmp_path):
    s = cmd(tmp_path, "import time; time.sleep(30)", timeout_s=1)
    started = time.monotonic()
    with pytest.raises(ReadError, match="timed out after 1 s"):
        dp_sources.read_command(s)
    assert time.monotonic() - started < 10


def test_command_not_json(tmp_path):
    s = cmd(tmp_path, "print('hello')")
    with pytest.raises(ReadError, match="not the expected JSON"):
        dp_sources.read_command(s)


def test_valid_tone_and_progress(tmp_path):
    s = cmd(tmp_path, """
        import json
        print(json.dumps({"items": [{"title": "build", "tone": "bad", "progress": 40, "time_label": "finished"}]}))
    """)
    [item] = dp_sources.read_command(s)["items"]
    assert item == {"title": "build", "tone": "bad", "progress": 40, "time_label": "finished"}


def test_out_of_range_values_dropped(tmp_path):
    s = cmd(tmp_path, """
        import json
        print(json.dumps({"items": [{"title": "x", "tone": "purple", "progress": 140},
                                    {"title": "y", "progress": True, "time_label": "%s"}]}))
    """ % ("w" * 60))
    x, y = dp_sources.read_command(s)["items"]
    assert x == {"title": "x"}
    assert y == {"title": "y", "time_label": "w" * 40}


def test_command_malformed_optional_fields(tmp_path):
    s = cmd(tmp_path, """
        import json; print(json.dumps({"items": [{"title": "x", "detail": {}}, {"title": 3}], "total": "many", "note": []}))
    """)
    assert dp_sources.read_command(s) == {"items": [{"title": "x"}], "total": 1}


def test_command_output_cap(tmp_path):
    s = cmd(tmp_path, "import sys; sys.stdout.write('x' * (300 * 1024)); sys.stdout.flush()")
    with pytest.raises(ReadError, match="larger than 256 KiB"):
        dp_sources.read_command(s)


def test_stdin_never_read_still_times_out(tmp_path):
    sleeper = script(tmp_path, "import time; time.sleep(30)", name="sleeper.py")
    started = time.monotonic()
    with pytest.raises(ReadError, match="timed out"):
        dp_sources.run_capped(py(sleeper), timeout=0.5, stdin="x" * (1024 * 1024))
    assert time.monotonic() - started < 5


def test_descendant_holding_the_pipes_is_killed(tmp_path):
    marker = tmp_path / "descendant-alive"
    s = cmd(tmp_path, f"""
        import json, subprocess, sys
        subprocess.Popen([sys.executable, "-c", "import time, pathlib; time.sleep(3); pathlib.Path({str(marker)!r}).write_text('x')"])
        print(json.dumps({{"items": [{{"title": "done"}}]}}), flush=True)
    """, timeout_s=10)
    started = time.monotonic()
    assert dp_sources.read_command(s)["items"] == [{"title": "done"}]
    assert time.monotonic() - started < 2.5
    time.sleep(3.5)
    assert not marker.exists()


def _escaper(tmp_path, then):
    pid_file = tmp_path / "escaped.pid"
    body = f"""
        import json, subprocess, sys
        subprocess.Popen([sys.executable, "-c",
            "import os, time, pathlib; os.setsid(); pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(20)"])
        {then}
    """
    return script(tmp_path, body), pid_file


def _reap(pid_file):
    import os, signal
    for _ in range(20):
        if pid_file.exists() and pid_file.read_text():
            try:
                os.kill(int(pid_file.read_text()), signal.SIGKILL)
            except ProcessLookupError:
                pass
            return
        time.sleep(0.1)


def test_escaped_descendant_cannot_hold_the_read_open(tmp_path):
    path, pid_file = _escaper(tmp_path, 'print(json.dumps({"items": []}), flush=True)')
    started = time.monotonic()
    try:
        with pytest.raises(ReadError, match="output still open"):
            dp_sources.run_capped(py(path), timeout=5)
        assert time.monotonic() - started < 2
    finally:
        _reap(pid_file)


def test_escaped_descendant_does_not_stretch_the_timeout(tmp_path):
    path, pid_file = _escaper(tmp_path, "import time; time.sleep(20)")
    started = time.monotonic()
    try:
        with pytest.raises(ReadError, match="timed out after 0.3 s"):
            dp_sources.run_capped(py(path), timeout=0.3)
        assert time.monotonic() - started < 1.5
    finally:
        _reap(pid_file)


def test_stdin_is_delivered(tmp_path):
    echo = script(tmp_path, "import sys; data = sys.stdin.read(); print(len(data))", name="echo.py")
    code, out, _ = dp_sources.run_capped(py(echo), timeout=10, stdin="x" * (512 * 1024))
    assert code == 0 and out.strip() == str(512 * 1024)


def test_command_runs_without_shell(tmp_path):
    marker = tmp_path / "pwned"
    s = section(tmp_path, kind="command", options={"argv": [sys.executable, "-c", "print('{\"items\": []}')",
                                                           f"; touch {marker}"]})
    dp_sources.read_command(s)
    assert not marker.exists()


# ---------------------------------------------------------------- GitHub pull requests

def pr(repo, number, title="T", draft=False):
    return {"repository": {"nameWithOwner": repo}, "number": number, "title": title, "isDraft": draft,
            "url": f"https://github.com/{repo}/pull/{number}", "updatedAt": "2026-10-19T10:00:00Z"}


def gh_answers(mine, review):
    return FakeRunner(lambda argv: ok(mine if "--author" in argv else review))


def test_prs_authored_and_review(tmp_path):
    runner = gh_answers([pr("me/a", 1, draft=True)], [pr("other/b", 2)])
    out = dp_sources.read_github_prs(section(tmp_path, kind="github_prs"), runner=runner, gh="gh")
    assert [(i["title"], i.get("badge")) for i in out["items"]] == [("me/a#1 · T", "draft"),
                                                                     ("other/b#2 · T", "review requested")]
    assert out["items"][0]["pr"] == {"repo": "me/a", "number": 1, "draft": True}
    assert all(c["argv"][:3] == ["gh", "search", "prs"] for c in runner.calls)


def test_prs_without_gh(tmp_path, monkeypatch):
    monkeypatch.setattr(dp_sources, "find_tool", lambda name: None)
    with pytest.raises(ReadError, match="gh CLI was not found"):
        dp_sources.read_github_prs(section(tmp_path, kind="github_prs"))


def test_prs_exclude_and_dedupe(tmp_path):
    runner = gh_answers([pr("me/a", 1), pr("work/x", 9)], [pr("me/a", 1), pr("WORK/y", 3)])
    s = section(tmp_path, kind="github_prs", options={"exclude_owners": ["work"]})
    out = dp_sources.read_github_prs(s, runner=runner, gh="gh")
    assert [i["title"] for i in out["items"]] == ["me/a#1 · T"]


# ---------------------------------------------------------------- AI usage

def usage(provider, *windows):
    return {"provider": provider, "title": "limits", "plan": None, "unavailable_reason": None,
            "windows": [{"label": label, "used_percent": used, "resets_at": "2026-10-20T22:00:00Z"} for label, used in windows]}


def test_usage_two_providers(tmp_path):
    data = {"anthropic": usage("anthropic", ("Session", 9), ("Week", 85)),
            "openai-codex": usage("openai-codex", ("Session", 7), ("Weekly", 16))}
    runner = FakeRunner(lambda argv: ok(data[argv[argv.index("--provider") + 1]]))
    s = section(tmp_path, kind="ai_usage", options={"providers": ["anthropic", "openai-codex"]})
    out = dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")
    assert len(out["items"]) == 4
    assert [i["title"] for i in out["items"] if i.get("badge") == "high"] == ["anthropic · Week"]
    assert out["items"][1]["detail"] == "85% used" and "note" not in out


def test_usage_labelled_window(tmp_path):
    data = usage("claude-x", ("Current session", 68))
    data["windows"][0]["resets_at"] = "2026-10-19T16:00:00Z"
    runner = FakeRunner(lambda argv: ok(data))
    s = section(tmp_path, kind="ai_usage",
                options={"providers": ["claude-x"], "warn_percent": 80, "labels": {"claude-x": "Claude"}})
    [item] = dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")["items"]
    assert item == {"title": "Claude · Current session", "detail": "68% used", "time": "2026-10-19T16:00:00Z",
                    "time_label": "resets", "progress": 68}


def test_usage_window_exactly_at_the_warning_level(tmp_path):
    runner = FakeRunner(lambda argv: ok(usage("openai-codex", ("Weekly", 80))))
    s = section(tmp_path, kind="ai_usage", options={"providers": ["openai-codex"], "warn_percent": 80, "labels": {}})
    [item] = dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")["items"]
    assert item["title"] == "openai-codex · Weekly"
    assert item["badge"] == "high" and item["tone"] == "warn"


def test_usage_no_provider_name_reported(tmp_path):
    data = usage("ignored", ("Session", 10))
    del data["provider"]
    runner = FakeRunner(lambda argv: ok(data))
    s = section(tmp_path, kind="ai_usage", options={"providers": ["codex"], "warn_percent": 80, "labels": {"codex": "Codex"}})
    [item] = dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")["items"]
    assert item["title"] == "Codex · Session"
    none = section(tmp_path, kind="ai_usage", options={"providers": [], "warn_percent": 80, "labels": {}})
    [item] = dp_sources.read_ai_usage(none, runner=FakeRunner(lambda argv: ok(data)), hermes="hermes")["items"]
    assert item["title"] == "provider · Session"


def test_usage_one_provider_fails(tmp_path):
    runner = FakeRunner(lambda argv: ok(usage("a", ("S", 1))) if "a" in argv else (1, "", "no credential"))
    s = section(tmp_path, kind="ai_usage", options={"providers": ["a", "b"]})
    out = dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")
    assert [i["title"] for i in out["items"]] == ["a · S"] and "could not be read: b" in out["note"]


def test_usage_section_deadline(tmp_path):
    from helpers import Clock
    clock = Clock(0)

    def answer(argv):
        clock.now += 5  # provider a uses the whole budget
        return ReadError("timed out after 5 s")
    runner = FakeRunner(answer)
    s = section(tmp_path, kind="ai_usage", timeout_s=5, options={"providers": ["a", "b"]})
    with pytest.raises(ReadError, match=r"not read in time \(5 s\): a, b"):
        dp_sources.read_ai_usage(s, runner=runner, hermes="hermes", clock=clock)
    assert len(runner.calls) == 1 and runner.calls[0]["timeout"] == 5


def test_usage_every_provider_fails(tmp_path):
    runner = FakeRunner(lambda argv: (1, "", "Error: no credential configured"))
    s = section(tmp_path, kind="ai_usage", options={"providers": ["a"]})
    with pytest.raises(ReadError, match="a: exit 1, Error: no credential configured"):
        dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")


def test_usage_reason_shown_but_not_logged(tmp_path, caplog):
    import logging
    from day_panel import dp_config
    from day_panel.dp_panel import Panel

    data = {**usage("a"), "unavailable_reason": "SYNTHETIC_PROVIDER_OUTPUT"}
    runner = FakeRunner(lambda argv: ok(data))
    src = dp_config.parse({"sections": [{"id": "ai", "kind": "ai_usage", "options": {"providers": ["a"]}}]},
                          tmp_path / "f.yaml")
    with caplog.at_level(logging.WARNING, logger="hermes.plugins.day_panel"):
        [view] = Panel(lambda s: dp_sources.read_ai_usage(s, runner=runner, hermes="hermes")).sections(src)
    assert "SYNTHETIC_PROVIDER_OUTPUT" in view["error"]
    assert caplog.records and not any("SYNTHETIC_PROVIDER_OUTPUT" in r.getMessage() for r in caplog.records)


def test_usage_without_providers_uses_the_configured_one(tmp_path):
    runner = FakeRunner(lambda argv: ok(usage("claude", ("Session", 50))))
    out = dp_sources.read_ai_usage(section(tmp_path, kind="ai_usage"), runner=runner, hermes="hermes")
    assert runner.calls[0]["argv"] == ["hermes", "usage", "--json"] and out["items"][0]["title"] == "claude · Session"
