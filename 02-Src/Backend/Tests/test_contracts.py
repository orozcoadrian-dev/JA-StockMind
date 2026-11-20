import unittest

from pydantic import ValidationError

from Backend.Models.schemas import (
    CanonicalProductCreate,
    EquivalenceRuleCreate,
    ProductCreate,
    SupplierCreate,
)


class ContractsValidationTest(unittest.TestCase):
    def test_valid_supplier_passes(self):
        payload = {
            "name": "Inversiones Guerrero",
            "nit": "900123456-7",
            "contact": "Carlos Ruiz",
            "active": True,
        }

        supplier = SupplierCreate(**payload)

        self.assertEqual(supplier.name, "Inversiones Guerrero")
        self.assertTrue(supplier.active)

    def test_valid_product_passes(self):
        payload = {
            "supplier_id": 1,
            "provider_code": "IG-4471",
            "raw_name": "GRIP ROJO DEPORTIVO",
            "normalized_name": "grip rojo deportivo",
            "category": "manillar",
            "unit_price": 185000,
            "currency": "COP",
            "unit_of_measure": "unidad",
            "pack_quantity": 1,
            "price_list_date": "2026-09-01",
            "row_hash": "abc12345",
        }

        product = ProductCreate(**payload)

        self.assertEqual(product.category, "manillar")
        self.assertEqual(product.provider_code, "IG-4471")

    def test_valid_rule_passes_and_supports_exclusion_and_preference(self):
        equivalence_rule = EquivalenceRuleCreate(
            original_text="si un grip rojo lo provee Inversiones Guerrero y Malusa, es el mismo",
            structured_condition={
                "type": "supplier_equivalence",
                "match": {
                    "keywords": ["grip", "rojo"],
                    "attributes": {"color": "rojo", "type": "grip"},
                },
                "suppliers": ["Inversiones Guerrero", "Malusa"],
                "action": "merge_to_canonical",
                "confidence": 1.0,
            },
            supplier_names=["Inversiones Guerrero", "Malusa"],
            active=True,
        )

        exclusion_rule = EquivalenceRuleCreate(
            original_text="no son el mismo aunque se parezcan",
            structured_condition={
                "type": "exclusion",
                "match": {"keywords": ["grip", "azul"]},
                "suppliers": ["Malusa"],
                "action": "block_merge",
                "confidence": 0.99,
            },
            supplier_names=["Malusa"],
            active=True,
        )

        preference_rule = EquivalenceRuleCreate(
            original_text="para frenos, prefiere Distrimotos",
            structured_condition={
                "type": "purchase_preference",
                "match": {"category": "frenos"},
                "suppliers": ["Distrimotos"],
                "action": "prefer_supplier",
                "confidence": 0.95,
            },
            supplier_names=["Distrimotos"],
            active=True,
        )

        self.assertEqual(equivalence_rule.structured_condition["type"], "supplier_equivalence")
        self.assertEqual(exclusion_rule.structured_condition["action"], "block_merge")
        self.assertEqual(preference_rule.structured_condition["type"], "purchase_preference")

    def test_invalid_supplier_fails_with_clear_message(self):
        with self.assertRaises(ValidationError):
            SupplierCreate(name="", nit="bad", contact="", active="yes")

    def test_invalid_product_fails_when_required_fields_are_missing(self):
        with self.assertRaises(ValidationError):
            ProductCreate(
                supplier_id=1,
                provider_code="",
                raw_name="",
                normalized_name="grip rojo",
                category="manillar",
                unit_price=-1,
                currency="COP",
                unit_of_measure="unidad",
                pack_quantity=0,
                price_list_date="2026-09-01",
                row_hash="abc",
            )

    def test_invalid_rule_fails_on_wrong_condition_type(self):
        with self.assertRaises(ValidationError):
            EquivalenceRuleCreate(
                original_text="regla inválida",
                structured_condition={
                    "type": "unknown_rule",
                    "match": {"keywords": ["grip"]},
                    "suppliers": ["Inversiones Guerrero"],
                    "action": "merge_to_canonical",
                    "confidence": 0.4,
                },
                supplier_names=["Inversiones Guerrero"],
                active=True,
            )

    def test_canonical_product_attributes_json_are_validated(self):
        payload = {
            "name": "Grip rojo deportivo",
            "category": "manillar",
            "attributes": {"color": "rojo", "measure": "22mm", "compatible_brand": "Kawasaki"},
            "stock_in_bodega": 45,
            "minimum_stock": 10,
        }

        canonical = CanonicalProductCreate(**payload)
        self.assertEqual(canonical.attributes["color"], "rojo")


if __name__ == "__main__":
    unittest.main()
