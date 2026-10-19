"""Shared test helpers: write a sources file, build sections, fake program runners."""

from __future__ import annotations

import json
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import yaml

from day_panel import dp_config


def write_sources(folder: Path, sections: List[Dict[str, Any]], name: str = "sources.yaml") -> Path:
    path = folder / name
    path.write_text(yaml.safe_dump({"sections": sections}, sort_keys=False), encoding="utf-8")
    return path


def section(tmp_path: Path, **raw: Any) -> dp_config.Section:
    raw.setdefault("id", "s")
    return dp_config.parse({"sections": [raw]}, tmp_path / "sources.yaml").sections[0]


def script(tmp_path: Path, body: str, name: str = "src.py") -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(body), encoding="utf-8")
    return path


def py(path: Path) -> List[str]:
    return [sys.executable, str(path)]


class FakeRunner:
    """Answers by argv: a function of argv returning (code, stdout, stderr); records each call."""

    def __init__(self, answer: Callable[[List[str]], Any]):
        self.answer, self.calls = answer, []

    def __call__(self, argv: List[str], timeout: float = 0, cwd: Optional[Path] = None, stdin: Optional[str] = None,
                 **_: Any):
        self.calls.append({"argv": list(argv), "timeout": timeout, "cwd": cwd, "stdin": stdin})
        out = self.answer(list(argv))
        if isinstance(out, BaseException):
            raise out
        return out


class Clock:
    def __init__(self, now: float = 1000.0):
        self.now = now

    def __call__(self) -> float:
        return self.now


def ok(data: Any):
    return 0, json.dumps(data), ""
