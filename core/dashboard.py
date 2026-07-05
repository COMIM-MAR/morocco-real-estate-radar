import json

from .config import DOCS_DIR


def build(projects):
    DOCS_DIR.mkdir(exist_ok=True)
    payload = [project.to_dict() for project in projects]
    urgent_count = len([project for project in projects if project.status == "urgent"])
    watch_count = len([project for project in projects if project.status == "watch"])
    source_count = sum(len(project.sources) for project in projects)
    signal_count = sum(project.evidence.get("signal_count", len(project.signals)) for project in projects)
    page = f"""<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Morocco Real Estate Intelligence</title>
  <style>
    :root {{
      --bg: #f2eadb;
      --paper: rgba(255, 250, 242, 0.9);
      --card: #fff8ef;
      --ink: #1d2935;
      --muted: #5c6876;
      --line: #e6d9c5;
      --accent: #ad5c18;
      --accent-soft: #fae3c3;
      --ok: #17633d;
      --warn: #8f4d1f;
      --pill: #f4ecdd;
      --shadow: 0 18px 45px rgba(35, 43, 56, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(255,255,255,0.75), transparent 35%),
        linear-gradient(180deg, #f8f2e9 0%, #f0e4d1 100%);
    }}
    main {{ max-width: 1380px; margin: 0 auto; padding: 28px 18px 56px; }}
    h1, h2, h3, h4, p {{ margin: 0; }}
    button, input, select {{ font: inherit; }}
    .hero, .panel {{
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--paper);
      box-shadow: var(--shadow);
    }}
    .hero {{ padding: 28px; display: grid; gap: 20px; }}
    .eyebrow {{
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .hero-grid, .stats, .project-grid, .detail-grid, .mini-grid {{
      display: grid;
      gap: 16px;
    }}
    .hero-grid {{ grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); }}
    .stats {{ grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); margin-top: 8px; }}
    .panel {{ padding: 20px; }}
    .stat-value {{ font-size: 34px; color: var(--accent); }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.9fr);
      gap: 18px;
      margin-top: 22px;
      align-items: start;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: 1.6fr repeat(4, minmax(120px, 1fr)) auto;
      gap: 12px;
      margin-top: 16px;
    }}
    .field {{
      border: 1px solid var(--line);
      background: #fffdf8;
      border-radius: 16px;
      padding: 12px 14px;
      color: var(--ink);
      width: 100%;
    }}
    .project-grid {{ grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); margin-top: 18px; }}
    .project-card {{
      border: 1px solid var(--line);
      background: var(--card);
      border-radius: 22px;
      padding: 18px;
      box-shadow: var(--shadow);
      display: grid;
      gap: 12px;
      cursor: pointer;
      transition: transform 140ms ease, border-color 140ms ease, box-shadow 140ms ease;
    }}
    .project-card:hover {{ transform: translateY(-2px); border-color: #d7bf9b; }}
    .project-card.active {{ border-color: var(--accent); box-shadow: 0 18px 40px rgba(173, 92, 24, 0.18); }}
    .project-card.favorite {{ background: linear-gradient(180deg, #fff9f1 0%, #fff1db 100%); }}
    .card-head, .row, .detail-head, .pill-row {{ display: flex; gap: 10px; }}
    .card-head, .detail-head {{ justify-content: space-between; align-items: start; }}
    .row {{ flex-wrap: wrap; }}
    .pill-row {{ flex-wrap: wrap; }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: var(--pill);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 10px;
      color: var(--muted);
      font-size: 13px;
    }}
    .status-urgent {{ color: #7a2200; background: #ffe3d4; }}
    .status-watch {{ color: var(--warn); background: #fff0d3; }}
    .status-monitor {{ color: var(--ok); background: #e7f5ec; }}
    .meta, .muted {{ color: var(--muted); font-size: 14px; }}
    .score-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }}
    .score-box {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 12px;
      background: #fffdf8;
    }}
    .score-box strong {{ display: block; color: var(--accent); font-size: 26px; }}
    .mini-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .list, .timeline {{
      list-style: none;
      padding: 0;
      margin: 0;
      display: grid;
      gap: 10px;
    }}
    .list li, .timeline li {{
      border: 1px solid var(--line);
      border-radius: 16px;
      background: #fffdf8;
      padding: 12px 14px;
    }}
    .detail-empty {{
      min-height: 520px;
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--muted);
    }}
    .toggle {{
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px 14px;
      background: #fffdf8;
      color: var(--ink);
      cursor: pointer;
    }}
    .summary {{
      line-height: 1.5;
      color: var(--muted);
    }}
    .section-stack {{ display: grid; gap: 18px; }}
    .footer-note {{ margin-top: 14px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 1120px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .toolbar {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 720px) {{
      .toolbar {{ grid-template-columns: 1fr; }}
      .score-grid, .mini-grid {{ grid-template-columns: 1fr 1fr; }}
      .project-grid {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <div>
        <p class="eyebrow">Morocco Real Estate Intelligence Engine</p>
        <h1>Explorer les projets, pas les annonces.</h1>
        <p class="summary">Le dashboard devient une surface d'exploration: filtres rapides, favoris locaux, dossier projet, historique des confirmations et timeline d'évolution.</p>
      </div>
      <div class="hero-grid">
        <div class="panel"><h3>🔥 Nouveaux projets</h3><p class="meta">{urgent_count} projets urgents à haute confiance.</p></div>
        <div class="panel"><h3>❤️ Favoris</h3><p class="meta">Sauvegarde locale des projets à suivre dans le navigateur.</p></div>
        <div class="panel"><h3>📅 Timeline</h3><p class="meta">Visualisation des dernières mises à jour et des confirmations.</p></div>
        <div class="panel"><h3>🔎 Recherche</h3><p class="meta">Recherche texte, ville, statut, type d'actif et favoris uniquement.</p></div>
      </div>
      <div class="stats">
        <div class="panel"><div class="stat-value">{len(projects)}</div><p class="meta">Projets suivis</p></div>
        <div class="panel"><div class="stat-value">{source_count}</div><p class="meta">Sources fusionnées</p></div>
        <div class="panel"><div class="stat-value">{signal_count}</div><p class="meta">Signaux totalisés</p></div>
        <div class="panel"><div class="stat-value">{watch_count}</div><p class="meta">À surveiller</p></div>
      </div>
    </section>

    <section class="layout">
      <div class="section-stack">
        <section class="panel">
          <div class="card-head">
            <div>
              <p class="eyebrow">Intelligence Browser</p>
              <h2>Catalogue projets</h2>
            </div>
            <div class="pill">Top 100 projets synchronisés</div>
          </div>
          <div class="toolbar">
            <input id="searchInput" class="field" placeholder="Rechercher un projet, un promoteur, une zone..." />
            <select id="cityFilter" class="field"><option value="">Toutes les villes</option></select>
            <select id="statusFilter" class="field"><option value="">Tous les statuts</option></select>
            <select id="assetFilter" class="field"><option value="">Tous les types</option></select>
            <select id="sortFilter" class="field">
              <option value="confidence">Trier par confidence</option>
              <option value="investment">Trier par investment</option>
              <option value="updated">Trier par date</option>
              <option value="confirmations">Trier par confirmations</option>
            </select>
            <button id="favoritesOnly" class="toggle" type="button">Afficher favoris</button>
          </div>
          <div id="projectCount" class="footer-note"></div>
          <div id="projectGrid" class="project-grid"></div>
        </section>
      </div>

      <aside class="section-stack">
        <section id="detailPanel" class="panel detail-empty">
          <div>
            <p class="eyebrow">Project Dossier</p>
            <h2>Sélectionne un projet</h2>
            <p class="summary">Le panneau de droite affiche le dossier complet, les confirmations, les liens sources et la timeline d'évolution.</p>
          </div>
        </section>
      </aside>
    </section>
  </main>

  <script id="project-data" type="application/json">{json.dumps(payload, ensure_ascii=False)}</script>
  <script>
    const projects = JSON.parse(document.getElementById("project-data").textContent);
    const favoriteKey = "morocco-real-estate-intelligence:favorites";
    const favoriteIds = new Set(JSON.parse(localStorage.getItem(favoriteKey) || "[]"));
    const projectGrid = document.getElementById("projectGrid");
    const detailPanel = document.getElementById("detailPanel");
    const projectCount = document.getElementById("projectCount");
    const searchInput = document.getElementById("searchInput");
    const cityFilter = document.getElementById("cityFilter");
    const statusFilter = document.getElementById("statusFilter");
    const assetFilter = document.getElementById("assetFilter");
    const sortFilter = document.getElementById("sortFilter");
    const favoritesOnly = document.getElementById("favoritesOnly");
    let selectedId = projects[0] ? projects[0].project_id : null;
    let onlyFavorites = false;

    function uniqueValues(field) {{
      return [...new Set(projects.map(project => project[field]).filter(Boolean))].sort((left, right) => left.localeCompare(right));
    }}

    function populateSelect(select, values) {{
      values.forEach(value => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}

    populateSelect(cityFilter, uniqueValues("city"));
    populateSelect(statusFilter, uniqueValues("status"));
    populateSelect(assetFilter, uniqueValues("asset_type"));

    function saveFavorites() {{
      localStorage.setItem(favoriteKey, JSON.stringify([...favoriteIds]));
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

    function renderProjectCard(project) {{
      const favorite = favoriteIds.has(project.project_id);
      const card = document.createElement("article");
      card.className = "project-card" + (selectedId === project.project_id ? " active" : "") + (favorite ? " favorite" : "");
      const confirmations = (project.evidence.confirmations || []).slice(0, 2).join(", ") || "Confirmation en cours";
      card.innerHTML = `
        <div class="card-head">
          <div>
            <p class="eyebrow">${{favorite ? "Favori" : "Projet"}}</p>
            <h3>${{escapeHtml(project.name)}}</h3>
          </div>
          <button class="toggle" type="button" data-action="favorite">${{favorite ? "★" : "☆"}}</button>
        </div>
        <div class="pill-row">
          <span class="pill status-${{project.status}}">${{escapeHtml(project.status)}}</span>
          <span class="pill">${{escapeHtml(project.city || "Ville à confirmer")}}</span>
          <span class="pill">${{escapeHtml(project.asset_type || "Type à confirmer")}}</span>
        </div>
        <p class="summary">${{escapeHtml(project.summary)}}</p>
        <div class="score-grid">
          <div class="score-box"><span class="meta">Confidence</span><strong>${{project.confidence_score}}</strong></div>
          <div class="score-box"><span class="meta">Investment</span><strong>${{project.investment_score}}</strong></div>
          <div class="score-box"><span class="meta">Urgency</span><strong>${{project.urgency_score}}</strong></div>
          <div class="score-box"><span class="meta">Confirm.</span><strong>${{project.evidence.confirmation_count || 0}}</strong></div>
        </div>
        <p class="meta">${{escapeHtml(confirmations)}}</p>
      `;
      card.addEventListener("click", (event) => {{
        if (event.target.dataset.action === "favorite") return;
        selectedId = project.project_id;
        render();
      }});
      card.querySelector("[data-action='favorite']").addEventListener("click", (event) => {{
        event.stopPropagation();
        if (favoriteIds.has(project.project_id)) favoriteIds.delete(project.project_id);
        else favoriteIds.add(project.project_id);
        saveFavorites();
        render();
      }});
      return card;
    }}

    function escapeHtml(value) {{
      return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
    }}

    function renderDetail(project) {{
      if (!project) {{
        detailPanel.className = "panel detail-empty";
        detailPanel.innerHTML = `
          <div>
            <p class="eyebrow">Project Dossier</p>
            <h2>Aucun projet visible</h2>
            <p class="summary">Ajuste les filtres ou désactive le mode favoris pour revoir des projets.</p>
          </div>
        `;
        return;
      }}
      const favorite = favoriteIds.has(project.project_id);
      const timeline = (project.timeline || []).slice(0, 8).map(item => `
        <li>
          <strong>${{escapeHtml(item.observed_at || item.detected_at || "")}}</strong><br>
          <span class="meta">${{escapeHtml(item.status || item.channel || "")}}</span><br>
          <span>${{escapeHtml(item.title || item.recommendation || "")}}</span>
        </li>
      `).join("");
      const sourceLinks = (project.source_urls || []).slice(0, 8).map(url => `<li><a href="${{escapeHtml(url)}}" target="_blank" rel="noreferrer">${{escapeHtml(url)}}</a></li>`).join("");
      const reasons = (project.reasons || []).slice(0, 8).map(reason => `<li>${{escapeHtml(reason)}}</li>`).join("");
      const changes = (project.evidence.changes || []).slice(0, 8).map(change => `<li>${{escapeHtml(change)}}</li>`).join("") || "<li>Aucune évolution notable sur ce run.</li>";
      const confirmations = (project.evidence.confirmations || []).slice(0, 8).map(item => `<li>${{escapeHtml(item)}}</li>`).join("") || "<li>Aucune confirmation forte.</li>";
      detailPanel.className = "section-stack";
      detailPanel.innerHTML = `
        <section class="panel">
          <div class="detail-head">
            <div>
              <p class="eyebrow">Project Dossier</p>
              <h2>${{escapeHtml(project.name)}}</h2>
              <p class="summary">${{escapeHtml(project.summary)}}</p>
            </div>
            <button id="detailFavorite" class="toggle" type="button">${{favorite ? "Retirer favori" : "Ajouter favori"}}</button>
          </div>
          <div class="pill-row" style="margin-top: 14px;">
            <span class="pill status-${{project.status}}">${{escapeHtml(project.status)}}</span>
            <span class="pill">${{escapeHtml(project.city || "Ville à confirmer")}}</span>
            <span class="pill">${{escapeHtml(project.promoter || "Promoteur à confirmer")}}</span>
            <span class="pill">${{escapeHtml(project.asset_type || "Type à confirmer")}}</span>
          </div>
          <div class="score-grid" style="margin-top: 16px;">
            <div class="score-box"><span class="meta">Launch</span><strong>${{project.launch_score}}</strong></div>
            <div class="score-box"><span class="meta">Confidence</span><strong>${{project.confidence_score}}</strong></div>
            <div class="score-box"><span class="meta">Investment</span><strong>${{project.investment_score}}</strong></div>
            <div class="score-box"><span class="meta">Urgency</span><strong>${{project.urgency_score}}</strong></div>
          </div>
          <div class="mini-grid" style="margin-top: 16px;">
            <div class="panel">
              <h4>Fiche</h4>
              <ul class="list" style="margin-top: 10px;">
                <li>Aliases: ${{escapeHtml((project.aliases || []).join(", ") || "n/a")}}</li>
                <li>Prix min: ${{escapeHtml(project.prices.min || "n/a")}}</li>
                <li>Prix max: ${{escapeHtml(project.prices.max || "n/a")}}</li>
                <li>Première détection: ${{escapeHtml(project.first_detected_at)}}</li>
                <li>Dernière mise à jour: ${{escapeHtml(project.last_updated_at)}}</li>
              </ul>
            </div>
            <div class="panel">
              <h4>Evidence</h4>
              <ul class="list" style="margin-top: 10px;">
                <li>Sources: ${{project.evidence.source_count || 0}}</li>
                <li>Signals: ${{project.evidence.signal_count || 0}}</li>
                <li>Primary channels: ${{escapeHtml((project.evidence.primary_channels || []).join(", ") || "n/a")}}</li>
                <li>Secondary channels: ${{escapeHtml((project.evidence.secondary_channels || []).join(", ") || "n/a")}}</li>
                <li>Confirmations: ${{project.evidence.confirmation_count || 0}}</li>
              </ul>
            </div>
          </div>
        </section>
        <section class="panel">
          <p class="eyebrow">Confirmations</p>
          <h3>Pourquoi ce projet monte</h3>
          <ul class="list" style="margin-top: 12px;">${{confirmations}}</ul>
        </section>
        <section class="panel">
          <p class="eyebrow">Evolution</p>
          <h3>Changements récents</h3>
          <ul class="list" style="margin-top: 12px;">${{changes}}</ul>
        </section>
        <section class="panel">
          <p class="eyebrow">Timeline</p>
          <h3>Historique projet</h3>
          <ul class="timeline" style="margin-top: 12px;">${{timeline || "<li>Aucune timeline disponible.</li>"}}</ul>
        </section>
        <section class="panel">
          <p class="eyebrow">Sources</p>
          <h3>Liens et raisons</h3>
          <div class="mini-grid" style="margin-top: 12px;">
            <div>
              <h4>URLs</h4>
              <ul class="list" style="margin-top: 10px;">${{sourceLinks || "<li>Aucune URL enregistrée.</li>"}}</ul>
            </div>
            <div>
              <h4>Raisons</h4>
              <ul class="list" style="margin-top: 10px;">${{reasons || "<li>Aucune raison.</li>"}}</ul>
            </div>
          </div>
        </section>
      `;
      document.getElementById("detailFavorite").addEventListener("click", () => {{
        if (favoriteIds.has(project.project_id)) favoriteIds.delete(project.project_id);
        else favoriteIds.add(project.project_id);
        saveFavorites();
        render();
      }});
    }}

    function render() {{
      favoritesOnly.textContent = onlyFavorites ? "Afficher tout" : "Afficher favoris";
      const filtered = sortProjects(projects.filter(projectMatches));
      if (!filtered.some(project => project.project_id === selectedId)) {{
        selectedId = filtered[0] ? filtered[0].project_id : null;
      }}
      projectGrid.innerHTML = "";
      filtered.forEach(project => projectGrid.appendChild(renderProjectCard(project)));
      projectCount.textContent = `${{filtered.length}} projet(s) visibles sur ${{projects.length}}.`;
      renderDetail(filtered.find(project => project.project_id === selectedId) || null);
    }}

    [searchInput, cityFilter, statusFilter, assetFilter, sortFilter].forEach(control => {{
      control.addEventListener("input", render);
      control.addEventListener("change", render);
    }});
    favoritesOnly.addEventListener("click", () => {{
      onlyFavorites = !onlyFavorites;
      render();
    }});

    render();
  </script>
</body>
</html>"""
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")
    (DOCS_DIR / "projects.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
