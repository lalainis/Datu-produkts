import unittest
from unittest.mock import patch

import backend_service
from scripts.generate_data import hour_label, percentile, price_hour_label
from server import app


class BackendHelpersTestCase(unittest.TestCase):
    def test_parse_number_accepts_positive_finite_values_only(self):
        self.assertEqual(backend_service._parse_number("12.5"), 12.5)
        self.assertEqual(backend_service._parse_number("-2"), 0.0)
        self.assertEqual(backend_service._parse_number("not a number"), 0.0)
        self.assertEqual(backend_service._parse_number(float("nan")), 0.0)

    def test_normalize_client_type_falls_back_to_office(self):
        self.assertEqual(backend_service.normalize_client_type("retail"), "retail")
        self.assertEqual(backend_service.normalize_client_type("unknown"), "office")

    def test_normalize_solar_setting_handles_common_values(self):
        self.assertTrue(backend_service.normalize_solar_setting("yes"))
        self.assertTrue(backend_service.normalize_solar_setting("TRUE"))
        self.assertFalse(backend_service.normalize_solar_setting("no", fallback=True))
        self.assertTrue(backend_service.normalize_solar_setting(None, fallback=True))

    def test_extract_json_object_accepts_markdown_wrapped_json(self):
        raw = 'Model response:\n{"summary": "OK", "actions": []}'

        self.assertEqual(backend_service._extract_json_object(raw)["summary"], "OK")

    def test_generate_data_helpers_normalize_hours_and_percentiles(self):
        self.assertEqual(hour_label("08:00 - 09:00"), "08:00:00")
        self.assertEqual(price_hour_label("08:00 - 08:15"), "08:00")
        self.assertEqual(percentile([10, 20, 30], 0.5), 20)
        self.assertEqual(percentile([], 0.5), 0)


class BackendApiTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = app.test_client()

    def test_health_returns_dataset_metadata(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertGreater(payload["objects"], 0)
        self.assertTrue(payload["generatedAt"])

    def test_bootstrap_returns_objects_and_source_options(self):
        response = self.client.get("/api/bootstrap")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertGreater(len(payload["objects"]), 0)
        self.assertGreaterEqual(len(payload["availableSources"]), 1)
        self.assertIn("globalSummary", payload)
        self.assertIn("portfolio", payload)

    def test_dashboard_requires_object_id(self):
        response = self.client.get("/api/dashboard")

        self.assertEqual(response.status_code, 400)
        self.assertIn("objectId", response.get_json()["error"])

    def test_dashboard_rejects_unknown_object(self):
        response = self.client.get("/api/dashboard?objectId=missing")

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.get_json()["error"])

    def test_dashboard_returns_scenario_for_existing_object(self):
        bootstrap = self.client.get("/api/bootstrap").get_json()
        object_id = bootstrap["defaultObjectId"]

        with patch.object(backend_service, "LOCAL_AI_ENABLED", False):
            response = self.client.get(
                "/api/dashboard",
                query_string={
                    "objectId": object_id,
                    "clientType": "office",
                    "hasSolar": "no",
                    "area": "450",
                    "equipmentCount": "10",
                    "equipmentPowerWatts": "1200",
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["object"]["id"], object_id)
        self.assertIn("scenarioSummary", payload)
        self.assertIn("recommendations", payload)
        self.assertEqual(payload["aiConsultant"]["status"], "disabled")

    def test_source_endpoint_rejects_unknown_file(self):
        response = self.client.post("/api/source", json={"fileName": "missing.xlsx"})

        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.get_json()["error"])


if __name__ == "__main__":
    unittest.main()