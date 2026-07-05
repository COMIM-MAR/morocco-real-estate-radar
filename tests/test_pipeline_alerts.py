import unittest
from types import SimpleNamespace

from core.models import ProjectRecord
from core.alerts import attach_changes, select_digest_projects, select_immediate_alerts


def project(project_id: str, confidence: int, urgency: int, status: str, confirmation_count: int, source_count: int, prices=None):
    return ProjectRecord(
        project_id=project_id,
        name=f"Project {project_id}",
        city="Tanger",
        zone=None,
        promoter="CGI",
        asset_type="villa",
        first_detected_at="2026-01-01T00:00:00+00:00",
        last_updated_at="2026-01-02T00:00:00+00:00",
        launch_score=70,
        confidence_score=confidence,
        investment_score=80,
        urgency_score=urgency,
        recommendation="Watch",
        status=status,
        summary="summary",
        prices=prices or {"min": 2_000_000, "max": 2_500_000},
        aliases=["Project"],
        channels=["project_discovery", "google_discovery"],
        sources=["CGI", "Google Search"],
        source_urls=["https://example.com"],
        evidence={
            "signal_count": 3,
            "primary_signal_count": 2,
            "listing_signal_count": 1,
            "source_count": source_count,
            "channel_count": 2,
            "confirmation_count": confirmation_count,
            "confirmations": ["page promoteur + indexation Google"],
        },
        reasons=["reason"],
        timeline=[],
        signals=[SimpleNamespace(is_primary=True)],
    )


class PipelineAlertTests(unittest.TestCase):
    def test_selects_immediate_only_for_new_high_confidence_projects(self):
        config = {"alerts": {"immediate_confidence_threshold": 90, "max_items_per_email": 5}}
        projects = [project("new-1", 95, 88, "urgent", 2, 3), project("old-1", 96, 90, "urgent", 2, 3)]

        immediate = select_immediate_alerts(projects, {"old-1"}, config)

        self.assertEqual([item.project_id for item in immediate], ["new-1"])

    def test_attaches_changes_and_selects_digest_projects(self):
        previous = project("p1", 72, 60, "monitor", 0, 2, {"min": 2_100_000, "max": 2_400_000})
        current = project("p1", 84, 74, "watch", 2, 4, {"min": 2_000_000, "max": 2_400_000})
        config = {
            "alerts": {
                "digest_confidence_threshold": 70,
                "digest_min_change_count": 2,
                "max_items_per_email": 5,
            }
        }

        projects = attach_changes([current], {"p1": previous})
        digest = select_digest_projects(projects, {"p1"}, config)

        self.assertEqual(len(digest), 1)
        self.assertGreaterEqual(len(digest[0].evidence["changes"]), 2)
        self.assertIn("Nouvelles confirmations multi-sources", " | ".join(digest[0].evidence["changes"]))


if __name__ == "__main__":
    unittest.main()
