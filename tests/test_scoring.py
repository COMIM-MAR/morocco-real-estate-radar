import unittest

from core.models import ProjectRecord, SignalEvent
from core.scoring import detect_asset_type, detect_city_zone, enrich_project, enrich_signal


class ScoringTests(unittest.TestCase):
    def test_does_not_classify_sous_terrain_as_land(self):
        text = (
            "Découvrez Les Palmiers Résidences : des appartements modernes avec vue sur jardin, "
            "parking sous-terrain sécurisé et finitions premium."
        )
        asset_type, _ = detect_asset_type(text, {"land_r4_plus": 95})
        self.assertEqual(asset_type, "apartment_unknown")

    def test_prefers_apartment_over_land_when_navigation_mentions_terrain(self):
        text = (
            "Investir Retour Par thématique Lot de terrain Resort golfique "
            "Les résidences Green Homes proposent une offre diversifiée. "
            "Les appartements bénéficient de belles terrasses."
        )
        asset_type, _ = detect_asset_type(text, {"land_r4_plus": 95})
        self.assertEqual(asset_type, "apartment_unknown")

    def test_prefers_marrakech_over_menu_casablanca_when_text_is_project_specific(self):
        config = {
            "cities": {
                "casablanca": {"label": "Casablanca", "zones": ["Anfa"]},
                "marrakech": {"label": "Marrakech", "zones": ["Targa"]},
            }
        }
        text = (
            "Par ville Casablanca Agadir Marrakech Rabat "
            "JE CONSULTE Marrakech Les Orangers de Targa | CGI "
            "Les Orangers de Targa est situé à Marrakech sur la route de Targa."
        )
        city, zone = detect_city_zone(text, config)
        self.assertEqual(city, "Marrakech")
        self.assertEqual(zone, "Targa")


def build_config():
    return {
        "alerts": {"immediate_confidence_threshold": 90, "digest_confidence_threshold": 70},
        "cities": {},
        "asset_preferences": {},
        "profile": {"cash_ready": 1_500_000, "max_budget": 3_000_000},
    }


class AvailabilityScoringTests(unittest.TestCase):
    def test_enrich_signal_boosts_weight_for_limited_stock(self):
        config = build_config()
        signal = SignalEvent(
            collector="test",
            channel="project_discovery",
            source="Test",
            signal_type="promoter_page",
            title="Résidence Test",
            url="https://example.com/projet",
            text="Dernières unités disponibles sur cette résidence, stock limité.",
            is_primary=True,
            launch_weight=10,
            confidence_weight=10,
        )
        enriched = enrich_signal(signal, config)
        self.assertEqual(enriched.metadata["availability"]["status"], "limited")
        self.assertEqual(enriched.launch_weight, 25)
        self.assertGreaterEqual(enriched.confidence_weight, 18)

    def test_enrich_project_downgrades_recommendation_when_sold_out(self):
        config = build_config()
        signal = SignalEvent(
            collector="test",
            channel="project_discovery",
            source="Test",
            signal_type="promoter_page",
            title="Résidence Test",
            url="https://example.com/projet",
            text="Le projet est désormais complet, plus aucune disponibilité sur cette résidence.",
            is_primary=True,
            launch_weight=20,
            confidence_weight=95,
        )
        signal = enrich_signal(signal, config)
        project = ProjectRecord(
            project_id="p1",
            name="Résidence Test",
            city=None,
            zone=None,
            promoter=None,
            asset_type=None,
            first_detected_at="2026-01-01T00:00:00+00:00",
            last_updated_at="2026-01-01T00:00:00+00:00",
            launch_score=0,
            confidence_score=0,
            investment_score=0,
            urgency_score=0,
            recommendation="Watch",
            status="monitor",
            summary="",
            prices={},
            aliases=["Résidence Test"],
            channels=["project_discovery"],
            sources=["Test"],
            source_urls=["https://example.com/projet"],
            evidence={},
            reasons=[],
            timeline=[],
            signals=[signal],
        )
        enriched_project = enrich_project(project, config)
        self.assertEqual(enriched_project.evidence["availability"]["status"], "sold_out")
        self.assertEqual(enriched_project.recommendation, "Watch")
        self.assertTrue(any("marqué complet" in reason for reason in enriched_project.reasons))


if __name__ == "__main__":
    unittest.main()
