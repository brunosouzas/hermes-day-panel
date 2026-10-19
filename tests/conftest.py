"""Shared fixtures: the page backend mounted on a FastAPI app with fake sources and gh."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

API_FILE = Path(__file__).resolve().parent.parent / "dashboard" / "plugin_api.py"


def load_api():
    spec = importlib.util.spec_from_file_location("day_panel_plugin_api", API_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


from helpers import Clock  # noqa: E402


@pytest.fixture
def api(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    module = load_api()
    config = module._mod("dp_config")
    panel_mod = module._mod("dp_panel")
    merge_mod = module._mod("dp_merge")
    state = {"path": tmp_path / "sources.yaml", "reads": [], "results": {}, "clock": Clock()}

    def reader(section):
        state["reads"].append(section.id)
        answer = state["results"].get(section.id, {"items": [], "total": 0})
        if isinstance(answer, BaseException):
            raise answer
        return answer

    state["panel"] = panel_mod.Panel(reader, clock=state["clock"])
    state["gh_calls"] = []
    state["gh"] = lambda argv: (0, "{}", "")

    def gh_runner(argv, timeout=0, **_):
        state["gh_calls"].append(list(argv))
        return state["gh"](list(argv))

    state["merger"] = merge_mod.Merger(runner=gh_runner, gh="gh", clock=state["clock"])
    module.path_provider = lambda: state["path"]
    module.panel_provider = lambda: state["panel"]
    module.merger_provider = lambda: state["merger"]
    app = FastAPI()
    app.include_router(module.router, prefix="/api/plugins/day-panel")
    state.update(client=TestClient(app), base="/api/plugins/day-panel", module=module, config=config,
                 ReadError=module._mod("dp_sources").ReadError)
    return state
