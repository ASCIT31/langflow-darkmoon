"""
Unit tests for DarkmoonClient using a programmable mock transport.

These cover the paths that are awkward to trigger against a live server:
remediation validation, HTTP error mapping (401/403/404/500), empty and
malformed responses, wait/poll timeouts, and - importantly - that no secret
(JWT, password, or credential value) ever leaks into an error message.

Run:  pytest -q   (no server required)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from lfx_darkmoon.components.darkmoon.darkmoon_client import DarkmoonClient, DarkmoonError, HttpResponse  # noqa: E402


def mock_http(routes, sink=None):
    """routes: list of (predicate(opts)->bool, HttpResponse | callable(opts)->HttpResponse)."""

    def http(opts):
        if sink is not None:
            sink.append(opts)
        for pred, resp in routes:
            if pred(opts):
                return resp(opts) if callable(resp) else resp
        return HttpResponse(200, {"data": [], "total": 0})

    return http


def ok(body):
    return HttpResponse(200, body)


def err(code, detail):
    return HttpResponse(code, {"detail": detail})


NO_SLEEP = lambda _s: None  # noqa: E731


# -- remediation validation ------------------------------------------------
def test_validate_remediation_requires_credential():
    with pytest.raises(DarkmoonError) as ei:
        DarkmoonClient.validate_remediation(True, "")
    assert "credential reference" in str(ei.value).lower()


def test_validate_remediation_off_is_ok():
    DarkmoonClient.validate_remediation(False, None)  # no raise


def test_validate_remediation_with_credential_is_ok():
    DarkmoonClient.validate_remediation(True, "cred_x")  # no raise


# -- run body shape --------------------------------------------------------
def test_run_without_remediation_sends_no_remediation_fields():
    sink = []
    c = DarkmoonClient(
        "http://x",
        mock_http([(lambda o: o["url"].endswith("/run/campaign"), ok({"run_id": "r1", "pid": 1}))], sink),
    )
    c.run_campaign({"target": "t"})
    body = sink[0]["body"]
    assert "remediate" not in body and "credential_id" not in body


def test_run_with_remediation_sends_opaque_credential_no_raw_secret():
    sink = []
    c = DarkmoonClient(
        "http://x",
        mock_http([(lambda o: o["url"].endswith("/run/campaign"), ok({"run_id": "r2", "pid": 2}))], sink),
    )
    c.run_campaign({"target": "t", "remediate": True, "credential_id": "cred_ref_9", "git_repo": "https://g/r"})
    body = sink[0]["body"]
    assert body["credential_id"] == "cred_ref_9" and body["remediate"] is True
    import json

    serialized = json.dumps(body)
    assert not any(k in serialized.lower() for k in ('"token"', '"password"', '"secret"', '"api_key"'))


# -- empty / malformed responses ------------------------------------------
def test_empty_pr_list():
    c = DarkmoonClient("http://x", mock_http([(lambda o: "/pull-requests" in o["url"], ok({"data": [], "total": 0}))]))
    assert c.list_pull_requests("camp_empty") == []


def test_malformed_pr_response_does_not_crash():
    c = DarkmoonClient(
        "http://x", mock_http([(lambda o: "/pull-requests" in o["url"], HttpResponse(200, "<html>not json</html>"))])
    )
    assert c.list_pull_requests() == []


def test_run_without_run_id_is_error_not_fake_success():
    c = DarkmoonClient("http://x", mock_http([(lambda o: o["url"].endswith("/run/campaign"), ok({"nope": True}))]))
    with pytest.raises(DarkmoonError):
        c.run_campaign({"target": "t"})


# -- HTTP error mapping ----------------------------------------------------
@pytest.mark.parametrize("code,where", [(401, "login"), (403, "campaigns"), (500, "campaigns")])
def test_http_error_maps_to_darkmoon_error(code, where):
    c = DarkmoonClient("http://x", mock_http([(lambda o: True, err(code, f"boom-{code}"))]))
    with pytest.raises(DarkmoonError) as ei:
        if where == "login":
            c.login("u", "p")
        else:
            c.list_campaigns()
    assert ei.value.status_code == code


def test_http_404_on_get_pull_request():
    c = DarkmoonClient(
        "http://x", mock_http([(lambda o: "/pull-requests/" in o["url"], err(404, "Pull request pr_x not found"))])
    )
    with pytest.raises(DarkmoonError) as ei:
        c.get_pull_request("pr_x")
    assert ei.value.status_code == 404


# -- timeouts (never loop forever) -----------------------------------------
def test_wait_for_run_times_out_without_terminal_event():
    c = DarkmoonClient(
        "http://x", mock_http([(lambda o: "/run/logs/" in o["url"], ok({"data": [{"type": "step"}], "total": 1}))])
    )
    res = c.wait_for_run("r", poll_s=0.001, timeout_s=0.01, sleep=NO_SLEEP)
    assert res["timed_out"] is True and res["terminal"] is None


def test_wait_for_pull_requests_times_out_cleanly():
    c = DarkmoonClient("http://x", mock_http([(lambda o: "/pull-requests" in o["url"], ok({"data": [], "total": 0}))]))
    res = c.wait_for_pull_requests("camp", min_count=1, poll_s=0.001, timeout_s=0.01, sleep=NO_SLEEP)
    assert res["timed_out"] is True and res["pull_requests"] == []


def test_wait_for_run_returns_on_terminal_event():
    events = [{"type": "step"}, {"type": "run_completed"}]
    c = DarkmoonClient("http://x", mock_http([(lambda o: "/run/logs/" in o["url"], ok({"data": events, "total": 2}))]))
    res = c.wait_for_run("r", poll_s=0.001, timeout_s=1, sleep=NO_SLEEP)
    assert res["timed_out"] is False and res["terminal"]["type"] == "run_completed"


# -- campaign resolution ---------------------------------------------------
def test_resolve_run_campaign_picks_new_campaign():
    campaigns = [{"id": "camp_old", "date": "1"}, {"id": "camp_new_host", "date": "2"}]
    c = DarkmoonClient("http://x", mock_http([(lambda o: o["url"].endswith("/campaigns"), ok({"data": campaigns}))]))
    resolved = c.resolve_run_campaign({"camp_old"}, "host")
    assert resolved["id"] == "camp_new_host"


# -- pull-request client-side filter ---------------------------------------
def test_filter_pull_requests_by_state_and_repo():
    prs = [
        {"id": "1", "state": "open", "repo": "org/a"},
        {"id": "2", "state": "merged", "repo": "org/b"},
        {"id": "3", "state": "open", "repo": "org/b"},
    ]
    assert [p["id"] for p in DarkmoonClient.filter_pull_requests(prs, state=["open"])] == ["1", "3"]
    assert [p["id"] for p in DarkmoonClient.filter_pull_requests(prs, repository="org/b")] == ["2", "3"]


# -- no secret leakage in errors -------------------------------------------
def test_no_secret_leakage_in_errors():
    SECRET_PW = "S3cret-Passw0rd!"
    TOKEN = "jwt.header.signature.SECRET"
    CRED = "cred_ref_should_be_opaque"
    c = DarkmoonClient(
        "http://x",
        mock_http(
            [
                (lambda o: o["url"].endswith("/auth/login"), ok({"token": TOKEN})),
                (lambda o: o["url"].endswith("/run/campaign"), err(500, "internal error")),
            ]
        ),
    )
    c.login("admin", SECRET_PW)
    msg = ""
    try:
        c.run_campaign({"target": "t", "remediate": True, "credential_id": CRED})
    except DarkmoonError as e:
        import traceback

        msg = str(e) + " " + "".join(traceback.format_exception(e))
    assert SECRET_PW not in msg
    assert TOKEN not in msg
    assert "internal error" in msg
