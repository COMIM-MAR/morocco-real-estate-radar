import unittest

from collectors.promoters.websites import derive_project_title, is_generic_promoter_category, is_generic_promoter_url


class PromoterCollectorTests(unittest.TestCase):
    def test_filters_generic_category_pages(self):
        text = (
            "Projets économiques Chaabi Lil Iskane "
            "Projets économiques Projets moyen standing Projets haut standing "
            "Lots de terrains Locaux commerciaux Plateaux de bureaux"
        )
        self.assertTrue(is_generic_promoter_category("Projets économiques", text))

    def test_keeps_real_project_page(self):
        text = (
            "Les Palmiers Résidences Agadir appartements 2 chambres "
            "projet immobilier moderne avec vue sur jardin"
        )
        self.assertFalse(is_generic_promoter_category("Les Palmiers Résidences", text))

    def test_derives_project_title_from_url_when_cta_is_generic(self):
        title = derive_project_title(
            "https://www.cgi.ma/fr/projet/cgt-green-homes-iii",
            "JE CONSULTE",
            "JE CONSULTE CGT-Green Homes III | CGI",
        )
        self.assertEqual(title, "Cgt Green Homes Iii")

    def test_filters_generic_promoter_type_urls(self):
        self.assertTrue(is_generic_promoter_url("https://www.liliskane.com/projet/type/1/projets-economiques"))
        self.assertFalse(is_generic_promoter_url("https://www.liliskane.com/projet/95/riad-garden-i"))


if __name__ == "__main__":
    unittest.main()
