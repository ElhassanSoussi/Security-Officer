from __future__ import annotations

import importlib


def test_smoke_frontend_requires_frontend_url(monkeypatch, capsys):
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    monkeypatch.delenv("VERCEL_FRONTEND_URL", raising=False)

    mod = importlib.import_module("scripts.smoke_production_frontend")
    exit_code = mod.main()

    captured = capsys.readouterr().out
    assert exit_code == 2
    assert "FAIL: config - FRONTEND_URL is required" in captured
