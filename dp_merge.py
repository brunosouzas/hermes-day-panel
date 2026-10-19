"""Pull request merge from the Today page: opt-in, previewed, confirmed once, head-guarded.

A preview reads the pull request now and returns a single-use token bound to the
section, the pull request, its head commit and the merge method, valid for 120
seconds. Confirming consumes the token first, re-reads the sources file, and runs
``gh pr merge --match-head-commit`` so GitHub refuses if the branch moved.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .dp_config import Section, Sources
from .dp_sources import ReadError, Runner, find_tool, last_line, run_capped

TOKEN_TTL_S = 120
GH_TIMEOUT_S = 60
# GitHub owners: letters, digits, hyphens; repositories also allow . and _, but never "." or "..".
REPO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/(?!\.\.?$)[A-Za-z0-9_.-]{1,100}$")
VIEW_FIELDS = "number,title,baseRefName,headRefOid,isDraft,state,url"


class MergeError(RuntimeError):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


@dataclass
class Pending:
    section_id: str
    repo: str
    number: int
    head: str
    method: str
    expires: float


class Merger:
    def __init__(self, runner: Runner = run_capped, gh: Optional[str] = None,
                 clock: Callable[[], float] = time.monotonic):
        self.runner, self.gh, self.clock = runner, gh, clock
        self.tokens: Dict[str, Pending] = {}
        self.lock = threading.Lock()
        self.merging = threading.Lock()

    def _gh(self) -> str:
        gh = self.gh or find_tool("gh")
        if not gh:
            raise MergeError(502, "gh_missing", "the gh CLI was not found")
        return gh

    @staticmethod
    def _eligible(section: Optional[Section]) -> Section:
        if section is None or section.kind != "github_prs" or not section.merge.get("enabled"):
            raise MergeError(409, "merge_disabled", "merge is not enabled for this section")
        return section

    def preview(self, section: Optional[Section], repo: Any, number: Any, known: list) -> Dict[str, Any]:
        section = self._eligible(section)
        if not isinstance(repo, str) or not REPO_RE.match(repo) or isinstance(number, bool) or not isinstance(number, int):
            raise MergeError(400, "invalid", "repo must be owner/name and number a whole number")
        if not any(r.get("repo") == repo and r.get("number") == number for r in known):
            raise MergeError(404, "not_found", "that pull request is not in this section")
        try:
            code, stdout, stderr = self.runner([self._gh(), "pr", "view", str(number), "--repo", repo,
                                                "--json", VIEW_FIELDS], timeout=GH_TIMEOUT_S)
        except ReadError as exc:
            raise MergeError(502, "gh_failed", str(exc)) from None
        if code != 0:
            raise MergeError(502, "gh_failed", f"gh exited with status {code}: {last_line(stderr)}")
        try:
            pr = json.loads(stdout)
        except ValueError:
            raise MergeError(502, "gh_failed", "gh did not return JSON") from None
        if pr.get("isDraft"):
            raise MergeError(409, "draft", "draft pull requests are not merged")
        if pr.get("state") != "OPEN":
            raise MergeError(409, "not_open", f"the pull request is {str(pr.get('state')).lower()}")
        head = pr.get("headRefOid")
        if not isinstance(head, str) or not re.match(r"^[0-9a-f]{7,64}$", head):
            raise MergeError(502, "gh_failed", "gh did not return the head commit")
        method = section.merge.get("method", "squash")
        token = secrets.token_urlsafe(18)
        with self.lock:
            now = self.clock()
            self.tokens = {k: v for k, v in self.tokens.items() if v.expires > now}
            self.tokens[token] = Pending(section.id, repo, number, head, method, now + TOKEN_TTL_S)
        return {"token": token, "repo": repo, "number": number, "title": str(pr.get("title") or "")[:300],
                "base": str(pr.get("baseRefName") or ""), "head": head, "method": method,
                "url": pr.get("url") if isinstance(pr.get("url"), str) else None, "expires_in": TOKEN_TTL_S}

    def confirm(self, token: Any, load_sources: Callable[[], Sources]) -> Dict[str, Any]:
        with self.lock:
            pending = self.tokens.pop(token, None) if isinstance(token, str) else None  # consumed, whatever follows
        if pending is None or self.clock() > pending.expires:
            raise MergeError(409, "token_invalid", "this confirmation expired or was already used; preview again")
        try:
            sources = load_sources()
        except Exception:
            raise MergeError(409, "sources_invalid", "the sources file no longer validates; nothing was merged") from None
        section = self._eligible(sources.get(pending.section_id))
        if section.merge.get("method") != pending.method:
            raise MergeError(409, "changed", "the merge method changed after the preview; preview again")
        if not self.merging.acquire(blocking=False):
            raise MergeError(409, "in_progress", "another merge is running")
        try:
            argv = [self._gh(), "pr", "merge", str(pending.number), "--repo", pending.repo, f"--{pending.method}",
                    "--match-head-commit", pending.head]
            try:
                code, stdout, stderr = self.runner(argv, timeout=GH_TIMEOUT_S)
            except ReadError as exc:
                raise MergeError(502, "merge_failed", str(exc)) from None
        finally:
            self.merging.release()
        if code != 0:
            raise MergeError(502, "merge_failed", f"gh exited with status {code}: {last_line(stderr) or 'no error output'}")
        return {"merged": True, "repo": pending.repo, "number": pending.number, "method": pending.method,
                "section": pending.section_id}
