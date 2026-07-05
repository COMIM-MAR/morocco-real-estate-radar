import unittest

from core.entity_resolution import resolve_projects
from core.models import SignalEvent


TEST_CONFIG = {
    "alerts": {
        "immediate_confidence_threshold": 90,
        "digest_confidence_threshold": 70,
    },
    "profile": {
        "cash_ready": 1_500_000,
        "max_budget": 3_000_000,
    },
    "asset_preferences": {
        "villa": 100,
        "land_r4_plus": 95,
        "apartment_3_bed": 75,
    },
    "cities": {
        "tangier": {
            "label": "Tanger",
            "priority": 100,
            "zones": ["Tanja Balia"],
        }
    },
    "promoters": {
        "tracked": ["CGI"],
    },
}


class EntityResolutionTests(unittest.TestCase):
    def test_groups_related_signals_into_one_project(self):
        signals = [
            SignalEvent(
                collector="promoters.websites",
                channel="project_discovery",
                source="CGI",
                signal_type="promoter_page",
                title="Sun Hills Tanger - nouveau projet",
                url="https://example.com/projet/sun-hills",
                text="Pré-commercialisation villas Tanja Balia Tanger CGI",
                is_primary=True,
                launch_weight=30,
                confidence_weight=30,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Meta Ad Library",
                signal_type="meta_watch",
                title="Sun Hills lancement Tanger",
                url="https://facebook.example/sun-hills",
                text="CGI lancement Sun Hills Tanger",
                is_primary=True,
                launch_weight=20,
                confidence_weight=24,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="listings.portals",
                channel="listing",
                source="Mubawab",
                signal_type="listing_detail",
                title="Villa Sun Hills à vendre",
                url="https://mubawab.example/sun-hills-villa",
                text="Villa Sun Hills Tanger Tanja Balia 2300000 dh",
                is_primary=False,
                launch_weight=4,
                confidence_weight=8,
            ),
        ]

        projects = resolve_projects(signals, TEST_CONFIG)

        self.assertEqual(len(projects), 1)
        project = projects[0]
        self.assertEqual(project.promoter, "CGI")
        self.assertEqual(project.city, "Tanger")
        self.assertIn("project_discovery", project.channels)
        self.assertGreaterEqual(project.evidence["signal_count"], 3)
        self.assertGreaterEqual(project.confidence_score, 60)


if __name__ == "__main__":
    unittest.main()
