import unittest

from fastapi.testclient import TestClient

from Backend.app import app


class ApiEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_endpoint_is_available(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_compare_skus_returns_high_confidence_for_similar_names(self):
        response = self.client.post(
            "/api/compare-skus",
            json={"sku_a": "Manillar rojo", "sku_b": "Grip rojo"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.json()["analysis"]["confidence"], 72)
        self.assertEqual(response.json()["analysis"]["recommendation"], "Fusionar")


if __name__ == "__main__":
    unittest.main()
