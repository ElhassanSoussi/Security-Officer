import os

# Ensure env vars so Settings() doesn't crash during app import
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


def _get_test_client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_health_endpoint_shape_has_minimum_fields():
    # /health does DB best-effort; we only require these stable keys.
    client = _get_test_client()
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "version" in data
    assert "timestamp" in data


def test_security_headers_include_csp():
    client = _get_test_client()
    res = client.get("/health/ping")
    assert res.status_code == 200
    assert "Content-Security-Policy" in res.headers
    assert "X-Content-Type-Options" in res.headers


def test_rate_limit_assistant_message_triggers_429(monkeypatch):
    # Make limiter very small for deterministic test.
    monkeypatch.setenv("RATE_LIMIT_CRITICAL", "2")
    monkeypatch.setenv("RATE_LIMIT_CRITICAL_WINDOW_SECONDS", "60")

    # Re-import app to pick up env (best-effort; relies on module cache isolation)
    import importlib
    import app.main as main_mod
    importlib.reload(main_mod)

    from fastapi.testclient import TestClient
    client = TestClient(main_mod.app, raise_server_exceptions=False)

    # Route requires auth; we can still test middleware by calling without auth.
    # The limiter should run before auth dependency and return 429.
    for _ in range(2):
        r = client.post("/api/v1/assistant/message", json={"message": "hi", "org_id": "00000000-0000-0000-0000-000000000000"})
        assert r.status_code in (401, 403, 422)

    r3 = client.post("/api/v1/assistant/message", json={"message": "hi", "org_id": "00000000-0000-0000-0000-000000000000"})
    assert r3.status_code == 429
    body = r3.json()
    assert body.get("error") == "rate_limited"
    assert "retry_after_seconds" in body
    assert "X-Request-Id" in r3.headers


def test_unhandled_exception_is_structured_and_has_request_id(monkeypatch):
    # Patch an endpoint handler to raise an exception.
    from fastapi import APIRouter
    from fastapi.testclient import TestClient

    import importlib
    import app.main as main_mod

    # Ensure fresh app
    importlib.reload(main_mod)

    # Add a temporary route for testing
    r = APIRouter()

    @r.get("/__test__/boom")
    def _boom():
        raise RuntimeError("boom")

    main_mod.app.include_router(r)
    client = TestClient(main_mod.app, raise_server_exceptions=False)

    resp = client.get("/__test__/boom")
    assert resp.status_code == 500
    data = resp.json()
    assert data["error"] == "internal_error"
    assert data["message"]
    assert "request_id" in data
    assert resp.headers.get("X-Request-Id") == data["request_id"]
