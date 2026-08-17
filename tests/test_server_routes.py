"""
Route-level tests for the FastAPI app, with emphasis on the SPA fallback.

Serving a single-page app behind an API is easy to get subtly wrong:
StaticFiles(html=True) serves index.html at "/" but 404s every client-side
route, so /strategies worked when reached by in-app navigation and broke on
refresh or a shared link. These tests pin that behaviour down.
"""

import pathlib

import pytest
from fastapi.testclient import TestClient

from src.config import get_home
from src.server import make_app


@pytest.fixture
def home(tmp_path):
    return get_home(str(tmp_path / "data"))


@pytest.fixture
def client(home):
    return TestClient(make_app(home))


@pytest.fixture
def client_with_ui(home, tmp_path):
    """An app pointed at a minimal stand-in for a built UI."""
    dist = tmp_path / "dist"
    (dist / "static").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>shell</title>")
    (dist / "static" / "app.js").write_text("console.log(1)")
    (dist / "favicon.svg").write_text("<svg/>")
    return TestClient(make_app(home, ui_dist=dist))


# ------------------------------------------------------------------- api

def test_api_endpoints_respond(client):
    for path in ["/api/config", "/api/strategies", "/api/providers",
                 "/api/accounts", "/api/sessions", "/api/jobs",
                 "/api/rankings", "/api/live/list", "/api/credentials"]:
        r = client.get(path)
        assert r.status_code == 200, f"{path} → {r.status_code}"


def test_unknown_api_route_is_a_json_404(client):
    """An API client must never get the HTML shell in place of an error."""
    r = client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


def test_unknown_job_and_account_are_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/accounts/nope").status_code == 404
    assert client.get("/api/live/nope/status").status_code == 404


def test_backtest_rejects_unknown_strategy(client):
    r = client.post("/api/backtest", json={
        "strategy": "no_such_strategy", "ticker": "TEST",
        "start": "2026-01-01", "end": "2026-02-01",
    })
    assert r.status_code == 400
    assert "unknown strategy" in r.json()["detail"]


def test_accounts_roundtrip(client):
    created = client.post("/api/accounts", json={"name": "t", "starting_balance": 100.0})
    assert created.status_code == 200
    aid = created.json()["account_id"]

    assert client.get(f"/api/accounts/{aid}").status_code == 200
    assert client.delete(f"/api/accounts/{aid}").status_code == 200
    assert client.get(f"/api/accounts/{aid}").status_code == 404


def test_prune_defaults_to_a_dry_run(client):
    client.post("/api/accounts", json={"name": "mw_scratch"})
    r = client.post("/api/accounts/prune")
    assert r.status_code == 200
    body = r.json()
    assert body["dry_run"] is True and body["deleted"] == 0 and body["matched"] == 1
    # still there, because it was only a report
    assert any(a["name"] == "mw_scratch" for a in client.get("/api/accounts").json()["accounts"])


# ------------------------------------------------------------------- spa

def test_without_a_build_there_is_no_spa_fallback(home, tmp_path):
    """
    With no ui/dist, non-API paths 404 rather than erroring — the API is
    perfectly usable on its own.

    ui_dist is passed explicitly: the default points at the repo's real
    ui/dist, which exists or not depending on whether anyone has run a UI
    build, and a test must not depend on that.
    """
    app = make_app(home, ui_dist=tmp_path / "no-such-dist")
    c = TestClient(app)
    assert c.get("/strategies").status_code == 404
    assert c.get("/api/config").status_code == 200


@pytest.mark.parametrize("route", ["/", "/strategies", "/research", "/live",
                                   "/sessions", "/accounts", "/deep/nested/route"])
def test_client_routes_serve_the_app_shell(client_with_ui, route):
    """
    Every client-side route must return index.html so a refresh or a shared
    link works. This is the regression that shipped: only "/" resolved.
    """
    r = client_with_ui.get(route)
    assert r.status_code == 200
    assert "<title>shell</title>" in r.text


def test_real_assets_are_served_not_shadowed_by_the_fallback(client_with_ui):
    r = client_with_ui.get("/favicon.svg")
    assert r.status_code == 200 and "<svg/>" in r.text

    r = client_with_ui.get("/static/app.js")
    assert r.status_code == 200 and "console.log" in r.text


def test_missing_asset_404s_instead_of_returning_html(client_with_ui):
    """
    A missing .js must not resolve to the HTML shell — that turns an obvious
    404 into a confusing syntax error in the browser console.
    """
    r = client_with_ui.get("/static/gone.js")
    assert r.status_code == 404

    r = client_with_ui.get("/nope.js")
    assert r.status_code == 404


def test_api_still_wins_over_the_spa_fallback(client_with_ui):
    assert client_with_ui.get("/api/config").status_code == 200

    r = client_with_ui.get("/api/not-a-route")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


# ----------------------------------------------------------------- errors

def test_bad_input_is_a_json_400_not_an_opaque_500(client):
    """
    The engine raises ValueError for unusable input (unknown ticker, a range
    with no bars). Unhandled, FastAPI answers 500 with the bare string
    "Internal Server Error" — not JSON, so a client cannot pull a message
    out of it and the user is shown nothing at all.
    """
    r = client.post("/api/backtest", json={
        "strategy": "trend_momentum",
        "ticker": "NOT_A_REAL_TICKER_XYZ",
        "start": "2025-01-01", "end": "2025-02-01", "interval": "1d",
        "data_provider": "csv",           # no path → ValueError, no network
        # Otherwise the tick-coverage gate refuses first, which is a
        # different check with its own test below.
        "require_ticks": False,
    })
    assert r.status_code == 400
    assert r.headers["content-type"].startswith("application/json")
    assert r.json()["detail"]             # a message the UI can surface


def test_a_backtest_without_ticks_is_refused_not_silently_downgraded(client):
    """
    A result computed from provider bars looks identical to one computed
    from our own ticks, which makes a silent downgrade worse than a refusal.
    """
    r = client.post("/api/backtest", json={
        "strategy": "trend_momentum", "ticker": "GC=F",
        "start": "2020-01-01", "end": "2020-02-01", "interval": "1d",
    })
    assert r.status_code == 422
    detail = r.json()["detail"]
    assert detail["error"] == "insufficient tick coverage"
    assert detail["coverage"]["covered"] == 0
    # The refusal must say how to proceed deliberately.
    assert "require_ticks" in detail["hint"]


def test_coverage_can_be_checked_before_running(client):
    r = client.get("/api/coverage/GC=F", params={"start": "2020-01-01",
                                                 "end": "2020-02-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["trustworthy"] is False
    assert body["source"] == "provider"
    assert body["coverage"]["expected"] > 0        # weekdays were counted


def test_malformed_body_is_rejected_with_422(client):
    r = client.post("/api/backtest", json={"strategy": "trend_momentum"})
    assert r.status_code == 422           # pydantic: missing required fields
