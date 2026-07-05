import html
import json

from .config import DOCS_DIR


def build(projects):
    DOCS_DIR.mkdir(exist_ok=True)
    urgent = [project for project in projects if project.status == "urgent"][:6]
    rows = "".join(
        f"<tr><td>{project.confidence_score}</td><td>{project.investment_score}</td>"
        f"<td>{html.escape(project.name)}</td><td>{html.escape(project.city or '')}</td>"
        f"<td>{html.escape(project.promoter or '')}</td><td>{html.escape(project.asset_type or '')}</td>"
        f"<td>{project.prices.get('min') or ''}</td><td>{html.escape(', '.join(project.sources[:4]))}</td>"
        f"<td>{project.evidence.get('signal_count', 0)}</td><td>{html.escape(project.status)}</td></tr>"
        for project in projects
    )
    urgent_cards = "".join(
        f"<article class='card'><p class='eyebrow'>🔥 Nouveau projet</p><h3>{html.escape(project.name)}</h3>"
        f"<p>{html.escape(project.summary)}</p><p class='meta'>Confidence {project.confidence_score}/100 · "
        f"Investment {project.investment_score}/100</p></article>"
        for project in urgent
    ) or "<article class='card'><p>Aucun nouveau projet urgent pour le moment.</p></article>"
    timeline = "".join(
        f"<li><strong>{html.escape(project.name)}</strong> · {html.escape(project.last_updated_at[:10])} · "
        f"{html.escape(project.recommendation)} · {project.evidence.get('source_count', 0)} sources</li>"
        for project in projects[:12]
    )
    dossier_cards = "".join(
        f"<article class='card'><p class='eyebrow'>Knowledge Base</p><h3>{html.escape(project.name)}</h3>"
        f"<p>{html.escape(', '.join(project.aliases[:3]) or project.name)}</p>"
        f"<p class='meta'>{project.evidence.get('source_count', 0)} sources · "
        f"{project.evidence.get('channel_count', 0)} channels · "
        f"{len(project.timeline)} updates</p></article>"
        for project in projects[:4]
    )
    page = f"""<!doctype html>
<html lang='fr'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Morocco Real Estate Intelligence</title>
  <style>
    :root {{
      --bg: #f5f1e8;
      --card: #fffaf2;
      --ink: #1f2933;
      --muted: #52606d;
      --accent: #b45309;
      --accent-soft: #fde7c7;
      --line: #e5dccd;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: Georgia, 'Times New Roman', serif; background: linear-gradient(180deg, #f7f1e8 0%, #efe6d6 100%); color: var(--ink); }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1, h2, h3 {{ margin: 0; }}
    p {{ color: var(--muted); }}
    .hero {{ display: grid; gap: 16px; padding: 28px; border: 1px solid var(--line); border-radius: 24px; background: rgba(255,255,255,0.72); backdrop-filter: blur(10px); }}
    .hero-grid, .cards, .stats {{ display: grid; gap: 16px; }}
    .hero-grid {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .cards {{ grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); margin-top: 18px; }}
    .card, .panel {{ padding: 20px; border-radius: 20px; border: 1px solid var(--line); background: var(--card); box-shadow: 0 10px 30px rgba(24, 39, 75, 0.06); }}
    .eyebrow {{ margin: 0 0 8px; color: var(--accent); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }}
    .stats {{ grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); margin: 24px 0; }}
    .stat-value {{ font-size: 34px; color: var(--accent); }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ padding: 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }}
    ul {{ padding-left: 18px; color: var(--muted); }}
    .sections {{ display: grid; grid-template-columns: 2fr 1fr; gap: 16px; }}
    .meta {{ color: var(--muted); font-size: 14px; }}
    @media (max-width: 900px) {{ .sections {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <main>
    <section class='hero'>
      <p class='eyebrow'>Morocco Real Estate Intelligence Engine</p>
      <h1>Des projets avant les annonces.</h1>
      <p>Le moteur fusionne les signaux promoteurs, Google, Meta, urbanisme, social et listings pour suivre des projets immobiliers au lieu d'empiler des annonces.</p>
      <div class='hero-grid'>
        <div class='panel'><h3>🔥 Nouveaux projets</h3><p>{len(urgent)} signaux urgents à haute confiance.</p></div>
        <div class='panel'><h3>📍 Carte</h3><p>Fondation prête pour enrichissement GPS, quartiers et mobilité.</p></div>
        <div class='panel'><h3>📅 Timeline</h3><p>Chaque projet conserve première détection et dernières évolutions.</p></div>
        <div class='panel'><h3>🧠 Knowledge Base</h3><p>Chaque projet devient une fiche enrichie avec alias, sources, historique et signaux.</p></div>
      </div>
    </section>

    <section class='stats'>
      <div class='panel'><div class='stat-value'>{len(projects)}</div><p>Projets suivis</p></div>
      <div class='panel'><div class='stat-value'>{sum(len(project.sources) for project in projects)}</div><p>Sources fusionnées</p></div>
      <div class='panel'><div class='stat-value'>{sum(len(project.signals) for project in projects)}</div><p>Signaux collectés</p></div>
      <div class='panel'><div class='stat-value'>{len([project for project in projects if project.status == 'watch'])}</div><p>À surveiller</p></div>
    </section>

    <section>
      <h2>🔥 Nouveaux projets</h2>
      <div class='cards'>{urgent_cards}</div>
    </section>

    <section style='margin-top: 24px;'>
      <h2>🧠 Project Dossiers</h2>
      <div class='cards'>{dossier_cards}</div>
    </section>

    <section class='sections' style='margin-top: 24px;'>
      <div class='panel'>
        <h2>📊 Intelligence Projects</h2>
        <table>
          <tr><th>Confidence</th><th>Investment</th><th>Projet</th><th>Ville</th><th>Promoteur</th><th>Type</th><th>Prix min</th><th>Sources</th><th>Signals</th><th>Statut</th></tr>
          {rows}
        </table>
      </div>
      <div class='panel'>
        <h2>📅 Timeline</h2>
        <ul>{timeline}</ul>
      </div>
    </section>
  </main>
</body>
</html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / "projects.json").write_text(
        json.dumps([project.to_dict() for project in projects], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
