"""
email_service.py — Transactional Email Notifications
=====================================================

Best-effort email delivery for billing / compliance events.
Never raises — all errors are swallowed after one warning.

Supports SMTP (Mailgun, SES, SendGrid, etc.) when EMAIL_ENABLED=true.

Usage::

    from app.core.email_service import send_email, EmailTemplate

    send_email(to="user@example.com", template=EmailTemplate.LIMIT_HIT,
               context={"resource": "projects", "limit": 5, "plan": "Starter"})
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Dict, Optional

from app.core.config import get_settings

logger = logging.getLogger("core.email_service")

_smtp_warned = False


# ── Template enum ────────────────────────────────────────────────────────────


class EmailTemplate(str, Enum):
    LIMIT_HIT = "limit_hit"
    UPGRADE_CONFIRMATION = "upgrade_confirmation"
    WELCOME_NEW_PLAN = "welcome_new_plan"
    DOCUMENT_EXPIRY = "document_expiry"


# ── Template rendering ───────────────────────────────────────────────────────

TEMPLATES: Dict[EmailTemplate, Dict[str, str]] = {
    EmailTemplate.LIMIT_HIT: {
        "subject": "⚠️ You've hit your {resource} limit on {plan} plan",
        "html": """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#1e293b;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">🛡️ NYC Compliance Architect</h2>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <h3 style="color:#1e293b;margin-top:0">Plan Limit Reached</h3>
    <p style="color:#475569">You've reached the <strong>{resource}</strong> limit on your <strong>{plan}</strong> plan.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr><td style="padding:8px 0;color:#64748b">Current usage</td><td style="padding:8px 0;text-align:right;font-weight:600">{used} / {limit}</td></tr>
      <tr><td style="padding:8px 0;color:#64748b">Resource</td><td style="padding:8px 0;text-align:right;font-weight:600">{resource}</td></tr>
    </table>
    <p style="color:#475569">Upgrade your plan to unlock higher limits and keep your compliance workflow uninterrupted.</p>
    <a href="{frontend_url}/settings/billing" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px">Upgrade Now →</a>
  </div>
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px">NYC Compliance Architect · Automated Compliance for Construction</p>
</div>
""",
    },
    EmailTemplate.UPGRADE_CONFIRMATION: {
        "subject": "✅ Plan upgraded to {new_plan}!",
        "html": """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#1e293b;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">🛡️ NYC Compliance Architect</h2>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <h3 style="color:#1e293b;margin-top:0">🎉 Upgrade Confirmed!</h3>
    <p style="color:#475569">Your organization has been upgraded from <strong>{previous_plan}</strong> to <strong>{new_plan}</strong>.</p>
    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:16px 0">
      <p style="color:#166534;margin:0;font-weight:600">What's unlocked:</p>
      <ul style="color:#166534;margin:8px 0 0 0;padding-left:20px">
        <li>Higher project, document, and run limits</li>
        <li>Priority compliance processing</li>
        <li>Advanced analytics and reporting</li>
      </ul>
    </div>
    <a href="{frontend_url}/dashboard" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px">Go to Dashboard →</a>
  </div>
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px">NYC Compliance Architect · Automated Compliance for Construction</p>
</div>
""",
    },
    EmailTemplate.WELCOME_NEW_PLAN: {
        "subject": "Welcome to {plan} — let's get started!",
        "html": """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#1e293b;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">🛡️ NYC Compliance Architect</h2>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <h3 style="color:#1e293b;margin-top:0">Welcome to your {plan} plan! 🎊</h3>
    <p style="color:#475569">Your subscription is now active. Here's how to make the most of it:</p>
    <ol style="color:#475569;line-height:1.8">
      <li><strong>Upload questionnaires</strong> — drag & drop Excel files for AI analysis</li>
      <li><strong>Build your knowledge base</strong> — upload past submissions for answer reuse</li>
      <li><strong>Run compliance analysis</strong> — let AI fill in your questionnaires</li>
      <li><strong>Export & submit</strong> — download ready-to-submit Excel files</li>
    </ol>
    <a href="{frontend_url}/dashboard" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px">Start Now →</a>
  </div>
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px">NYC Compliance Architect · Automated Compliance for Construction</p>
</div>
""",
    },
    EmailTemplate.DOCUMENT_EXPIRY: {
        "subject": "📋 {count} document(s) expiring soon",
        "html": """
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#1e293b;color:#fff;padding:16px 24px;border-radius:8px 8px 0 0">
    <h2 style="margin:0;font-size:18px">🛡️ NYC Compliance Architect</h2>
  </div>
  <div style="background:#fff;border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 8px 8px">
    <h3 style="color:#1e293b;margin-top:0">Compliance Documents Expiring Soon</h3>
    <p style="color:#475569"><strong>{count}</strong> document(s) in your organization will expire within the next <strong>{days}</strong> days.</p>
    <div style="background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;padding:16px;margin:16px 0">
      <p style="color:#92400e;margin:0">⚠️ Review and re-run analysis to maintain compliance.</p>
    </div>
    <a href="{frontend_url}/documents" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600;margin-top:8px">Review Documents →</a>
  </div>
  <p style="color:#94a3b8;font-size:12px;text-align:center;margin-top:16px">NYC Compliance Architect · Automated Compliance for Construction</p>
</div>
""",
    },
}


def _render_template(template: EmailTemplate, context: Dict[str, Any]) -> Dict[str, str]:
    """Render subject + html body with context substitution."""
    t = TEMPLATES[template]
    subject = t["subject"]
    html = t["html"]
    for key, value in context.items():
        subject = subject.replace(f"{{{key}}}", str(value))
        html = html.replace(f"{{{key}}}", str(value))
    return {"subject": subject, "html": html}


# ── Send email ────────────────────────────────────────────────────────────────


def send_email(
    to: str,
    template: EmailTemplate,
    context: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Send a transactional email. Returns True on success, False on failure.
    Never raises.
    """
    global _smtp_warned
    settings = get_settings()

    if not settings.EMAIL_ENABLED:
        logger.debug("send_email: EMAIL_ENABLED=false — skipping %s to %s", template.value, to)
        return False

    if not settings.SMTP_HOST:
        if not _smtp_warned:
            _smtp_warned = True
            logger.warning("send_email: SMTP_HOST not configured — emails will not be sent")
        return False

    ctx = dict(context or {})
    ctx.setdefault("frontend_url", settings.FRONTEND_URL.rstrip("/"))

    try:
        rendered = _render_template(template, ctx)

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to
        msg["Subject"] = rendered["subject"]
        msg.attach(MIMEText(rendered["html"], "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info("Email sent: template=%s to=%s", template.value, to[:30])
        return True

    except Exception as exc:
        logger.warning("send_email failed: template=%s to=%s error=%s", template.value, to[:30], str(exc)[:200])
        return False


def send_limit_hit_email(
    to: str,
    resource: str,
    used: int,
    limit: int,
    plan: str,
) -> bool:
    """Convenience: send a limit-hit alert email."""
    return send_email(
        to=to,
        template=EmailTemplate.LIMIT_HIT,
        context={"resource": resource, "used": used, "limit": limit, "plan": plan.title()},
    )


def send_upgrade_confirmation_email(
    to: str,
    previous_plan: str,
    new_plan: str,
) -> bool:
    """Convenience: send an upgrade confirmation email."""
    return send_email(
        to=to,
        template=EmailTemplate.UPGRADE_CONFIRMATION,
        context={"previous_plan": previous_plan.title(), "new_plan": new_plan.title()},
    )


def send_welcome_email(to: str, plan: str) -> bool:
    """Convenience: send a welcome-to-plan email."""
    return send_email(
        to=to,
        template=EmailTemplate.WELCOME_NEW_PLAN,
        context={"plan": plan.title()},
    )


def send_document_expiry_email(to: str, count: int, days: int = 30) -> bool:
    """Convenience: send a document expiry alert email."""
    return send_email(
        to=to,
        template=EmailTemplate.DOCUMENT_EXPIRY,
        context={"count": count, "days": days},
    )
