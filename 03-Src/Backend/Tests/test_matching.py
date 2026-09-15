import unittest

from Backend.Models.product import Product
from Backend.Services.matcher import compare_products, find_candidates


def product(product_id, supplier_id, name, price, category="manillar"):
    return Product(
        id=product_id,
        supplier_id=supplier_id,
        provider_code=f"SKU-{product_id}",
        raw_name=name,
        normalized_name=name.lower(),
        category=category,
        unit_price=price,
        currency="COP",
        unit_of_measure="unidad",
        pack_quantity=1,
        price_list_date="2026-09-01",
        row_hash=f"hash-{product_id}",
    )


class MatchingEngineTest(unittest.TestCase):
    def test_red_grips_match_but_blue_and_different_measure_do_not(self):
        guerrero = product(1, 1, "GRIP ROJO DEPORTIVO 22mm", 185000)
        malusa_red = product(2, 2, "Manubrio grip rojo 22mm", 190000)
        malusa_blue = product(3, 2, "Manubrio grip azul 22mm", 190000)
        malusa_different_measure = product(4, 2, "Manubrio grip rojo 28mm", 190000)

        red_score, red_reasons = compare_products(guerrero, malusa_red)
        blue_score, blue_reasons = compare_products(guerrero, malusa_blue)
        measure_score, measure_reasons = compare_products(guerrero, malusa_different_measure)

        self.assertGreater(red_score, 0.90)
        self.assertTrue(any("color" in reason.lower() for reason in red_reasons))
        self.assertLess(blue_score, 0.65)
        self.assertTrue(any("contradic" in reason.lower() for reason in blue_reasons))
        self.assertLess(measure_score, 0.65)
        self.assertTrue(any("medida" in reason.lower() for reason in measure_reasons))

    def test_find_candidates_returns_threshold_and_reasons(self):
        source = product(1, 1, "GRIP ROJO DEPORTIVO 22mm", 185000)
        candidate = product(2, 2, "Manubrio grip rojo 22mm", 190000)

        results = find_candidates(source, [candidate])

        self.assertEqual(len(results), 1)
        self.assertGreater(results[0][1], 0.90)
        self.assertTrue(results[0][2])


if __name__ == "__main__":
    unittest.main()