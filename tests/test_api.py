"""Spec today-page: backend routes, refresh, and the merge preview and confirmation."""

from __future__ import annotations

import json

from helpers import write_sources

HEAD = "abc1234def5678abc1234def5678abc1234def56"


def pr_item(repo="owner/repo", number=7, draft=False):
    return {"title": f"{repo}#{number} · T", "url": f"https://github.com/{repo}/pull/{number}",
            "pr": {"repo": repo, "number": number, "draft": draft}}


def setup_prs(api, merge=None, enabled=True):
    opts = {"merge": merge} if merge is not None else {}
    write_sources(api["path"].parent, [{"id": "prs", "kind": "github_prs", "enabled": enabled, "options": opts},
                                       {"id": "usage", "kind": "ai_usage"}])
    api["results"]["prs"] = {"items": [pr_item(), pr_item(number=8, draft=True)], "total": 2}
    api["client"].get(f"{api['base']}/sections")


def gh_view(draft=False, state="OPEN", merge_code=0, merge_err=""):
    def answer(argv):
        if argv[1:3] == ["pr", "view"]:
            return 0, json.dumps({"number": int(argv[3]), "title": "T", "baseRefName": "main", "headRefOid": HEAD,
                                  "isDraft": draft, "state": state, "url": "https://github.com/owner/repo/pull/7"}), ""
        if argv[1:3] == ["pr", "merge"]:
            return merge_code, "", merge_err
        raise AssertionError(argv)
    return answer


def preview(api, number=7):
    return api["client"].post(f"{api['base']}/sections/prs/merge/preview", json={"repo": "owner/repo", "number": number})


def confirm(api, token):
    return api["client"].post(f"{api['base']}/merge/confirm", json={"token": token})


def merges(api):
    return [c for c in api["gh_calls"] if c[1:3] == ["pr", "merge"]]


# ---------------------------------------------------------------- sections and refresh

def test_sections_shown_with_errors(api):
    write_sources(api["path"].parent, [{"id": "prs", "kind": "github_prs"}, {"id": "usage", "kind": "ai_usage"}])
    api["results"]["prs"] = {"items": [{"title": "a"}, {"title": "b"}], "total": 2}
    api["results"]["usage"] = api["ReadError"]("no credential")
    body = api["client"].get(f"{api['base']}/sections").json()
    assert body["errors"] == []
    assert [(s["id"], s["status"], len(s["items"])) for s in body["sections"]] == [("prs", "ok", 2), ("usage", "error", 0)]
    assert body["sections"][1]["error"] == "no credential"


def test_invalid_sources_file(api):
    write_sources(api["path"].parent, [{"id": "x", "kind": "calendar"}])
    body = api["client"].get(f"{api['base']}/sections").json()
    assert body["sections"] == [] and "unknown kind" in body["errors"][0]


def test_refresh_one_section(api):
    write_sources(api["path"].parent, [{"id": "prs", "kind": "github_prs"}, {"id": "usage", "kind": "ai_usage"}])
    api["client"].get(f"{api['base']}/sections")
    api["reads"].clear()
    view = api["client"].post(f"{api['base']}/sections/prs/refresh").json()
    assert api["reads"] == ["prs"] and view["id"] == "prs" and view["read_at"]


def test_refresh_all(api):
    write_sources(api["path"].parent, [{"id": "prs", "kind": "github_prs"}, {"id": "usage", "kind": "ai_usage"}])
    api["client"].get(f"{api['base']}/sections")
    api["reads"].clear()
    api["client"].post(f"{api['base']}/refresh")
    assert sorted(api["reads"]) == ["prs", "usage"]


def test_unknown_section_id(api):
    write_sources(api["path"].parent, [{"id": "prs", "kind": "github_prs"},
                                       {"id": "off", "kind": "ai_usage", "enabled": False}])
    for sid in ("..%2Fetc", "nope", "off"):
        assert api["client"].post(f"{api['base']}/sections/{sid}/refresh").status_code == 404
    assert api["reads"] == []


# ---------------------------------------------------------------- merge

def test_merge_off_by_default(api):
    setup_prs(api)
    [prs, _] = api["client"].get(f"{api['base']}/sections").json()["sections"]
    assert prs["merge"] is False
    response = preview(api)
    assert response.status_code == 409 and api["gh_calls"] == []


def test_merge_draft_refused(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view(draft=True)
    response = preview(api, number=8)
    assert response.status_code == 409 and response.json()["detail"]["message"] == "draft pull requests are not merged"


def test_merge_unknown_pr_refused(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    assert preview(api, number=99).status_code == 404
    assert api["client"].post(f"{api['base']}/sections/prs/merge/preview",
                              json={"repo": "../x", "number": 7}).status_code == 400
    assert api["gh_calls"] == []


def test_merge_confirmed(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    p = preview(api).json()
    assert (p["repo"], p["number"], p["head"], p["method"], p["base"]) == ("owner/repo", 7, HEAD, "squash", "main")
    response = confirm(api, p["token"])
    assert response.status_code == 200 and response.json()["merged"] is True
    assert merges(api) == [["gh", "pr", "merge", "7", "--repo", "owner/repo", "--squash", "--match-head-commit", HEAD]]


def test_merge_token_used_twice(api):
    setup_prs(api, merge={"enabled": True, "method": "merge"})
    api["gh"] = gh_view()
    token = preview(api).json()["token"]
    assert confirm(api, token).status_code == 200
    assert confirm(api, token).status_code == 409 and len(merges(api)) == 1


def test_merge_token_expired(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    token = preview(api).json()["token"]
    api["clock"].now += 121
    assert confirm(api, token).status_code == 409 and merges(api) == []


def test_merge_section_disabled_after_preview(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    token = preview(api).json()["token"]
    setup_prs(api, merge={"enabled": True}, enabled=False)
    assert confirm(api, token).status_code == 409 and merges(api) == []


def test_merge_turned_off_after_preview(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    token = preview(api).json()["token"]
    setup_prs(api, merge={"enabled": False})
    assert confirm(api, token).status_code == 409 and merges(api) == []
    setup_prs(api, merge={"enabled": True})
    assert confirm(api, token).status_code == 409 and merges(api) == []  # the token was consumed


def test_merge_method_changed_after_preview(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    token = preview(api).json()["token"]
    setup_prs(api, merge={"enabled": True, "method": "rebase"})
    assert confirm(api, token).status_code == 409 and merges(api) == []


def test_merge_head_moved(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view(merge_code=1, merge_err="GraphQL: Head branch was modified. Review and try the merge again.")
    token = preview(api).json()["token"]
    response = confirm(api, token)
    assert response.status_code == 502 and "Head branch was modified" in response.json()["detail"]["message"]
    assert "status 1" in response.json()["detail"]["message"]
    assert confirm(api, token).status_code == 409 and len(merges(api)) == 1


def test_merge_one_at_a_time(api):
    setup_prs(api, merge={"enabled": True})
    api["gh"] = gh_view()
    first, second = preview(api).json()["token"], preview(api).json()["token"]
    api["merger"].merging.acquire()
    try:
        response = confirm(api, second)
        assert response.status_code == 409 and response.json()["detail"]["code"] == "in_progress"
    finally:
        api["merger"].merging.release()
    assert confirm(api, first).status_code == 200 and len(merges(api)) == 1
