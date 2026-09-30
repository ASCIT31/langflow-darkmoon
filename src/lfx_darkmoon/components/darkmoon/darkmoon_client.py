"""
DarkmoonClient - dependency-free client for the Darkmoon Dashboard API.

This module deliberately has NO Dify or third-party imports. It receives an
injected HTTP function so it can run both inside a Dify tool (wrapping
``requests``) and in a plain test harness (wrapping a mock). This keeps the
component logic free of heavy runtime dependencies and lets the integration be
unit-tested end to end without a live Darkmoon instance.

The Darkmoon Dashboard API is a versioned FastAPI service (self-hosted). The
endpoints used here mirror the ones the maintained n8n and Activepieces
Darkmoon integrations use, read from Dark-Moon-Front-API (branch dev):

    POST   /api/v1/auth/login                  -> { token, ... }
    POST   /api/v1/run/campaign                -> { run_id, pid, command }
    GET    /api/v1/run/logs/{run_id}           -> { data: events[], total }
    DELETE /api/v1/run/{run_id}/stop           -> { message, run_id }
    GET    /api/v1/campaigns                   -> { data: campaigns[], total }
    GET    /api/v1/vulnerabilities?campaign_id -> { data, total, stats }
    GET    /api/v1/campaigns/{id}/report       -> { content, format }
    GET    /api/v1/pull-requests?campaign_id   -> { data: PullRequest[], total }

There is no public hosted endpoint; every deployment is self-hosted, so the
base URL is always supplied by the operator.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

# The exact PR states the store recognises (pr_store.PR_STATES).
PR_STATES = ("proposed", "draft", "open", "merged", "closed", "error")

# Run-log event types that mark a run as finished.
_TERMINAL_TYPES = frozenset({"run_completed", "run_error"})


@dataclass
class HttpResponse:
    """Raw HTTP result the injected transport must return."""

    status_code: int
    body: Any


# Injected transport. Must return the raw status and parsed JSON body, and must
# NEVER raise on a non-2xx status - the client inspects status_code itself so
# error messages carry the API's own ``detail`` (and never a local secret).
HttpFn = Callable[[Dict[str, Any]], HttpResponse]


class DarkmoonError(Exception):
    """Error carrying the API's own detail plus the HTTP status code."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _detail(res: HttpResponse, fallback: str) -> str:
    body = res.body if res else None
    if isinstance(body, dict):
        d = body.get("detail", body.get("message"))
        if isinstance(d, str) and d:
            return d
    return fallback


def _data_list(res: HttpResponse) -> List[Any]:
    body = res.body
    if isinstance(body, dict) and isinstance(body.get("data"), list):
        return body["data"]
    return []


class DarkmoonClient:
    """A thin, transport-injected client over the Darkmoon Dashboard API."""

    def __init__(self, base_url: str, http: HttpFn) -> None:
        # Strip trailing slashes so path joins stay clean.
        self.base_url = base_url.rstrip("/")
        self._http = http
        self._token: Optional[str] = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _auth_headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Content-Type": "application/json"}
        if self._token:
            h["Authorization"] = f"Bearer {self._token}"
        return h

    # -- auth ---------------------------------------------------------------
    def login(self, username: str, password: str) -> str:
        """Authenticate and cache the JWT for subsequent calls."""
        res = self._http(
            {
                "method": "POST",
                "url": self._url("/api/v1/auth/login"),
                "headers": {"Content-Type": "application/json"},
                "body": {"username": username, "password": password},
            }
        )
        token = res.body.get("token") if isinstance(res.body, dict) else None
        if res.status_code != 200 or not token:
            raise DarkmoonError(_detail(res, "Darkmoon login failed"), res.status_code)
        self._token = token
        return token

    # -- campaigns ----------------------------------------------------------
    def list_campaigns(self) -> List[Dict[str, Any]]:
        res = self._http(
            {"method": "GET", "url": self._url("/api/v1/campaigns"), "headers": self._auth_headers()}
        )
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, "Failed to list campaigns"), res.status_code)
        return _data_list(res)

    # -- run ----------------------------------------------------------------
    def run_campaign(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Start a pentest in the background. Returns the run handle."""
        res = self._http(
            {
                "method": "POST",
                "url": self._url("/api/v1/run/campaign"),
                "headers": self._auth_headers(),
                "body": params,
            }
        )
        run_id = res.body.get("run_id") if isinstance(res.body, dict) else None
        if res.status_code >= 400 or not run_id:
            raise DarkmoonError(_detail(res, "Failed to start pentest run"), res.status_code)
        return res.body

    def get_run_log(self, run_id: str) -> List[Dict[str, Any]]:
        res = self._http(
            {
                "method": "GET",
                "url": self._url(f"/api/v1/run/logs/{quote(run_id, safe='')}"),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code == 404:
            return []
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, "Failed to read run log"), res.status_code)
        return _data_list(res)

    def stop_run(self, run_id: str) -> None:
        self._http(
            {
                "method": "DELETE",
                "url": self._url(f"/api/v1/run/{quote(run_id, safe='')}/stop"),
                "headers": self._auth_headers(),
            }
        )

    def wait_for_run(
        self,
        run_id: str,
        poll_s: float = 3.0,
        timeout_s: float = 30 * 60,
        on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
        sleep: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        """Poll the run's JSONL log until a terminal event or the timeout.

        The log is the API's single source of truth for run state: no terminal
        event means the run is still going. Never loops forever.
        """
        _sleep = sleep or time.sleep
        start = time.monotonic()
        seen = 0
        while time.monotonic() - start < timeout_s:
            events = self.get_run_log(run_id)
            if on_event:
                for e in events[seen:]:
                    on_event(e)
            seen = len(events)
            terminal = next((e for e in events if e.get("type") in _TERMINAL_TYPES), None)
            if terminal is not None:
                return {"events": events, "terminal": terminal, "timed_out": False}
            _sleep(poll_s)
        events = self.get_run_log(run_id)
        return {"events": events, "terminal": None, "timed_out": True}

    def resolve_run_campaign(
        self, before_ids: "set[str]", target_host: str
    ) -> Optional[Dict[str, Any]]:
        """Resolve the campaign produced by a run.

        The trigger returns a run_id, not a campaign_id - the agent mints the
        campaign inside the run. We diff the campaign set captured before the
        run against the set after it, preferring a new campaign whose id matches
        the target host, and fall back to the newest campaign otherwise.
        """
        campaigns = self.list_campaigns()
        host = (target_host or "").strip().lower()

        def by_date(c: Dict[str, Any]) -> str:
            return str(c.get("date") or "")

        fresh = [c for c in campaigns if c.get("id") not in before_ids]
        if len(fresh) == 1:
            return fresh[0]
        if len(fresh) > 1:
            fresh.sort(key=by_date, reverse=True)
            if host:
                for c in fresh:
                    if host in str(c.get("id", "")).lower():
                        return c
            return fresh[0]
        if not campaigns:
            return None
        return sorted(campaigns, key=by_date, reverse=True)[0]

    # -- findings / report --------------------------------------------------
    def get_findings(self, campaign_id: str) -> Dict[str, Any]:
        res = self._http(
            {
                "method": "GET",
                "url": self._url(
                    f"/api/v1/vulnerabilities?campaign_id={quote(campaign_id, safe='')}"
                ),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, "Failed to fetch findings"), res.status_code)
        body = res.body if isinstance(res.body, dict) else {}
        return {
            "data": body.get("data") or [],
            "total": body.get("total") or 0,
            "stats": body.get("stats") or {},
        }

    def get_report(self, campaign_id: str) -> Dict[str, Any]:
        res = self._http(
            {
                "method": "GET",
                "url": self._url(f"/api/v1/campaigns/{quote(campaign_id, safe='')}/report"),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, "Failed to fetch report"), res.status_code)
        body = res.body if isinstance(res.body, dict) else {}
        return {"content": body.get("content") or "", "format": body.get("format") or "markdown"}

    # -- pull requests (read-only) -----------------------------------------
    def list_pull_requests(self, campaign_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List fix pull requests. campaign_id is the ONLY server-side filter."""
        q = f"?campaign_id={quote(campaign_id, safe='')}" if campaign_id else ""
        res = self._http(
            {
                "method": "GET",
                "url": self._url(f"/api/v1/pull-requests{q}"),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, "Failed to list pull requests"), res.status_code)
        return _data_list(res)

    def get_pull_request(self, pr_id: str) -> Dict[str, Any]:
        res = self._http(
            {
                "method": "GET",
                "url": self._url(f"/api/v1/pull-requests/{quote(pr_id, safe='')}"),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code != 200:
            raise DarkmoonError(_detail(res, f"Pull request {pr_id} not found"), res.status_code)
        body = res.body if isinstance(res.body, dict) else {}
        return body.get("data") or {}

    def get_pull_requests_for_finding(self, vuln_id: str) -> List[Dict[str, Any]]:
        res = self._http(
            {
                "method": "GET",
                "url": self._url(f"/api/v1/pull-requests/finding/{quote(vuln_id, safe='')}"),
                "headers": self._auth_headers(),
            }
        )
        if res.status_code != 200:
            raise DarkmoonError(
                _detail(res, f"Failed to fetch pull requests for finding {vuln_id}"),
                res.status_code,
            )
        return _data_list(res)

    @staticmethod
    def filter_pull_requests(
        prs: List[Dict[str, Any]],
        state: Optional[List[str]] = None,
        provider: Optional[str] = None,
        repository: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Client-side narrowing. The API does not filter by these fields."""
        out = prs
        if state:
            want = {s.lower() for s in state}
            out = [p for p in out if str(p.get("state", "")).lower() in want]
        if provider:
            p = provider.lower()
            out = [x for x in out if str(x.get("provider", "")).lower() == p]
        if repository:
            r = repository.lower()
            out = [x for x in out if r in str(x.get("repo", "")).lower()]
        return out

    def wait_for_pull_requests(
        self,
        campaign_id: str,
        min_count: int = 1,
        poll_s: float = 5.0,
        timeout_s: float = 5 * 60,
        sleep: Optional[Callable[[float], None]] = None,
    ) -> Dict[str, Any]:
        _sleep = sleep or time.sleep
        start = time.monotonic()
        prs: List[Dict[str, Any]] = []
        while time.monotonic() - start < timeout_s:
            prs = self.list_pull_requests(campaign_id)
            if len(prs) >= min_count:
                return {"pull_requests": prs, "timed_out": False}
            _sleep(poll_s)
        prs = self.list_pull_requests(campaign_id)
        return {"pull_requests": prs, "timed_out": len(prs) < min_count}

    @staticmethod
    def validate_remediation(remediate: bool, credential_id: Optional[str]) -> None:
        """Guard for remediation (Pro) parameters.

        When remediation is enabled a credential reference (an opaque vault id,
        NOT a token) is required, validated before any request so a run is never
        started half-configured.
        """
        if remediate and not str(credential_id or "").strip():
            raise DarkmoonError(
                "Remediation is enabled but no credential reference was provided. "
                "Set the opaque Darkmoon credential reference (a vault id, not a token) "
                "so the remediation agent can prepare a fix pull request for review."
            )
