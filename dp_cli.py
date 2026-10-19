"""`hermes day show` and `hermes day check`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, List

from . import dp_config
from .dp_panel import Panel

MARK = {"ok": "ok", "stale": "stale", "error": "error"}


def setup_parser(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="day_command")
    show = sub.add_parser("show", help="Read every enabled section now and print it")
    show.add_argument("--json", action="store_true", help="Print the sections as JSON")
    sub.add_parser("check", help="Validate the sources file")


def format_sections(views: List[dict]) -> str:
    lines: List[str] = []
    for view in views:
        head = f"## {view['title']} [{MARK.get(view['status'], view['status'])}]"
        if view.get("total") and view["total"] > len(view["items"]):
            head += f" ({len(view['items'])} of {view['total']})"
        lines.append(head)
        if view.get("error"):
            lines.append(f"! {view['error']}")
        for item in view["items"]:
            extra = " · ".join(x for x in (item.get("badge"), item.get("detail"), item.get("time")) if x)
            lines.append(f"- {item['title']}" + (f" ({extra})" if extra else ""))
        if not view["items"] and not view.get("error"):
            lines.append("(nothing)")
        if view.get("note"):
            lines.append(f"  {view['note']}")
        lines.append("")
    return "\n".join(lines).rstrip()


def make_handler(path_fn: Callable[[], Path], panel_fn: Callable[[], Panel]) -> Callable[[argparse.Namespace], int]:
    def handler(args: argparse.Namespace) -> int:
        command = getattr(args, "day_command", None)
        path = path_fn()
        try:
            sources = dp_config.load(path)
        except dp_config.ConfigError as exc:
            for error in exc.errors:
                print(f"refused: {error}")
            return 2
        if command == "check":
            enabled = len(sources.enabled)
            print(f"ok: {path} ({len(sources.sections)} sections, {enabled} enabled)")
            return 0
        if command == "show":
            views = panel_fn().sections(sources, force_all=True)
            print(json.dumps(views, ensure_ascii=False, indent=1) if args.json else format_sections(views))
            return 0
        print("usage: hermes day {show [--json] | check}")
        return 1
    return handler
