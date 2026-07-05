# Morocco Real Estate Intelligence V3

Radar immobilier centré sur les signaux de lancement/projets, avec une facette annonces moins prédominante.

## Secrets GitHub à conserver

Cette version utilise les mêmes secrets que ton radar actuel :

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `ALERT_EMAIL_FROM`
- `ALERT_EMAIL_TO`

Tu n'as pas besoin de les recréer si tu remplaces les fichiers dans le même dépôt.

## Dashboard

Activer GitHub Pages : Settings → Pages → Deploy from a branch → `main` → `/docs`.

## Scheduler

`.github/workflows/radar.yml` lance le radar toutes les 3 heures et peut être lancé manuellement depuis l'onglet Actions.
