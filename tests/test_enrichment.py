import unittest

from core.enrichment import enrich_project_intelligence
from core.models import ProjectRecord


class EnrichmentTests(unittest.TestCase):
    def test_adds_geo_infra_and_roi_fields(self):
        project = ProjectRecord(
            project_id="p1",
            name="Sun Hills",
            city="Tanger",
            zone="Tanja Balia",
            promoter="CGI",
            asset_type="villa",
            first_detected_at="2026-01-01T00:00:00+00:00",
            last_updated_at="2026-01-02T00:00:00+00:00",
            launch_score=80,
            confidence_score=92,
            investment_score=84,
            urgency_score=88,
            recommendation="Buy",
            status="urgent",
            summary="summary",
            prices={"min": 2_000_000, "max": 2_400_000},
            aliases=["Sun Hills"],
            channels=["project_discovery"],
            sources=["CGI"],
            source_urls=["https://example.com"],
            evidence={},
            reasons=[],
            timeline=[],
            signals=[],
        )
        config = {"profile": {"cash_ready": 1_500_000, "max_budget": 3_000_000}}

        enrich_project_intelligence(project, config)

        self.assertEqual(project.evidence["price_band"], "within_budget")
        self.assertIn("roi", project.evidence)
        self.assertIn("geo", project.evidence)
        self.assertEqual(project.evidence["geo"]["lat"], 35.7448)
        self.assertIn("recommendation_narrative", project.evidence)


if __name__ == "__main__":
    unittest.main()
