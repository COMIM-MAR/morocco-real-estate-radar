import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.models import SignalEvent
from core.promoter_discovery import (
    discover_candidates,
    extract_candidates_from_signal,
    init_candidate_table,
    is_plausible_candidate,
    load_pending_candidates,
    normalize_candidate_name,
    upsert_candidates,
)


def signal(channel="advertising", source="Meta Ads", title="", text="", url="https://example.com/ad/1", promoter_hint=None, metadata=None):
    return SignalEvent(
        collector="test",
        channel=channel,
        source=source,
        signal_type="ad",
        title=title,
        url=url,
        text=text,
        is_primary=True,
        promoter_hint=promoter_hint,
        metadata=metadata or {},
    )


class NormalizeAndPlausibilityTests(unittest.TestCase):
    def test_normalize_candidate_name_collapses_whitespace(self):
        self.assertEqual(normalize_candidate_name("  Résidence   Al Manar  "), "Résidence Al Manar")

    def test_normalize_candidate_name_handles_none(self):
        self.assertEqual(normalize_candidate_name(None), "")

    def test_is_plausible_candidate_rejects_short_names(self):
        self.assertFalse(is_plausible_candidate("Ab", set()))

    def test_is_plausible_candidate_rejects_generic_blocklist(self):
        self.assertFalse(is_plausible_candidate("Google News", set()))

    def test_is_plausible_candidate_rejects_already_tracked(self):
        self.assertFalse(is_plausible_candidate("CGI", {"CGI"}))

    def test_is_plausible_candidate_accepts_new_name(self):
        self.assertTrue(is_plausible_candidate("Groupe Palmier", {"CGI"}))


class ExtractCandidatesFromSignalTests(unittest.TestCase):
    def test_extracts_meta_ad_page_name_when_no_promoter_hint(self):
        s = signal(channel="advertising", metadata={"page_name": "Groupe Palmier Immo"})

        candidates = extract_candidates_from_signal(s, tracked_promoters=set())

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["name"], "Groupe Palmier Immo")
        self.assertEqual(candidates[0]["confidence"], 55)

    def test_skips_meta_ad_when_promoter_hint_already_set(self):
        s = signal(channel="advertising", promoter_hint="CGI", metadata={"page_name": "CGI Officiel"})

        candidates = extract_candidates_from_signal(s, tracked_promoters=set())

        self.assertEqual(candidates, [])

    def test_skips_meta_ad_when_page_name_is_generic(self):
        s = signal(channel="advertising", metadata={"page_name": "Facebook"})

        candidates = extract_candidates_from_signal(s, tracked_promoters=set())

        self.assertEqual(candidates, [])

    def test_extracts_developer_mention_from_text(self):
        s = signal(
            channel="news",
            title="Nouveau projet",
            text="Le promoteur immobilier Atlas Habitat lance un nouveau projet à Tanger.",
        )

        candidates = extract_candidates_from_signal(s, tracked_promoters=set())

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["name"], "Atlas Habitat")
        self.assertEqual(candidates[0]["confidence"], 40)

    def test_skips_developer_mention_when_already_tracked(self):
        s = signal(
            channel="news",
            title="Nouveau projet",
            text="Le promoteur immobilier CGI lance un nouveau projet à Tanger.",
        )

        candidates = extract_candidates_from_signal(s, tracked_promoters={"CGI"})

        self.assertEqual(candidates, [])


class DiscoverCandidatesTests(unittest.TestCase):
    def test_discover_candidates_aggregates_across_signals(self):
        signals = [
            signal(channel="advertising", metadata={"page_name": "Groupe Palmier Immo"}),
            signal(
                channel="news",
                title="",
                text="Le développeur immobilier Atlas Habitat annonce un lancement.",
                url="https://example.com/news/1",
            ),
        ]
        config = {"promoters": {"tracked": ["CGI"]}}

        candidates = discover_candidates(signals, config)

        names = {candidate["name"] for candidate in candidates}
        self.assertEqual(names, {"Groupe Palmier Immo", "Atlas Habitat"})


class CandidatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self._tmpdir.name) / "test_intelligence.db"
        patcher = patch("core.database.DATABASE_PATH", db_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._tmpdir.cleanup)

    def test_upsert_and_load_pending_candidates_round_trip(self):
        init_candidate_table()
        upsert_candidates(
            [
                {
                    "name": "Groupe Palmier Immo",
                    "reason": "page Meta Ad Library non reconnue comme promoteur suivi",
                    "url": "https://example.com/ad/1",
                    "confidence": 55,
                }
            ]
        )

        pending = load_pending_candidates(min_confidence=0)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["name"], "Groupe Palmier Immo")
        self.assertEqual(pending[0]["occurrence_count"], 1)
        self.assertEqual(pending[0]["status"], "pending")

    def test_upsert_accumulates_occurrence_and_confidence_on_repeat(self):
        candidate = {
            "name": "Atlas Habitat",
            "reason": "mention explicite \"promoteur/développeur\" détectée dans le texte",
            "url": "https://example.com/news/1",
            "confidence": 40,
        }

        upsert_candidates([candidate])
        upsert_candidates([candidate])

        pending = load_pending_candidates(min_confidence=0)

        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["occurrence_count"], 2)
        self.assertGreater(pending[0]["confidence"], 40)

    def test_load_pending_candidates_filters_by_min_confidence(self):
        upsert_candidates(
            [
                {"name": "Low Confidence Co", "reason": "r", "url": "https://example.com/1", "confidence": 20},
                {"name": "High Confidence Co", "reason": "r", "url": "https://example.com/2", "confidence": 80},
            ]
        )

        pending = load_pending_candidates(min_confidence=50)

        names = {candidate["name"] for candidate in pending}
        self.assertEqual(names, {"High Confidence Co"})


if __name__ == "__main__":
    unittest.main()
