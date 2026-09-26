"""
Tests for the real Langflow components, driven by a mock-transport client.

These instantiate the actual ``lfx`` components, inject a mock-transport
DarkmoonClient (by monkeypatching the client factory), run the output methods,
and verify each component builds a valid Langflow frontend node. No network.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import darkmoon._base as base  # noqa: E402
from darkmoon import (  # noqa: E402
    DarkmoonGetFindingsComponent,
    DarkmoonListCampaignsComponent,
    DarkmoonListPullRequestsComponent,
    DarkmoonRunPentestComponent,
)
from darkmoon.darkmoon_client import DarkmoonClient, DarkmoonError, HttpResponse  # noqa: E402


def make_client(routes, sink=None):
    def http(opts):
        if sink is not None:
            sink.append(opts)
        for pred, resp in routes:
            if pred(opts):
                return resp(opts) if callable(resp) else resp
        return HttpResponse(200, {"data": [], "total": 0})

    return DarkmoonClient("http://x", http)


def ok(body):
    return HttpResponse(200, body)


CONN = {"base_url": "http://x", "username": "u", "password": "p", "_session_id": "t"}


@pytest.fixture
def inject_client(monkeypatch):
    """Return a setter that patches the client factory to yield a given client."""

    def _set(client):
        monkeypatch.setattr(base, "logged_in_client", lambda *a, **k: client)

    return _set


def test_list_campaigns_component(inject_client):
    inject_client(make_client([(lambda o: o["url"].endswith("/campaigns"), ok({"data": [{"id": "camp_1"}], "total": 1}))]))
    comp = DarkmoonListCampaignsComponent(**CONN)
    out = comp.list_campaigns_action()
    assert out.data["total"] == 1 and out.data["campaigns"][0]["id"] == "camp_1"


def test_get_findings_component(inject_client):
    inject_client(
        make_client([(lambda o: "/vulnerabilities" in o["url"], ok({"data": [{"id": "v1", "severity": "high"}], "total": 1, "stats": {"by_severity": {"high": 1}}}))])
    )
    comp = DarkmoonGetFindingsComponent(campaign_id="camp_1", **CONN)
    out = comp.get_findings_action()
    assert out.data["total"] == 1 and out.data["stats"]["by_severity"]["high"] == 1


def test_run_pentest_component_without_wait(inject_client):
    sink = []
    inject_client(
        make_client(
            [
                (lambda o: o["url"].endswith("/campaigns"), ok({"data": [], "total": 0})),
                (lambda o: o["url"].endswith("/run/campaign"), ok({"run_id": "r1", "pid": 1})),
            ],
            sink,
        )
    )
    comp = DarkmoonRunPentestComponent(target="example.test", wait_for_completion=False, **CONN)
    out = comp.run_pentest_action()
    assert out.data["status"] == "started" and out.data["run_id"] == "r1"
    run_body = [s["body"] for s in sink if s["url"].endswith("/run/campaign")][0]
    assert "remediate" not in run_body and "credential_id" not in run_body


def test_run_pentest_component_remediation_requires_credential(inject_client):
    inject_client(make_client([(lambda o: True, ok({"data": [], "total": 0}))]))
    comp = DarkmoonRunPentestComponent(target="example.test", remediate=True, **CONN)
    with pytest.raises(DarkmoonError):
        comp.run_pentest_action()


def test_list_pull_requests_component_read_only_and_filter(inject_client):
    prs = [
        {"id": "1", "state": "open", "repo": "org/a"},
        {"id": "2", "state": "merged", "repo": "org/b"},
    ]
    inject_client(make_client([(lambda o: "/pull-requests" in o["url"], ok({"data": prs, "total": 2}))]))
    comp = DarkmoonListPullRequestsComponent(campaign_id="camp_1", state="open", **CONN)
    out = comp.list_pull_requests_action()
    assert out.data["total"] == 1 and out.data["pull_requests"][0]["id"] == "1"


@pytest.mark.parametrize(
    "cls",
    [
        DarkmoonRunPentestComponent,
        DarkmoonGetFindingsComponent,
        DarkmoonListCampaignsComponent,
        DarkmoonListPullRequestsComponent,
    ],
)
def test_component_builds_valid_frontend_node(cls):
    """Every component must serialise to a Langflow frontend node with its inputs/outputs."""
    comp = cls(**CONN)
    node = comp.to_frontend_node()
    template = node["data"]["node"]["template"]
    assert "base_url" in template and "password" in template
    assert node["data"]["node"]["outputs"]
