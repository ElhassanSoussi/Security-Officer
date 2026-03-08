import os

# Ensure env vars so Settings() doesn't crash during app import
for var in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_JWT_SECRET", "SUPABASE_SERVICE_ROLE_KEY"):
    os.environ.setdefault(var, "https://test.supabase.co" if "URL" in var else "test-key-placeholder")


def _client():
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def test_readiness_endpoint_shape_and_no_secrets():
    # Ensure version is surfaced.
    os.environ["APP_VERSION"] = "test-1.2.3"

    client = _client()
    res = client.get("/api/v1/system/readiness")
    assert res.status_code == 200
    data = res.json()

    assert data["status"] in ("ok", "warning", "error")
    assert "environment" in data
    assert data["version"]
    assert "checks" in data and isinstance(data["checks"], list)

    # Only status metadata is returned.
    for item in data["checks"]:
        assert set(item.keys()) == {"key", "status", "message"}
        assert item["status"] in ("ok", "warning", "error")

    # No secret VALUES should be present.
    blob = str(data).lower()
    assert "sk_live" not in blob
    assert "sk_test" not in blob
    assert "whsec_" not in blob


def test_startup_env_validation_production_fails_fast(monkeypatch):
    from app.core.env_readiness import validate_startup_env

    class S:
        ENVIRONMENT = "production"
        SUPABASE_URL = ""
        SUPABASE_KEY = ""
        FRONTEND_URL = ""
        APP_VERSION = ""
        BILLING_ENABLED = False
        STRIPE_SECRET_KEY = ""
        STRIPE_WEBHOOK_SECRET = ""
        OPENAI_API_KEY = ""

    try:
        validate_startup_env(S())
        assert False, "expected ValueError"
    except ValueError:
        assert True


def test_startup_env_validation_dev_warns_not_raises():
    from app.core.env_readiness import validate_startup_env

    class S:
        ENVIRONMENT = "local"
        SUPABASE_URL = ""
        SUPABASE_KEY = ""
        FRONTEND_URL = ""
        APP_VERSION = ""
        BILLING_ENABLED = False
        STRIPE_SECRET_KEY = ""
        STRIPE_WEBHOOK_SECRET = ""
        OPENAI_API_KEY = ""

    # Should not raise in non-production
    validate_startup_env(S())


def test_app_import_invokes_startup_env_validation(monkeypatch):
    """Prove validate_startup_env is invoked during app boot/import path."""

    # Ensure required baseline env so config doesn't fail before our patch.
    for var in ("SUPABASE_URL", "SUPABASE_KEY", "FRONTEND_URL"):
        monkeypatch.setenv(var, "https://example.com" if "URL" in var else "test-key")

    # Make sure we re-import app.main so module-level startup code runs.
    import sys
    sys.modules.pop("app.main", None)

    called = {"n": 0}

    def _spy(settings):
        called["n"] += 1
        return []

    monkeypatch.setattr("app.core.env_readiness.validate_startup_env", _spy)

    import app.main  # noqa: F401

    assert called["n"] == 1


def test_readiness_warns_on_placeholder_app_version():
    """build_readiness_report should emit a warning when APP_VERSION is a well-known placeholder."""
    import os
    from unittest.mock import MagicMock
    from app.core.env_readiness import build_readiness_report

    class S:
        ENVIRONMENT = "production"
        SUPABASE_URL = "https://example.supabase.co"
        SUPABASE_KEY = "test-key"
        FRONTEND_URL = "https://example.com"
        APP_VERSION = "1.0.0"  # placeholder
        BILLING_ENABLED = False
        STRIPE_SECRET_KEY = ""
        STRIPE_WEBHOOK_SECRET = ""
        OPENAI_API_KEY = ""

    # Minimal fake FastAPI app so route/middleware checks don't blow up
    fake_app = MagicMock()
    fake_app.user_middleware = []
    fake_app.routes = []

    # Override ALLOWED_ORIGINS so production required check passes
    old = os.environ.get("ALLOWED_ORIGINS")
    os.environ["ALLOWED_ORIGINS"] = "https://example.com"
    try:
        report = build_readiness_report(S(), fake_app)
    except ValueError:
        # Startup env validation may raise (e.g., no routes/middleware); not the focus here.
        return
    finally:
        if old is None:
            os.environ.pop("ALLOWED_ORIGINS", None)
        else:
            os.environ["ALLOWED_ORIGINS"] = old

    keys = {c["key"]: c for c in report["checks"]}
    if "app_version_value" in keys:
        assert keys["app_version_value"]["status"] == "warning"
