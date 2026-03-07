"""
test_email_notifications.py — Email Notification Service Tests
===============================================================

Validates:
  - EmailTemplate enum members
  - Template rendering with context substitution
  - send_email disabled when EMAIL_ENABLED=false
  - send_email SMTP path (mocked)
  - Convenience helpers: limit_hit, upgrade_confirmation, welcome, doc_expiry
  - Config settings for SMTP
  - _send_plan_change_emails integration
"""

from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT_DIR = Path(__file__).resolve().parents[2]


# ─── Config ──────────────────────────────────────────────────────────────────

class TestEmailConfig:
    """Verify email settings exist in config."""

    def test_01_smtp_host_setting(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "SMTP_HOST")

    def test_02_smtp_port_default(self):
        from app.core.config import Settings
        s = Settings()
        assert s.SMTP_PORT == 587

    def test_03_smtp_user_setting(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "SMTP_USER")

    def test_04_smtp_password_setting(self):
        from app.core.config import Settings
        s = Settings()
        assert hasattr(s, "SMTP_PASSWORD")

    def test_05_smtp_from_email(self):
        from app.core.config import Settings
        s = Settings()
        assert "@" in s.SMTP_FROM_EMAIL

    def test_06_smtp_from_name(self):
        from app.core.config import Settings
        s = Settings()
        assert s.SMTP_FROM_NAME

    def test_07_email_enabled_default_false(self):
        from app.core.config import Settings
        s = Settings()
        assert s.EMAIL_ENABLED is False


# ─── EmailTemplate ───────────────────────────────────────────────────────────

class TestEmailTemplate:
    """Verify EmailTemplate enum."""

    def test_08_limit_hit(self):
        from app.core.email_service import EmailTemplate
        assert EmailTemplate.LIMIT_HIT.value == "limit_hit"

    def test_09_upgrade_confirmation(self):
        from app.core.email_service import EmailTemplate
        assert EmailTemplate.UPGRADE_CONFIRMATION.value == "upgrade_confirmation"

    def test_10_welcome_new_plan(self):
        from app.core.email_service import EmailTemplate
        assert EmailTemplate.WELCOME_NEW_PLAN.value == "welcome_new_plan"

    def test_11_document_expiry(self):
        from app.core.email_service import EmailTemplate
        assert EmailTemplate.DOCUMENT_EXPIRY.value == "document_expiry"


# ─── Template Rendering ─────────────────────────────────────────────────────

class TestTemplateRendering:
    """Verify template rendering substitution."""

    def test_12_limit_hit_template_renders(self):
        from app.core.email_service import _render_template, EmailTemplate
        result = _render_template(EmailTemplate.LIMIT_HIT, {
            "resource": "projects", "used": 5, "limit": 5, "plan": "Starter",
            "frontend_url": "https://app.test",
        })
        assert "projects" in result["subject"]
        assert "Starter" in result["subject"]
        assert "5 / 5" in result["html"]

    def test_13_upgrade_confirmation_renders(self):
        from app.core.email_service import _render_template, EmailTemplate
        result = _render_template(EmailTemplate.UPGRADE_CONFIRMATION, {
            "previous_plan": "Starter", "new_plan": "Growth",
            "frontend_url": "https://app.test",
        })
        assert "Growth" in result["subject"]
        assert "Starter" in result["html"]
        assert "Growth" in result["html"]

    def test_14_welcome_template_renders(self):
        from app.core.email_service import _render_template, EmailTemplate
        result = _render_template(EmailTemplate.WELCOME_NEW_PLAN, {
            "plan": "Elite", "frontend_url": "https://app.test",
        })
        assert "Elite" in result["subject"]
        assert "Elite" in result["html"]

    def test_15_document_expiry_renders(self):
        from app.core.email_service import _render_template, EmailTemplate
        result = _render_template(EmailTemplate.DOCUMENT_EXPIRY, {
            "count": 3, "days": 30, "frontend_url": "https://app.test",
        })
        assert "3" in result["subject"]
        assert "30" in result["html"]

    def test_16_templates_dict_has_all_members(self):
        from app.core.email_service import TEMPLATES, EmailTemplate
        for t in EmailTemplate:
            assert t in TEMPLATES, f"Missing template: {t.value}"
            assert "subject" in TEMPLATES[t]
            assert "html" in TEMPLATES[t]


# ─── send_email ──────────────────────────────────────────────────────────────

class TestSendEmail:
    """Verify send_email behavior."""

    def test_17_returns_false_when_disabled(self):
        from app.core.email_service import send_email, EmailTemplate
        # EMAIL_ENABLED defaults to False
        result = send_email("test@example.com", EmailTemplate.LIMIT_HIT, {"resource": "x", "used": 1, "limit": 5, "plan": "S"})
        assert result is False

    @patch("app.core.email_service.get_settings")
    def test_18_returns_false_when_no_smtp_host(self, mock_settings):
        from app.core.email_service import send_email, EmailTemplate
        import app.core.email_service as mod
        mod._smtp_warned = False
        s = MagicMock()
        s.EMAIL_ENABLED = True
        s.SMTP_HOST = ""
        mock_settings.return_value = s
        result = send_email("test@example.com", EmailTemplate.LIMIT_HIT, {})
        assert result is False

    @patch("app.core.email_service.smtplib.SMTP")
    @patch("app.core.email_service.get_settings")
    def test_19_sends_via_smtp_when_configured(self, mock_settings, mock_smtp_class):
        from app.core.email_service import send_email, EmailTemplate
        s = MagicMock()
        s.EMAIL_ENABLED = True
        s.SMTP_HOST = "smtp.test.com"
        s.SMTP_PORT = 587
        s.SMTP_USER = "user"
        s.SMTP_PASSWORD = "pass"
        s.SMTP_FROM_EMAIL = "noreply@test.com"
        s.SMTP_FROM_NAME = "Test"
        s.FRONTEND_URL = "https://app.test"
        mock_settings.return_value = s

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = MagicMock(return_value=False)

        result = send_email("dest@test.com", EmailTemplate.WELCOME_NEW_PLAN, {"plan": "Growth"})
        assert result is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user", "pass")
        mock_server.send_message.assert_called_once()

    @patch("app.core.email_service.smtplib.SMTP")
    @patch("app.core.email_service.get_settings")
    def test_20_returns_false_on_smtp_exception(self, mock_settings, mock_smtp_class):
        from app.core.email_service import send_email, EmailTemplate
        s = MagicMock()
        s.EMAIL_ENABLED = True
        s.SMTP_HOST = "smtp.test.com"
        s.SMTP_PORT = 587
        s.SMTP_USER = ""
        s.SMTP_PASSWORD = ""
        s.SMTP_FROM_EMAIL = "noreply@test.com"
        s.SMTP_FROM_NAME = "Test"
        s.FRONTEND_URL = "https://app.test"
        mock_settings.return_value = s
        mock_smtp_class.side_effect = Exception("connection refused")

        result = send_email("dest@test.com", EmailTemplate.LIMIT_HIT, {"resource": "x", "used": 1, "limit": 5, "plan": "S"})
        assert result is False


# ─── Convenience helpers ─────────────────────────────────────────────────────

class TestConvenienceHelpers:
    """Verify convenience email functions."""

    @patch("app.core.email_service.send_email", return_value=True)
    def test_21_send_limit_hit_email(self, mock_send):
        from app.core.email_service import send_limit_hit_email
        result = send_limit_hit_email("u@t.com", "projects", 5, 5, "starter")
        assert result is True
        mock_send.assert_called_once()

    @patch("app.core.email_service.send_email", return_value=True)
    def test_22_send_upgrade_confirmation_email(self, mock_send):
        from app.core.email_service import send_upgrade_confirmation_email
        result = send_upgrade_confirmation_email("u@t.com", "starter", "growth")
        assert result is True
        mock_send.assert_called_once()

    @patch("app.core.email_service.send_email", return_value=True)
    def test_23_send_welcome_email(self, mock_send):
        from app.core.email_service import send_welcome_email
        result = send_welcome_email("u@t.com", "growth")
        assert result is True
        mock_send.assert_called_once()

    @patch("app.core.email_service.send_email", return_value=True)
    def test_24_send_document_expiry_email(self, mock_send):
        from app.core.email_service import send_document_expiry_email
        result = send_document_expiry_email("u@t.com", 3, 30)
        assert result is True
        mock_send.assert_called_once()


# ─── File existence checks ────────────────────────────────────────────────────

class TestFileExistence:
    """Verify source files exist."""

    def test_25_email_service_file_exists(self):
        path = ROOT_DIR / "backend" / "app" / "core" / "email_service.py"
        assert path.exists()

    def test_26_email_service_has_email_template(self):
        path = ROOT_DIR / "backend" / "app" / "core" / "email_service.py"
        content = path.read_text()
        assert "class EmailTemplate" in content

    def test_27_email_service_has_send_email(self):
        path = ROOT_DIR / "backend" / "app" / "core" / "email_service.py"
        content = path.read_text()
        assert "def send_email" in content

    def test_28_config_has_smtp_settings(self):
        path = ROOT_DIR / "backend" / "app" / "core" / "config.py"
        content = path.read_text()
        assert "SMTP_HOST" in content
        assert "EMAIL_ENABLED" in content

    def test_29_billing_endpoint_has_email_integration(self):
        path = ROOT_DIR / "backend" / "app" / "api" / "endpoints" / "billing.py"
        content = path.read_text()
        assert "_send_plan_change_emails" in content

    def test_30_templates_have_html(self):
        from app.core.email_service import TEMPLATES
        for key, val in TEMPLATES.items():
            assert "<div" in val["html"], f"Template {key} missing HTML structure"
