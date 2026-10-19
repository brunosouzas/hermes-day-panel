"""Demo source for hermes-day-panel: prints sample items for one section, with no login or network.

Usage: demo_source.py cards|prs|pipelines|routine|usage

Every section of examples/demo/sources.yaml runs this script with a different argument. Copy it as a
starting point for your own source: print one JSON object with an "items" list, and the page shows it.
Item fields: title (required), url, detail, badge, time (ISO 8601), time_label, tone (good, warn, bad,
muted) and progress (0-100). Times are relative to now, so the demo always looks current.
"""
import json
import sys
from datetime import datetime, timedelta, timezone

NOW = datetime.now(timezone.utc)


def at(**delta):
    return (NOW + timedelta(**delta)).isoformat(timespec="seconds")


SECTIONS = {
    "cards": {
        "items": [
            {"title": "#142 · Add retry to the payments client", "url": "https://example.com/board/142",
             "detail": "Doing · payments", "badge": "assigned to you"},
            {"title": "#139 · Rotate the staging certificates", "url": "https://example.com/board/139",
             "detail": "To Do · platform", "badge": "assigned to you"},
            {"title": "#131 · Write the onboarding guide", "url": "https://example.com/board/131",
             "detail": "Doing · docs"},
        ],
        "total": 7,
        "note": "Showing your cards first.",
    },
    "prs": {
        "items": [
            {"title": "acme/payments#88 · Retry idempotent calls", "url": "https://example.com/acme/payments/pull/88",
             "badge": "review requested", "time": at(minutes=-25), "time_label": "updated"},
            {"title": "acme/web#412 · Dark mode for settings", "url": "https://example.com/acme/web/pull/412",
             "badge": "draft", "time": at(hours=-5), "time_label": "updated"},
            {"title": "acme/infra#57 · Pin the base image", "url": "https://example.com/acme/infra/pull/57",
             "time": at(days=-2), "time_label": "updated"},
        ],
    },
    "pipelines": {
        "items": [
            {"title": "web-deploy #1204", "url": "https://example.com/ci/1204", "detail": "main",
             "badge": "succeeded", "tone": "good", "time": at(minutes=-12)},
            {"title": "payments-tests #881", "url": "https://example.com/ci/881", "detail": "feature/retry",
             "badge": "failed", "tone": "bad", "time": at(hours=-1)},
            {"title": "nightly-backup #310", "detail": "main", "badge": "running", "tone": "warn",
             "progress": 45, "time": at(minutes=-3), "time_label": "started"},
        ],
    },
    "routine": {
        "items": [
            {"title": "Stand-up", "detail": "15 min", "tone": "good"},
            {"title": "Deep work: payments retry", "detail": "2 h"},
            {"title": "Review open pull requests", "detail": "30 min"},
            {"title": "Walk", "tone": "muted"},
        ],
    },
    "usage": {
        "items": [
            {"title": "Assistant · Current session", "detail": "68% used", "progress": 68,
             "time": at(minutes=40), "time_label": "resets"},
            {"title": "Assistant · Week", "detail": "86% used", "progress": 86, "tone": "warn", "badge": "high",
             "time": at(days=3, hours=2), "time_label": "resets"},
            {"title": "Coding agent · Week", "detail": "12% used · Plus", "progress": 12,
             "time": at(days=5), "time_label": "resets"},
        ],
    },
}

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else ""
    if name not in SECTIONS:
        print(f"usage: demo_source.py {'|'.join(SECTIONS)}", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(SECTIONS[name]))
