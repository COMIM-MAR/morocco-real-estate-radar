import json, html
from .config import DOCS_DIR

def build(events):
    DOCS_DIR.mkdir(exist_ok=True)
    rows="".join(f"<tr><td>{e.total_score}</td><td>{html.escape(e.channel)}</td><td>{html.escape(e.source)}</td><td>{html.escape(e.city or '')}</td><td>{html.escape(e.zone or '')}</td><td>{html.escape(e.asset_type or '')}</td><td>{e.price_mad or ''}</td><td><a href='{html.escape(e.url)}'>open</a></td><td>{html.escape(e.title[:120])}</td></tr>" for e in events)
    page=f"""<!doctype html><html><head><meta charset='utf-8'><title>Morocco Real Estate Intelligence</title><style>body{{font-family:Arial;margin:24px}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:8px}}th{{background:#f5f5f5}}</style></head><body><h1>Morocco Real Estate Intelligence</h1><p>Dernière mise à jour automatique GitHub Actions.</p><table><tr><th>Score</th><th>Canal</th><th>Source</th><th>Ville</th><th>Zone</th><th>Type</th><th>Prix</th><th>Lien</th><th>Titre</th></tr>{rows}</table></body></html>"""
    (DOCS_DIR/"index.html").write_text(page,encoding="utf-8")
    (DOCS_DIR/"events.json").write_text(json.dumps([e.to_dict() for e in events],ensure_ascii=False,indent=2),encoding="utf-8")
