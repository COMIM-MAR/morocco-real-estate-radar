# Morocco Real Estate Intelligence Engine

This repository is now structured as a project-level intelligence engine instead of a listing radar.

Current foundation implemented in this repo:
- modular collectors under `collectors/` for promoters, Google, Meta Ads, news, social, urbanism, and listings
- project-level entity resolution and fusion
- SQLite persistence at `data/intelligence.db`
- project dossiers with aliases, evidence, channels, URLs, and update history
- dashboard publishing in `docs/index.html` with filters, favorites, dossier view, timeline exploration, and dedicated project pages under `docs/projects/`
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
python -m playwright install chromium
python run.py
```

Meta Ads collector:
- default mode is `playwright` when Playwright is installed
- fallback mode is HTTP parsing when Playwright is unavailable or blocked
- useful env vars:
  - `META_COLLECTOR_MODE=playwright|http`
  - `META_PLAYWRIGHT_HEADLESS=1`
  - `META_PLAYWRIGHT_TIMEOUT_MS=45000`
  - `META_PLAYWRIGHT_WAIT_MS=4500`
  - `META_STORAGE_STATE_PATH=/path/to/storage-state.json` for an authenticated browser session if Meta challenges anonymous traffic
  - `META_SSL_INSECURE=1` only for temporary debugging, never as a long-term production setting

Most robust setup for Meta:
1. Install dependencies and Chromium
   ```bash
   python -m pip install -r requirements.txt
   python -m playwright install chromium
   ```
2. Create an authenticated browser storage state locally
   ```bash
   python scripts/meta_storage_state_login.py
   ```
3. This writes a reusable session file by default to `secrets/meta-storage-state.json`
4. Run locally with:
   ```bash
   META_STORAGE_STATE_PATH=secrets/meta-storage-state.json python run.py
   ```
5. For GitHub Actions, base64-encode the file and store it in the repository secret `META_STORAGE_STATE_JSON_B64`
   ```bash
   base64 < secrets/meta-storage-state.json
   ```

GitHub Actions:
- the workflow installs Chromium automatically with `python -m playwright install --with-deps chromium`
- if the secret `META_STORAGE_STATE_JSON_B64` is present, the workflow restores `secrets/meta-storage-state.json` automatically
- Meta exact ad extraction remains dependent on Meta Ad Library allowing automated access from the runner
- the most reliable mode is Playwright + authenticated `storage_state`
- if Meta still serves a client challenge, the collector falls back to watch links instead of producing fake confirmations

Outputs:
- `data/intelligence.db`
- `data/all_signals.json`
- `data/projects.json`
- `data/knowledge_base.json`
- `data/latest_alerts.json`
- `docs/index.html`
- `docs/projects.json`
