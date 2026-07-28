import unittest
from unittest.mock import patch

from collectors.listings.portals import collect, detect_listing_date


class ListingDateDetectionTests(unittest.TestCase):
    def test_detects_relative_publication_date(self):
        text = "Annonce publiée il y a 3 jours par un particulier."
        self.assertEqual(detect_listing_date(text), "publiée il y a 3 jours")

    def test_detects_absolute_publication_date(self):
        text = "Mis à jour le 12/06/2026 avec de nouvelles photos."
        self.assertEqual(detect_listing_date(text), "Mis à jour le 12/06/2026")

    def test_returns_none_when_no_date_marker(self):
        self.assertIsNone(detect_listing_date("Bel appartement lumineux avec terrasse."))


class ListingsCollectorTests(unittest.TestCase):
    @patch("collectors.listings.portals.fetch")
    @patch("collectors.listings.portals.collect_detail_pages")
    def test_collect_extracts_availability_surface_and_date(self, mock_detail_pages, mock_fetch):
        mock_detail_pages.return_value = [("https://portal.example/a/villa-tanger", "Villa Tanger")]
        mock_fetch.return_value = (
            None,
            "Villa Tanger dernières unités disponibles, villa de 250 à 350 m², publiée il y a 2 jours.",
        )

        signals = collect(
            {
                "sources": {
                    "listings": [
                        {"name": "Mubawab Tanger Villas", "url": "https://portal.example/villas"},
                    ]
                }
            }
        )

        self.assertEqual(len(signals), 1)
        signal = signals[0]
        self.assertEqual(signal.metadata["availability"]["status"], "limited")
        self.assertEqual(signal.metadata["availability"]["surface_m2"], {"min": 250, "max": 350})
        self.assertEqual(signal.metadata["listing_date_hint"], "publiée il y a 2 jours")
        self.assertGreater(signal.launch_weight, 4)
        self.assertIn("stock limité repéré sur portail", signal.reasons)


if __name__ == "__main__":
    unittest.main()
