from __future__ import annotations

import os
import smtplib
import requests
from email.message import EmailMessage
from .models import Opportunity


def format_opportunity(op: Opportunity) -> str:
    reasons = "\n".join(f"- {r}" for r in (op.reasons or [])[:8])
    return (
        f"🏠 Morocco Real Estate Radar\n"
        f"Score: {op.score}/100 | Urgence: {op.urgency}\n"
        f"Source: {op.source}\n"
        f"Ville: {op.city or 'à confirmer'} | Zone: {op.zone or 'à confirmer'} | Type: {op.asset_type or 'à confirmer'}\n"
        f"Prix détecté: {op.price_mad or 'non détecté'} MAD\n"
        f"Titre: {op.title}\n"
        f"Lien: {op.url}\n\n"
        f"Raisons:\n{reasons}"
    )


def notify_telegram(opportunities: list[Opportunity]) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("Telegram not configured; skipping")
        return
    for op in opportunities:
        text = format_opportunity(op)
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:3900], "disable_web_page_preview": False},
            timeout=20,
        )


def notify_email(opportunities: list[Opportunity]) -> None:
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_addr = os.getenv("ALERT_EMAIL_TO")
    from_addr = os.getenv("ALERT_EMAIL_FROM", user or "radar@example.com")
    if not all([host, user, password, to_addr]):
        print("Email not configured; skipping")
        return

    body = "\n\n---\n\n".join(format_opportunity(op) for op in opportunities)
    msg = EmailMessage()
    msg["Subject"] = f"Radar immobilier Maroc: {len(opportunities)} opportunité(s)"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)

    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)


def notify(opportunities: list[Opportunity]) -> None:
    if not opportunities:
        print("No opportunities to notify")
        return
    notify_telegram(opportunities)
    notify_email(opportunities)
