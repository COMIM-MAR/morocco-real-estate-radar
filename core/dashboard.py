import html
import json
import re
from pathlib import Path

from .config import DOCS_DIR


ALL_STATUSES = [
    ("urgent", "Signal très fort avec niveau de confiance élevé."),
    ("watch", "Projet crédible à surveiller activement."),
    ("monitor", "Projet faible ou encore trop tôt à qualifier."),
]

STATUS_LABELS = {
    "urgent": "Urgent",
    "watch": "À surveiller",
    "monitor": "En observation",
}

ALL_ASSET_TYPES = [
    ("villa", "Villa"),
    ("land_r4_plus", "Terrain / Immeuble R+4+"),
    ("penthouse", "Penthouse"),
    ("apartment_3_bed", "Appartement 3 chambres"),
    ("apartment_2_bed", "Appartement 2 chambres"),
    ("studio", "Studio"),
    ("apartment_unknown", "Appartement"),
]
REVIEW_STATUSES = [
    ("new", "Nouveau", "Projet détecté par le radar mais pas encore qualifié par toi."),
    ("to_qualify", "À qualifier", "Projet ouvert ou repéré par toi, mais décision pas encore prise."),
    ("interested", "Intéressé", "Projet que tu veux creuser, contacter ou visiter."),
    ("in_contact", "En contact", "Projet pour lequel tu as déjà commencé des échanges ou actions."),
    ("archived", "Archivé", "Projet vu, traité, mais que tu ne souhaites pas poursuivre."),
]

KPI_EXPLANATIONS = {
    "projects": "Nombre total de projets actuellement présents dans la base affichée.",
    "urgent": "Nombre de projets dépassant le seuil de confiance immédiat.",
    "watch": "Nombre de projets crédibles mais encore à surveiller.",
    "sources": "Total des sources distinctes fusionnées dans les projets visibles.",
    "cities": "Nombre de villes couvertes par les projets actuellement visibles dans la base.",
    "confirmations_global": "Total des confirmations fortes détectées entre plusieurs canaux indépendants sur l'ensemble des projets visibles.",
    "launch": "Score de lancement = poids des signaux primaires + bonus listings + bonus confirmations. Plus il monte, plus le projet ressemble à un vrai lancement commercial.",
    "confidence": "Score de confiance = poids de crédibilité des signaux primaires + bonus diversité de sources + bonus confirmations multi-canaux + bonus canaux primaires.",
    "investment": "Score investissement = priorité de la ville + bonus zone + bonus type d'actif + ajustement selon budget/prix détecté.",
    "roi": "ROI 5 ans = estimation simplifiée dérivée du score investissement, légèrement renforcée si la confiance est élevée.",
    "confirmations": "Nombre de confirmations fortes entre plusieurs canaux indépendants.",
    "timeline": "Historique des runs où le projet a été observé et mis à jour. Chaque ligne correspond à un passage du moteur de veille.",
}

REVIEW_LABELS = {value: label for value, label, _ in REVIEW_STATUSES}
REVIEW_HELP = " · ".join(f"{label}: {description}" for _, label, description in REVIEW_STATUSES)


def esc(value):
    return html.escape(str(value or ""))


def build(projects):
    DOCS_DIR.mkdir(exist_ok=True)
    projects_dir = DOCS_DIR / "projects"
    projects_dir.mkdir(exist_ok=True)
    payload = [project.to_dict() for project in projects]
    for project in projects:
        write_project_page(project, projects_dir)
    write_index(projects, payload)
    (DOCS_DIR / "projects.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (projects_dir / "index.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def tooltip(label: str, text: str) -> str:
    return (
        f"{esc(label)}"
        f"<span class='tip' tabindex='0' data-tip='{esc(text)}'>i</span>"
    )


def status_display(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "À confirmer")


def source_list(items) -> str:
    if not items:
        return "<li>Aucune source disponible dans cette catégorie.</li>"
    return "".join(
        f"<li><strong>{esc(item.get('kind_label'))}</strong> · {esc(item.get('label'))}<br>"
        f"<span>{esc(item.get('description'))}</span><br>"
        f"<span>Niveau: {esc('preuve directe' if item.get('proof_level') == 'direct' else 'veille / indice')}</span><br>"
        f"<a href='{esc(item.get('url'))}' target='_blank' rel='noreferrer'>ouvrir la source</a></li>"
        for item in items
    )


def value_or_na(value):
    return "n/a" if value in (None, "") else value


def project_media_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://", "data:")):
        return url
    if url.startswith("../"):
        return url
    return f"../{url.lstrip('./')}"


def media_signal_map(project) -> dict[str, object]:
    mapping = {}
    for signal in project.signals:
        metadata = signal.metadata or {}
        ad_id = str(metadata.get("ad_id") or "").strip()
        if ad_id:
            mapping[ad_id] = signal
    return mapping


def media_ad_id(url: str) -> str | None:
    match = re.search(r"meta-ad-(\d+)\.(?:png|jpg|jpeg|webp|gif|mp4|mov)$", url or "")
    return match.group(1) if match else None


def render_image_card(url: str, signal) -> str:
    media_url = project_media_url(url)
    ad_id = (signal.metadata or {}).get("ad_id") if signal else media_ad_id(url) or "n/a"
    title = (signal.metadata or {}).get("page_name") if signal else None
    title = title or (signal.source if signal else "Capture publicitaire")
    excerpt = (signal.text or "")[:220] if signal else ""
    source_link = (
        f"<a href='{esc(signal.url)}' target='_blank' rel='noreferrer'>Ouvrir la source Meta</a>"
        if signal
        else ""
    )
    return (
        f"<article class='gallery-card-wrap'>"
        f"<a class='gallery-card' href='{esc(media_url)}' target='_blank' rel='noreferrer' aria-label='Ouvrir le visuel en grand'>"
        f"<img src='{esc(media_url)}' alt='image projet' class='gallery-image'>"
        f"</a>"
        f"<div class='gallery-meta'>"
        f"<strong>{esc(title)}</strong><br>"
        f"<span class='gallery-caption'>ad_id {esc(ad_id)} · cliquer pour agrandir</span>"
        f"<p class='gallery-text'>{esc(excerpt)}</p>"
        f"<div class='gallery-actions'>"
        f"<a class='gallery-link' href='{esc(media_url)}' target='_blank' rel='noreferrer'>Voir en grand</a>"
        f"{source_link}"
        f"</div>"
        f"</div>"
        f"</article>"
    )


def confirmation_list(items) -> str:
    if not items:
        return "<li>Aucune confirmation forte.</li>"
    blocks = []
    for item in items:
        proofs = item.get("proofs", [])
        proofs_html = "".join(
            f"<li><strong>{esc(proof.get('channel_label'))}</strong> · {esc(proof.get('title'))}<br>"
            f"<span>{esc(proof.get('proof_note'))}</span><br>"
            f"<a href='{esc(proof.get('url'))}' target='_blank' rel='noreferrer'>ouvrir la preuve</a></li>"
            for proof in proofs
        ) or "<li>Aucune preuve attachée.</li>"
        blocks.append(
            f"<li><strong>{esc(item.get('label'))}</strong><br>"
            f"<span>Preuves attachées :</span>"
            f"<ul class='list' style='margin-top:8px;'>{proofs_html}</ul></li>"
        )
    return "".join(blocks)


def write_project_page(project, projects_dir: Path):
    slug = project.evidence.get("project_slug", project.project_id)
    infra = project.evidence.get("infrastructure", {})
    roi = project.evidence.get("roi", {})
    evolution = project.evidence.get("price_evolution", {})
    practical = project.evidence.get("practical", {})
    ai_analysis = project.evidence.get("ai_analysis", {})
    geo = project.evidence.get("geo", {})
    confirmations = confirmation_list(project.evidence.get("confirmation_details", [])[:8])
    changes = "".join(f"<li>{esc(item)}</li>" for item in project.evidence.get("changes", [])[:8]) or "<li>Aucune évolution récente.</li>"
    timeline = "".join(
        f"<li><strong>{esc(item.get('observed_at') or item.get('detected_at'))}</strong><br>"
        f"<span>{esc(item.get('title') or status_display(item.get('status')) or item.get('recommendation'))}</span><br>"
        f"<span>Launch {esc(item.get('launch_score'))} · Confidence {esc(item.get('confidence_score'))} · Investment {esc(item.get('investment_score'))}</span></li>"
        for item in project.timeline[:10]
    ) or "<li>Aucune timeline.</li>"
    official_sources = source_list(project.evidence.get("official_links", []))
    social_sources = source_list(project.evidence.get("social_links", []))
    listing_sources = source_list(project.evidence.get("listing_links", []))
    news_sources = source_list(project.evidence.get("news_links", []))
    urbanism_sources = source_list(project.evidence.get("urbanism_links", []))
    images = project.evidence.get("images", [])
    videos = project.evidence.get("videos", [])
    signal_by_ad_id = media_signal_map(project)
    image_block = "".join(render_image_card(url, signal_by_ad_id.get(media_ad_id(url) or "")) for url in images[:6])
    video_block = "".join(
        f"<article class='gallery-card-wrap'>"
        f"<div class='gallery-card'>"
        f"<video class='gallery-video' controls preload='metadata' playsinline>"
        f"<source src='{esc(project_media_url(url))}'>"
        "Votre navigateur ne supporte pas la lecture vidéo."
        "</video>"
        f"</div>"
        f"<div class='gallery-meta'>"
        f"<span class='gallery-caption'>Vidéo pub</span>"
        f"<div class='gallery-actions'><a class='gallery-link' href='{esc(project_media_url(url))}' target='_blank' rel='noreferrer'>Ouvrir la vidéo</a></div>"
        f"</div>"
        f"</article>"
        for url in videos[:4]
    )
    media_block = image_block + video_block or "<p class='muted'>Aucun visuel exploitable n'a été détecté automatiquement pour le moment.</p>"
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(project.name)} · Morocco Real Estate Intelligence</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  >
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lexend:wght@600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #f4f5fb;
      --panel: #ffffff;
      --panel-soft: #f7f8fd;
      --line: #e7e8f2;
      --ink: #14152b;
      --muted: #676c85;
      --accent: #4f46e5;
      --accent-ink: #ffffff;
      --accent-soft: #eef0ff;
      --radius: 20px;
      --radius-sm: 12px;
      --shadow-sm: 0 1px 2px rgba(20, 21, 43, .04);
      --shadow-md: 0 14px 30px -12px rgba(79, 70, 229, .16), 0 2px 8px rgba(20, 21, 43, .04);
    }}
    * {{ box-sizing: border-box; min-width: 0; }}
    body {{
      margin: 0; background:
        radial-gradient(1100px 420px at 12% -8%, #eef0ff 0%, rgba(238,240,255,0) 60%),
        var(--bg);
      color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    h1, h2, h3, h4 {{ font-family: Lexend, Inter, sans-serif; letter-spacing: -.01em; }}
    .topbar {{
      position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: space-between;
      padding: 14px 20px; background: rgba(244, 245, 251, .78); backdrop-filter: blur(10px); border-bottom: 1px solid var(--line);
    }}
    .topbar-inner {{ max-width: 980px; margin: 0 auto; width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 14px; color: var(--ink); text-decoration: none; }}
    .brand-mark {{
      width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; color: #fff; font-size: 15px;
      background: linear-gradient(135deg, #4f46e5, #7c6cff);
      box-shadow: var(--shadow-sm);
    }}
    .back-link {{
      display: inline-flex; align-items: center; gap: 6px; font-size: 13px; font-weight: 600; color: var(--muted);
      text-decoration: none; padding: 8px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--panel);
      transition: color .15s ease, border-color .15s ease;
    }}
    .back-link:hover {{ color: var(--accent); border-color: #c7c9f7; text-decoration: none; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 24px 16px 56px; display: grid; gap: 16px; }}
    .panel {{ background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: 22px; box-shadow: var(--shadow-sm); }}
    .grid, .facts, .metrics {{ display: grid; gap: 12px; }}
    .metrics {{ grid-template-columns: repeat(4, 1fr); }}
    .facts {{ grid-template-columns: 1fr 1fr; }}
    .metric, .fact-box {{ border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); padding: 16px; }}
    .metric strong {{ display: block; font-size: 30px; font-weight: 700; color: var(--accent); margin-top: 6px; font-family: Lexend, Inter, sans-serif; }}
    .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
    .muted, p, li {{ color: var(--muted); line-height: 1.55; overflow-wrap: anywhere; }}
    .pill {{ display: inline-flex; align-items: center; padding: 6px 12px; border-radius: 999px; background: var(--panel-soft); border: 1px solid var(--line); color: var(--muted); margin: 4px 8px 0 0; font-size: 12.5px; font-weight: 600; }}
    .pill.review-new {{ background: #eef2ff; color: #4338ca; border-color: #e0e2ff; }}
    .pill.review-to_qualify {{ background: #fff7ed; color: #b45309; border-color: #fce9d1; }}
    .pill.review-interested {{ background: #ecfdf5; color: #047857; border-color: #d3f7e6; }}
    .pill.review-in_contact {{ background: #ecfeff; color: #0e7490; border-color: #d3f4fa; }}
    .pill.review-archived {{ background: #f3f4f6; color: #4b5563; border-color: #e5e7eb; }}
    .tip {{
      display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
      margin-left: 6px; border-radius: 999px; border: 1px solid var(--line); font-size: 11px; color: var(--muted); cursor: help; position: relative;
    }}
    .tip:hover::after, .tip:focus::after {{
      content: attr(data-tip); position: absolute; left: 50%; top: calc(100% + 8px); transform: translateX(-50%);
      width: 260px; padding: 10px 12px; background: #14152b; color: #fff; border-radius: 10px; font-size: 12px; line-height: 1.4; white-space: normal; z-index: 10;
    }}
    .tip:hover::before, .tip:focus::before {{
      content: ""; position: absolute; left: 50%; top: 100%; transform: translateX(-50%);
      border: 6px solid transparent; border-bottom-color: #14152b;
    }}
    .list {{ list-style: none; padding: 0; margin: 12px 0 0 0; display: grid; gap: 8px; }}
    .list li {{ padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: #fff; }}
    .map-wrap {{ display: grid; gap: 10px; }}
    #projectMap {{ width: 100%; min-height: 320px; border-radius: 16px; border: 1px solid var(--line); overflow: hidden; }}
    .gallery {{ display: grid; gap: 10px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }}
    .gallery-card-wrap {{ border: 1px solid var(--line); border-radius: var(--radius-sm); padding: 10px; background: #fff; display: grid; gap: 10px; align-content: start; transition: box-shadow .15s ease, border-color .15s ease; }}
    .gallery-card-wrap:hover {{ box-shadow: var(--shadow-md); border-color: #d8d9f5; }}
    .gallery-card {{
      display: grid; gap: 8px; padding: 0; border: 0; background: transparent; text-align: left;
    }}
    .gallery-image {{ width: 100%; height: 320px; object-fit: contain; border-radius: 12px; border: 1px solid var(--line); background: var(--panel-soft); }}
    .gallery-video {{ width: 100%; height: 320px; object-fit: contain; border-radius: 12px; border: 1px solid var(--line); background: #000; }}
    .gallery-caption {{ font-size: 12px; color: var(--muted); }}
    .gallery-meta {{ display: grid; gap: 6px; }}
    .gallery-text {{ margin: 0; font-size: 13px; color: var(--muted); display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }}
    .gallery-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .gallery-link {{
      display: inline-flex; align-items: center; justify-content: center; min-height: 36px; padding: 8px 14px;
      border-radius: 10px; border: 1px solid var(--line); background: #fff; color: var(--ink); text-decoration: none; font-weight: 600; font-size: 13px;
      transition: border-color .15s ease, background .15s ease;
    }}
    .gallery-link:hover {{ text-decoration: none; border-color: #c7c9f7; background: var(--accent-soft); }}
    .lightbox {{
      position: fixed; inset: 0; background: rgba(15, 15, 30, .84); backdrop-filter: blur(2px); display: none; align-items: center; justify-content: center; padding: 24px; z-index: 2000;
    }}
    .lightbox.is-open {{ display: flex; }}
    .lightbox-panel {{
      width: min(1180px, 100%); max-height: 92vh; background: #0f1024; border-radius: 20px; border: 1px solid rgba(255,255,255,.08); padding: 16px; display: grid; gap: 12px;
      box-shadow: 0 30px 60px -20px rgba(0,0,0,.5);
    }}
    .lightbox-head {{ display: flex; justify-content: space-between; align-items: center; gap: 12px; color: #fff; }}
    .lightbox-actions {{ display: flex; gap: 10px; flex-wrap: wrap; }}
    .lightbox-btn {{
      min-height: 38px; padding: 8px 14px; border-radius: 10px; border: 1px solid rgba(255,255,255,.18); background: rgba(255,255,255,.04); color: #fff; cursor: pointer;
      font-weight: 600; transition: background .15s ease;
    }}
    .lightbox-btn:hover {{ background: rgba(255,255,255,.12); }}
    .lightbox-media-wrap {{ overflow: auto; max-height: 76vh; border-radius: 14px; background: #020314; }}
    .lightbox-image {{ width: 100%; height: auto; display: block; }}
    .lightbox-video {{ width: 100%; max-height: 76vh; display: block; }}
    .review-toolbar {{ display: grid; gap: 10px; margin-top: 16px; }}
    .review-select {{
      width: 100%; max-width: 280px; min-height: 44px; padding: 10px 14px;
      border: 1px solid var(--line); border-radius: var(--radius-sm); background: #fff; color: var(--ink); font-weight: 600;
      transition: border-color .15s ease, box-shadow .15s ease;
    }}
    .review-select:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }}
    .notes-box {{
      width: 100%; min-height: 110px; margin-top: 12px; padding: 12px 14px; resize: vertical;
      border: 1px solid var(--line); border-radius: var(--radius-sm); background: #fff; color: var(--ink);
      transition: border-color .15s ease, box-shadow .15s ease;
    }}
    .notes-box:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }}
    .comment-actions {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }}
    .comment-btn {{
      min-height: 42px; padding: 9px 16px; border-radius: var(--radius-sm); border: 1px solid transparent;
      background: var(--accent); color: #fff; cursor: pointer; font-weight: 600; font-size: 13.5px;
      box-shadow: var(--shadow-sm); transition: transform .1s ease, box-shadow .15s ease;
    }}
    .comment-btn:hover {{ box-shadow: var(--shadow-md); transform: translateY(-1px); }}
    .comment-entry-actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }}
    .comment-entry-btn {{
      min-height: 32px; padding: 6px 12px; border-radius: 10px; border: 1px solid var(--line);
      background: #fff; color: var(--ink); cursor: pointer; font-weight: 600; font-size: 12.5px; transition: border-color .15s ease;
    }}
    .comment-entry-btn:hover {{ border-color: #c7c9f7; color: var(--accent); }}
    .inline-meta {{ display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }}
    .mini-card {{ border: 1px solid var(--line); border-radius: var(--radius-sm); background: #fff; padding: 12px 14px; }}
    a {{ color: var(--accent); text-decoration: none; overflow-wrap: anywhere; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 860px) {{ .metrics, .facts {{ grid-template-columns: 1fr 1fr; }} }}
    @media (max-width: 640px) {{ .metrics, .facts {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="../index.html">
        <span class="brand-mark">MR</span>
        <span>Morocco Real Estate Intelligence</span>
      </a>
      <a class="back-link" href="../index.html">&larr; Retour à la recherche</a>
    </div>
  </div>
  <main>
    <section class="panel">
      <h1 style="margin-top:0;font-size:26px;">{esc(project.name)}</h1>
      <p style="margin-top:8px;">{esc(project.summary)}</p>
      <div style="margin-top:14px;">
        <span class="pill">{esc(status_display(project.status))}</span>
        <span class="pill">{esc(project.city or "Ville à confirmer")}</span>
        <span class="pill">{esc(project.promoter or "Promoteur à confirmer")}</span>
        <span class="pill">{esc(practical.get("asset_label"))}</span>
        <span id="reviewBadge" class="pill review-new">Nouveau</span>
      </div>
      <div class="review-toolbar">
        <select id="reviewSelect" class="review-select" aria-label="Statut manuel projet">
          <option value="new">Nouveau</option>
          <option value="to_qualify">À qualifier</option>
          <option value="interested">Intéressé</option>
          <option value="in_contact">En contact</option>
          <option value="archived">Archivé</option>
        </select>
      </div>
    </section>

    <section class="metrics">
      <div class="metric"><span class="label">{tooltip("Launch", KPI_EXPLANATIONS["launch"])}</span><strong>{project.launch_score}</strong></div>
      <div class="metric"><span class="label">{tooltip("Confidence", KPI_EXPLANATIONS["confidence"])}</span><strong>{project.confidence_score}</strong></div>
      <div class="metric"><span class="label">{tooltip("Investment", KPI_EXPLANATIONS["investment"])}</span><strong>{project.investment_score}</strong></div>
      <div class="metric"><span class="label">{tooltip("ROI 5 ans", KPI_EXPLANATIONS["roi"])}</span><strong>{esc(roi.get("five_year_upside_score"))}</strong></div>
    </section>

    <section class="facts">
      <div class="fact-box">
        <h3>Décision rapide</h3>
        <p style="margin-top:10px;">{esc(ai_analysis.get("summary") or project.evidence.get("recommendation_narrative"))}</p>
        <ul class="list">
          <li>Statut: {esc(status_display(project.status))}</li>
          <li>Type détecté: {esc(practical.get("asset_label"))}</li>
          <li>Disponibilité: {esc(practical.get("public_status"))}</li>
          <li>Prix min: {esc(value_or_na(practical.get("price_min")))} MAD</li>
          <li>Prix max: {esc(value_or_na(practical.get("price_max")))} MAD</li>
          <li>Évolution prix: {esc(evolution.get("summary"))}</li>
        </ul>
      </div>
      <div class="fact-box">
        <h3>Analyse AI</h3>
        <ul class="list">
          <li><strong>Pourquoi c'est intéressant</strong><br>{esc(" / ".join(ai_analysis.get("strengths", [])) or "Pas assez de signaux différenciants pour conclure fortement.")}</li>
          <li><strong>Points de vigilance</strong><br>{esc(" / ".join(ai_analysis.get("risks", [])) or "Aucun risque majeur détecté automatiquement.")}</li>
          <li><strong>Actions conseillées</strong><br>{esc(" / ".join(ai_analysis.get("next_steps", [])))}</li>
        </ul>
      </div>
    </section>

    <section class="panel map-wrap">
      <h3>Localisation pratique</h3>
      <p class="muted">La carte interactive sert à situer rapidement le projet. Les distances mer / gare / autoroute sont des estimations de proximité.</p>
      <div id="projectMap"></div>
      <ul class="list">
        <li>Zone: {esc(project.zone or "à confirmer")}</li>
        <li>Mer: {esc(infra.get("sea_distance_km"))} km · Gare: {esc(infra.get("station_distance_km"))} km · Autoroute: {esc(infra.get("highway_distance_km"))} km</li>
      </ul>
    </section>

    <section class="facts">
      <div class="fact-box">
        <h3>{tooltip("Confirmations", KPI_EXPLANATIONS["confirmations"])}</h3>
        <ul class="list">{confirmations}</ul>
      </div>
      <div class="fact-box">
        <h3>Évolutions récentes</h3>
        <ul class="list">{changes}</ul>
      </div>
    </section>

    <section class="panel">
      <h3>Qualification manuelle</h3>
      <div class="inline-meta">
        <div class="mini-card"><strong id="manualStatusLabel">Nouveau</strong><br><span class="muted">Statut actuel</span></div>
        <div class="mini-card"><strong id="manualCreatedAt">—</strong><br><span class="muted">Créé le</span></div>
        <div class="mini-card"><strong id="manualUpdatedAt">—</strong><br><span class="muted">Dernier changement</span></div>
      </div>
      <ul id="manualWorkflow" class="list"></ul>
      <h4 style="margin-top:14px;">Journal des commentaires</h4>
      <p class="muted">Ajoute un commentaire à chaque étape: qualification manuelle, appel, réception des plans, visite, négociation, motif d’archivage, etc.</p>
      <textarea id="manualCommentInput" class="notes-box" placeholder="Ex: appelé le promoteur, il m'envoie les plans demain. Ticket annoncé: 1,9 MDH."></textarea>
      <div class="comment-actions">
        <button id="manualCommentAdd" class="comment-btn" type="button">Ajouter le commentaire</button>
      </div>
      <ul id="manualComments" class="list"></ul>
    </section>

    <section class="panel">
      <h3>{tooltip("Timeline", KPI_EXPLANATIONS["timeline"])}</h3>
      <p class="muted">La timeline correspond aux différents runs du moteur où ce projet a été observé ou mis à jour.</p>
      <ul class="list">{timeline}</ul>
    </section>

    <section class="facts">
      <div class="fact-box">
        <h3>Site officiel / sources promoteur</h3>
        <ul class="list">{official_sources}</ul>
      </div>
      <div class="fact-box">
        <h3>Réseaux / publicité</h3>
        <ul class="list">{social_sources}</ul>
      </div>
    </section>

    <section class="facts">
      <div class="fact-box">
        <h3>Portails / disponibilités</h3>
        <ul class="list">{listing_sources}</ul>
      </div>
      <div class="fact-box">
        <h3>Presse / urbanisme</h3>
        <ul class="list">{news_sources}{urbanism_sources}</ul>
      </div>
    </section>

    <section class="panel">
      <h3>Visuels détectés</h3>
      <p class="muted">Quand une publicité Meta contient une image ou une vidéo exploitable, on l’affiche ici automatiquement.</p>
      <div class="gallery" style="margin-top:12px;">{media_block}</div>
    </section>
  </main>

  <div id="mediaLightbox" class="lightbox" aria-hidden="true">
    <div class="lightbox-panel" role="dialog" aria-modal="true" aria-label="Visuel publicité">
      <div class="lightbox-head">
        <strong>Preuve publicitaire</strong>
        <div class="lightbox-actions">
          <a id="mediaOpenNew" class="lightbox-btn" href="#" target="_blank" rel="noreferrer">Ouvrir l’image</a>
          <button id="mediaClose" type="button" class="lightbox-btn">Fermer</button>
        </div>
      </div>
      <div id="mediaLightboxBody" class="lightbox-media-wrap"></div>
    </div>
  </div>

  <script src="../supabase-config.js"></script>
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    (function() {{
      const qualificationKey = "morocco-real-estate-intelligence:qualification";
      const supabaseConfig = window.__RADAR_SUPABASE__ || {{}};
      const supabaseTable = "project_qualifications";
      const reviewLabels = {json.dumps(REVIEW_LABELS, ensure_ascii=False)};
      const projectId = {json.dumps(project.project_id)};
      const reviewBadge = document.getElementById("reviewBadge");
      const reviewSelect = document.getElementById("reviewSelect");
      const workflowList = document.getElementById("manualWorkflow");
      const commentInput = document.getElementById("manualCommentInput");
      const commentAdd = document.getElementById("manualCommentAdd");
      const commentsList = document.getElementById("manualComments");
      const manualStatusLabel = document.getElementById("manualStatusLabel");
      const manualCreatedAt = document.getElementById("manualCreatedAt");
      const manualUpdatedAt = document.getElementById("manualUpdatedAt");
      const mediaLightbox = document.getElementById("mediaLightbox");
      const mediaLightboxBody = document.getElementById("mediaLightboxBody");
      const mediaOpenNew = document.getElementById("mediaOpenNew");
      const mediaClose = document.getElementById("mediaClose");

      function nowIso() {{
        return new Date().toISOString();
      }}

      function hasSupabaseConfig() {{
        return Boolean(supabaseConfig && supabaseConfig.url && supabaseConfig.anonKey);
      }}

      async function supabaseRequest(path, options = {{}}) {{
        const response = await fetch(`${{String(supabaseConfig.url).replace(/\\/$/, "")}}/rest/v1/${{path}}`, {{
          ...options,
          headers: {{
            apikey: supabaseConfig.anonKey,
            Authorization: `Bearer ${{supabaseConfig.anonKey}}`,
            "Content-Type": "application/json",
            ...(options.headers || {{}}),
          }},
        }});
        if (!response.ok) {{
          const text = await response.text();
          throw new Error(`Supabase error ${{response.status}}: ${{text}}`);
        }}
        if (response.status === 204) return null;
        return response.json();
      }}

      function formatDate(value) {{
        if (!value) return "—";
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return value;
        return date.toLocaleString("fr-FR");
      }}

      function openMediaLightbox(src, type) {{
        if (!src || !mediaLightbox || !mediaLightboxBody || !mediaOpenNew) return;
        mediaOpenNew.href = src;
        mediaLightboxBody.innerHTML = type === "video"
          ? `<video class="lightbox-video" controls autoplay preload="metadata" playsinline><source src="${{src}}"></video>`
          : `<img class="lightbox-image" src="${{src}}" alt="Preuve publicitaire">`;
        mediaLightbox.classList.add("is-open");
        mediaLightbox.setAttribute("aria-hidden", "false");
      }}

      function closeMediaLightbox() {{
        if (!mediaLightbox || !mediaLightboxBody) return;
        mediaLightbox.classList.remove("is-open");
        mediaLightbox.setAttribute("aria-hidden", "true");
        mediaLightboxBody.innerHTML = "";
      }}

      function parseCommentsFromNotes(notes) {{
        if (!notes) return [];
        if (typeof notes !== "string") return [];
        try {{
          const parsed = JSON.parse(notes);
          if (parsed && Array.isArray(parsed.comments)) return parsed.comments;
        }} catch (error) {{
        }}
        return notes.trim()
          ? [{{ id: "legacy-note", text: notes.trim(), created_at: nowIso() }}]
          : [];
      }}

      function serializeComments(comments) {{
        return JSON.stringify({{ comments }});
      }}

      function loadQualifications() {{
        try {{
          return JSON.parse(localStorage.getItem(qualificationKey) || "{{}}");
        }} catch (error) {{
          return {{}};
        }}
      }}

      function defaultRecord() {{
        const createdAt = nowIso();
        return {{
          status: "new",
          notes: serializeComments([]),
          comments: [],
          created_at: createdAt,
          updated_at: createdAt,
          history: [{{ status: "new", at: createdAt }}],
        }};
      }}

      function getRecord() {{
        const data = loadQualifications();
        const existing = data[projectId];
        if (existing && typeof existing === "object") {{
          existing.status = existing.status || "new";
          existing.comments = parseCommentsFromNotes(existing.notes || "");
          existing.notes = serializeComments(existing.comments);
          existing.created_at = existing.created_at || nowIso();
          existing.updated_at = existing.updated_at || existing.created_at;
          existing.history = Array.isArray(existing.history) && existing.history.length
            ? existing.history
            : [{{ status: existing.status, at: existing.created_at }}];
          return existing;
        }}
        return defaultRecord();
      }}

      function normalizeRecord(record) {{
        const normalized = record && typeof record === "object" ? {{ ...record }} : defaultRecord();
        normalized.status = normalized.status || "new";
        normalized.comments = Array.isArray(normalized.comments)
          ? normalized.comments
          : parseCommentsFromNotes(normalized.notes || "");
        normalized.notes = serializeComments(normalized.comments);
        normalized.created_at = normalized.created_at || nowIso();
        normalized.updated_at = normalized.updated_at || normalized.created_at;
        normalized.history = Array.isArray(normalized.history) && normalized.history.length
          ? normalized.history
          : [{{ status: normalized.status, at: normalized.created_at }}];
        return normalized;
      }}

      function ensureRecord() {{
        const data = loadQualifications();
        if (!data[projectId]) {{
          data[projectId] = defaultRecord();
          localStorage.setItem(qualificationKey, JSON.stringify(data));
        }}
      }}

      function saveRecord(record) {{
        const data = loadQualifications();
        data[projectId] = normalizeRecord(record);
        localStorage.setItem(qualificationKey, JSON.stringify(data));
      }}

      async function loadRemoteRecord() {{
        if (!hasSupabaseConfig()) return null;
        const rows = await supabaseRequest(
          `${{supabaseTable}}?select=project_id,status,notes,history,created_at,updated_at&project_id=eq.${{projectId}}`
        );
        return Array.isArray(rows) && rows.length ? normalizeRecord(rows[0]) : null;
      }}

      async function persistRemoteRecord(record) {{
        if (!hasSupabaseConfig()) return normalizeRecord(record);
        const payload = normalizeRecord({{
          project_id: projectId,
          status: record.status,
          notes: serializeComments(record.comments || []),
          history: record.history || [],
          created_at: record.created_at,
          updated_at: record.updated_at,
        }});
        const rows = await supabaseRequest(
          `${{supabaseTable}}?on_conflict=project_id`,
          {{
            method: "POST",
            headers: {{
              Prefer: "return=representation,resolution=merge-duplicates",
            }},
            body: JSON.stringify([payload]),
          }},
        );
        return Array.isArray(rows) && rows.length ? normalizeRecord(rows[0]) : payload;
      }}

      function setStatus(status) {{
        const record = normalizeRecord(getRecord());
        if (record.status !== status) {{
          const changedAt = nowIso();
          record.status = status;
          record.updated_at = changedAt;
          record.history.push({{ status, at: changedAt }});
          saveRecord(record);
        }}
      }}

      function renderReview() {{
        const record = getRecord();
        const status = record.status || "new";
        reviewBadge.textContent = reviewLabels[status] || "Nouveau";
        reviewBadge.className = `pill review-${{status}}`;
        reviewSelect.value = status;
        manualStatusLabel.textContent = reviewLabels[status] || "Nouveau";
        manualCreatedAt.textContent = formatDate(record.created_at);
        manualUpdatedAt.textContent = formatDate(record.updated_at);
        workflowList.innerHTML = (record.history || []).map((item) => `
          <li><strong>${{escapeHtml(reviewLabels[item.status] || item.status)}}</strong><br><span>${{escapeHtml(formatDate(item.at))}}</span></li>
        `).join("") || "<li>Aucun historique.</li>";
        commentsList.innerHTML = [...(record.comments || [])]
          .sort((left, right) => String(right.created_at || "").localeCompare(String(left.created_at || "")))
          .map((item) => `
            <li data-comment-id="${{escapeHtml(item.id || "")}}">
              <strong>${{escapeHtml(formatDate(item.created_at))}}</strong><br>
              <span>${{escapeHtml(item.text || "")}}</span>
              <div class="comment-entry-actions">
                <button class="comment-entry-btn" type="button" data-comment-action="edit" data-comment-id="${{escapeHtml(item.id || "")}}">Modifier</button>
                <button class="comment-entry-btn" type="button" data-comment-action="delete" data-comment-id="${{escapeHtml(item.id || "")}}">Supprimer</button>
              </div>
            </li>
          `).join("") || "<li>Aucun commentaire pour le moment.</li>";
        commentsList.querySelectorAll("[data-comment-action]").forEach((button) => {{
          button.addEventListener("click", async () => {{
            const action = button.dataset.commentAction;
            const commentId = button.dataset.commentId;
            const current = normalizeRecord(getRecord());
            const comments = Array.isArray(current.comments) ? [...current.comments] : [];
            const index = comments.findIndex((item) => item.id === commentId);
            if (index === -1) return;
            if (action === "delete") {{
              comments.splice(index, 1);
            }} else if (action === "edit") {{
              const nextText = window.prompt("Modifier le commentaire", comments[index].text || "");
              if (nextText === null) return;
              const trimmed = nextText.trim();
              if (!trimmed) return;
              comments[index] = {{
                ...comments[index],
                text: trimmed,
                edited_at: nowIso(),
              }};
            }}
            current.comments = comments;
            current.notes = serializeComments(comments);
            current.updated_at = nowIso();
            saveRecord(current);
            renderReview();
            try {{
              const synced = await persistRemoteRecord(current);
              saveRecord(synced);
              renderReview();
            }} catch (error) {{
              console.warn("Supabase comment sync failed, local cache kept.", error);
            }}
          }});
        }});
      }}

      function escapeHtml(value) {{
        return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
      }}

      reviewSelect.addEventListener("change", async () => {{
        setStatus(reviewSelect.value);
        renderReview();
        try {{
          const synced = await persistRemoteRecord(getRecord());
          saveRecord(synced);
          renderReview();
        }} catch (error) {{
          console.warn("Supabase sync failed, local cache kept.", error);
        }}
      }});

      commentAdd.addEventListener("click", async () => {{
        const text = (commentInput.value || "").trim();
        if (!text) return;
        const record = normalizeRecord(getRecord());
        const createdAt = nowIso();
        record.comments = Array.isArray(record.comments) ? record.comments : [];
        record.comments.push({{
          id: `comment-${{createdAt}}-${{Math.random().toString(36).slice(2, 8)}}`,
          text,
          created_at: createdAt,
        }});
        record.notes = serializeComments(record.comments);
        record.updated_at = createdAt;
        saveRecord(record);
        commentInput.value = "";
        renderReview();
        try {{
          const synced = await persistRemoteRecord(record);
          saveRecord(synced);
          renderReview();
        }} catch (error) {{
          console.warn("Supabase comment sync failed, local cache kept.", error);
        }}
      }});

      const lat = {json.dumps(geo.get("lat"))};
      const lng = {json.dumps(geo.get("lng"))};
      ensureRecord();
      renderReview();
      loadRemoteRecord()
        .then(async (remote) => {{
          const local = normalizeRecord(getRecord());
          if (!remote) {{
            if (local.notes || local.status != "new" || (local.history || []).length > 1) {{
              const synced = await persistRemoteRecord(local);
              saveRecord(synced);
              renderReview();
            }}
            return;
          }}
          const localUpdated = new Date(local.updated_at || 0).getTime();
          const remoteUpdated = new Date(remote.updated_at || 0).getTime();
          if (localUpdated > remoteUpdated && (local.notes || local.status != "new" || (local.history || []).length > 1)) {{
            const synced = await persistRemoteRecord(local);
            saveRecord(synced);
          }} else {{
            saveRecord(remote);
          }}
          renderReview();
        }})
        .catch((error) => {{
          console.warn("Supabase unavailable, using local cache.", error);
        }});
      if (!window.L || typeof lat !== "number" || typeof lng !== "number") {{
        document.getElementById("projectMap").innerHTML = "<div style='padding:16px;color:#6b7280;'>Carte indisponible pour ce projet.</div>";
        return;
      }}
      const map = L.map("projectMap", {{ scrollWheelZoom: false }}).setView([lat, lng], 12);
      L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap"
      }}).addTo(map);
      L.marker([lat, lng]).addTo(map).bindPopup({json.dumps(project.name, ensure_ascii=False)});
    }})();
  </script>
</body>
</html>"""
    (projects_dir / f"{slug}.html").write_text(page, encoding="utf-8")


def write_index(projects, payload):
    urgent_count = len([project for project in projects if project.status == "urgent"])
    watch_count = len([project for project in projects if project.status == "watch"])
    city_count = len({project.city for project in projects if project.city})
    confirmation_count = sum(project.evidence.get("confirmation_count", 0) for project in projects)
    status_help = " · ".join(f"{status_display(name)}: {desc}" for name, desc in ALL_STATUSES)
    type_help = " · ".join(f"{label}" for _, label in ALL_ASSET_TYPES)
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Morocco Real Estate Intelligence</title>
  <link
    rel="stylesheet"
    href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
    integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
    crossorigin=""
  >
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Lexend:wght@600;700&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg: #f4f5fb;
      --panel: #ffffff;
      --panel-soft: #f7f8fd;
      --line: #e7e8f2;
      --ink: #14152b;
      --muted: #676c85;
      --accent: #4f46e5;
      --accent-ink: #ffffff;
      --accent-soft: #eef0ff;
      --urgent: #fef2f2;
      --urgent-ink: #b91c1c;
      --urgent-line: #fbdada;
      --watch: #fffbeb;
      --watch-ink: #b45309;
      --watch-line: #fbe8bf;
      --monitor: #ecfdf5;
      --monitor-ink: #047857;
      --monitor-line: #cdf3e2;
      --radius: 20px;
      --radius-sm: 12px;
      --shadow-sm: 0 1px 2px rgba(20, 21, 43, .04);
      --shadow-md: 0 14px 30px -12px rgba(79, 70, 229, .16), 0 2px 8px rgba(20, 21, 43, .04);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; background:
        radial-gradient(1200px 460px at 15% -10%, #eef0ff 0%, rgba(238,240,255,0) 62%),
        var(--bg);
      color: var(--ink); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      -webkit-font-smoothing: antialiased;
    }}
    h1, h2, h3, h4 {{ margin: 0; font-family: Lexend, Inter, sans-serif; letter-spacing: -.01em; }}
    p {{ margin: 0; }}
    input, select, button {{ font: inherit; }}
    .topbar {{
      position: sticky; top: 0; z-index: 20; display: flex; align-items: center; justify-content: center;
      padding: 14px 20px; background: rgba(244, 245, 251, .78); backdrop-filter: blur(10px); border-bottom: 1px solid var(--line);
    }}
    .topbar-inner {{ max-width: 1320px; margin: 0 auto; width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }}
    .brand {{ display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 14px; color: var(--ink); text-decoration: none; }}
    .brand-mark {{
      width: 30px; height: 30px; border-radius: 9px; display: grid; place-items: center; color: #fff; font-size: 15px;
      background: linear-gradient(135deg, #4f46e5, #7c6cff);
      box-shadow: var(--shadow-sm);
    }}
    .hero, .panel, .metric, .project-card {{ background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); box-shadow: var(--shadow-sm); }}
    .hero {{ padding: 28px; background: linear-gradient(180deg, #fbfbff 0%, var(--panel) 100%); }}
    .hero-top {{ display: flex; justify-content: space-between; gap: 20px; align-items: end; flex-wrap: wrap; }}
    .hero h1 {{ font-size: 30px; }}
    .label {{ font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--muted); }}
    .muted, .helper {{ color: var(--muted); line-height: 1.55; overflow-wrap: anywhere; }}
    .tip {{
      display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px;
      margin-left: 6px; border-radius: 999px; border: 1px solid var(--line); font-size: 11px; color: var(--muted); cursor: help; position: relative;
    }}
    .tip:hover::after, .tip:focus::after {{
      content: attr(data-tip); position: absolute; left: 50%; top: calc(100% + 8px); transform: translateX(-50%);
      width: 260px; padding: 10px 12px; background: #14152b; color: #fff; border-radius: 10px; font-size: 12px; line-height: 1.4; white-space: normal; z-index: 10;
    }}
    .tip:hover::before, .tip:focus::before {{
      content: ""; position: absolute; left: 50%; top: 100%; transform: translateX(-50%);
      border: 6px solid transparent; border-bottom-color: #14152b;
    }}
    .stats {{ display: grid; gap: 12px; grid-template-columns: repeat(5, 1fr); margin-top: 22px; }}
    .metric {{ padding: 16px; background: var(--panel-soft); box-shadow: none; }}
    .metric strong {{ display: block; font-size: 32px; font-weight: 700; color: var(--accent); margin-top: 6px; font-family: Lexend, Inter, sans-serif; }}
    .overview {{ display: grid; grid-template-columns: 1.1fr .9fr; gap: 18px; margin-top: 18px; }}
    .panel {{ padding: 20px; }}
    .layout {{ display: grid; gap: 18px; margin-top: 18px; }}
    .toolbar {{ display: grid; grid-template-columns: 1.8fr repeat(4, minmax(130px, 1fr)) minmax(140px, 1fr) auto; gap: 10px; margin-top: 18px; }}
    .field, .toggle {{
      width: 100%;
      min-height: 46px;
      border: 1px solid var(--line);
      border-radius: var(--radius-sm);
      padding: 10px 14px;
      background: #fff;
      color: var(--ink);
      transition: border-color .15s ease, box-shadow .15s ease;
    }}
    .field:focus, .toggle:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }}
    .toggle {{ cursor: pointer; background: var(--panel-soft); font-weight: 600; }}
    .toggle.is-active {{ background: var(--accent); border-color: var(--accent); color: #fff; }}
    .project-grid {{ display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); margin-top: 18px; }}
    .project-card {{ padding: 18px; display: grid; gap: 12px; overflow: hidden; transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease; }}
    .project-card:hover {{ transform: translateY(-2px); border-color: #d7d9f6; box-shadow: var(--shadow-md); }}
    .project-card.favorite {{ border-color: #c7c9f7; box-shadow: 0 0 0 3px var(--accent-soft); }}
    .card-top {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .card-top > div {{ flex: 1 1 auto; min-width: 0; }}
    .card-title {{
      font-size: 18px; font-weight: 700; line-height: 1.25; font-family: Lexend, Inter, sans-serif;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }}
    .card-subtitle {{
      margin-top: 4px;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }}
    .pill-row {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .pill {{
      display: inline-flex; align-items: center; padding: 5px 11px; border-radius: 999px;
      max-width: 100%; background: var(--panel-soft); color: var(--muted); font-size: 12px; font-weight: 600; border: 1px solid var(--line);
    }}
    .pill.urgent {{ background: var(--urgent); color: var(--urgent-ink); border-color: var(--urgent-line); }}
    .pill.watch {{ background: var(--watch); color: var(--watch-ink); border-color: var(--watch-line); }}
    .pill.monitor {{ background: var(--monitor); color: var(--monitor-ink); border-color: var(--monitor-line); }}
    .pill.review-new {{ background: #eef2ff; color: #4338ca; border-color: #e0e2ff; }}
    .pill.review-to_qualify {{ background: #fff7ed; color: #b45309; border-color: #fce9d1; }}
    .pill.review-interested {{ background: #ecfdf5; color: #047857; border-color: #d3f7e6; }}
    .pill.review-in_contact {{ background: #ecfeff; color: #0e7490; border-color: #d3f4fa; }}
    .pill.review-archived {{ background: #f3f4f6; color: #4b5563; border-color: #e5e7eb; }}
    .project-summary {{
      display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
      min-height: 4.5em;
    }}
    .scores {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }}
    .score {{ border: 1px solid var(--line); border-radius: var(--radius-sm); background: var(--panel-soft); padding: 10px 12px; min-width: 0; }}
    .score span {{ display: block; font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; }}
    .score strong {{ display: block; font-size: 21px; margin-top: 4px; color: var(--ink); font-family: Lexend, Inter, sans-serif; }}
    .map-panel {{ min-height: 420px; }}
    #overviewMap {{ width: 100%; min-height: 320px; border-radius: 16px; border: 1px solid var(--line); overflow: hidden; margin-top: 14px; }}
    .list {{ list-style: none; padding: 0; margin: 12px 0 0 0; display: grid; gap: 8px; }}
    .list li {{ color: var(--muted); padding: 12px 14px; border: 1px solid var(--line); border-radius: var(--radius-sm); background: #fff; }}
    .recent-list li {{ display: flex; justify-content: space-between; gap: 12px; align-items: start; }}
    .card-actions {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .review-actions {{ display: grid; gap: 8px; grid-template-columns: minmax(0, 1fr); }}
    .review-select {{
      width: 100%; min-height: 40px; padding: 8px 12px; border-radius: 10px;
      border: 1px solid var(--line); background: #fff; color: var(--ink); font-weight: 600;
      transition: border-color .15s ease, box-shadow .15s ease;
    }}
    .review-select:focus {{ outline: none; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-soft); }}
    .link-btn {{
      display: inline-flex; align-items: center; justify-content: center; min-height: 40px; padding: 8px 14px;
      border-radius: var(--radius-sm); border: 1px solid var(--line); background: #fff; color: var(--ink); text-decoration: none; font-weight: 600;
      transition: border-color .15s ease, background .15s ease, transform .1s ease;
    }}
    .link-btn:hover {{ text-decoration: none; border-color: #c7c9f7; background: var(--accent-soft); }}
    .link-btn.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); box-shadow: var(--shadow-sm); }}
    .link-btn.primary:hover {{ background: #4338ca; transform: translateY(-1px); }}
    a {{ color: var(--accent); text-decoration: none; overflow-wrap: anywhere; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 1180px) {{ .overview {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 1080px) {{
      .project-grid {{ grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
    }}
    @media (max-width: 840px) {{
      .stats {{ grid-template-columns: 1fr 1fr; }}
      .toolbar {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 640px) {{
      .stats, .toolbar, .scores {{ grid-template-columns: 1fr; }}
      .project-grid {{ grid-template-columns: 1fr; }}
      .review-actions {{ grid-template-columns: 1fr; }}
      .topbar-inner .pill {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="topbar">
    <div class="topbar-inner">
      <a class="brand" href="index.html">
        <span class="brand-mark">MR</span>
        <span>Morocco Real Estate Intelligence</span>
      </a>
      <span class="pill">Page index / recherche</span>
    </div>
  </div>
  <main>
    <section class="hero">
      <div class="hero-top">
        <div>
          <p class="label">Morocco Real Estate Intelligence</p>
          <h1 style="margin-top:8px;">Recherche projets & KPIs</h1>
          <p style="margin-top:10px; max-width:760px;">Cette page sert à explorer les projets disponibles, voir les KPI globaux, la couverture géographique et ouvrir une fiche projet séparée.</p>
        </div>
      </div>
      <div class="stats">
        <div class="metric"><span class="label">{tooltip("Projets", KPI_EXPLANATIONS["projects"])}</span><strong>{len(projects)}</strong></div>
        <div class="metric"><span class="label">{tooltip("Urgents", KPI_EXPLANATIONS["urgent"])}</span><strong>{urgent_count}</strong></div>
        <div class="metric"><span class="label">{tooltip("À surveiller", KPI_EXPLANATIONS["watch"])}</span><strong>{watch_count}</strong></div>
        <div class="metric"><span class="label">{tooltip("Villes", KPI_EXPLANATIONS["cities"])}</span><strong>{city_count}</strong></div>
        <div class="metric"><span class="label">{tooltip("Confirmations", KPI_EXPLANATIONS["confirmations_global"])}</span><strong>{confirmation_count}</strong></div>
      </div>
    </section>

    <section class="overview">
      <section class="panel map-panel">
        <p class="label">Carte</p>
        <h2 style="margin-top:4px;">Couverture des projets</h2>
        <p class="helper">Carte interactive des villes visibles dans les résultats filtrés. Clique un marqueur pour voir le nombre de projets dans la ville.</p>
        <div id="overviewMap"></div>
      </section>

      <section class="panel">
        <p class="label">Repères</p>
        <h2 style="margin-top:4px;">Aide de lecture</h2>
        <ul class="list">
          <li><strong>Statuts possibles</strong><br>{esc(status_help)}</li>
          <li><strong>Types possibles</strong><br>{esc(type_help)}</li>
          <li><strong>Launch</strong><br>{esc(KPI_EXPLANATIONS["launch"])}</li>
          <li><strong>Confidence</strong><br>{esc(KPI_EXPLANATIONS["confidence"])}</li>
          <li><strong>Investment</strong><br>{esc(KPI_EXPLANATIONS["investment"])}</li>
          <li><strong>Timeline</strong><br>{esc(KPI_EXPLANATIONS["timeline"])}</li>
          <li><strong>Qualification</strong><br>{esc(REVIEW_HELP)}</li>
        </ul>
        <p class="helper" style="margin-top:12px;">Tu peux aussi survoler les petits “i” à côté des KPI pour voir leur explication.</p>
      </section>
    </section>

    <section class="panel" style="margin-top:18px;">
      <p class="label">Recherche</p>
      <h2 style="margin-top:4px;">Projets disponibles</h2>
      <p class="helper">Filtre la liste, puis ouvre le projet sur sa page complète. Ici on n’affiche pas la fiche détaillée pour garder une page de recherche simple.</p>
      <div class="toolbar">
        <input id="searchInput" class="field" placeholder="Recherche: projet, promoteur, zone..." />
        <select id="cityFilter" class="field"><option value="">Toutes les villes</option></select>
        <select id="statusFilter" class="field"><option value="">Tous les statuts</option></select>
        <select id="assetFilter" class="field"><option value="">Tous les types</option></select>
        <select id="reviewFilter" class="field"><option value="">Tous les suivis</option></select>
        <select id="sortFilter" class="field">
          <option value="confidence">Trier: confidence</option>
          <option value="investment">Trier: investment</option>
          <option value="updated">Trier: date</option>
          <option value="confirmations">Trier: confirmations</option>
        </select>
        <button id="favoritesOnly" class="toggle" type="button">Favoris uniquement</button>
      </div>
      <div id="projectCount" class="helper"></div>
      <div id="projectGrid" class="project-grid"></div>
    </section>

    <section class="panel" style="margin-top:18px;">
      <p class="label">Récents</p>
      <h2 style="margin-top:4px;">Derniers projets visibles</h2>
      <ul id="recentProjects" class="list recent-list"></ul>
    </section>
  </main>

  <script id="project-data" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
  <script src="supabase-config.js"></script>
  <script
    src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
    integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
    crossorigin=""
  ></script>
  <script>
    const projects = JSON.parse(document.getElementById("project-data").textContent);
    const favoriteKey = "morocco-real-estate-intelligence:favorites";
    const qualificationKey = "morocco-real-estate-intelligence:qualification";
    const supabaseConfig = window.__RADAR_SUPABASE__ || {{}};
    const supabaseTable = "project_qualifications";
    const reviewLabels = {json.dumps(REVIEW_LABELS, ensure_ascii=False)};
    const favoriteIds = new Set(JSON.parse(localStorage.getItem(favoriteKey) || "[]"));
    const projectGrid = document.getElementById("projectGrid");
    const projectCount = document.getElementById("projectCount");
    const searchInput = document.getElementById("searchInput");
    const cityFilter = document.getElementById("cityFilter");
    const statusFilter = document.getElementById("statusFilter");
    const assetFilter = document.getElementById("assetFilter");
    const reviewFilter = document.getElementById("reviewFilter");
    const sortFilter = document.getElementById("sortFilter");
    const favoritesOnly = document.getElementById("favoritesOnly");
    const recentProjects = document.getElementById("recentProjects");
    let onlyFavorites = false;
    let overviewMap = null;
    let mapLayer = null;

    const allStatuses = {json.dumps([{"value": name, "label": status_display(name)} for name, _ in ALL_STATUSES], ensure_ascii=False)};
    const allAssetTypes = {json.dumps([{"value": name, "label": label} for name, label in ALL_ASSET_TYPES], ensure_ascii=False)};
    const allReviewStatuses = {json.dumps([{"value": value, "label": label} for value, label, _ in REVIEW_STATUSES], ensure_ascii=False)};

    function uniqueValues(field) {{
      return [...new Set(projects.map(project => project[field]).filter(Boolean))].sort((left, right) => left.localeCompare(right));
    }}

    function populateSelect(select, values) {{
      values.forEach(value => {{
        const option = document.createElement("option");
        if (typeof value === "string") {{
          option.value = value;
          option.textContent = value;
        }} else {{
          option.value = value.value;
          option.textContent = value.label;
        }}
        select.appendChild(option);
      }});
    }}

    populateSelect(cityFilter, uniqueValues("city"));
    populateSelect(statusFilter, allStatuses);
    populateSelect(assetFilter, allAssetTypes);
    populateSelect(reviewFilter, allReviewStatuses);

    function saveFavorites() {{
      localStorage.setItem(favoriteKey, JSON.stringify([...favoriteIds]));
    }}

    function nowIso() {{
      return new Date().toISOString();
    }}

      function hasSupabaseConfig() {{
      return Boolean(supabaseConfig && supabaseConfig.url && supabaseConfig.anonKey);
    }}

    async function supabaseRequest(path, options = {{}}) {{
      const response = await fetch(`${{String(supabaseConfig.url).replace(/\\/$/, "")}}/rest/v1/${{path}}`, {{
        ...options,
        headers: {{
          apikey: supabaseConfig.anonKey,
          Authorization: `Bearer ${{supabaseConfig.anonKey}}`,
          "Content-Type": "application/json",
          ...(options.headers || {{}}),
        }},
      }});
      if (!response.ok) {{
        const text = await response.text();
        throw new Error(`Supabase error ${{response.status}}: ${{text}}`);
      }}

      document.querySelectorAll(".gallery-card").forEach((node) => {{
        node.addEventListener("click", () => openMediaLightbox(node.dataset.mediaSrc, node.dataset.mediaType || "image"));
      }});
      mediaClose?.addEventListener("click", closeMediaLightbox);
      mediaLightbox?.addEventListener("click", (event) => {{
        if (event.target === mediaLightbox) closeMediaLightbox();
      }});
      document.addEventListener("keydown", (event) => {{
        if (event.key === "Escape") closeMediaLightbox();
      }});
      if (response.status === 204) return null;
      return response.json();
    }}

    function loadQualifications() {{
      try {{
        return JSON.parse(localStorage.getItem(qualificationKey) || "{{}}");
      }} catch (error) {{
        return {{}};
      }}
    }}

    function defaultQualification() {{
      const createdAt = nowIso();
      return {{
        status: "new",
        notes: JSON.stringify({{ comments: [] }}),
        comments: [],
        created_at: createdAt,
        updated_at: createdAt,
        history: [{{ status: "new", at: createdAt }}],
      }};
    }}

    function parseCommentsFromNotes(notes) {{
      if (!notes) return [];
      if (typeof notes !== "string") return [];
      try {{
        const parsed = JSON.parse(notes);
        if (parsed && Array.isArray(parsed.comments)) return parsed.comments;
      }} catch (error) {{
      }}
      return notes.trim()
        ? [{{ id: "legacy-note", text: notes.trim(), created_at: nowIso() }}]
        : [];
    }}

    function serializeComments(comments) {{
      return JSON.stringify({{ comments }});
    }}

    function getQualification(projectId) {{
      const data = loadQualifications();
      const existing = data[projectId];
      if (existing && typeof existing === "object") {{
        existing.status = existing.status || "new";
        existing.comments = parseCommentsFromNotes(existing.notes || "");
        existing.notes = serializeComments(existing.comments);
        existing.created_at = existing.created_at || nowIso();
        existing.updated_at = existing.updated_at || existing.created_at;
        existing.history = Array.isArray(existing.history) && existing.history.length
          ? existing.history
          : [{{ status: existing.status, at: existing.created_at }}];
        return existing;
      }}
      return defaultQualification();
    }}

    function normalizeQualification(record) {{
      const normalized = record && typeof record === "object" ? {{ ...record }} : defaultQualification();
      normalized.status = normalized.status || "new";
      normalized.comments = Array.isArray(normalized.comments)
        ? normalized.comments
        : parseCommentsFromNotes(normalized.notes || "");
      normalized.notes = serializeComments(normalized.comments);
      normalized.created_at = normalized.created_at || nowIso();
      normalized.updated_at = normalized.updated_at || normalized.created_at;
      normalized.history = Array.isArray(normalized.history) && normalized.history.length
        ? normalized.history
        : [{{ status: normalized.status, at: normalized.created_at }}];
      return normalized;
    }}

    function projectReviewStatus(projectId) {{
      return getQualification(projectId).status || "new";
    }}

    function saveProjectReview(projectId, status) {{
      const data = loadQualifications();
      const record = normalizeQualification(getQualification(projectId));
      if (record.status !== status) {{
        const changedAt = nowIso();
        record.status = status;
        record.updated_at = changedAt;
        record.history.push({{ status, at: changedAt }});
      }}
      data[projectId] = record;
      localStorage.setItem(qualificationKey, JSON.stringify(data));
      return record;
    }}

    function saveQualificationRecord(projectId, record) {{
      const data = loadQualifications();
      data[projectId] = normalizeQualification(record);
      localStorage.setItem(qualificationKey, JSON.stringify(data));
    }}

    async function loadRemoteQualifications(projectIds) {{
      if (!hasSupabaseConfig() || !projectIds.length) return [];
      const path = `${{supabaseTable}}?select=project_id,status,notes,history,created_at,updated_at&project_id=in.(${{projectIds.join(",")}})`;
      const rows = await supabaseRequest(path);
      return Array.isArray(rows) ? rows.map(normalizeQualification) : [];
    }}

    async function persistRemoteQualification(projectId, record) {{
      if (!hasSupabaseConfig()) return normalizeQualification(record);
      const payload = normalizeQualification({{
        project_id: projectId,
        status: record.status,
        notes: serializeComments(record.comments || []),
        history: record.history || [],
        created_at: record.created_at,
        updated_at: record.updated_at,
      }});
      const rows = await supabaseRequest(
        `${{supabaseTable}}?on_conflict=project_id`,
        {{
          method: "POST",
          headers: {{
            Prefer: "return=representation,resolution=merge-duplicates",
          }},
          body: JSON.stringify([payload]),
        }},
      );
      return Array.isArray(rows) && rows.length ? normalizeQualification(rows[0]) : payload;
    }}

    function escapeHtml(value) {{
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }}

    function projectMatches(project) {{
      const query = searchInput.value.trim().toLowerCase();
      const haystack = [
        project.name,
        project.promoter,
        project.city,
        project.zone,
        project.asset_type,
        ...(project.aliases || []),
        ...(project.sources || []),
      ].filter(Boolean).join(" ").toLowerCase();
      if (query && !haystack.includes(query)) return false;
      if (cityFilter.value && project.city !== cityFilter.value) return false;
      if (statusFilter.value && project.status !== statusFilter.value) return false;
      if (assetFilter.value && project.asset_type !== assetFilter.value) return false;
      if (reviewFilter.value && projectReviewStatus(project.project_id) !== reviewFilter.value) return false;
      if (onlyFavorites && !favoriteIds.has(project.project_id)) return false;
      return true;
    }}

    function sortProjects(list) {{
      const sorted = [...list];
      const mode = sortFilter.value;
      sorted.sort((left, right) => {{
        if (mode === "investment") return right.investment_score - left.investment_score;
        if (mode === "updated") return String(right.last_updated_at).localeCompare(String(left.last_updated_at));
        if (mode === "confirmations") return (right.evidence.confirmation_count || 0) - (left.evidence.confirmation_count || 0);
        return right.confidence_score - left.confidence_score;
      }});
      return sorted;
    }}

    function buildCityStats(list) {{
      const map = new Map();
      list.forEach(project => {{
        const city = project.city || "À confirmer";
        if (!map.has(city)) {{
          map.set(city, {{
            name: city,
            count: 0,
            lat: project.evidence?.geo?.lat,
            lng: project.evidence?.geo?.lng,
          }});
        }}
        map.get(city).count += 1;
      }});
      return [...map.values()].filter(city => typeof city.lat === "number" && typeof city.lng === "number");
    }}

    function ensureMap() {{
      if (!window.L) {{
        document.getElementById("overviewMap").innerHTML = "<div style='padding:16px;color:#6b7280;'>Carte interactive indisponible ici.</div>";
        return null;
      }}
      if (overviewMap) return overviewMap;
      overviewMap = L.map("overviewMap", {{ scrollWheelZoom: false }}).setView([31.8, -7.2], 5.5);
      L.tileLayer("https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png", {{
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap"
      }}).addTo(overviewMap);
      mapLayer = L.layerGroup().addTo(overviewMap);
      return overviewMap;
    }}

    function renderMap(filtered) {{
      const map = ensureMap();
      if (!map || !mapLayer) return;
      mapLayer.clearLayers();
      const cities = buildCityStats(filtered);
      if (!cities.length) return;
      const bounds = [];
      cities.forEach(city => {{
        const marker = L.circleMarker([city.lat, city.lng], {{
          radius: Math.max(8, Math.min(18, 6 + city.count * 2)),
          color: "#c05621",
          fillColor: "#f7d9c7",
          fillOpacity: 0.8,
          weight: 2,
        }}).addTo(mapLayer);
        marker.bindPopup(`<strong>${{escapeHtml(city.name)}}</strong><br>${{city.count}} projet(s)`);
        bounds.push([city.lat, city.lng]);
      }});
      if (bounds.length === 1) map.setView(bounds[0], 8);
      else map.fitBounds(bounds, {{ padding: [20, 20] }});
    }}

    function renderProjectCard(project) {{
      const favorite = favoriteIds.has(project.project_id);
      const reviewStatus = projectReviewStatus(project.project_id);
      const slug = project.evidence.project_slug || project.project_id;
      const statusClass = project.status === "urgent" ? "urgent" : project.status === "watch" ? "watch" : "monitor";
      const card = document.createElement("article");
      card.className = "project-card" + (favorite ? " favorite" : "");
      card.innerHTML = `
        <div class="card-top">
          <div>
            <div class="card-title">${{escapeHtml(project.name)}}</div>
            <div class="muted card-subtitle">${{escapeHtml(project.promoter || "Promoteur à confirmer")}}</div>
          </div>
          <button class="toggle" type="button" data-action="favorite" style="width:auto; min-height:auto; padding:8px 10px;">${{favorite ? "★" : "☆"}}</button>
        </div>
        <div class="pill-row">
          <span class="pill ${{statusClass}}">${{escapeHtml(({json.dumps(STATUS_LABELS, ensure_ascii=False)})[project.status] || project.status)}}</span>
          <span class="pill">${{escapeHtml(project.city || "Ville à confirmer")}}</span>
          <span class="pill">${{escapeHtml((project.evidence.practical || {{}}).asset_label || project.asset_type || "Type à confirmer")}}</span>
          <span class="pill review-${{reviewStatus}}">${{escapeHtml(reviewLabels[reviewStatus] || "Nouveau")}}</span>
        </div>
        <p class="muted project-summary">${{escapeHtml((project.evidence.ai_analysis || {{}}).summary || project.evidence.recommendation_narrative || project.summary)}}</p>
        <div class="scores">
          <div class="score"><span>Confidence</span><strong>${{project.confidence_score}}</strong></div>
          <div class="score"><span>Investment</span><strong>${{project.investment_score}}</strong></div>
          <div class="score"><span>Confirm.</span><strong>${{project.evidence.confirmation_count || 0}}</strong></div>
          <div class="score"><span>ROI 5 ans</span><strong>${{(project.evidence.roi || {{}}).five_year_upside_score || "n/a"}}</strong></div>
        </div>
        <div class="review-actions">
          <select class="review-select" data-review-select>
            <option value="new" ${{reviewStatus === "new" ? "selected" : ""}}>Nouveau</option>
            <option value="to_qualify" ${{reviewStatus === "to_qualify" ? "selected" : ""}}>À qualifier</option>
            <option value="interested" ${{reviewStatus === "interested" ? "selected" : ""}}>Intéressé</option>
            <option value="in_contact" ${{reviewStatus === "in_contact" ? "selected" : ""}}>En contact</option>
            <option value="archived" ${{reviewStatus === "archived" ? "selected" : ""}}>Archivé</option>
          </select>
        </div>
        <div class="card-actions">
          <a class="link-btn primary" href="projects/${{escapeHtml(slug)}}.html">Ouvrir le projet</a>
          <a class="link-btn" href="projects/${{escapeHtml(slug)}}.html" target="_blank" rel="noreferrer">Nouvel onglet</a>
        </div>
      `;
      card.querySelector("[data-action='favorite']").addEventListener("click", (event) => {{
        event.preventDefault();
        event.stopPropagation();
        if (favoriteIds.has(project.project_id)) favoriteIds.delete(project.project_id);
        else favoriteIds.add(project.project_id);
        saveFavorites();
        render();
      }});
      card.querySelector("[data-review-select]").addEventListener("change", async (event) => {{
        event.preventDefault();
        event.stopPropagation();
        const record = saveProjectReview(project.project_id, event.target.value);
        render();
        try {{
          const synced = await persistRemoteQualification(project.project_id, record);
          saveQualificationRecord(project.project_id, synced);
          render();
        }} catch (error) {{
          console.warn("Supabase sync failed, local cache kept.", error);
        }}
      }});
      return card;
    }}

    function renderRecent(filtered) {{
      const recent = [...filtered].sort((a, b) => String(b.last_updated_at).localeCompare(String(a.last_updated_at))).slice(0, 6);
      recentProjects.innerHTML = recent.map(project => {{
        const slug = project.evidence.project_slug || project.project_id;
        return `
          <li>
            <div>
              <strong>${{escapeHtml(project.name)}}</strong><br>
              <span class="muted">${{escapeHtml(project.city || "Ville à confirmer")}} · ${{escapeHtml(project.promoter || "Promoteur à confirmer")}}</span>
            </div>
            <a href="projects/${{escapeHtml(slug)}}.html">Ouvrir</a>
          </li>
        `;
      }}).join("") || "<li>Aucun projet visible.</li>";
    }}

    function render() {{
      favoritesOnly.textContent = onlyFavorites ? "Voir tous les projets" : "Favoris uniquement";
      favoritesOnly.classList.toggle("is-active", onlyFavorites);
      const filtered = sortProjects(projects.filter(projectMatches));
      projectGrid.innerHTML = "";
      filtered.forEach(project => projectGrid.appendChild(renderProjectCard(project)));
      projectCount.textContent = `${{filtered.length}} projet(s) affiché(s) sur ${{projects.length}}.`;
      renderRecent(filtered);
      renderMap(filtered);
    }}

    [searchInput, cityFilter, statusFilter, assetFilter, reviewFilter, sortFilter].forEach(control => {{
      control.addEventListener("input", render);
      control.addEventListener("change", render);
    }});

    favoritesOnly.addEventListener("click", () => {{
      onlyFavorites = !onlyFavorites;
      render();
    }});

    render();
    loadRemoteQualifications(projects.map((project) => project.project_id))
      .then(async (rows) => {{
        const remoteIds = new Set();
        rows.forEach((row) => {{
          remoteIds.add(row.project_id);
          saveQualificationRecord(row.project_id, row);
        }});
        const syncPromises = projects.map(async (project) => {{
          const local = normalizeQualification(getQualification(project.project_id));
          if (remoteIds.has(project.project_id)) return;
          if (local.notes || local.status !== "new" || (local.history || []).length > 1) {{
            const synced = await persistRemoteQualification(project.project_id, local);
            saveQualificationRecord(project.project_id, synced);
          }}
        }});
        await Promise.all(syncPromises);
        render();
      }})
      .catch((error) => {{
        console.warn("Supabase unavailable, using local cache.", error);
      }});
  </script>
</body>
</html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
