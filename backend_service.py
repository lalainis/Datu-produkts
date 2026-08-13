import json
import math
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "app-data.json"
SOURCE_FILES = [
    BASE_DIR / "Dati_prototipesanai.xlsx",
    BASE_DIR / "NP_Cenas_LV.xlsx",
    BASE_DIR / "scripts" / "generate_data.py",
]

_DATA_CACHE = None
_DATA_MTIME = None


def _parse_number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0


def _round_currency(value):
    return round(value, 2)


def _fmt_number(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def ensure_dataset():
    data_missing = not DATA_FILE.exists()
    source_newer = False
    if not data_missing:
        data_mtime = DATA_FILE.stat().st_mtime
        source_newer = any(path.exists() and path.stat().st_mtime > data_mtime for path in SOURCE_FILES)

    if data_missing or source_newer:
        subprocess.run(
            [sys.executable, str(BASE_DIR / "scripts" / "generate_data.py")],
            cwd=BASE_DIR,
            check=True,
        )


def load_dataset():
    global _DATA_CACHE, _DATA_MTIME

    ensure_dataset()
    current_mtime = DATA_FILE.stat().st_mtime
    if _DATA_CACHE is None or _DATA_MTIME != current_mtime:
        _DATA_CACHE = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _DATA_MTIME = current_mtime
    return _DATA_CACHE


def _build_insights(selected_object, inputs, tomorrow_prices):
    installed_power_kw = (
        (inputs["equipmentCount"] * inputs["equipmentPowerWatts"]) / 1000
        if inputs["equipmentCount"] > 0 and inputs["equipmentPowerWatts"] > 0
        else 0
    )

    expensive_hours = [item["hour"] for item in tomorrow_prices["expensiveHours"]]
    cheap_hours = [item["hour"] for item in tomorrow_prices["cheapestHours"]]
    hourly_map = {item["hour"]: item["consumption"] for item in selected_object["hourlyProfile"]}

    expensive_load = sum(hourly_map.get(hour, 0) for hour in expensive_hours)
    default_flexible_energy = selected_object["summary"]["averageDailyConsumption"] * 0.12
    equipment_flexible_energy = installed_power_kw * 2 if installed_power_kw > 0 else 0
    shiftable_energy = min(expensive_load * 0.3, max(default_flexible_energy, equipment_flexible_energy))

    avg_expensive_price = sum(item["price"] for item in tomorrow_prices["expensiveHours"]) / len(
        tomorrow_prices["expensiveHours"]
    )
    avg_cheap_price = sum(item["price"] for item in tomorrow_prices["cheapestHours"]) / len(
        tomorrow_prices["cheapestHours"]
    )
    potential_savings = ((avg_expensive_price - avg_cheap_price) * shiftable_energy) / 1000

    load_reduction_kw = max(
        0,
        selected_object["summary"]["currentAllowedLoadKw"]
        - selected_object["summary"]["recommendedAllowedLoadKw"],
    )
    load_reserve_percent = max(
        0,
        (
            1
            - (
                selected_object["summary"]["peakHourlyConsumption"]
                / max(selected_object["summary"]["currentAllowedLoadKw"], 1)
            )
        )
        * 100,
    )

    intensity_value = None
    intensity_label = "nav novērtēts"
    intensity_tone = "warning"
    intensity_text = "Pievieno telpu platību un iekārtu parametrus, lai backend modelis novērtētu efektivitātes intensitāti."

    if inputs["area"] > 0:
        intensity_value = selected_object["summary"]["totalConsumption"] / inputs["area"]
        if intensity_value < 140:
            intensity_label = "ļoti labs"
            intensity_tone = "success"
        elif intensity_value <= 220:
            intensity_label = "pieņemams"
            intensity_tone = "warning"
        else:
            intensity_label = "paaugstināts"
            intensity_tone = "danger"
        intensity_text = (
            f"Aprēķinātā patēriņa intensitāte ir {_fmt_number(intensity_value, 1)} kWh/m² gadā, "
            f"kas biroja profilam ir {intensity_label}."
        )

    load_text = (
        f"Novērotais profils atbalsta atļautās slodzes pārskatīšanu no "
        f"{_fmt_number(selected_object['summary']['currentAllowedLoadKw'], 0)} kW uz aptuveni "
        f"{_fmt_number(selected_object['summary']['recommendedAllowedLoadKw'], 0)} kW."
        if load_reduction_kw >= 15
        else "Pašreizējā atļautā slodze jau ir tuvu ieteicamajai drošības rezervei."
    )

    anomaly_count = selected_object["summary"]["anomalyCount"]
    recommendations = [
        {
            "tone": "success" if potential_savings >= 3 else "warning",
            "title": "Pārcel elastīgo slodzi uz lētajām stundām",
            "text": (
                f"Lētākās stundas ir {', '.join(cheap_hours)}, bet dārgākās ir {', '.join(expensive_hours)}. "
                f"Pārbīdot ap {_fmt_number(shiftable_energy, 1)} kWh, iespējamais ietaupījums ir {_fmt_number(potential_savings, 2)} EUR dienā."
            ),
            "metric": f"{_fmt_number(potential_savings, 2)} EUR/dienā",
        },
        {
            "tone": "success" if load_reduction_kw >= 15 else "warning",
            "title": "Optimizē pieslēguma slodzi",
            "text": load_text,
            "metric": f"{_fmt_number(load_reduction_kw, 0)} kW rezerve",
        },
        {
            "tone": "danger" if anomaly_count > 20 else "warning",
            "title": "Iestati anomāliju brīdinājumus",
            "text": (
                f"Vēsturē atrasti {anomaly_count} anomāli patēriņa notikumi. "
                f"Riska stundas visbiežāk ir {', '.join(item['hour'] for item in selected_object['summary']['topPeakHours'][:3])}."
            ),
            "metric": f"{anomaly_count} notikumi",
        },
        {
            "tone": intensity_tone,
            "title": "Precizē ēkas energoefektivitātes modeli",
            "text": intensity_text,
            "metric": f"{_fmt_number(intensity_value, 1)} kWh/m²" if intensity_value is not None else "Trūkst platības",
        },
    ]

    if installed_power_kw > 0:
        recommendations.append(
            {
                "tone": "success"
                if installed_power_kw <= selected_object["summary"]["currentAllowedLoadKw"]
                else "danger",
                "title": "Salīdzini uzstādīto jaudu ar limitu",
                "text": (
                    f"Ievadītais iekārtu parks veido aptuveni {_fmt_number(installed_power_kw, 1)} kW uzstādītās jaudas. "
                    "Šo apjomu vari izmantot, lai plānotu slodzes pārcelšanu pa stundām."
                ),
                "metric": f"{_fmt_number(installed_power_kw, 1)} kW",
            }
        )

    status_chips = [
        {
            "tone": "success" if potential_savings >= 3 else "warning",
            "label": f"Ietaupījuma potenciāls {_fmt_number(potential_savings, 2)} EUR/dienā",
        },
        {
            "tone": "success" if load_reduction_kw >= 15 else "warning",
            "label": f"Slodzes rezerve {_fmt_number(load_reserve_percent, 0)}%",
        },
        {
            "tone": intensity_tone,
            "label": (
                f"Intensitāte {_fmt_number(intensity_value, 1)} kWh/m²"
                if intensity_value is not None
                else "Nav ēkas intensitātes datu"
            ),
        },
    ]

    return {
        "installedPowerKw": round(installed_power_kw, 2),
        "shiftableEnergy": round(shiftable_energy, 2),
        "potentialSavings": _round_currency(potential_savings),
        "loadReductionKw": round(load_reduction_kw, 2),
        "loadReservePercent": round(load_reserve_percent, 1),
        "scenarioText": f"{intensity_text} {load_text}",
        "recommendations": recommendations,
        "statusChips": status_chips,
    }


def _plan_rows(selected_object, tomorrow_prices):
    cheap_set = {item["hour"] for item in tomorrow_prices["cheapestHours"]}
    expensive_set = {item["hour"] for item in tomorrow_prices["expensiveHours"]}
    profile_map = {item["hour"]: item["consumption"] for item in selected_object["hourlyProfile"]}

    rows = []
    for price_item in tomorrow_prices["hourly"]:
        hour = price_item["hour"]
        if hour in cheap_set:
            action = "Ieteicams pārcelt elastīgo patēriņu"
            tone = "success"
        elif hour in expensive_set:
            action = "Izvairīties no izvēles slodzes"
            tone = "danger"
        elif price_item["price"] > tomorrow_prices["averagePrice"]:
            action = "Samazini neobligāto slodzi"
            tone = "warning"
        else:
            action = "Neitrāla stunda"
            tone = "neutral"

        rows.append(
            {
                "hour": hour,
                "consumption": round(profile_map.get(hour, 0), 2),
                "price": round(price_item["price"], 2),
                "action": action,
                "tone": tone,
            }
        )
    return rows


def _build_cards(selected_object, insights):
    summary = selected_object["summary"]
    return [
        {
            "label": "Gada patēriņš",
            "value": round(summary["totalConsumption"], 1),
            "unit": "kWh",
            "note": "Balstīts uz vēsturiskajiem stundas datiem.",
        },
        {
            "label": "Gada izmaksas",
            "value": round(summary["totalCost"], 0),
            "unit": "EUR",
            "note": "Aptuvenās izmaksas pēc vēsturiskajām biržas cenām.",
        },
        {
            "label": "Stundas pīķis",
            "value": round(summary["peakHourlyConsumption"], 1),
            "unit": "kWh",
            "note": f"Atļautā slodze {summary['currentAllowedLoadKw']:.0f} kW.",
        },
        {
            "label": "Ieteicamā slodze",
            "value": round(summary["recommendedAllowedLoadKw"], 0),
            "unit": "kW",
            "note": "Aprēķins no maksimuma un 99. percentiles.",
        },
        {
            "label": "Dienas ietaupījuma potenciāls",
            "value": insights["potentialSavings"],
            "unit": "EUR",
            "note": f"Pārbīdāmais apjoms {insights['shiftableEnergy']:.1f} kWh.",
        },
        {
            "label": "Anomāliju apjoms",
            "value": summary["anomalyCount"],
            "unit": "not.",
            "note": "Nepieciešami automātiski brīdinājumi.",
        },
    ]


def get_bootstrap_data():
    data = load_dataset()
    objects = data["objects"]
    total_consumption = sum(item["summary"]["totalConsumption"] for item in objects)
    total_cost = sum(item["summary"]["totalCost"] for item in objects)
    total_anomalies = sum(item["summary"]["anomalyCount"] for item in objects)

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
        "defaultObjectId": objects[0]["id"] if objects else None,
        "marketPricePeriod": data["marketPricePeriod"],
        "tomorrowPriceDate": data["tomorrowPrices"]["date"],
        "objects": [{"id": item["id"], "name": item["name"]} for item in objects],
        "globalSummary": {
            "objectCount": len(objects),
            "totalConsumption": round(total_consumption, 0),
            "totalCost": round(total_cost, 0),
            "totalAnomalies": total_anomalies,
            "averageTomorrowPrice": round(data["tomorrowPrices"]["averagePrice"], 2),
        },
        "portfolio": portfolio,
    }


def get_dashboard_data(object_id, query_args):
    data = load_dataset()
    selected_object = next((item for item in data["objects"] if item["id"] == object_id), None)
    if selected_object is None:
        raise KeyError(f"Object '{object_id}' not found")

    inputs = {
        "area": _parse_number(query_args.get("area")),
        "equipmentCount": _parse_number(query_args.get("equipmentCount")),
        "equipmentPowerWatts": _parse_number(query_args.get("equipmentPowerWatts")),
    }

    insights = _build_insights(selected_object, inputs, data["tomorrowPrices"])
    portfolio = get_bootstrap_data()["portfolio"]
    rank = next((index + 1 for index, item in enumerate(portfolio) if item["id"] == object_id), None)
    plan_rows = _plan_rows(selected_object, data["tomorrowPrices"])

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
        "cards": _build_cards(selected_object, insights),
        "scenarioSummary": {
            "title": "Scenārija novērtējums",
            "text": insights["scenarioText"],
        },
        "statusChips": insights["statusChips"],
        "priceSignals": {
            "averagePrice": data["tomorrowPrices"]["averagePrice"],
            "cheapestHours": data["tomorrowPrices"]["cheapestHours"],
            "expensiveHours": data["tomorrowPrices"]["expensiveHours"],
        },
        "recommendations": insights["recommendations"],
        "charts": {
            "consumptionHourly": selected_object["hourlyProfile"],
            "priceHourly": data["tomorrowPrices"]["hourly"],
            "dailyTrend": selected_object["last30Days"],
        },
        "planRows": plan_rows,
        "alerts": selected_object["anomalies"][:12],
        "benchmark": {
            "portfolioRank": rank,
            "portfolioSize": len(portfolio),
            "installedPowerKw": insights["installedPowerKw"],
            "loadReductionKw": insights["loadReductionKw"],
            "shiftableEnergy": insights["shiftableEnergy"],
        },
    }
