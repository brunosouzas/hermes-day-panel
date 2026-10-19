"""Refresh and cache: each section's last result, kept in memory, read again when it is old.

The cache is keyed by the section's id plus a hash of its definition, so editing a
section's command, options or limits starts it afresh. A read already running for
a key is joined. At most four reads run at once. A failed read keeps the previous
good items and marks the section stale. Nothing is written to disk.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional

from .dp_config import Section, Sources
from .dp_sources import ReadError

logger = logging.getLogger("hermes.plugins.day_panel")
MAX_PARALLEL = 4


@dataclass
class Entry:
    good: Optional[Dict[str, Any]] = None  # last successful result
    error: Optional[str] = None  # error of the latest read, None when it succeeded
    read_at: float = 0.0  # wall clock of the latest read
    read_mono: float = 0.0  # monotonic clock of the latest read, for the refresh interval
    duration_ms: int = 0


class Panel:
    def __init__(self, reader: Callable[[Section], Dict[str, Any]], clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time, max_parallel: int = MAX_PARALLEL):
        self.reader, self.clock, self.wall = reader, clock, wall
        self.pool = ThreadPoolExecutor(max_workers=max_parallel, thread_name_prefix="day-panel")
        self.lock = threading.Lock()
        self.entries: Dict[str, Entry] = {}
        self.running: Dict[str, Future] = {}
        self.current: set = set()

    # -- reading -----------------------------------------------------------------------------

    def _read(self, section: Section) -> None:
        started_wall, started = self.wall(), self.clock()
        good, error, logged = None, None, None
        try:
            good = self.reader(section)
        except ReadError as exc:
            error = str(exc) or "the read failed"
            logged = exc.log_message or error
        except Exception as exc:  # a bug in a source must not take the page down
            error = logged = f"the read failed ({type(exc).__name__})"
        duration = int((self.clock() - started) * 1000)
        if error:
            logger.warning("day-panel: section %s (%s) read failed: %s", section.id, section.kind, logged)
        with self.lock:
            self.running.pop(section.key, None)
            if section.key not in self.current:
                return  # the definition changed while this read ran: discard it
            entry = self.entries.setdefault(section.key, Entry())
            if good is not None:
                entry.good = good
            entry.error = error
            entry.read_at, entry.read_mono, entry.duration_ms = started_wall, started, duration

    def _start(self, section: Section) -> Future:
        """The running read for this definition, or a new one. Call with the lock held."""
        future = self.running.get(section.key)
        if future is None:
            future = self.pool.submit(self._read, section)
            self.running[section.key] = future
        return future

    def _due(self, section: Section) -> bool:
        entry = self.entries.get(section.key)
        return entry is None or self.clock() - entry.read_mono >= section.refresh_minutes * 60

    def sections(self, sources: Sources, force: Iterable[str] = (), force_all: bool = False,
                 wait: bool = True, only: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        """Views of the enabled sections in file order, reading those that are due or forced.
        With ``only``, nothing outside those ids is read (their cached views are still returned)."""
        forced = set(force)
        limit = set(only) if only is not None else None
        enabled = sources.enabled
        futures = []
        with self.lock:
            self.current = {s.key for s in enabled}
            for key in list(self.entries):
                if key not in self.current:
                    del self.entries[key]
            for section in enabled:
                if limit is not None and section.id not in limit:
                    continue
                if force_all or section.id in forced or self._due(section):
                    futures.append(self._start(section))
        if wait:
            for future in futures:
                future.result()
        with self.lock:
            return [self.view(s) for s in enabled]

    def invalidate(self, section: Section) -> None:
        with self.lock:
            entry = self.entries.get(section.key)
            if entry is not None:
                entry.read_mono = float("-inf")

    # -- views -------------------------------------------------------------------------------

    def view(self, section: Section) -> Dict[str, Any]:
        entry = self.entries.get(section.key) or Entry()
        if entry.error is None and entry.good is not None:
            status = "ok"
        elif entry.good is not None:
            status = "stale"
        else:
            status = "error"
        good = entry.good or {"items": [], "total": 0}
        out: Dict[str, Any] = {
            "id": section.id, "title": section.title, "kind": section.kind, "status": status,
            "items": good.get("items", []), "total": good.get("total", 0), "note": good.get("note"),
            "error": entry.error if status != "ok" else None,
            "read_at": datetime.fromtimestamp(entry.read_at, timezone.utc).isoformat(timespec="seconds")
            if entry.read_at else None,
            "duration_ms": entry.duration_ms,
            "merge": bool(section.kind == "github_prs" and section.merge.get("enabled")),
        }
        if entry.read_at == 0 and entry.error is None:
            out["error"] = "not read yet"
        return out

    def cached_item_refs(self, section: Section) -> List[Dict[str, Any]]:
        with self.lock:
            entry = self.entries.get(section.key)
            items = (entry.good or {}).get("items", []) if entry else []
            return [i["pr"] for i in items if isinstance(i.get("pr"), dict)]
