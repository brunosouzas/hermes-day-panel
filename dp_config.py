"""The sources file: load, validate and describe the Today page's sections.

The file is the user's; the plugin only reads it, on every request, so an edit
applies at the next page refresh or CLI run. Validation is all-or-nothing: one
broken rule refuses the whole file and no source runs.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

KINDS = ("command", "github_prs", "mcp_tool", "ai_usage")
MAX_SECTIONS = 20
ID_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
SECTION_KEYS = ("id", "kind", "title", "enabled", "refresh_minutes", "max_items", "timeout_s", "options")
# name: (default, low, high)
LIMITS = {"refresh_minutes": (15, 1, 1440), "max_items": (10, 1, 50), "timeout_s": (30, 1, 120)}
MERGE_METHODS = ("squash", "merge", "rebase")
PR_INCLUDE = ("author", "review_requested")
MCP_FIELDS = ("title", "detail", "badge", "time", "url")
DEFAULT_RELATIVE = Path("day-panel") / "sources.yaml"


class ConfigError(ValueError):
    """The sources file cannot be used; ``errors`` lists every broken rule."""

    def __init__(self, errors: List[str]):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


@dataclass
class Section:
    id: str
    kind: str
    title: str
    enabled: bool
    refresh_minutes: int
    max_items: int
    timeout_s: int
    options: Dict[str, Any]
    base_dir: Path
    key: str = ""  # id + hash of the definition: a changed definition is a new cache entry

    @property
    def merge(self) -> Dict[str, Any]:
        return self.options.get("merge") or {"enabled": False, "method": "squash"}


@dataclass
class Sources:
    path: Path
    sections: List[Section] = field(default_factory=list)

    @property
    def enabled(self) -> List[Section]:
        return [s for s in self.sections if s.enabled]

    def get(self, section_id: str) -> Optional[Section]:
        return next((s for s in self.enabled if s.id == section_id), None)


def hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home  # type: ignore

        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or Path.home() / ".hermes")


def sources_path(setting: Any, home: Optional[Path] = None) -> Path:
    """The ``sources_file`` setting, or ``$HERMES_HOME/day-panel/sources.yaml`` when empty."""
    home = home or hermes_home()
    if isinstance(setting, str) and setting.strip():
        raw = setting.strip().replace("$HERMES_HOME", str(home))
        return Path(os.path.expandvars(os.path.expanduser(raw)))
    return home / DEFAULT_RELATIVE


# ---------------------------------------------------------------- validation helpers

class _Check:
    def __init__(self) -> None:
        self.errors: List[str] = []

    def fail(self, where: str, message: str) -> None:
        self.errors.append(f"{where}: {message}")

    def int_in(self, where: str, name: str, value: Any, lo: int, hi: int) -> Optional[int]:
        if isinstance(value, bool) or not isinstance(value, int):
            self.fail(where, f"{name} must be a whole number between {lo} and {hi}")
            return None
        if not lo <= value <= hi:
            self.fail(where, f"{name} must be between {lo} and {hi} (got {value})")
            return None
        return value

    def text(self, where: str, name: str, value: Any, required: bool = False) -> Optional[str]:
        if not isinstance(value, str) or (required and not value.strip()):
            self.fail(where, f"{name} must be {'non-empty ' if required else ''}text")
            return None
        return value

    def text_list(self, where: str, name: str, value: Any, lo: int, hi: int,
                  allowed: Optional[tuple] = None) -> Optional[List[str]]:
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            self.fail(where, f"{name} must be a list of non-empty text")
            return None
        if not lo <= len(value) <= hi:
            self.fail(where, f"{name} must have between {lo} and {hi} entries (got {len(value)})")
            return None
        if allowed is not None:
            bad = [v for v in value if v not in allowed]
            if bad:
                self.fail(where, f"{name}: {', '.join(bad)} not allowed (allowed: {', '.join(allowed)})")
                return None
        return list(value)

    def mapping(self, where: str, name: str, value: Any) -> Optional[Dict[str, Any]]:
        if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
            self.fail(where, f"{name} must be a mapping")
            return None
        return value

    def only(self, where: str, name: str, value: Dict[str, Any], allowed: tuple) -> bool:
        unknown = [k for k in value if k not in allowed]
        for key in unknown:
            self.fail(where, f"unknown {name} {key!r} (allowed: {', '.join(allowed) or 'none'})")
        return not unknown


# ---------------------------------------------------------------- kind options

def _command_options(c: _Check, where: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if not c.only(where, "option", opts, ("argv",)):
        return out
    if "argv" not in opts:
        c.fail(where, "option argv is required (a list of strings, the program first)")
    else:
        argv = c.text_list(where, "argv", opts["argv"], 1, 50)
        if argv is not None:
            out["argv"] = argv
    return out


def _github_options(c: _Check, where: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"include": list(PR_INCLUDE), "exclude_owners": [],
                           "merge": {"enabled": False, "method": "squash"}}
    if not c.only(where, "option", opts, ("include", "exclude_owners", "merge")):
        return out
    if "include" in opts:
        include = c.text_list(where, "include", opts["include"], 1, 2, PR_INCLUDE)
        if include is not None:
            out["include"] = list(dict.fromkeys(include))
    if "exclude_owners" in opts:
        owners = c.text_list(where, "exclude_owners", opts["exclude_owners"], 0, 50)
        if owners is not None:
            out["exclude_owners"] = owners
    if "merge" in opts:
        merge = c.mapping(where, "merge", opts["merge"])
        if merge is not None and c.only(where, "merge key", merge, ("enabled", "method")):
            enabled = merge.get("enabled", False)
            if not isinstance(enabled, bool):
                c.fail(where, "merge.enabled must be true or false")
            method = merge.get("method", "squash")
            if method not in MERGE_METHODS:
                c.fail(where, f"merge.method must be one of {', '.join(MERGE_METHODS)}")
            out["merge"] = {"enabled": enabled is True, "method": method if method in MERGE_METHODS else "squash"}
    return out


def _mcp_options(c: _Check, where: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"args": {}, "fields": {"title": "title"}, "list_key": None}
    if not c.only(where, "option", opts, ("server", "tool", "args", "fields", "list_key")):
        return out
    for name in ("server", "tool"):
        if name not in opts:
            c.fail(where, f"option {name} is required")
        else:
            value = c.text(where, name, opts[name], required=True)
            if value is not None:
                out[name] = value.strip()
    if "args" in opts:
        args = c.mapping(where, "args", opts["args"])
        if args is not None:
            try:
                json.dumps(args)
                out["args"] = args
            except (TypeError, ValueError):
                c.fail(where, "args must hold only JSON values")
    if "fields" in opts:
        fields = c.mapping(where, "fields", opts["fields"])
        if fields is not None and c.only(where, "fields key", fields, MCP_FIELDS):
            if not all(isinstance(v, str) and v.strip() for v in fields.values()):
                c.fail(where, "fields values must be non-empty text (element keys)")
            elif "title" not in fields:
                c.fail(where, "fields must map title")
            else:
                out["fields"] = dict(fields)
    if "list_key" in opts:
        key = c.text(where, "list_key", opts["list_key"], required=True)
        if key is not None:
            out["list_key"] = key
    return out


def _usage_options(c: _Check, where: str, opts: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"providers": [], "warn_percent": 80}
    if not c.only(where, "option", opts, ("providers", "warn_percent")):
        return out
    if "providers" in opts:
        providers = c.text_list(where, "providers", opts["providers"], 0, 10)
        if providers is not None:
            out["providers"] = providers
    if "warn_percent" in opts:
        warn = c.int_in(where, "warn_percent", opts["warn_percent"], 1, 100)
        if warn is not None:
            out["warn_percent"] = warn
    return out


KIND_OPTIONS: Dict[str, Callable[[_Check, str, Dict[str, Any]], Dict[str, Any]]] = {
    "command": _command_options, "github_prs": _github_options, "mcp_tool": _mcp_options, "ai_usage": _usage_options,
}
KIND_OPTION_NAMES = {
    "command": ("argv",), "github_prs": ("include", "exclude_owners", "merge"),
    "mcp_tool": ("server", "tool", "args", "fields", "list_key"), "ai_usage": ("providers", "warn_percent"),
}


# ---------------------------------------------------------------- the file

def definition_key(section_id: str, kind: str, options: Dict[str, Any], limits: Dict[str, int]) -> str:
    blob = json.dumps({"kind": kind, "options": options, "limits": limits}, sort_keys=True, default=str)
    return f"{section_id}:{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


def parse(raw: Any, path: Path) -> Sources:
    c = _Check()
    if not isinstance(raw, dict):
        raise ConfigError([f"{path.name}: the file must be a mapping with a sections list"])
    if not c.only(path.name, "top-level key", raw, ("sections",)):
        raise ConfigError(c.errors)
    items = raw.get("sections")
    if not isinstance(items, list) or not items:
        raise ConfigError([f"{path.name}: sections must be a non-empty list"])
    if len(items) > MAX_SECTIONS:
        raise ConfigError([f"{path.name}: at most {MAX_SECTIONS} sections (got {len(items)})"])
    sections: List[Section] = []
    seen = set()
    for index, item in enumerate(items, 1):
        where = f"section {index}"
        if not isinstance(item, dict):
            c.fail(where, "must be a mapping")
            continue
        sid = item.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid):
            c.fail(where, "id must be 1-40 lowercase letters, digits or hyphens, starting with a letter")
            continue
        where = f"section {sid}"
        if sid in seen:
            c.fail(where, "id appears twice")
            continue
        seen.add(sid)
        if not c.only(where, "key", item, SECTION_KEYS):
            continue
        kind = item.get("kind")
        if kind not in KINDS:
            c.fail(where, f"unknown kind {kind!r} (allowed kinds: {', '.join(KINDS)})")
            continue
        title = item.get("title", sid)
        if not isinstance(title, str) or not title.strip():
            c.fail(where, "title must be non-empty text")
            title = sid
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            c.fail(where, "enabled must be true or false")
        limits: Dict[str, int] = {}
        for name, (default, lo, hi) in LIMITS.items():
            value = c.int_in(where, name, item[name], lo, hi) if name in item else default
            limits[name] = value if value is not None else default
        opts_raw = item.get("options", {})
        opts = c.mapping(where, "options", opts_raw) if opts_raw is not None else {}
        options = KIND_OPTIONS[kind](c, where, opts if opts is not None else {})
        sections.append(Section(id=sid, kind=kind, title=title.strip()[:120], enabled=enabled is True,
                                options=options, base_dir=path.parent,
                                key=definition_key(sid, kind, options, limits), **limits))
    if c.errors:
        raise ConfigError(c.errors)
    return Sources(path=path, sections=sections)


def load(path: Path) -> Sources:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigError([f"sources file not found: {path}"]) from None
    except OSError as exc:
        raise ConfigError([f"sources file unreadable: {path}: {exc.strerror or exc}"]) from None
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise ConfigError([f"{path.name} is not valid YAML{where}"]) from None
    return parse(raw, path)
