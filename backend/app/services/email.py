"""Optional SMTP Email Alert Notification Service."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


def send_alert_email(
    recipient: str | None,
    subject: str,
    alert_payload: dict[str, Any],
) -> bool:
    """Send an alert notification email via SMTP.

    Gracefully falls back and logs if SMTP is unconfigured.
    Credentials are read ONLY from environment variables (app.config.settings).
    """
    to_email = recipient or settings.alert_notification_email
    if not settings.smtp_host or not to_email:
        logger.info(
            "SMTP email notification skipped (smtp_host or recipient not configured). Alert: %s",
            subject,
        )
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AgniNetra Alert] {subject}"
        msg["From"] = settings.smtp_user or "alerts@agnietra.gov.in"
        msg["To"] = to_email

        body_text = f"""AgniNetra AI — Emergency Thermal Alert
======================================
Subject: {subject}
Severity: {alert_payload.get('severity', 'UNKNOWN').upper()}
Risk Score: {alert_payload.get('risk_score', 'N/A')}/100
Classification: {alert_payload.get('predicted_class', 'Unassigned')}
Coordinates: {alert_payload.get('latitude')}, {alert_payload.get('longitude')}
FRP: {alert_payload.get('frp')} MW

Access National Command Centre: http://localhost:5173/investigate/{alert_payload.get('hotspot_id', '')}
"""
        msg.attach(MIMEText(body_text, "plain"))

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            server.ehlo()
            if settings.smtp_port in (587, 25):
                server.starttls()
                server.ehlo()
            if settings.smtp_user and settings.smtp_pass:
                server.login(settings.smtp_user, settings.smtp_pass)
            server.sendmail(msg["From"], [to_email], msg.as_string())

        logger.info("Alert email successfully dispatched to %s", to_email)
        return True
    except Exception as exc:
        logger.warning("Failed to dispatch alert email: %s", exc)
        return False
