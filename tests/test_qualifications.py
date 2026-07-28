import unittest
from unittest.mock import Mock, patch

from core.qualifications import (
    attach_qualifications,
    fetch_qualifications,
    is_alert_suppressed,
)


class FakeProject:
    def __init__(self, project_id):
        self.project_id = project_id
        self.evidence = {}


class QualificationsFetchTests(unittest.TestCase):
    @patch("core.qualifications.SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    @patch("core.qualifications.SUPABASE_URL", "https://example.supabase.co")
    @patch("core.qualifications.requests.get")
    def test_fetch_qualifications_indexes_rows_by_project_id(self, mock_get):
        mock_response = Mock()
        mock_response.json.return_value = [
            {"project_id": "p1", "status": "archived", "notes": "pas intéressé"},
            {"project_id": "p2", "status": "in_contact", "notes": ""},
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        qualifications = fetch_qualifications()

        self.assertEqual(qualifications["p1"]["status"], "archived")
        self.assertEqual(qualifications["p2"]["status"], "in_contact")

    @patch("core.qualifications.SUPABASE_SERVICE_ROLE_KEY", "")
    @patch("core.qualifications.SUPABASE_URL", "")
    def test_fetch_qualifications_returns_empty_when_not_configured(self):
        self.assertEqual(fetch_qualifications(), {})

    @patch("core.qualifications.SUPABASE_SERVICE_ROLE_KEY", "service-role-key")
    @patch("core.qualifications.SUPABASE_URL", "https://example.supabase.co")
    @patch("core.qualifications.requests.get", side_effect=RuntimeError("network down"))
    def test_fetch_qualifications_returns_empty_on_request_failure(self, mock_get):
        self.assertEqual(fetch_qualifications(), {})


class QualificationsWiringTests(unittest.TestCase):
    def test_attach_qualifications_defaults_to_new_when_missing(self):
        projects = [FakeProject("p1"), FakeProject("p2")]
        qualifications = {"p1": {"status": "interested", "notes": "à visiter"}}

        attach_qualifications(projects, qualifications)

        self.assertEqual(projects[0].evidence["qualification"]["status"], "interested")
        self.assertEqual(projects[1].evidence["qualification"]["status"], "new")

    def test_is_alert_suppressed_only_for_archived_status(self):
        qualifications = {"p1": {"status": "archived"}, "p2": {"status": "interested"}}
        self.assertTrue(is_alert_suppressed("p1", qualifications))
        self.assertFalse(is_alert_suppressed("p2", qualifications))
        self.assertFalse(is_alert_suppressed("unknown", qualifications))


if __name__ == "__main__":
    unittest.main()
