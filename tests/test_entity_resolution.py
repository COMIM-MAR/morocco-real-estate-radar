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
        self.assertGreaterEqual(project.evidence["signal_count"], 2)
        self.assertGreaterEqual(project.confidence_score, 40)
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

    def test_skips_non_real_estate_meta_ads_even_when_address_contains_residence(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Medicine Chinoise Marrakech",
                signal_type="meta_ad",
                title="Medicine Chinoise Marrakech · ad #4476703432475114",
                url="https://facebook.example/ad-4476703432475114",
                text="Dans notre clinique à Marrakech, chaque patient est accompagné selon son état. Adresse : Résidence Bab Doukkala, Marrakech. Acupuncture et médecine chinoise.",
                is_primary=True,
            )
        ]
        self.assertEqual(resolve_projects(signals, TEST_CONFIG), [])

    def test_skips_hotel_and_business_travel_meta_ads(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Barceló Anfa Casablanca",
                signal_type="meta_ad",
                title="Barceló Anfa Casablanca · ad #1443477047548472",
                url="https://facebook.example/ad-1443477047548472",
                text="Travaillez, échangez et détendez-vous dans un cadre pensé pour les voyageurs d’affaires. Hôtel, séminaire et hospitalité d’exception.",
                is_primary=True,
            )
        ]
        self.assertEqual(resolve_projects(signals, TEST_CONFIG), [])

    def test_skips_medical_lab_meta_ads(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Centre de biologie Agadir",
                signal_type="meta_ad",
                title="Centre de biologie Agadir · ad #720000464505757",
                url="https://facebook.example/ad-720000464505757",
                text="Analyses sanguines, tests d’allergies et bilans de santé complets au centre de biologie médicale Agadir.",
                is_primary=True,
            )
        ]
        self.assertEqual(resolve_projects(signals, TEST_CONFIG), [])

    def test_extracts_project_name_from_form_cta_copy(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Rabatgardens",
                signal_type="meta_ad",
                title="Rabatgardens · ad #3868826090092010",
                url="https://facebook.example/ad-3868826090092010",
                text="Appartements 2 & 3 chambres. Recevez les prix, plans disponibles et informations du projet Rabat Garden en remplissant ce formulaire.",
                is_primary=True,
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].name, "Rabat Garden")

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

    def test_extracts_domain_tagana_instead_of_generic_phrase(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Mubawab Maroc",
                signal_type="meta_ad",
                title="Mubawab Maroc · ad #1308892521356270",
                url="https://facebook.example/ad-domaine-tagana",
                text="Avec Domaine Tagana, investissez dans des lots de terrains pour villas isolées à Marrakech. Les atouts du projet : terrains 4 façades.",
                is_primary=True,
                metadata={"ad_id": "1308892521356270"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects[0].name, "Domaine Tagana")

    def test_skips_rental_marketplace_meta_ads(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Appartement À Louer Agadir",
                signal_type="meta_ad",
                title="Appartement À Louer Agadir · ad #1366906295376095",
                url="https://facebook.example/ad-rental",
                text="Appartement meublé à louer par jour – Agadir Tilila. Facebook Marketplace avec ascenseur.",
                is_primary=True,
                metadata={"ad_id": "1366906295376095"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects, [])

    def test_skips_generic_agency_leadgen_meta_ads(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="agence immobilière anour",
                signal_type="meta_ad",
                title="agence immobilière anour · ad #4346086468963057",
                url="https://facebook.example/ad-anour",
                text="Je peux vous aider à trouver le bien qui correspond à votre budget et à vos besoins. Envoyez-moi un message privé avec votre budget.",
                is_primary=True,
                metadata={"ad_id": "4346086468963057"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects, [])

    def test_prefers_specific_page_name_when_body_phrase_is_generic(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="PLEIN SUD Résidences",
                signal_type="meta_ad",
                title="PLEIN SUD Résidences · ad #1335084374912174",
                url="https://facebook.example/ad-plein-sud",
                text="Nouveau projet situé à La Ferme Bretonne à Casablanca. Appartements modernes.",
                is_primary=True,
                metadata={"ad_id": "1335084374912174"},
            )
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        self.assertEqual(projects[0].name, "PLEIN SUD Résidences")

    def test_extracts_specific_names_from_meta_text(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Green lotus",
                signal_type="meta_ad",
                title="Green lotus · ad #858732286995931",
                url="https://facebook.example/ad-green-lotus",
                text="Green Lotus Business est un centre d'affaires moderne à Casablanca.",
                is_primary=True,
                metadata={"ad_id": "858732286995931"},
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Mubawab Maroc",
                signal_type="meta_ad",
                title="Mubawab Maroc · ad #889691464148330",
                url="https://facebook.example/ad-jnane-agadir",
                text="JNANE AGADIR IMMOBILIER propose des locaux commerciaux au cœur d’Agadir.",
                is_primary=True,
                metadata={"ad_id": "889691464148330"},
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Chaabane immobilier",
                signal_type="meta_ad",
                title="Chaabane immobilier · ad #1362893569120529",
                url="https://facebook.example/ad-oree-palm",
                text="Lancement de votre tout nouveau projet résidentiel L'Orée du Palm à Marrakech : Villas haut standing avec piscine.",
                is_primary=True,
                metadata={"ad_id": "1362893569120529"},
            ),
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Twenty Campus Casa Anfa",
                signal_type="meta_ad",
                title="Twenty Campus Casa Anfa · ad #1046854941349832",
                url="https://facebook.example/ad-twenty-campus",
                text="Résidence moderne avec ménage, internet, coworking, petit déjeuner. À Twenty Campus Casa Anfa.",
                is_primary=True,
                metadata={"ad_id": "1046854941349832"},
            ),
        ]
        projects = resolve_projects(signals, TEST_CONFIG)
        names = {project.name for project in projects}
        self.assertIn("Green Lotus Business", names)
        self.assertIn("JNANE AGADIR IMMOBILIER", names)
        self.assertIn("L'Orée du Palm", names)
        self.assertIn("Twenty Campus Casa Anfa", names)

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

    def test_skips_generic_portal_meta_ad_without_project_name(self):
        signals = [
            SignalEvent(
                collector="ads.meta_ads",
                channel="advertising",
                source="Agenz",
                signal_type="meta_ad",
                title="Agenz · ad #856031357200962",
                url="https://facebook.example/ad-agenz",
                text="Nouveau projet résidentiel à Oulfa, Casablanca, au sein d’une résidence fermée. Appartements de 67 m² à 190 m².",
                is_primary=True,
                metadata={"ad_id": "856031357200962"},
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
                collector="ads.meta_ads",
                channel="advertising",
                source="Meta Ad Library",
                signal_type="meta_watch",
                title="Meta Ads watch: Cap Spartel",
                url="https://www.facebook.com/ads/library/?q=Cap%20Spartel",
                text="Cap Spartel",
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
