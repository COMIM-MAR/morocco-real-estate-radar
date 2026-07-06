import unittest

from core.enrichment import enrich_project_intelligence
from core.models import ProjectRecord, SignalEvent
from core.scoring import enrich_project


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
        self.assertIn("source_catalog", project.evidence)
        self.assertIn("practical", project.evidence)
        self.assertIn("ai_analysis", project.evidence)
        self.assertEqual(project.evidence["practical"]["asset_label"], "Villa")
        self.assertTrue(project.evidence["official_links"])


class ConfirmationEvidenceTests(unittest.TestCase):
    def test_confirmation_details_attach_proofs(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Meta Ad Library",
                signal_type="meta_watch",
                title="Meta Ads watch: CGI lancement immobilier Maroc",
                url="https://www.facebook.com/ads/library/?q=CGI",
                text="CGI lancement immobilier Maroc",
                is_primary=True,
                launch_weight=30,
                confidence_weight=30,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="google.search",
                channel="google_discovery",
                source="Google Search",
                signal_type="search_result",
                title="CGI Tanger projet immobilier",
                url="https://www.cgi.ma/projet-tanger",
                text="CGI Tanger projet immobilier",
                is_primary=True,
                launch_weight=20,
                confidence_weight=22,
                metadata={"promoter_hint": "CGI"},
                city_hint="Tanger",
            ),
            SignalEvent(
                collector="urbanism.watch",
                channel="urbanism",
                source="Agence Urbaine de Tanger",
                signal_type="urbanism_page",
                title="Permis résidence Tanger",
                url="https://www.autanger.ma/permis-residence.pdf",
                text="Permis résidence Tanger",
                is_primary=True,
                launch_weight=22,
                confidence_weight=18,
                city_hint="Tanger",
            ),
        ]
        project = ProjectRecord(
            project_id="p2",
            name="CGI Tanger",
            city="Tanger",
            zone=None,
            promoter="CGI",
            asset_type="apartment_unknown",
            first_detected_at="2026-01-01T00:00:00+00:00",
            last_updated_at="2026-01-02T00:00:00+00:00",
            launch_score=0,
            confidence_score=0,
            investment_score=0,
            urgency_score=0,
            recommendation="Watch",
            status="watch",
            summary="",
            prices={"min": None, "max": None},
            aliases=["CGI Tanger"],
            channels=["advertising", "google_discovery", "urbanism"],
            sources=["Meta Ad Library", "Google Search", "Agence Urbaine de Tanger"],
            source_urls=[signal.url for signal in signals],
            evidence={},
            reasons=[],
            timeline=[],
            signals=signals,
        )
        config = {
            "profile": {"cash_ready": 1_500_000, "max_budget": 3_000_000},
            "cities": {"tangier": {"label": "Tanger", "priority": 100, "zones": []}},
            "asset_preferences": {"apartment_unknown": 35},
            "alerts": {"immediate_confidence_threshold": 90, "digest_confidence_threshold": 70},
        }

        enrich_project(project, config)

        self.assertTrue(project.evidence["confirmation_details"])
        labels = [item["label"] for item in project.evidence["confirmation_details"]]
        self.assertIn("document urbanisme + indexation Google", labels)
        self.assertNotIn("publicité Meta + indexation Google", labels)
        proofs = project.evidence["confirmation_details"][0]["proofs"]
        self.assertTrue(any(item["channel"] == "google_discovery" for item in proofs))


if __name__ == "__main__":
    unittest.main()
