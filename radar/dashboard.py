from __future__ import annotations
import html
import json
from .config import DOCS_DIR
from .models import Signal


def render_dashboard(signals: list[Signal]) -> None:
    DOCS_DIR.mkdir(exist_ok=True)
    data = [s.to_dict() for s in signals]
    (DOCS_DIR / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = []
    for s in sorted(signals, key=lambda x: x.total_score, reverse=True)[:200]:
        rows.append(f"""
        <tr>
          <td><b>{s.total_score}</b><br><small>Opp {s.opportunity_score} / Conf {s.confidence_score}</small></td>
          <td>{html.escape(s.channel)}</td>
          <td>{html.escape(s.source)}</td>
          <td>{html.escape(s.city or '—')}</td>
          <td>{html.escape(s.zone or '—')}</td>
          <td>{html.escape(s.asset_type or '—')}</td>
          <td>{html.escape(str(s.price_mad or '—'))}</td>
          <td><a href="{html.escape(s.url)}" target="_blank">{html.escape(s.title[:120])}</a><br><small>{html.escape('; '.join(s.reasons[:4]))}</small></td>
        </tr>""")
    html_doc = f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Morocco Real Estate Intelligence</title>
<style>
body{{font-family:Inter,Arial,sans-serif;margin:24px;background:#f7f7f8;color:#111}}h1{{margin-bottom:4px}}.card{{background:white;border-radius:14px;padding:18px;box-shadow:0 1px 8px #0001;margin-bottom:18px}}table{{width:100%;border-collapse:collapse;background:white}}td,th{{padding:10px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}}th{{background:#111;color:white;position:sticky;top:0}}small{{color:#666}}a{{color:#0645ad}}</style>
</head><body><div class="card"><h1>Morocco Real Estate Intelligence</h1><p>Dashboard généré automatiquement par GitHub Actions. Signaux affichés: {len(signals)}</p></div>
<table><thead><tr><th>Score</th><th>Canal</th><th>Source</th><th>Ville</th><th>Zone</th><th>Type</th><th>Prix MAD</th><th>Signal</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</body></html>"""
    (DOCS_DIR / "index.html").write_text(html_doc, encoding="utf-8")
