import os, smtplib
from email.message import EmailMessage

def fmt(e):
    rs="\n".join(f"- {r}" for r in e.reasons[:8])
    return f"🏗️ Morocco Real Estate Intelligence\nScore total: {e.total_score}/100 | Opportunity: {e.opportunity_score}/100 | Launch: {e.launch_confidence}/100\nCanal: {e.channel} | Source: {e.source}\nVille: {e.city or 'à confirmer'} | Zone: {e.zone or 'à confirmer'} | Type: {e.asset_type or 'à confirmer'}\nPrix: {e.price_mad or 'non détecté'} MAD\nTitre: {e.title}\nLien: {e.url}\n\nRaisons:\n{rs}"
def notify(events):
    if not events: print("No email to send"); return
    host=os.getenv("SMTP_HOST"); user=os.getenv("SMTP_USER"); pwd=os.getenv("SMTP_PASSWORD"); to=os.getenv("ALERT_EMAIL_TO"); frm=os.getenv("ALERT_EMAIL_FROM",user)
    if not all([host,user,pwd,to]): print("Email not configured"); return
    msg=EmailMessage(); msg["Subject"]=f"Real Estate Intelligence: {len(events)} signal(s)"; msg["From"]=frm; msg["To"]=to
    msg.set_content("\n\n---\n\n".join(fmt(e) for e in events))
    with smtplib.SMTP(host,int(os.getenv("SMTP_PORT","587"))) as s:
        s.starttls(); s.login(user,pwd); s.send_message(msg)
