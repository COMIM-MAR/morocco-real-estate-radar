# Morocco Real Estate Radar

MVP de radar immobilier Maroc pour détecter les lancements, pré-commercialisations, VEFA, lots, villas, terrains R+4+, penthouses et appartements dans les villes prioritaires.

## Profil intégré

- Cash disponible: 1,5 M MAD
- Budget max: 3 M MAD si livraison sous environ 24 mois
- Objectif: location 4-5 ans puis résidence principale possible
- Priorité villes: Tanger, Casablanca, Rabat, Agadir, Marrakech, autres
- Priorité biens: villa, terrain R+4+, penthouse, appartement 3 chambres, appartement 2 chambres, studio exceptionnel
- Rendement cible: 7-8% avec forte plus-value
- VEFA et rénovation acceptées

## Lancement local

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

## GitHub Actions

Le workflow `.github/workflows/radar.yml` lance le radar toutes les 2 heures et peut aussi être déclenché manuellement.

## Secrets Telegram recommandés

Créer un bot via BotFather, puis ajouter dans GitHub > Settings > Secrets and variables > Actions:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Secrets email optionnels

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `ALERT_EMAIL_TO`
- `ALERT_EMAIL_FROM`

## Personnalisation

Modifier `config/profile.yml` pour ajouter:

- nouvelles sources
- nouveaux quartiers
- mots-clés
- seuils d’alerte
- pondération du scoring

## Limites du MVP

- Scraping générique: certains sites dynamiques peuvent nécessiter Playwright.
- Les plateformes administratives et réseaux sociaux ont souvent des contraintes d’accès; il faudra ajouter des connecteurs dédiés.
- Les prix et rendements sont détectés de manière prudente; une V2 peut intégrer une base de comparables par m².
