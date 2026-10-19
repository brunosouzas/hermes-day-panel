"""Child process for an ``mcp_tool`` section: one read-only call through Hermes' own MCP client.

Run by ``dp_sources.call_mcp_child`` with Hermes' Python (``python -I dp_mcp_child.py``),
so the parent can kill it at the section's timeout. Reads one JSON request on
standard input ({server, tool, args, hermes_root, sys_path}) and prints one line
``DAY_PANEL_RESULT {"ok": ..., "text"|"error": ...}``.

The tool is called only when the server marked it read-only (``readOnlyHint``),
which Hermes records when it discovers the server's tools.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any, Callable, Dict, Optional

RESULT_MARK = "DAY_PANEL_RESULT "


class ChildError(RuntimeError):
    """``str()`` is shown on the page; ``log`` (when set) replaces it in the log, without tool output."""

    def __init__(self, message: str, log: Optional[str] = None):
        super().__init__(message)
        self.log = log


def call(server: str, tool: str, args: Dict[str, Any], *, configured: Callable[[], Dict[str, Any]],
         discover: Callable[[list], Any], tool_name: Callable[[str, str], str], exists: Callable[[str], bool],
         read_only: Callable[[str, str], bool], dispatch: Callable[[str, Dict[str, Any]], str]) -> str:
    """The checks and the call, with every Hermes entry point passed in (tests use fakes)."""
    if server not in (configured() or {}):
        raise ChildError(f"the MCP server {server!r} is not configured in Hermes")
    discover([server])
    name = tool_name(server, tool)
    if not exists(name):
        raise ChildError(f"the MCP server {server!r} has no tool {tool!r} (or it did not connect)")
    if not read_only(server, tool):
        raise ChildError(f"the tool {tool!r} is not read-only (no readOnlyHint), so it is not called")
    raw = dispatch(name, args)
    try:
        answer = json.loads(raw)
    except (TypeError, ValueError):
        return str(raw)
    if isinstance(answer, dict) and "error" in answer and "result" not in answer:
        raise ChildError(f"the tool failed: {str(answer['error'])[:200]}", log="the tool returned an error")
    if isinstance(answer, dict) and "result" in answer:
        value = answer["result"]
        return value if isinstance(value, str) else json.dumps(value)
    return raw if isinstance(raw, str) else json.dumps(raw)


def hermes_entry_points() -> Dict[str, Callable[..., Any]]:  # pragma: no cover - needs a Hermes install
    from hermes_cli.config import load_config  # type: ignore
    from tools.mcp_tool_discovery import discover_mcp_tools  # type: ignore
    from tools.mcp_tool_handlers import _tool_is_read_only  # type: ignore
    from tools.mcp_tool_schema import mcp_prefixed_tool_name  # type: ignore
    from tools.registry import registry  # type: ignore

    return {
        "configured": lambda: (load_config() or {}).get("mcp_servers") or {},
        "discover": discover_mcp_tools,
        "tool_name": mcp_prefixed_tool_name,
        "exists": lambda name: registry.get_entry(name) is not None,
        "read_only": _tool_is_read_only,
        "dispatch": registry.dispatch,
    }


def main(stdin=None, entry: Optional[Dict[str, Callable[..., Any]]] = None) -> int:
    logging.disable(logging.WARNING)  # the parent reads only the result line
    try:
        request = json.loads((stdin or sys.stdin).read())
        paths = [p for p in request.get("sys_path") or [] if isinstance(p, str) and p]
        if paths:
            sys.path[:] = paths + [p for p in sys.path if p not in paths]
        root = request.get("hermes_root")
        if root and root not in sys.path:
            sys.path.insert(0, root)
        if entry is None:
            entry = hermes_entry_points()
        text = call(str(request["server"]), str(request["tool"]), request.get("args") or {}, **entry)
        answer = {"ok": True, "text": text}
    except ChildError as exc:
        answer = {"ok": False, "error": str(exc)}
        if exc.log:
            answer["log"] = exc.log
    except ImportError:
        answer = {"ok": False, "error": "Hermes' MCP client could not be loaded"}
    except Exception as exc:  # report, never a traceback on stdout
        answer = {"ok": False, "error": f"the MCP call failed ({type(exc).__name__})"}
    sys.stdout.write(RESULT_MARK + json.dumps(answer) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    import os

    # Hard exit: Hermes' MCP client keeps a background event loop that would hold the process open.
    os._exit(main())
