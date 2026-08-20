"""Backend service API: orchestration layer."""
from analytics import (
    build_cards,
    build_insights,
    build_plan_rows,
    build_price_comparison,
    build_solar_summary,
    _build_default_ai_actions,
    _build_default_ai_summary,
    _build_default_tomorrow_plan,
    _parse_number,
)
from ai_consultant import (
    build_ai_consultant,
    _extract_json_object,
)
from config import (
    CLIENT_PROFILES,
    SOLAR_OPTIONS,
    normalize_client_type,
    normalize_solar_setting,
    LOCAL_AI_ENABLED,
)
from data_loader import (
    get_active_consumption_source,
    get_available_source_options,
    load_dataset,
    set_active_consumption_source,
)
from portfolio import get_portfolio_rank_and_size


# Re-export for backward compatibility with tests
__all__ = [
    "get_bootstrap_data",
    "get_dashboard_data",
    "load_dataset",
    "set_active_consumption_source",
    "normalize_client_type",
    "normalize_solar_setting",
    "_parse_number",
    "_extract_json_object",
    "LOCAL_AI_ENABLED",
    "CLIENT_PROFILES",
    "SOLAR_OPTIONS",
]
def get_bootstrap_data():
    """Get global portfolio summary and source options."""
    data = load_dataset()
    objects = data["objects"]
    total_consumption = sum(item["summary"]["totalConsumption"] for item in objects)
    total_cost = sum(item["summary"]["totalCost"] for item in objects)
    total_anomalies = sum(item["summary"]["anomalyCount"] for item in objects)
    source_options = get_available_source_options()

    portfolio = sorted(
        [
            {
                "id": item["id"],
                "name": item["name"],
                "annualConsumption": round(item["summary"]["totalConsumption"], 0),
                "annualCost": round(item["summary"]["totalCost"], 0),
                "anomalyCount": item["summary"]["anomalyCount"],
                "peakLoad": round(item["summary"]["peakHourlyConsumption"], 1),
            }
            for item in objects
        ],
        key=lambda entry: entry["annualCost"],
        reverse=True,
    )

    return {
        "generatedAt": data["generatedAt"],
        "sourceFile": data.get("sourceFile"),
        "sourceHasSolar": data.get("sourceHasSolar", False),
        "defaultObjectId": objects[0]["id"] if objects else None,
        "marketPricePeriod": data["marketPricePeriod"],
        "tomorrowPriceDate": data["tomorrowPrices"]["date"],
        "objects": [{"id": item["id"], "name": item["name"]} for item in objects],
        "activeSource": source_options["activeSource"],
        "availableSources": source_options["availableSources"],
        "clientTypeOptions": [{"value": key, "label": value["label"]} for key, value in CLIENT_PROFILES.items()],
        "solarOptions": SOLAR_OPTIONS,
        "globalSummary": {
            "objectCount": len(objects),
            "totalConsumption": round(total_consumption, 0),
            "totalCost": round(total_cost, 0),
            "totalAnomalies": total_anomalies,
            "averageTomorrowPrice": round(data["tomorrowPrices"]["averagePrice"], 2),
        },
        "portfolio": portfolio,
    }


def get_portfolio_report_data(object_ids, query_args):
    """Get compact analytics report for multiple objects without AI."""
    data = load_dataset()
    client_type = normalize_client_type(query_args.get("clientType"))

    results = []
    for object_id in object_ids:
        selected_object = next((item for item in data["objects"] if item["id"] == object_id), None)
        if selected_object is None:
            continue

        has_solar = normalize_solar_setting(
            query_args.get("hasSolar"),
            fallback=selected_object.get("solar", {}).get("detected", data.get("sourceHasSolar", False)),
        )
        inputs = {
            "area": _parse_number(query_args.get("area")),
            "equipmentCount": _parse_number(query_args.get("equipmentCount")),
            "equipmentPowerWatts": _parse_number(query_args.get("equipmentPowerWatts")),
            "solarCapacityKw": _parse_number(query_args.get("solarCapacityKw")),
        }

        insights = build_insights(selected_object, inputs, data["tomorrowPrices"], client_type, has_solar)
        rank, portfolio_size = get_portfolio_rank_and_size(object_id)

        results.append({
            "id": selected_object["id"],
            "name": selected_object["name"],
            "rank": rank,
            "portfolioSize": portfolio_size,
            "clientTypeLabel": insights["clientTypeLabel"],
            "hasSolar": has_solar,
            "cards": build_cards(selected_object, insights),
            "loadReductionKw": round(insights["loadReductionKw"], 1),
            "shiftableEnergy": round(insights["shiftableEnergy"], 1),
            "potentialSavings": insights["potentialSavings"],
            "recommendations": insights["recommendations"][:3],
            "statusChips": insights["statusChips"],
            "period": {
                "start": selected_object["summary"]["periodStart"],
                "end": selected_object["summary"]["periodEnd"],
            },
        })

    return {"objects": results}


def get_dashboard_data(object_id, query_args):
    """Get detailed dashboard data for an object without rebuilding full portfolio."""
    from analytics import _parse_number

    data = load_dataset()
    selected_object = next((item for item in data["objects"] if item["id"] == object_id), None)
    if selected_object is None:
        raise KeyError(f"Object '{object_id}' not found")
    client_type = normalize_client_type(query_args.get("clientType"))
    has_solar = normalize_solar_setting(
        query_args.get("hasSolar"),
        fallback=selected_object.get("solar", {}).get("detected", data.get("sourceHasSolar", False)),
    )

    inputs = {
        "area": _parse_number(query_args.get("area")),
        "equipmentCount": _parse_number(query_args.get("equipmentCount")),
        "equipmentPowerWatts": _parse_number(query_args.get("equipmentPowerWatts")),
        "solarCapacityKw": _parse_number(query_args.get("solarCapacityKw")),
    }
    fixed_price_eur_mwh = _parse_number(query_args.get("fixedPriceEurMwh")) or None

    insights = build_insights(selected_object, inputs, data["tomorrowPrices"], client_type, has_solar)

    # Optimization: get rank and portfolio size without rebuilding full bootstrap
    rank, portfolio_size = get_portfolio_rank_and_size(object_id)

    plan_rows = build_plan_rows(selected_object, data["tomorrowPrices"], fixed_price_eur_mwh)
    solar_summary = build_solar_summary(selected_object, insights, has_solar)

    # Prepare default values for AI consultant
    recommended_hours = [item["hour"] for item in solar_summary.get("recommendedHours", [])[:3]]
    default_summary = _build_default_ai_summary(selected_object, insights, has_solar, recommended_hours)
    default_actions = _build_default_ai_actions(insights, data["tomorrowPrices"], has_solar, recommended_hours)
    default_tomorrow_plan = _build_default_tomorrow_plan(data["tomorrowPrices"], has_solar, recommended_hours)

    ai_consultant = build_ai_consultant(
        selected_object,
        insights,
        inputs,
        data["tomorrowPrices"],
        has_solar,
        solar_summary,
        rank,
        portfolio_size,
        default_actions,
        default_tomorrow_plan,
        default_summary,
    )

    return {
        "generatedAt": data["generatedAt"],
        "object": {
            "id": selected_object["id"],
            "name": selected_object["name"],
            "rankByAnnualCost": rank,
        },
        "period": {
            "consumptionStart": selected_object["summary"]["periodStart"],
            "consumptionEnd": selected_object["summary"]["periodEnd"],
            "marketStart": data["marketPricePeriod"]["startDate"],
            "marketEnd": data["marketPricePeriod"]["endDate"],
            "tomorrowPriceDate": data["tomorrowPrices"]["date"],
        },
        "inputs": inputs,
        "clientType": client_type,
        "clientTypeLabel": insights["clientTypeLabel"],
        "hasSolar": has_solar,
        "solarLabel": "SES uzstādīts" if has_solar else "Bez SES",
        "cards": build_cards(selected_object, insights),
        "scenarioSummary": {
            "title": f"Scenārija novērtējums - {insights['clientTypeLabel']}",
            "text": insights["scenarioText"],
        },
        "statusChips": insights["statusChips"],
        "priceSignals": {
            "averagePrice": data["tomorrowPrices"]["averagePrice"],
            "cheapestHours": data["tomorrowPrices"]["cheapestHours"],
            "expensiveHours": data["tomorrowPrices"]["expensiveHours"],
        },
        "recommendations": insights["recommendations"],
        "aiConsultant": ai_consultant,
        "charts": {
            "consumptionHourly": selected_object["hourlyProfile"],
            "priceHourly": data["tomorrowPrices"]["hourly"],
            "dailyTrend": selected_object["last30Days"],
            "solarComparison": solar_summary["chart"],
        },
        "planRows": plan_rows,
        "priceComparison": build_price_comparison(selected_object, data["tomorrowPrices"], fixed_price_eur_mwh),
        "alerts": selected_object["anomalies"][:12],
        "solarSummary": solar_summary,
        "benchmark": {
            "portfolioRank": rank,
            "portfolioSize": portfolio_size,
            "installedPowerKw": insights["installedPowerKw"],
            "loadReductionKw": insights["loadReductionKw"],
            "shiftableEnergy": insights["shiftableEnergy"],
            "solarCapacityKw": insights["solarCapacityKw"],
        },
    }
