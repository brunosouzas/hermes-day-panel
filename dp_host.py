"""Adapters between the plugin and Hermes: where the sources file is, and one shared panel."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from . import dp_config, dp_sources
from .dp_merge import Merger
from .dp_panel import Panel

PLUGIN_ID = "day-panel"
_shared: dict = {}
_shared_lock = threading.Lock()


def path_from_ctx(ctx: Any) -> Path:
    return dp_config.sources_path(ctx.get_config("sources_file", ""))


def path_from_config() -> Path:
    """For the dashboard backend, which has no plugin context: read config.yaml directly."""
    setting: Optional[str] = None
    try:
        from hermes_cli.config import load_config  # type: ignore

        entries = (load_config() or {}).get("plugins", {}).get("entries", {}) or {}
        setting = ((entries.get(PLUGIN_ID) or {}).get("settings") or {}).get("sources_file")
    except Exception:
        setting = None
    return dp_config.sources_path(setting)


def shared_panel() -> Panel:
    with _shared_lock:
        if "panel" not in _shared:
            _shared["panel"] = Panel(dp_sources.read)
        return _shared["panel"]


def shared_merger() -> Merger:
    with _shared_lock:
        if "merger" not in _shared:
            _shared["merger"] = Merger()
        return _shared["merger"]
