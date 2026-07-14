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
        self.assertEqual(project.evidence["confirmation_count"], 0)
        self.assertTrue(any("surveillance" in reason or "marqueur" in reason or "ville:" in reason for reason in project.reasons))

    def test_rewards_multi_source_confirmation(self):
        signals = [
            SignalEvent(
                collector="promoters.websites",
                channel="project_discovery",
                source="CGI",
                signal_type="promoter_page",
                title="Résidence Horizon Tanger",
                url="https://cgi.example/projet/horizon",
                text="Nouveau projet résidence Horizon Tanja Balia CGI",
                is_primary=True,
                launch_weight=25,
                confidence_weight=24,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="google.search",
                channel="google_discovery",
                source="Google Search",
                signal_type="search_result",
                title="Résidence Horizon - CGI Tanger",
                url="https://search.example/horizon",
                text="Résidence Horizon CGI Tanger",
                is_primary=True,
                launch_weight=18,
                confidence_weight=20,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="urbanism.watch",
                channel="urbanism",
                source="Agence Urbaine de Tanger",
                signal_type="urbanism_page",
                title="Permis résidence Horizon Tanja Balia",
                url="https://urban.example/horizon",
                text="Permis lotissement résidence Horizon Tanger",
                is_primary=True,
                launch_weight=20,
                confidence_weight=16,
            ),
        ]

        project = resolve_projects(signals, TEST_CONFIG)[0]

        self.assertGreaterEqual(project.evidence["confirmation_count"], 2)
        self.assertIn("google_discovery", project.evidence["primary_channels"])
        self.assertGreaterEqual(project.confidence_score, 80)

    def test_splits_generic_portal_ads_by_real_project_name(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Avito Immobilier Neuf",
                signal_type="meta_ad",
                title="Avito Immobilier Neuf · ad #1",
                url="https://facebook.example/ad-1",
                text="Découvrez Jnane Sorour, la première résidence fermée et sécurisée de moyen standing à Had Soualem.",
                is_primary=True,
                launch_weight=20,
                confidence_weight=24,
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Avito Immobilier Neuf",
                signal_type="meta_ad",
                title="Avito Immobilier Neuf · ad #2",
                url="https://facebook.example/ad-2",
                text="Les Perles de l'Atlas, votre nouvelle adresse à Marrakech ! Confort, modernité et qualité de vie.",
                is_primary=True,
                launch_weight=20,
                confidence_weight=24,
            ),
        ]

        projects = resolve_projects(signals, TEST_CONFIG)

        self.assertEqual(len(projects), 2)
        names = sorted(project.name for project in projects)
        self.assertEqual(names, ["Jnane Sorour", "Les Perles de l'Atlas"])

    def test_splits_generic_promoter_cta_pages_by_url_slug(self):
        config = {
            **TEST_CONFIG,
            "cities": {
                "tangier": {"label": "Tanger", "priority": 100, "zones": ["Tanja Balia"]},
                "casablanca": {"label": "Casablanca", "priority": 90, "zones": ["Anfa"]},
                "marrakech": {"label": "Marrakech", "priority": 85, "zones": ["Targa"]},
            },
        }
        signals = [
            SignalEvent(
                collector="promoters.websites",
                channel="project_discovery",
                source="CGI",
                signal_type="promoter_page",
                title="JE CONSULTE",
                url="https://www.cgi.ma/fr/projet/cgt-green-homes-iii",
                text="JE CONSULTE CGT-Green Homes III Casablanca Les appartements bénéficient de belles terrasses.",
                is_primary=True,
                launch_weight=30,
                confidence_weight=30,
                metadata={"promoter_hint": "CGI"},
            ),
            SignalEvent(
                collector="promoters.websites",
                channel="project_discovery",
                source="CGI",
                signal_type="promoter_page",
                title="JE CONSULTE",
                url="https://www.cgi.ma/fr/projet/les-orangers-de-targa",
                text="JE CONSULTE Les Orangers de Targa Marrakech Les villas construites sont réparties le long des avenues.",
                is_primary=True,
                launch_weight=30,
                confidence_weight=30,
                metadata={"promoter_hint": "CGI"},
            ),
        ]

        projects = resolve_projects(signals, config)

        self.assertEqual(len(projects), 2)
        names = {project.name for project in projects}
        self.assertEqual(names, {"Cgt Green Homes Iii", "Les Orangers Targa"})

    def test_skips_generic_promoter_category_urls(self):
        signals = [
            SignalEvent(
                collector="promoters.websites",
                channel="project_discovery",
                source="Chaabi Lil Iskane",
                signal_type="promoter_page",
                title="Projets économiques",
                url="https://www.liliskane.com/projet/type/1/projets-economiques",
                text="Projets économiques Lots de terrains Projets haut standing",
                is_primary=True,
                launch_weight=30,
                confidence_weight=30,
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects, [])

    def test_splits_same_promoter_meta_ads_when_project_names_differ(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Hamilton By Saham Immobilier",
                signal_type="meta_ad",
                title="Hamilton By Saham Immobilier · ad #3705538012919384",
                url="https://facebook.example/ad-3705538012919384",
                text="Hamilton By Saham Immobilier Duplex avec terrasse à Casablanca.",
                is_primary=True,
                metadata={"ad_id": "3705538012919384"},
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Le 25 By Saham Immobilier",
                signal_type="meta_ad",
                title="Le 25 By Saham Immobilier · ad #1948175832535249",
                url="https://facebook.example/ad-1948175832535249",
                text="Le 25 By Saham Immobilier surfaces commerciales et bureaux à Casablanca.",
                is_primary=True,
                metadata={"ad_id": "1948175832535249"},
            ),
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        names = {project.name for project in projects}
        self.assertEqual(names, {"Hamilton", "Le 25"})

    def test_extracts_real_project_name_from_meta_body(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Groupe Allali - L'immobilier autrement",
                signal_type="meta_ad",
                title="Groupe Allali - L'immobilier autrement · ad #1470832837415483",
                url="https://facebook.example/ad-evergreen",
                text="Lancement du nouveau projet Evergreen, signé Groupe allali Située à Californie, Casablanca.",
                is_primary=True,
                metadata={"ad_id": "1470832837415483"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects[0].name, "Evergreen")

    def test_extracts_project_name_from_meta_phrase_with_a_les(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Moubina Immobilier",
                signal_type="meta_ad",
                title="Moubina Immobilier · ad #2286079785469367",
                url="https://facebook.example/ad-les-palmiers",
                text="Appartements 2 chambres + salon à Les Palmiers Résidences. Projet par Moubina Immobilier à Agadir.",
                is_primary=True,
                metadata={"ad_id": "2286079785469367"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects[0].name, "Les Palmiers Résidences")

    def test_skips_meta_platform_source_without_specific_project(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Lotti.ma",
                signal_type="meta_ad",
                title="Lotti.ma · ad #4411805202396598",
                url="https://facebook.example/ad-lotti",
                text="Lotti.ma — le Google Maps des terrains au Maroc. Carte interactive unique.",
                is_primary=True,
                metadata={"ad_id": "4411805202396598"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects, [])

    def test_skips_generic_watch_and_urbanism_signals(self):
        signals = [
            SignalEvent(
                collector="google.search",
                channel="google_discovery",
                source="Google Search",
                signal_type="search_watch",
                title="Google discovery watch: site:cgi.ma tanger projet immobilier",
                url="https://www.google.com/search?q=site%3Acgi.ma+tanger+projet+immobilier&hl=fr",
                text="site:cgi.ma tanger projet immobilier",
                is_primary=True,
            ),
            SignalEvent(
                collector="urbanism.watch",
                channel="urbanism",
                source="Agence Urbaine de Casablanca",
                signal_type="urbanism_page",
                title="Urbanisme, planification, autorisations",
                url="https://www.auc.ma/",
                text="Urbanisme planification autorisations",
                is_primary=True,
            ),
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects, [])


if __name__ == "__main__":
    unittest.main()
