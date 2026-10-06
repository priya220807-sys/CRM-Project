"""Optional e-mail notifications. If SMTP is not configured, messages are only logged."""
import logging
import smtplib
from email.message import EmailMessage
from flask import current_app

log = logging.getLogger("crm.notify")


def send_email(to_addr, subject, body):
    cfg = current_app.config
    if not (cfg.get("SMTP_HOST") and to_addr):
        log.info("[email not sent - SMTP off] to=%s subject=%s", to_addr, subject)
        return False
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = cfg["MAIL_FROM"], to_addr, subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(cfg["SMTP_HOST"], cfg["SMTP_PORT"], timeout=10) as s:
            s.starttls()
            if cfg.get("SMTP_USER"):
                s.login(cfg["SMTP_USER"], cfg["SMTP_PASSWORD"])
            s.send_message(msg)
        return True
    except Exception as exc:  # never break the API because mail failed
        log.warning("Email failed: %s", exc)
        return False


def notify_lead_update(lead, message):
    if lead.assignee:
        send_email(lead.assignee.email, f"CRM: update on lead #{lead.id}", message)
