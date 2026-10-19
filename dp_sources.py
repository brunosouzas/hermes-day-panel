"""The four source kinds. Each read returns a section result or raises ReadError.

Every source is read-only and runs as a child process without a shell: the
user's command, ``gh``, ``hermes usage`` and the MCP child (``dp_mcp_child.py``).
Source output is untrusted: it is cut, typed and returned as plain data.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .dp_config import Section

TEXT_MAX = 300
STDOUT_CAP = 256 * 1024
STDERR_KEEP = 4096
TOOL_PREFIXES = ("/opt/homebrew/bin", "/usr/local/bin", str(Path.home() / ".local" / "bin"))
CHILD = Path(__file__).resolve().parent / "dp_mcp_child.py"
RESULT_MARK = "DAY_PANEL_RESULT "


class ReadError(RuntimeError):
    """A read failed. ``str()`` is shown on the page; ``log_message`` is what the log gets, and it never
    carries a source's output or a tool's result (it defaults to the shown message when that is safe)."""

    def __init__(self, message: str, log_message: Optional[str] = None):
        super().__init__(message)
        self.log_message = log_message if log_message is not None else message


# ---------------------------------------------------------------- running programs

Completed = Tuple[int, str, str]  # exit status, stdout, stderr
Runner = Callable[..., Completed]


def run_capped(argv: List[str], timeout: float, cwd: Optional[Path] = None, stdin: Optional[str] = None,
               cap: int = STDOUT_CAP, env: Optional[Dict[str, str]] = None) -> Completed:
    """Run argv without a shell, all within one deadline: writing stdin, running, and draining output.

    The program runs in its own process group. That group is killed at the deadline, when stdout
    passes cap, and also once the program exits, so a descendant left holding the pipes can neither
    keep the read open nor outlive it.
    """
    deadline = time.monotonic() + timeout
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd) if cwd else None, env=env,
                                stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except FileNotFoundError:
        raise ReadError(f"program not found: {Path(argv[0]).name}") from None
    except OSError as exc:
        raise ReadError(f"could not start {Path(argv[0]).name}: {exc.strerror or exc}") from None
    out = bytearray()
    err = bytearray()
    over = threading.Event()

    def pump_out() -> None:
        try:
            while True:
                chunk = proc.stdout.read1(65536)
                if not chunk:
                    return
                if len(out) + len(chunk) > cap:
                    over.set()
                    _kill(proc)
                    return
                out.extend(chunk)
        except (OSError, ValueError):
            return

    def pump_err() -> None:
        try:
            while True:
                chunk = proc.stderr.read1(65536)
                if not chunk:
                    return
                err.extend(chunk)
                del err[:-STDERR_KEEP]
        except (OSError, ValueError):
            return

    def feed() -> None:
        try:
            proc.stdin.write(stdin.encode("utf-8"))
            proc.stdin.close()
        except (OSError, ValueError):
            pass

    readers = [threading.Thread(target=pump_out, daemon=True), threading.Thread(target=pump_err, daemon=True)]
    threads = readers + ([threading.Thread(target=feed, daemon=True)] if stdin is not None else [])
    for t in threads:
        t.start()
    timed_out = False
    try:
        code = proc.wait(timeout=max(0.0, deadline - time.monotonic()))
    except subprocess.TimeoutExpired:
        timed_out = True
    _kill(proc)  # the deadline passed, or the program exited: nothing of its group stays behind
    if timed_out:
        proc.wait()
    for t in readers:
        t.join(timeout=max(0.2, min(2.0, deadline - time.monotonic())))
    for pipe in (proc.stdin, proc.stdout, proc.stderr):
        try:
            if pipe:
                pipe.close()
        except OSError:
            pass
    if timed_out:
        raise ReadError(f"timed out after {_seconds(timeout)} s")
    if over.is_set():
        raise ReadError(f"output larger than {cap // 1024} KiB")
    if any(t.is_alive() for t in readers):
        raise ReadError("output still open after the program exited (a process outside its group holds it)")
    return code, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")


def _kill(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        try:
            proc.kill()
        except OSError:
            pass


def _seconds(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def last_line(text: str) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return lines[-1][:200] if lines else ""


def find_tool(name: str) -> Optional[str]:
    """Absolute path of gh/hermes: a backend started by launchd may have a short PATH."""
    found = shutil.which(name)
    if found:
        return found
    for prefix in TOOL_PREFIXES:
        candidate = Path(prefix) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return None


# ---------------------------------------------------------------- result normalisation

def clip(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = " ".join(value.split())
    return value[:TEXT_MAX] if value else None


def safe_url(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    value = value.strip()
    lower = value.lower()
    if (lower.startswith("https://") or lower.startswith("http://")) and len(value) > 8 and " " not in value:
        return value[:2000]
    return None


def normalise_item(raw: Any) -> Optional[Dict[str, Any]]:
    """One item from untrusted data: a text title is required; other fields are kept only when valid."""
    if not isinstance(raw, dict):
        return None
    title = clip(raw.get("title"))
    if not title:
        return None
    item: Dict[str, Any] = {"title": title}
    url = safe_url(raw.get("url"))
    if url:
        item["url"] = url
    for name in ("detail", "badge", "time"):
        value = clip(raw.get(name))
        if value:
            item[name] = value
    return item


def result(items: List[Any], max_items: int, total: Any = None, note: Any = None) -> Dict[str, Any]:
    kept = [i for i in (normalise_item(x) for x in items) if i is not None]
    count = total if isinstance(total, int) and not isinstance(total, bool) and total >= 0 else len(kept)
    out: Dict[str, Any] = {"items": kept[:max_items], "total": count}
    note = clip(note)
    if note:
        out["note"] = note
    return out


# ---------------------------------------------------------------- command

def read_command(section: Section, runner: Runner = run_capped) -> Dict[str, Any]:
    argv = [sys.executable if a == "{python}" else a for a in section.options["argv"]]
    code, stdout, stderr = runner(argv, timeout=section.timeout_s, cwd=section.base_dir)
    if code != 0:
        tail = last_line(stderr)
        raise ReadError(f"exited with status {code}" + (f": {tail}" if tail else ""))
    try:
        data = json.loads(stdout)
    except ValueError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ReadError('the output is not the expected JSON (an object with an "items" list)')
    return result(data["items"], section.max_items, data.get("total"), data.get("note"))


# ---------------------------------------------------------------- GitHub pull requests

PR_FIELDS = "repository,title,number,url,isDraft,updatedAt"


def read_github_prs(section: Section, runner: Runner = run_capped, gh: Optional[str] = None) -> Dict[str, Any]:
    gh = gh or find_tool("gh")
    if not gh:
        raise ReadError("the gh CLI was not found")
    deadline = time.monotonic() + section.timeout_s
    excluded = {o.lower() for o in section.options["exclude_owners"]}
    flags = {"author": "--author", "review_requested": "--review-requested"}
    seen, raw_items = set(), []
    for which in section.options["include"]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ReadError(f"timed out after {section.timeout_s} s")
        code, stdout, stderr = runner([gh, "search", "prs", "--state", "open", flags[which], "@me",
                                       "--json", PR_FIELDS, "--limit", "50"], timeout=remaining)
        if code != 0:
            raise ReadError(f"gh exited with status {code}" + (f": {last_line(stderr)}" if last_line(stderr) else ""))
        try:
            rows = json.loads(stdout or "[]")
        except ValueError:
            raise ReadError("gh did not return JSON") from None
        if not isinstance(rows, list):
            raise ReadError("gh returned an unexpected shape")
        for pr in rows:
            if not isinstance(pr, dict):
                continue
            repo = (pr.get("repository") or {}).get("nameWithOwner") if isinstance(pr.get("repository"), dict) else None
            number = pr.get("number")
            if not isinstance(repo, str) or "/" not in repo or not isinstance(number, int):
                continue
            if repo.split("/")[0].lower() in excluded or (repo, number) in seen:
                continue
            seen.add((repo, number))
            draft = pr.get("isDraft") is True
            raw_items.append(({"title": f"{repo}#{number} · {pr.get('title') or ''}", "url": pr.get("url"),
                               "badge": "review requested" if which == "review_requested" else ("draft" if draft else None),
                               "time": pr.get("updatedAt")}, {"repo": repo, "number": number, "draft": draft}))
    out = result([i for i, _ in raw_items], section.max_items)
    # The pull request reference rides along (for the page's merge action); it is not source text.
    refs = [ref for item, ref in raw_items if normalise_item(item) is not None]
    for item, ref in zip(out["items"], refs):
        item["pr"] = ref
    return out


# ---------------------------------------------------------------- read-only MCP tool

def hermes_root() -> Optional[str]:
    try:
        import hermes_constants  # type: ignore

        return str(Path(hermes_constants.__file__).resolve().parent)
    except Exception:
        return None


def call_mcp_child(server: str, tool: str, args: Dict[str, Any], timeout: float,
                   runner: Runner = run_capped, child: Optional[List[str]] = None) -> str:
    """Run the MCP child in Hermes' Python; return the tool's text result or raise ReadError."""
    root = hermes_root()
    argv = child or [sys.executable, "-I", str(CHILD)]
    # -I drops the environment's paths; the child gets the backend's own import path instead, which is
    # how Hermes' launcher sets it up (PYTHONPATH is empty there).
    payload = json.dumps({"server": server, "tool": tool, "args": args, "hermes_root": root,
                          "sys_path": [p for p in sys.path if isinstance(p, str) and p]})
    code, stdout, stderr = runner(argv, timeout=timeout, stdin=payload)
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_MARK):
            try:
                answer = json.loads(line[len(RESULT_MARK):])
            except ValueError:
                break
            if answer.get("ok") is True and isinstance(answer.get("text"), str):
                return answer["text"]
            shown = str(answer.get("error") or "the MCP call failed")[:300]
            raise ReadError(shown, log_message=str(answer.get("log") or shown)[:300])
    raise ReadError(f"the MCP child exited with status {code}" + (f": {last_line(stderr)}" if last_line(stderr) else ""))


def _decode_json(text: str) -> Tuple[bool, Any]:
    try:
        return True, json.loads(text)
    except ValueError:
        pass
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith(("[", "{")):
            try:
                return True, json.loads("\n".join(lines[index:]))
            except ValueError:
                return False, None
    return False, None


def map_mcp_result(text: str, options: Dict[str, Any], max_items: int) -> Dict[str, Any]:
    decoded, data = _decode_json(text)
    if not decoded:
        lines = [{"title": line} for line in text.splitlines() if line.strip()]
        return result(lines, max_items)
    if data is None:
        return result([], max_items)
    if isinstance(data, dict):
        key = options.get("list_key")
        if not key:
            raise ReadError("the result is an object; set options.list_key to the name of its list")
        data = data.get(key)
        if not isinstance(data, list):
            raise ReadError(f"{key} is not a list in the result")
    elif not isinstance(data, list):
        return result([{"title": str(data)}], max_items)
    fields = options.get("fields") or {"title": "title"}
    items, skipped = [], 0
    for element in data:
        if not isinstance(element, dict):
            skipped += 1
            continue
        item = {}
        for name, source_key in fields.items():
            value = element.get(source_key)
            if value is not None:
                item[name] = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if not clip(item.get("title")):
            skipped += 1
            continue
        items.append(item)
    note = f"{skipped} entr{'y' if skipped == 1 else 'ies'} skipped (no {fields['title']})" if skipped else None
    return result(items, max_items, note=note)


def read_mcp_tool(section: Section, call: Callable[..., str] = call_mcp_child) -> Dict[str, Any]:
    opts = section.options
    text = call(opts["server"], opts["tool"], opts.get("args") or {}, section.timeout_s)
    return map_mcp_result(text, opts, section.max_items)


# ---------------------------------------------------------------- AI usage windows

def _usage_items(data: Dict[str, Any], name: str, warn: int) -> List[Dict[str, Any]]:
    label = data.get("provider") if isinstance(data.get("provider"), str) else name
    plan = data.get("plan") if isinstance(data.get("plan"), str) else ""
    items = []
    for window in data.get("windows") or []:
        if not isinstance(window, dict):
            continue
        used = window.get("used_percent")
        if isinstance(used, bool) or not isinstance(used, (int, float)):
            continue
        item = {"title": f"{label or 'provider'} · {window.get('label') or 'window'}",
                "detail": f"{used:.0f}% used" + (f" · {plan}" if plan else ""),
                "time": window.get("resets_at") if isinstance(window.get("resets_at"), str) else None}
        if used >= warn:
            item["badge"] = "high"
        items.append(item)
    return items


def read_ai_usage(section: Section, runner: Runner = run_capped, hermes: Optional[str] = None,
                  clock: Callable[[], float] = time.monotonic) -> Dict[str, Any]:
    hermes = hermes or find_tool("hermes")
    if not hermes:
        raise ReadError("the hermes command was not found")
    providers = section.options["providers"] or [None]
    warn = section.options["warn_percent"]
    deadline = clock() + section.timeout_s
    items: List[Dict[str, Any]] = []
    failed: List[str] = []
    late: List[str] = []
    errors: List[str] = []
    for name in providers:
        label = name or "configured provider"
        remaining = deadline - clock()
        if remaining <= 0:
            late.append(label)
            continue
        argv = [hermes, "usage", "--json"] + (["--provider", name] if name else [])
        try:
            code, stdout, stderr = runner(argv, timeout=remaining)
        except ReadError as exc:
            if str(exc).startswith("timed out"):
                late.append(label)
            else:
                failed.append(label)
                errors.append(f"{label}: {exc}")
            continue
        data = None
        if code == 0:
            try:
                data = json.loads(stdout)
            except ValueError:
                data = None
        if not isinstance(data, dict) or data.get("unavailable_reason"):
            reason = (data or {}).get("unavailable_reason") if isinstance(data, dict) else None
            failed.append(label)
            errors.append(f"{label}: " + (str(reason)[:120] if reason else f"exit {code}" +
                                         (f", {last_line(stderr)}" if last_line(stderr) else "")))
            continue
        items.extend(_usage_items(data, label, warn))
    notes = []
    if failed:
        notes.append("could not be read: " + ", ".join(failed))
    if late:
        notes.append(f"not read in time ({section.timeout_s} s): " + ", ".join(late))
    if not items and (failed or late):
        raise ReadError("; ".join(errors + ([notes[-1]] if late else [])) or "no provider could be read")
    return result(items, section.max_items, note="; ".join(notes) or None)


# ---------------------------------------------------------------- dispatch

def read(section: Section) -> Dict[str, Any]:
    if section.kind == "command":
        return read_command(section)
    if section.kind == "github_prs":
        return read_github_prs(section)
    if section.kind == "mcp_tool":
        return read_mcp_tool(section)
    if section.kind == "ai_usage":
        return read_ai_usage(section)
    raise ReadError(f"unknown kind {section.kind}")  # pragma: no cover - validated earlier
