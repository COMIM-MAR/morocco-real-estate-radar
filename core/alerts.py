from __future__ import annotations


def project_changes(previous, current) -> list[str]:
    changes: list[str] = []
    if previous is None:
        return changes
    if current.confidence_score >= previous.confidence_score + 8:
        changes.append(f"Confidence score en hausse: {previous.confidence_score} → {current.confidence_score}")
    if current.urgency_score >= previous.urgency_score + 8:
        changes.append(f"Urgency score en hausse: {previous.urgency_score} → {current.urgency_score}")
    prev_confirmations = previous.evidence.get("confirmation_count", 0)
    curr_confirmations = current.evidence.get("confirmation_count", 0)
    if curr_confirmations > prev_confirmations:
        changes.append(f"Nouvelles confirmations multi-sources: {prev_confirmations} → {curr_confirmations}")
    prev_sources = previous.evidence.get("source_count", len(previous.sources))
    curr_sources = current.evidence.get("source_count", len(current.sources))
    if curr_sources > prev_sources:
        changes.append(f"Nouvelles sources détectées: {prev_sources} → {curr_sources}")
    prev_status = previous.status
    if current.status != prev_status:
        changes.append(f"Statut projet: {prev_status} → {current.status}")
    prev_price = previous.prices.get("min")
    curr_price = current.prices.get("min")
    if prev_price and curr_price and prev_price != curr_price:
        changes.append(f"Prix minimum mis à jour: {prev_price} → {curr_price} MAD")
    return changes


def attach_changes(projects, previous_map):
    for project in projects:
        previous = previous_map.get(project.project_id)
        changes = project_changes(previous, project)
        project.evidence["changes"] = changes
        project.evidence["is_new_project"] = previous is None
    return projects


def select_immediate_alerts(projects, known_project_ids, config):
    alerts = []
    for project in projects:
        if project.project_id in known_project_ids:
            continue
        if project.confidence_score < config["alerts"]["immediate_confidence_threshold"]:
            continue
        if not any(signal.is_primary for signal in project.signals):
            continue
        alerts.append(project)
        if len(alerts) >= config["alerts"]["max_items_per_email"]:
            break
    return alerts


def select_digest_projects(projects, known_project_ids, config):
    digest = []
    min_change_count = config["alerts"].get("digest_min_change_count", 2)
    for project in projects:
        if project.project_id not in known_project_ids:
            continue
        if project.confidence_score < config["alerts"]["digest_confidence_threshold"]:
            continue
        if len(project.evidence.get("changes", [])) < min_change_count:
            continue
        digest.append(project)
        if len(digest) >= config["alerts"]["max_items_per_email"]:
            break
    return digest
