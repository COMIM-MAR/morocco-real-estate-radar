import unittest
from types import SimpleNamespace

from core.availability import (
    analyze_availability,
    detect_availability_status,
    detect_surface_m2,
    detect_unit_count,
    project_availability_summary,
)


class AvailabilityDetectionTests(unittest.TestCase):
    def test_detects_sold_out_status(self):
        text = "Le programme est désormais complet, plus aucune disponibilité sur cette résidence."
        self.assertEqual(detect_availability_status(text), "sold_out")

    def test_detects_limited_status(self):
        text = "Dernières unités disponibles sur la résidence, stock limité avant fin de programme."
        self.assertEqual(detect_availability_status(text), "limited")

    def test_detects_available_status(self):
        text = "De nouveaux lots disponibles viennent d'être ouverts à la vente sur cette tranche."
        self.assertEqual(detect_availability_status(text), "available")

    def test_returns_none_when_no_marker_present(self):
        text = "Découvrez notre nouvelle résidence avec piscine et espaces verts."
        self.assertIsNone(detect_availability_status(text))

    def test_sold_out_takes_priority_over_available_marker(self):
        text = "Résidence disponible à la vente il y a quelques mois, désormais projet complet."
        self.assertEqual(detect_availability_status(text), "sold_out")

    def test_detects_unit_count(self):
        text = "Il ne reste que 6 villas disponibles sur ce programme exclusif."
        self.assertEqual(detect_unit_count(text), 6)

    def test_detects_surface_range(self):
        surface = detect_surface_m2("Appartements de 65 à 120 m² avec terrasse.")
        self.assertEqual(surface, {"min": 65, "max": 120})

    def test_detects_single_surface(self):
        surface = detect_surface_m2("Villa de 350 m² sur un lot arboré.")
        self.assertEqual(surface, {"min": 350, "max": 350})

    def test_analyze_availability_combines_all_signals(self):
        result = analyze_availability("Dernières unités: 3 villas disponibles de 300 à 400 m².")
        self.assertEqual(result["status"], "limited")
        self.assertEqual(result["unit_count"], 3)
        self.assertEqual(result["surface_m2"], {"min": 300, "max": 400})


class ProjectAvailabilitySummaryTests(unittest.TestCase):
    def test_aggregates_most_urgent_status_across_signals(self):
        signals = [
            SimpleNamespace(metadata={"availability": {"status": "available", "unit_count": None, "surface_m2": {"min": None, "max": None}}}),
            SimpleNamespace(metadata={"availability": {"status": "limited", "unit_count": 4, "surface_m2": {"min": 80, "max": 100}}}),
        ]
        summary = project_availability_summary(signals)
        self.assertEqual(summary["status"], "limited")
        self.assertEqual(summary["unit_count_min"], 4)
        self.assertEqual(summary["surface_m2"], {"min": 80, "max": 100})
        self.assertEqual(summary["signal_count"], 2)

    def test_returns_none_status_when_no_signal_carries_availability(self):
        signals = [SimpleNamespace(metadata={})]
        summary = project_availability_summary(signals)
        self.assertIsNone(summary["status"])
        self.assertEqual(summary["signal_count"], 0)


if __name__ == "__main__":
    unittest.main()
