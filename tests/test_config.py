import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.config import merge_approved_promoters


class MergeApprovedPromotersTests(unittest.TestCase):
    def _with_approved(self, approved):
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)
        path = Path(tmpdir.name) / "approved_promoters.json"
        if approved is not None:
            path.write_text(json.dumps(approved, ensure_ascii=False), encoding="utf-8")
        return patch("core.config.APPROVED_PROMOTERS_PATH", path)

    def test_returns_config_unchanged_when_file_missing(self):
        config = {"promoters": {"tracked": ["CGI"]}}
        with self._with_approved(None):
            result = merge_approved_promoters(config)

        self.assertEqual(result, config)

    def test_appends_new_tracked_promoter_and_source(self):
        config = {"promoters": {"tracked": ["CGI"]}, "sources": {"promoters": []}}
        approved = [{"name": "Groupe Palmier Immo", "url": "https://palmier-immo.ma"}]
        with self._with_approved(approved):
            result = merge_approved_promoters(config)

        self.assertIn("Groupe Palmier Immo", result["promoters"]["tracked"])
        self.assertIn(
            {"name": "Groupe Palmier Immo", "url": "https://palmier-immo.ma"},
            result["sources"]["promoters"],
        )

    def test_does_not_duplicate_already_tracked_promoter(self):
        config = {"promoters": {"tracked": ["CGI"]}, "sources": {"promoters": []}}
        approved = [{"name": "cgi", "url": "https://cgi.ma"}]
        with self._with_approved(approved):
            result = merge_approved_promoters(config)

        self.assertEqual(result["promoters"]["tracked"].count("CGI"), 1)
        self.assertNotIn("cgi", result["promoters"]["tracked"])

    def test_does_not_duplicate_already_present_source_url(self):
        config = {
            "promoters": {"tracked": ["CGI"]},
            "sources": {"promoters": [{"name": "CGI", "url": "https://cgi.ma"}]},
        }
        approved = [{"name": "CGI", "url": "https://cgi.ma"}]
        with self._with_approved(approved):
            result = merge_approved_promoters(config)

        self.assertEqual(len(result["sources"]["promoters"]), 1)

    def test_skips_entries_without_a_name(self):
        config = {"promoters": {"tracked": []}, "sources": {"promoters": []}}
        approved = [{"url": "https://no-name.ma"}]
        with self._with_approved(approved):
            result = merge_approved_promoters(config)

        self.assertEqual(result["promoters"]["tracked"], [])
        self.assertEqual(result["sources"]["promoters"], [])


if __name__ == "__main__":
    unittest.main()
