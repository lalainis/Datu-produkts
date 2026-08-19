"""Unit tests for analytics.py calculation functions."""
import unittest

from analytics import build_cards, build_insights, build_plan_rows, build_solar_summary


# --- Shared fixtures ---

_HOURLY_PROFILE = [{"hour": f"{h:02d}:00", "consumption": 10.0 + h * 0.5} for h in range(24)]

_TOMORROW_PRICES = {
    "date": "2026-08-20",
    "hourly": [{"hour": f"{h:02d}:00", "price": 50.0 + h * 2} for h in range(24)],
    "cheapestHours": [
        {"hour": "00:00", "price": 50.0},
        {"hour": "01:00", "price": 52.0},
        {"hour": "02:00", "price": 54.0},
    ],
    "expensiveHours": [
        {"hour": "23:00", "price": 96.0},
        {"hour": "22:00", "price": 94.0},
        {"hour": "21:00", "price": 92.0},
    ],
    "averagePrice": 73.0,
}

_SUMMARY = {
    "totalConsumption": 87600.0,
    "totalCost": 5000.0,
    "averageDailyConsumption": 240.0,
    "peakHourlyConsumption": 75.0,
    "currentAllowedLoadKw": 100.0,
    "recommendedAllowedLoadKw": 80.0,
    "anomalyCount": 5,
    "topPeakHours": [
        {"hour": "23:00", "consumption": 21.5},
        {"hour": "22:00", "consumption": 21.0},
        {"hour": "21:00", "consumption": 20.5},
    ],
}

_SOLAR_DATA = {
    "detected": False,
    "totalExport": 0.0,
    "averageDailyExport": 0.0,
    "peakExport": 0.0,
    "exportHours": 0,
    "topExportHours": [],
}

_SELECTED_OBJECT = {
    "id": "test-obj",
    "name": "Testa Objekts",
    "hourlyProfile": _HOURLY_PROFILE,
    "exportHourlyProfile": [],
    "solar": _SOLAR_DATA,
    "summary": _SUMMARY,
}

_INPUTS = {
    "equipmentCount": 0,
    "equipmentPowerWatts": 0,
    "solarCapacityKw": 0.0,
    "area": 0.0,
}


class BuildCardsTestCase(unittest.TestCase):
    def setUp(self):
        self.insights = {"potentialSavings": 4.50, "shiftableEnergy": 18.0}

    def test_returns_six_cards(self):
        cards = build_cards(_SELECTED_OBJECT, self.insights)
        self.assertEqual(len(cards), 6)

    def test_total_consumption_card_value(self):
        cards = build_cards(_SELECTED_OBJECT, self.insights)
        card = next(c for c in cards if c["unit"] == "kWh" and "patēriņš" in c["label"].lower())
        self.assertAlmostEqual(card["value"], 87600.0, places=0)

    def test_savings_card_uses_insights_value(self):
        cards = build_cards(_SELECTED_OBJECT, self.insights)
        card = next(c for c in cards if "ietaupīj" in c["label"].lower())
        self.assertEqual(card["value"], self.insights["potentialSavings"])

    def test_anomaly_card_matches_summary(self):
        cards = build_cards(_SELECTED_OBJECT, self.insights)
        card = next(c for c in cards if c["unit"] == "not.")
        self.assertEqual(card["value"], _SUMMARY["anomalyCount"])

    def test_recommended_load_card(self):
        cards = build_cards(_SELECTED_OBJECT, self.insights)
        card = next(c for c in cards if c["unit"] == "kW")
        self.assertAlmostEqual(card["value"], _SUMMARY["recommendedAllowedLoadKw"], places=0)


class BuildPlanRowsTestCase(unittest.TestCase):
    def setUp(self):
        self.rows = build_plan_rows(_SELECTED_OBJECT, _TOMORROW_PRICES)
        self.row_map = {r["hour"]: r for r in self.rows}

    def test_row_count_matches_hourly_prices(self):
        self.assertEqual(len(self.rows), len(_TOMORROW_PRICES["hourly"]))

    def test_cheap_hours_get_success_tone(self):
        cheap_hours = {item["hour"] for item in _TOMORROW_PRICES["cheapestHours"]}
        for row in self.rows:
            if row["hour"] in cheap_hours:
                self.assertEqual(row["tone"], "success")

    def test_expensive_hours_get_danger_tone(self):
        expensive_hours = {item["hour"] for item in _TOMORROW_PRICES["expensiveHours"]}
        for row in self.rows:
            if row["hour"] in expensive_hours:
                self.assertEqual(row["tone"], "danger")

    def test_rows_have_required_fields(self):
        for row in self.rows:
            for field in ("hour", "consumption", "price", "action", "tone"):
                self.assertIn(field, row)

    def test_consumption_matches_hourly_profile(self):
        profile_map = {item["hour"]: item["consumption"] for item in _HOURLY_PROFILE}
        for row in self.rows:
            expected = round(profile_map.get(row["hour"], 0), 2)
            self.assertAlmostEqual(row["consumption"], expected, places=2)

    def test_above_average_price_gets_warning_tone(self):
        expensive_hours = {item["hour"] for item in _TOMORROW_PRICES["expensiveHours"]}
        cheap_hours = {item["hour"] for item in _TOMORROW_PRICES["cheapestHours"]}
        for row in self.rows:
            if row["hour"] in expensive_hours or row["hour"] in cheap_hours:
                continue
            if row["price"] > _TOMORROW_PRICES["averagePrice"]:
                self.assertEqual(row["tone"], "warning")
            else:
                self.assertEqual(row["tone"], "neutral")


class BuildInsightsTestCase(unittest.TestCase):
    def _insights(self, inputs=None, selected_object=None, has_solar=False, client_type="office"):
        return build_insights(
            selected_object or _SELECTED_OBJECT,
            {**_INPUTS, **(inputs or {})},
            _TOMORROW_PRICES,
            client_type,
            has_solar,
        )

    def test_required_keys_present(self):
        result = self._insights()
        for key in (
            "shiftableEnergy", "potentialSavings", "loadReductionKw",
            "loadReservePercent", "recommendations", "statusChips",
            "clientTypeLabel", "hasSolar",
        ):
            self.assertIn(key, result)

    def test_potential_savings_positive_given_price_spread(self):
        result = self._insights()
        self.assertGreater(result["potentialSavings"], 0)

    def test_load_reduction_kw_equals_current_minus_recommended(self):
        result = self._insights()
        expected = _SUMMARY["currentAllowedLoadKw"] - _SUMMARY["recommendedAllowedLoadKw"]
        self.assertAlmostEqual(result["loadReductionKw"], expected, places=1)

    def test_load_reduction_kw_is_zero_when_recommended_exceeds_current(self):
        summary = {**_SUMMARY, "currentAllowedLoadKw": 80.0, "recommendedAllowedLoadKw": 90.0}
        result = self._insights(selected_object={**_SELECTED_OBJECT, "summary": summary})
        self.assertEqual(result["loadReductionKw"], 0.0)

    def test_intensity_computed_when_area_provided(self):
        result = self._insights(inputs={"area": 1000.0, "equipmentCount": 0, "equipmentPowerWatts": 0, "solarCapacityKw": 0.0})
        # 87600 kWh / 1000 m² = 87.6 kWh/m²
        self.assertIn("87,6", result["scenarioText"])

    def test_no_solar_fields_when_has_solar_false(self):
        result = self._insights(has_solar=False)
        self.assertFalse(result["hasSolar"])
        self.assertEqual(result["solarCapacityKw"], 0.0)
        self.assertEqual(result["solarWindowConsumptionKwh"], 0.0)

    def test_solar_capacity_included_when_has_solar_true(self):
        solar_obj = {
            **_SELECTED_OBJECT,
            "solar": {
                **_SOLAR_DATA,
                "detected": True,
                "totalExport": 5.0,
                "averageDailyExport": 2.0,
                "topExportHours": [{"hour": "11:00", "export": 1.5}, {"hour": "12:00", "export": 1.2}],
            },
        }
        result = self._insights(
            selected_object=solar_obj,
            has_solar=True,
            inputs={"area": 0.0, "equipmentCount": 0, "equipmentPowerWatts": 0, "solarCapacityKw": 10.0},
        )
        self.assertTrue(result["hasSolar"])
        self.assertEqual(result["solarCapacityKw"], 10.0)
        self.assertGreater(result["solarWindowConsumptionKwh"], 0)

    def test_solar_adds_extra_recommendations(self):
        solar_obj = {
            **_SELECTED_OBJECT,
            "solar": {**_SOLAR_DATA, "detected": True, "totalExport": 5.0, "averageDailyExport": 2.0,
                      "topExportHours": [{"hour": "11:00", "export": 1.5}]},
        }
        no_solar = self._insights(has_solar=False)
        with_solar = self._insights(selected_object=solar_obj, has_solar=True)
        self.assertGreater(len(with_solar["recommendations"]), len(no_solar["recommendations"]))

    def test_installed_power_calculated_from_equipment_inputs(self):
        result = self._insights(
            inputs={"equipmentCount": 5, "equipmentPowerWatts": 2000, "solarCapacityKw": 0.0, "area": 0.0}
        )
        self.assertAlmostEqual(result["installedPowerKw"], 10.0, places=1)

    def test_equipment_recommendation_included_when_equipment_provided(self):
        result = self._insights(
            inputs={"equipmentCount": 5, "equipmentPowerWatts": 2000, "solarCapacityKw": 0.0, "area": 0.0}
        )
        titles = [r["title"] for r in result["recommendations"]]
        self.assertTrue(any("jaud" in t.lower() for t in titles))

    def test_client_type_label_differs_by_type(self):
        office = self._insights(client_type="office")
        retail = self._insights(client_type="retail")
        self.assertNotEqual(office["clientTypeLabel"], retail["clientTypeLabel"])


class BuildSolarSummaryTestCase(unittest.TestCase):
    def _insights(self, capacity_kw=0.0, self_use=0.0, priority_hours=None):
        return {
            "solarCapacityKw": capacity_kw,
            "solarSelfUsePotentialKwh": self_use,
            "solarPriorityHours": priority_hours or ["10:00", "11:00", "12:00", "13:00", "14:00"],
        }

    def test_result_has_required_keys(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(), has_solar=False)
        for key in ("cards", "recommendedHours", "chart"):
            self.assertIn(key, result)

    def test_cards_length_is_four(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(), has_solar=False)
        self.assertEqual(len(result["cards"]), 4)

    def test_capacity_card_reflects_insights_value(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(capacity_kw=15.0), has_solar=True)
        self.assertAlmostEqual(result["cards"][0]["value"], 15.0, places=1)

    def test_forecast_generation_zero_without_capacity(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(capacity_kw=0.0), has_solar=False)
        for row in result["chart"]["items"]:
            self.assertEqual(row["forecastGeneration"], 0.0)

    def test_self_use_potential_capped_at_consumption(self):
        solar_obj = {
            **_SELECTED_OBJECT,
            "exportHourlyProfile": [{"hour": "11:00", "export": 999.0}],
        }
        result = build_solar_summary(solar_obj, self._insights(capacity_kw=5.0), has_solar=True)
        for row in result["chart"]["items"]:
            self.assertLessEqual(row["selfUsePotential"], row["consumption"] + 1e-9)

    def test_secondary_key_is_forecast_when_capacity_set(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(capacity_kw=10.0), has_solar=True)
        self.assertEqual(result["chart"]["secondaryValueKey"], "forecastGeneration")

    def test_secondary_key_is_export_when_no_capacity(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(capacity_kw=0.0), has_solar=False)
        self.assertEqual(result["chart"]["secondaryValueKey"], "export")

    def test_recommended_hours_capped_at_three(self):
        result = build_solar_summary(_SELECTED_OBJECT, self._insights(capacity_kw=5.0), has_solar=True)
        self.assertLessEqual(len(result["recommendedHours"]), 3)


if __name__ == "__main__":
    unittest.main()
