import unittest

from collectors.ads.meta_ads import (
    best_entries,
    challenge_detected,
    detail_url,
    filter_relevant_entries,
    parse_text_blocks,
    query_contexts,
)


class MetaAdsParsingTests(unittest.TestCase):
    def test_extracts_exact_ad_entry_from_html_payload(self):
        html = """
        <html><body>
        <script>
        {"adArchiveID":"1234567890","pageName":"CGI Maroc","adSnapshotUrl":"https:\\/\\/www.facebook.com\\/ads\\/library\\/?id=1234567890","ad_creative_body":"Lancement projet immobilier à Tanger Prestigia","landing_page_url":"https:\\/\\/www.cgi.ma\\/prestigia-tanger"}
        </script>
        </body></html>
        """

        entries = best_entries(html, "CGI lancement immobilier Maroc", "CGI")

        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["ad_id"], "1234567890")
        self.assertEqual(entries[0]["snapshot_url"], detail_url("1234567890"))
        self.assertIn("Prestigia", entries[0]["body"])
        self.assertIn("cgi.ma", entries[0]["landing_page_url"])

    def test_detects_meta_client_challenge(self):
        self.assertTrue(challenge_detected("<html><body>Client challenge</body></html>"))
        self.assertFalse(challenge_detected("<html><body>normal page</body></html>"))

    def test_parses_visible_text_blocks_with_ad_ids(self):
        text = """
        Actif
        ID dans la bibliothèque : 4626203977511912
        Début de diffusion le 18 juin 2026
        Voir les détails de la publicité
        Green lotus
        Sponsorisé
        Green Lotus est un ensemble résidentiel et de services haut standing.
        La référence du bien-vivre à Casablanca
        """
        entries = parse_text_blocks(text)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["ad_id"], "4626203977511912")
        self.assertEqual(entries[0]["page_name"], "Green lotus")
        self.assertIn("ensemble résidentiel", entries[0]["body"])

    def test_builds_city_and_zone_meta_queries(self):
        config = {
            "promoters": {"tracked": ["CGI"]},
            "cities": {
                "casablanca": {"label": "Casablanca", "zones": ["Sidi Maarouf", "Bouskoura"]},
                "tangier": {"label": "Tanger", "zones": ["Malabata"]},
            },
            "sources": {"meta_ad_library_searches": ["pré-commercialisation Tanger"]},
        }
        queries = query_contexts(config)
        labels = [item["query"] for item in queries]
        self.assertIn("CGI Casablanca immobilier", labels)
        self.assertIn("CGI Sidi Maarouf", labels)
        self.assertIn("projet immobilier Tanger", labels)

    def test_filters_out_non_real_estate_entries(self):
        entries = [
            {
                "ad_id": "1",
                "page_name": "Green Lotus",
                "body": "Ensemble résidentiel haut standing à Casablanca",
                "caption": "",
                "landing_page_url": "https://greenlotus.ma/contact/",
                "snapshot_url": detail_url("1"),
            },
            {
                "ad_id": "2",
                "page_name": "Random Novel",
                "body": "A love story in another world",
                "caption": "",
                "landing_page_url": "https://example.com/story",
                "snapshot_url": detail_url("2"),
            },
        ]
        context = {"query": "Green Lotus", "promoter": None, "city": "Casablanca", "zone": None}
        filtered = filter_relevant_entries(entries, context)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["ad_id"], "1")


if __name__ == "__main__":
    unittest.main()
