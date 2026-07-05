import os, smtplib
from email.message import EmailMessage

def fmt(project):
    reasons = "\n".join(f"- {reason}" for reason in project.reasons[:8])
    prices = project.prices.get("min") or "non détecté"
    sources = ", ".join(project.sources[:6])
    confirmations = "\n".join(f"✅ {item}" for item in project.evidence.get("confirmations", [])[:5]) or "✅ Première détection à confirmer"
    roi_hint = "Élevé" if project.investment_score >= 75 else "Moyen" if project.investment_score >= 55 else "À qualifier"
    return (
        "🔥 Nouveau projet détecté\n"
        f"Nom: {project.name}\n"
        f"Ville: {project.city or 'à confirmer'}\n"
        f"Zone: {project.zone or 'à confirmer'}\n"
        f"Promoteur: {project.promoter or 'à confirmer'}\n"
        f"Type: {project.asset_type or 'à confirmer'}\n"
        f"Prix de lancement estimé: {prices} MAD\n"
        f"Confidence Score: {project.confidence_score}/100\n"
        f"Investment Score: {project.investment_score}/100\n"
        f"Urgency Score: {project.urgency_score}/100\n"
        f"ROI Hint: {roi_hint}\n"
        f"Sources: {sources}\n"
        f"Résumé: {project.summary}\n\n"
        f"Détecté grâce à:\n{confirmations}\n\n"
        f"Pourquoi c'est intéressant:\n{reasons}"
    )


def fmt_digest(project):
    changes = project.evidence.get("changes", [])
    change_lines = "\n".join(f"- {change}" for change in changes[:8]) or "- Pas de changement détaillé"
    return (
        "📬 Évolution projet\n"
        f"Nom: {project.name}\n"
        f"Ville: {project.city or 'à confirmer'}\n"
        f"Promoteur: {project.promoter or 'à confirmer'}\n"
        f"Confidence Score: {project.confidence_score}/100\n"
        f"Investment Score: {project.investment_score}/100\n"
        f"Urgency Score: {project.urgency_score}/100\n"
        f"Résumé: {project.summary}\n\n"
        f"Évolutions:\n{change_lines}"
    )


def send_email(subject: str, body: str):
    if not body.strip():
        print("No email to send")
        return
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASSWORD")
    to = os.getenv("ALERT_EMAIL_TO")
    frm = os.getenv("ALERT_EMAIL_FROM", user)
    if not all([host, user, pwd, to]):
        print("Email not configured")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = to
    msg.set_content(body)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(user, pwd)
        smtp.send_message(msg)


def notify_immediate(projects):
    if not projects:
        print("No immediate email to send")
        return
    send_email(
        f"Real Estate Intelligence: {len(projects)} new project signal(s)",
        "\n\n---\n\n".join(fmt(project) for project in projects),
    )


def notify_digest(projects):
    if not projects:
        print("No digest email to send")
        return
    send_email(
        f"Real Estate Intelligence Digest: {len(projects)} project update(s)",
        "\n\n---\n\n".join(fmt_digest(project) for project in projects),
    )
