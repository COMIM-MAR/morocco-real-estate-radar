import unittest
from unittest.mock import patch

from collectors.news.google_news import collect


class FakeEntry(dict):
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


class FakeFeed:
    def __init__(self, entries):
        self.entries = entries


class GoogleNewsCollectorTests(unittest.TestCase):
    @patch("collectors.news.google_news.feedparser.parse")
    def test_collect_emits_real_news_signals_from_feed_entries(self, mock_parse):
        mock_parse.return_value = FakeFeed(
            [
                FakeEntry(
                    title="Lancement du projet résidence Horizon à Tanger",
                    link="https://example-news.ma/horizon-tanger",
                    summary="Un nouveau programme immobilier villa et appartement à Tanger",
                    source={"title": "Le Site Info"},
                    published="Mon, 01 Jan 2026 08:00:00 GMT",
                )
            ]
        )

        signals = collect({"sources": {"news_queries": ["nouveau projet immobilier Tanger"]}})

        self.assertEqual(len(signals), 1)
        signal = signals[0]
        self.assertEqual(signal.signal_type, "news_result")
        self.assertEqual(signal.channel, "news")
        self.assertEqual(signal.source, "Le Site Info")
        self.assertEqual(signal.url, "https://example-news.ma/horizon-tanger")
        self.assertTrue(signal.is_primary)
        self.assertGreater(signal.confidence_weight, 16)

    @patch("collectors.news.google_news.feedparser.parse")
    def test_collect_falls_back_to_watch_signal_when_feed_is_empty(self, mock_parse):
        mock_parse.return_value = FakeFeed([])

        signals = collect({"sources": {"news_queries": ["requête sans résultat"]}})

        self.assertEqual(len(signals), 1)
        signal = signals[0]
        self.assertEqual(signal.signal_type, "news_watch")
        self.assertEqual(signal.source, "Google News")


if __name__ == "__main__":
    unittest.main()
