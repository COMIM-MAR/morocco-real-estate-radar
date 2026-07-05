import unittest
from unittest.mock import patch

try:
    from bs4 import BeautifulSoup
except ModuleNotFoundError:  # pragma: no cover - local bare Python can miss deps
    BeautifulSoup = None

try:
    from collectors.google.google_search import extract_results
    from collectors.urbanism.watch import extract_candidate_pages
except ModuleNotFoundError:  # pragma: no cover - local bare Python can miss deps
    extract_results = None
    extract_candidate_pages = None


@unittest.skipIf(BeautifulSoup is None or extract_results is None, "collector dependencies not installed locally")
class GoogleCollectorTests(unittest.TestCase):
    def test_extract_results_from_google_markup(self):
        soup = BeautifulSoup(
            """
            <html><body>
              <a href="/url?q=https://www.cgi.ma/projet/sun-hills&sa=U"><h3>Sun Hills Tanger - CGI</h3></a>
              <a href="/url?q=https://www.google.com/about&sa=U"><h3>Google About</h3></a>
              <a href="/url?q=https://www.alliances.co.ma/residence/ocean-view&sa=U">Ocean View Casablanca</a>
            </body></html>
            """,
            "lxml",
        )
        results = extract_results(soup)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0][0], "https://www.cgi.ma/projet/sun-hills")
        self.assertIn("Sun Hills", results[0][1])


@unittest.skipIf(BeautifulSoup is None or extract_candidate_pages is None, "collector dependencies not installed locally")
class UrbanismCollectorTests(unittest.TestCase):
    @patch("collectors.urbanism.watch.fetch")
    def test_extract_candidate_pages_uses_keyword_matches(self, mock_fetch):
        soup = BeautifulSoup(
            """
            <html><body>
              <a href="/documents/permis-lotissement.pdf">Permis de lotissement Tanja Balia</a>
              <a href="/about">A propos</a>
              <a href="/public/projet-residence-horizon">Projet résidence Horizon</a>
            </body></html>
            """,
            "lxml",
        )
        mock_fetch.return_value = (soup, "Nouveaux permis et plan d'aménagement")

        candidates = extract_candidate_pages(
            {
                "name": "Agence Urbaine de Tanger",
                "url": "https://urban.example",
                "description": "Permis et lotissements",
                "keywords": ["permis", "lotissement", "projet", "résidence"],
            }
        )

        self.assertGreaterEqual(len(candidates), 2)
        urls = [candidate[0] for candidate in candidates]
        self.assertIn("https://urban.example/documents/permis-lotissement.pdf", urls)


if __name__ == "__main__":
    unittest.main()
