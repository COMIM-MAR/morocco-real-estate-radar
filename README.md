# Morocco Real Estate Intelligence Engine

This repository is now structured as a project-level intelligence engine instead of a listing radar.

Current foundation implemented in this repo:
- modular collectors under `collectors/` for promoters, Google, Meta Ads, news, social, urbanism, and listings
- project-level entity resolution and fusion
- SQLite persistence at `data/intelligence.db`
- project dossiers with aliases, evidence, channels, URLs, and update history
- dashboard publishing in `docs/index.html` with filters, favorites, dossier view, and timeline exploration
- immediate alerts for high-confidence new project signals plus digest-style updates for meaningful project evolution
- GitHub Actions workflow using the existing SMTP secrets unchanged

Core flow:
1. Collect raw signals from multiple channels
2. Enrich each signal with city, zone, promoter, asset type, and price hints
3. Merge signals into projects
4. Enrich project dossiers with aliases, evidence, and observation history
5. Score projects with launch, confidence, investment, and urgency scores
6. Persist projects/signals to SQLite and publish the dashboard
7. Email only the strongest new project opportunities and digest-worthy evolutions

Existing SMTP secrets remain unchanged:
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `ALERT_EMAIL_FROM`
- `ALERT_EMAIL_TO`

Run locally:

```bash
python -m pip install -r requirements.txt
python run.py
```

Outputs:
- `data/intelligence.db`
- `data/all_signals.json`
- `data/projects.json`
- `data/knowledge_base.json`
- `data/latest_alerts.json`
- `docs/index.html`
- `docs/projects.json`
