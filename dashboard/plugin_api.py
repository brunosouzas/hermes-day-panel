"""Backend routes for the Today page (mounted by Hermes at /api/plugins/day-panel/).

Hermes mounts this router only while the plugin is enabled, inside the active
profile's server and behind Hermes' own authentication. Routes take section ids
and pull request references, never a path, a program or arguments: what runs is
decided only by the user's sources file.
"""

from __future__ import annotations

import importlib
import importlib.util
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException

_ROOT = Path(__file__).resolve().parent.parent
_PKG = "hermes_day_panel_backend"
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


def _package():
    if _PKG not in sys.modules:
        spec = importlib.util.spec_from_file_location(_PKG, _ROOT / "__init__.py", submodule_search_locations=[str(_ROOT)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[_PKG] = module
        spec.loader.exec_module(module)
    return sys.modules[_PKG]


def _mod(name: str):
    _package()
    return importlib.import_module(f"{_PKG}.{name}")


router = APIRouter()

# Seams for tests: where the sources file is, the panel (cache) and the merger.
path_provider = None
panel_provider = None
merger_provider = None


def _path() -> Path:
    return path_provider() if path_provider is not None else _mod("dp_host").path_from_config()


def _panel():
    return panel_provider() if panel_provider is not None else _mod("dp_host").shared_panel()


def _merger():
    return merger_provider() if merger_provider is not None else _mod("dp_host").shared_merger()


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _sources():
    return _mod("dp_config").load(_path())


def _page(force=(), force_all: bool = False) -> Dict[str, Any]:
    config = _mod("dp_config")
    base = {"date": datetime.now().astimezone().date().isoformat(), "sources_file": str(_path())}
    try:
        sources = _sources()
    except config.ConfigError as exc:
        return {**base, "errors": exc.errors, "sections": []}
    return {**base, "errors": [], "sections": _panel().sections(sources, force=force, force_all=force_all)}


@router.get("/sections")
def sections() -> Dict[str, Any]:
    return _page()


@router.post("/refresh")
def refresh_all() -> Dict[str, Any]:
    return _page(force_all=True)


def _section(section_id: str):
    config = _mod("dp_config")
    if not isinstance(section_id, str) or not ID_RE.match(section_id):
        raise _err(404, "not_found", "no such section")
    try:
        sources = _sources()
    except config.ConfigError as exc:
        raise _err(409, "sources_invalid", "; ".join(exc.errors)) from None
    section = sources.get(section_id)
    if section is None:
        raise _err(404, "not_found", "no such section")
    return sources, section


@router.post("/sections/{section_id}/refresh")
def refresh_one(section_id: str) -> Dict[str, Any]:
    sources, section = _section(section_id)
    views = _panel().sections(sources, force=[section.id])
    return next(v for v in views if v["id"] == section.id)


@router.post("/sections/{section_id}/merge/preview")
def merge_preview(section_id: str, payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    _sources_ok, section = _section(section_id)
    payload = payload if isinstance(payload, dict) else {}
    merge = _mod("dp_merge")
    try:
        return _merger().preview(section, payload.get("repo"), payload.get("number"),
                                 _panel().cached_item_refs(section))
    except merge.MergeError as exc:
        raise _err(exc.status, exc.code, exc.message) from None


@router.post("/merge/confirm")
def merge_confirm(payload: Optional[Dict[str, Any]] = Body(None)) -> Dict[str, Any]:
    token = payload.get("token") if isinstance(payload, dict) else None
    merge = _mod("dp_merge")
    try:
        out = _merger().confirm(token, _sources)
    except merge.MergeError as exc:
        raise _err(exc.status, exc.code, exc.message) from None
    try:  # the section's next read shows the pull request gone
        sources = _sources()
        section = sources.get(out["section"])
        if section is not None:
            _panel().invalidate(section)
    except Exception:
        pass
    return out
