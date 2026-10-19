"""The public demo (examples/demo) validates and every enabled section reads ok offline."""
from pathlib import Path

from day_panel import dp_config, dp_sources
from day_panel.dp_panel import Panel

DEMO = Path(__file__).resolve().parents[1] / "examples" / "demo" / "sources.yaml"


def test_demo_validates_and_reads_ok_offline():
    sources = dp_config.load(DEMO)  # raises SourcesError when the file breaks a rule
    enabled = [s for s in sources.sections if s.enabled]
    assert [s.id for s in enabled] == ["cards", "prs", "pipelines", "routine", "usage"]
    views = Panel(dp_sources.read).sections(sources)
    assert [v["status"] for v in views] == ["ok"] * len(enabled), [v.get("error") for v in views]
    by_id = {v["id"]: v for v in views}
    assert by_id["cards"]["total"] == 7
    tones = {i.get("tone") for i in by_id["pipelines"]["items"]}
    assert {"good", "bad", "warn"} <= tones
    assert all(0 <= i["progress"] <= 100 and i["time_label"] == "resets" for i in by_id["usage"]["items"])
    # the disabled ai_usage example is valid too, so turning it on only needs providers
    my_usage = next(s for s in sources.sections if s.id == "my-usage")
    assert my_usage.kind == "ai_usage" and my_usage.options["labels"] == {}
