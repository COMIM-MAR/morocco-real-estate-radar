from __future__ import annotations
import os
import smtplib
from email.message import EmailMessage
from .models import Signal


def money(v: int | None) -> str:
    return "non détecté" if not v else f"{v:,.0f} MAD".replace(",", " ")


def format_signal(sig: Signal) -> str:
    reasons = "\n".join(f"- {r}" for r in sig.reasons[:10])
    return f"""🔥 Morocco Real Estate Intelligence
Score total: {sig.total_score}/100 | Opportunité: {sig.opportunity_score}/100 | Confiance: {sig.confidence_score}/100
Canal: {sig.channel} | Source: {sig.source}
Ville: {sig.city or 'à confirmer'} | Zone: {sig.zone or 'à confirmer'} | Type: {sig.asset_type or 'à confirmer'}
Prix: {money(sig.price_mad)}
Titre: {sig.title}
Lien: {sig.url}

Raisons:
{reasons}
"""


def notify_email(signals: list[Signal]) -> None:
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    to_addr = os.getenv("ALERT_EMAIL_TO")
    from_addr = os.getenv("ALERT_EMAIL_FROM", user or "radar@example.com")
    if not all([host, user, password, to_addr]):
        print("Email not configured; skipping")
        return
    body = "\n\n---\n\n".join(format_signal(s) for s in signals)
    msg = EmailMessage()
    msg["Subject"] = f"Radar immobilier Maroc: {len(signals)} signal(aux) qualifié(s)"
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(body)
    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


def notify(signals: list[Signal]) -> None:
    if not signals:
        print("No qualified signals to notify")
        return
    notify_email(signals)
