"""
requests-based transport + client factory for the Langflow Darkmoon components.

Kept out of ``darkmoon_client`` so the client stays dependency free and
unit-testable without ``requests``. The transport never raises on a non-2xx
status: it returns the real status and parsed body so the client surfaces the
API's own ``detail`` rather than a local secret.
"""
from __future__ import annotations

from typing import Any, Dict

from lfx_darkmoon.components.darkmoon.darkmoon_client import DarkmoonClient, HttpResponse

DEFAULT_TIMEOUT = 60


def requests_transport(opts: Dict[str, Any]) -> HttpResponse:
    import requests  # imported lazily so tests need no network stack

    method = str(opts.get("method", "GET")).upper()
    url = opts["url"]
    headers = opts.get("headers") or {}
    body = opts.get("body")
    try:
        resp = requests.request(
            method,
            url,
            headers=headers,
            json=body if body is not None else None,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        return HttpResponse(status_code=0, body={"detail": f"Request to Darkmoon failed: {exc}"})
    try:
        parsed: Any = resp.json()
    except ValueError:
        parsed = resp.text
    return HttpResponse(status_code=resp.status_code, body=parsed)


def logged_in_client(base_url: str, username: str, password: str) -> DarkmoonClient:
    """Build a DarkmoonClient over the requests transport and authenticate it."""
    client = DarkmoonClient(base_url, requests_transport)
    client.login(username, password)
    return client
