import unittest

from core.scoring import detect_asset_type, detect_city_zone


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


if __name__ == "__main__":
    unittest.main()
