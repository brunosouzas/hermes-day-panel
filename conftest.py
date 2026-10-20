"""Test bootstrap: load the repository root as the package ``day_panel``, as Hermes does."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
collect_ignore = [p.name for p in REPO_ROOT.glob("*.py") if p.name != "conftest.py"] + ["dashboard", "desktop"]


def _hermes_yaml() -> None:
    """Outside Hermes, stand in for core's ``hermes_yaml`` (ruamel.yaml, as in core)."""
    try:
        import hermes_yaml  # noqa: F401  # type: ignore
    except ImportError:
        sys.path.insert(0, str(REPO_ROOT / "tests" / "stubs"))


def _load() -> None:
    if "day_panel" in sys.modules:
        return
    spec = importlib.util.spec_from_file_location("day_panel", REPO_ROOT / "__init__.py",
                                                  submodule_search_locations=[str(REPO_ROOT)])
    module = importlib.util.module_from_spec(spec)
    sys.modules["day_panel"] = module
    spec.loader.exec_module(module)


_hermes_yaml()
_load()
