import os, smtplib
from email.message import EmailMessage

def fmt(project):
    reasons = "\n".join(f"- {reason}" for reason in project.reasons[:8])
    prices = project.prices.get("min") or "non détecté"
    sources = ", ".join(project.sources[:6])
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
        f"Sources: {sources}\n"
        f"Résumé: {project.summary}\n\n"
        f"Pourquoi c'est intéressant:\n{reasons}"
    )


def notify(projects):
    if not projects:
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
    msg["Subject"] = f"Real Estate Intelligence: {len(projects)} new project signal(s)"
    msg["From"] = frm
    msg["To"] = to
    msg.set_content("\n\n---\n\n".join(fmt(project) for project in projects))
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587"))) as smtp:
        smtp.starttls()
        smtp.login(user, pwd)
        smtp.send_message(msg)
