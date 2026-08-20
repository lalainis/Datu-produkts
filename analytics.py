"""Analytics calculations: insights, recommendations, and scenario building."""
import math

from config import (
    CLIENT_PROFILES,
    DEFAULT_SOLAR_PRIORITY_HOURS,
    DEFAULT_SOLAR_SHAPE,
    normalize_client_type,
)


def _parse_number(value):
    """Parse and validate positive numeric values."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0


def _round_currency(value):
    """Round currency to 2 decimal places."""
    return round(value, 2)


def _fmt_number(value, digits=1):
    """Format number with comma as decimal separator."""
    return f"{value:.{digits}f}".replace(".", ",")


def _resolve_solar_priority_hours(solar_data):
    """Get priority hours from solar data or use defaults."""
    hours = [item["hour"] for item in solar_data.get("topExportHours", []) if item.get("hour")]
    return hours[:5] or DEFAULT_SOLAR_PRIORITY_HOURS


def _estimate_solar_window_consumption(hourly_map, solar_hours, solar_capacity_kw):
    """Estimate consumption that SES can cover during priority hours."""
    if solar_capacity_kw <= 0:
        return 0.0
    return round(sum(min(hourly_map.get(hour, 0), solar_capacity_kw) for hour in solar_hours), 2)


def _average_consumption_for_hours(hourly_map, hours):
    """Calculate average consumption for given hours."""
    if not hours:
        return 0.0
    values = [hourly_map.get(hour, 0) for hour in hours]
    return round(sum(values) / len(values), 2)


def _clean_business_summary(text):
    """Clean and normalize business summary text."""
    summary = " ".join((text or "").split())
    replacements = {
        "paterinājums": "patēriņš",
        "paterins": "patēriņš",
        "Sesija": "SES",
        "sesija": "SES",
        "portfela": "portfeļa",
        "aktivizēta": "aktīvs",
        "Elektrosabiedrības": "SES",
        "paspaterinājums": "pašpatēriņš",
        "paspaterins": "pašpatēriņš",
    }
    for source, target in replacements.items():
        summary = summary.replace(source, target)
    return summary[:320]


def _display_object_name(name):
    """Format object name for display."""
    cleaned = str(name or "").strip()
    if cleaned.isupper():
        return cleaned.capitalize()
    return cleaned


def _select_business_summary(candidate, fallback):
    """Select business summary if quality is acceptable, otherwise use fallback."""
    cleaned = _clean_business_summary(candidate)
    low_quality_markers = [
        "enerģijas pārvaldības analīze parāda",
        "energoefektīvuma pārbaude",
        "klienta tipa",
        "BIROJS",
    ]
    if not cleaned:
        return fallback
    if len(cleaned) < 90:
        return fallback
    if any(marker in cleaned for marker in low_quality_markers):
        return fallback
    return cleaned


def _build_default_ai_summary(selected_object, insights, has_solar, recommended_hours):
    """Build default AI summary when AI is unavailable."""
    object_name = _display_object_name(selected_object["name"])
    savings = _fmt_number(insights["potentialSavings"], 1)
    shiftable = _fmt_number(insights["shiftableEnergy"], 0)
    anomaly_count = selected_object["summary"]["anomalyCount"]
    summary = (
        f"{object_name} tuvākā prioritāte ir pārcelt ap {shiftable} kWh elastīgās slodzes uz lētākajām stundām, "
        f"lai sasniegtu aptuveni {savings} EUR dienas ietaupījumu."
    )
    if has_solar and recommended_hours:
        summary += f" SES gadījumā fokusējies uz stundām {', '.join(recommended_hours[:2])}, lai palielinātu pašpatēriņu."
    elif anomaly_count > 20:
        summary += f" Papildu uzmanība jāpievērš {anomaly_count} anomālijām patēriņa profilā."
    return summary[:320]


def _build_default_ai_actions(insights, tomorrow_prices, has_solar, recommended_hours):
    """Build default action recommendations."""
    cheap_hours = [item["hour"] for item in tomorrow_prices["cheapestHours"][:3]]
    expensive_hours = [item["hour"] for item in tomorrow_prices["expensiveHours"][:3]]
    actions = [
        {
            "title": "Pārcel elastīgo slodzi uz lētajām stundām",
            "reason": f"Primāri plāno elastīgos procesus stundās {', '.join(cheap_hours)} un izvairies no {', '.join(expensive_hours)}.",
            "impact": f"{_fmt_number(insights['potentialSavings'], 1)} EUR/dienā",
        },
        {
            "title": "Pārskati pieslēguma jaudas rezervi",
            "reason": f"Aprēķins rāda iespēju samazināt slodzi par aptuveni {_fmt_number(insights['loadReductionKw'], 0)} kW bez būtiska riska.",
            "impact": f"{_fmt_number(insights['loadReductionKw'], 0)} kW",
        },
    ]
    if has_solar and recommended_hours:
        actions.insert(
            1,
            {
                "title": "Palielini SES pašpatēriņu",
                "reason": f"Sinhronizē dienas procesus ar SES stundām {', '.join(recommended_hours[:3])}, lai mazinātu iepirkumu no tīkla.",
                "impact": "SES pašpatēriņš",
            },
        )
    return actions[:3]


def _build_default_tomorrow_plan(tomorrow_prices, has_solar, recommended_hours):
    """Build default tomorrow plan."""
    cheap_hours = [item["hour"] for item in tomorrow_prices["cheapestHours"][:2]]
    expensive_hours = [item["hour"] for item in tomorrow_prices["expensiveHours"][:2]]
    plan = [
        {
            "time": "Rīts",
            "action": "Sagatavo dienas elastīgos procesus",
            "why": f"Jau no rīta saplāno, kuras slodzes pārcelt uz {', '.join(cheap_hours)}.",
        },
        {
            "time": ", ".join(cheap_hours),
            "action": "Palaid pārbīdāmo patēriņu",
            "why": "Šajā logā ir zemākas biržas cenas un labāks izmaksu profils.",
        },
        {
            "time": ", ".join(expensive_hours),
            "action": "Samazini neobligāto slodzi",
            "why": "Šajās stundās jāierobežo neobligātie procesi, lai mazinātu izmaksu pīķi.",
        },
    ]
    if has_solar and recommended_hours:
        plan[1] = {
            "time": ", ".join(recommended_hours[:2]),
            "action": "Sinhronizē slodzi ar SES izstrādi",
            "why": "Dienas vidū var palielināt pašpatēriņu un samazināt tīkla iepirkumu.",
        }
    return plan


def _build_forecast_generation_map(hours, export_map, solar_capacity_kw):
    """Build forecast SES generation map based on capacity and export profile."""
    if solar_capacity_kw <= 0:
        return {hour: 0.0 for hour in hours}

    positive_exports = [value for value in export_map.values() if value > 0]
    if positive_exports:
        peak_export = max(positive_exports)
        return {
            hour: round(solar_capacity_kw * (export_map.get(hour, 0) / peak_export), 2)
            if export_map.get(hour, 0) > 0
            else 0.0
            for hour in hours
        }

    return {
        hour: round(solar_capacity_kw * DEFAULT_SOLAR_SHAPE.get(hour, 0), 2)
        for hour in hours
    }


def build_insights(selected_object, inputs, tomorrow_prices, client_type, has_solar):
    """Build comprehensive insights and recommendations for an object."""
    profile = CLIENT_PROFILES[normalize_client_type(client_type)]
    solar_data = selected_object.get("solar", {})
    installed_power_kw = (
        (inputs["equipmentCount"] * inputs["equipmentPowerWatts"]) / 1000
        if inputs["equipmentCount"] > 0 and inputs["equipmentPowerWatts"] > 0
        else 0
    )
    solar_capacity_kw = inputs["solarCapacityKw"] if has_solar else 0.0

    expensive_hours = [item["hour"] for item in tomorrow_prices["expensiveHours"]]
    cheap_hours = [item["hour"] for item in tomorrow_prices["cheapestHours"]]
    hourly_map = {item["hour"]: item["consumption"] for item in selected_object["hourlyProfile"]}
    solar_priority_hours = _resolve_solar_priority_hours(solar_data)
    top_export_hours = solar_priority_hours[:3]
    solar_window_consumption = _estimate_solar_window_consumption(hourly_map, solar_priority_hours, solar_capacity_kw)
    average_solar_hour_consumption = _average_consumption_for_hours(hourly_map, solar_priority_hours)

    expensive_load = sum(hourly_map.get(hour, 0) for hour in expensive_hours)
    default_flexible_energy = selected_object["summary"]["averageDailyConsumption"] * profile["default_flexible_share"]
    equipment_flexible_energy = installed_power_kw * profile["equipment_flexible_hours"] if installed_power_kw > 0 else 0
    shiftable_energy = min(
        expensive_load * profile["expensive_load_share"],
        max(default_flexible_energy, equipment_flexible_energy),
    )

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
    intensity_text = profile["missing_intensity"]

    if inputs["area"] > 0:
        intensity_value = selected_object["summary"]["totalConsumption"] / inputs["area"]
        low_threshold, high_threshold = profile["intensity_thresholds"]
        if intensity_value < low_threshold:
            intensity_label = "ļoti labs"
            intensity_tone = "success"
        elif intensity_value <= high_threshold:
            intensity_label = "pieņemams"
            intensity_tone = "warning"
        else:
            intensity_label = "paaugstināts"
            intensity_tone = "danger"
        intensity_text = (
            f"Aprēķinātā patēriņa intensitāte ir {_fmt_number(intensity_value, 1)} kWh/m² gadā, "
            f"kas {profile['profile_label']} ir {intensity_label}."
        )

    load_text = (
        f"Novērotais profils atbalsta atļautās slodzes pārskatīšanu no "
        f"{_fmt_number(selected_object['summary']['currentAllowedLoadKw'], 0)} kW uz aptuveni "
        f"{_fmt_number(selected_object['summary']['recommendedAllowedLoadKw'], 0)} kW."
        if load_reduction_kw >= 15
        else f"Pašreizējā atļautā slodze {profile['profile_label']} jau ir tuvu ieteicamajai drošības rezervei."
    )

    anomaly_count = selected_object["summary"]["anomalyCount"]
    solar_text = ""
    solar_capacity_text = ""
    solar_self_use_potential = 0.0
    if has_solar:
        baseline_export = solar_data.get("averageDailyExport", 0)
        solar_self_use_potential = round(min(baseline_export, shiftable_energy), 2) if baseline_export > 0 else 0.0
        if solar_capacity_kw > 0:
            solar_self_use_potential = round(
                min(
                    baseline_export if baseline_export > 0 else solar_window_consumption,
                    max(solar_window_consumption, shiftable_energy),
                ),
                2,
            )
            solar_capacity_text = (
                f" Ievadītā SES jauda {_fmt_number(solar_capacity_kw, 1)} kW tipiskajās saules stundās "
                f"ļauj nosegt līdz {_fmt_number(solar_window_consumption, 1)} kWh/dienā no objekta patēriņa."
            )
            if solar_capacity_kw > average_solar_hour_consumption * 1.15:
                solar_capacity_text += (
                    f" Dienas vidus vidējais patēriņš ir tikai {_fmt_number(average_solar_hour_consumption, 1)} kWh/h, "
                    "tāpēc bez papildu slodzes pārcelšanas daļa izstrādes, visticamāk, nonāks eksportā."
                )

        if solar_data.get("totalExport", 0) > 0:
            solar_text = (
                f" Objektā redzama SES ģenerācija ar aptuveni {_fmt_number(solar_data['averageDailyExport'], 1)} kWh eksporta dienā; "
                f"vērtīgākās pašpatēriņa stundas ir {', '.join(top_export_hours or ['11:00', '12:00', '13:00'])}."
            )
        else:
            solar_text = " Objektam ir norādīts SES profils, tāpēc ieteikumi prioritizē slodzes pārnešanu uz dienas vidu un pašpatēriņu."
        solar_text = f"{solar_text}{solar_capacity_text}"

    recommendations = [
        {
            "tone": "success" if potential_savings >= 3 else "warning",
            "title": profile["shift_title"],
            "text": (
                f"Lētākās stundas ir {', '.join(cheap_hours)}, bet dārgākās ir {', '.join(expensive_hours)}. "
                f"Pārbīdot ap {_fmt_number(shiftable_energy, 1)} kWh, iespējamais ietaupījums ir {_fmt_number(potential_savings, 2)} EUR dienā. "
                f"{profile['shift_hint']}{solar_text}"
            ),
            "metric": f"{_fmt_number(potential_savings, 2)} EUR/dienā",
        },
        {
            "tone": "success" if load_reduction_kw >= 15 else "warning",
            "title": profile["load_title"],
            "text": f"{load_text} {profile['load_hint']}",
            "metric": f"{_fmt_number(load_reduction_kw, 0)} kW rezerve",
        },
        {
            "tone": "danger" if anomaly_count > 20 else "warning",
            "title": profile["alert_title"],
            "text": (
                f"Vēsturē atrasti {anomaly_count} anomāli patēriņa notikumi. "
                f"Riska stundas visbiežāk ir {', '.join(item['hour'] for item in selected_object['summary']['topPeakHours'][:3])}."
            ),
            "metric": f"{anomaly_count} notikumi",
        },
        {
            "tone": intensity_tone,
            "title": profile["model_title"],
            "text": intensity_text,
            "metric": f"{_fmt_number(intensity_value, 1)} kWh/m²" if intensity_value is not None else "Trūkst platības",
        },
    ]

    if has_solar:
        solar_metric = (
            f"{_fmt_number(solar_data.get('averageDailyExport', 0), 1)} kWh/dienā"
            if solar_data.get("averageDailyExport", 0) > 0
            else "SES profils aktīvs"
        )
        recommendations.append(
            {
                "tone": "success",
                "title": "Palielini SES pašpatēriņu",
                "text": (
                    f"Plāno elastīgās slodzes dienas vidū un sinhronizē tās ar stundām {', '.join(top_export_hours or ['11:00', '12:00', '13:00'])}. "
                    "Tas samazina nodošanu tīklā un palīdz izmantot paša saražoto enerģiju objektā."
                ),
                "metric": solar_metric,
            }
        )
        if solar_capacity_kw > 0:
            recommendations.append(
                {
                    "tone": "warning" if solar_capacity_kw > average_solar_hour_consumption * 1.15 else "success",
                    "title": "Salāgo SES jaudu ar dienas patēriņu",
                    "text": (
                        f"Ievadītā SES jauda {_fmt_number(solar_capacity_kw, 1)} kW stundās {', '.join(top_export_hours or DEFAULT_SOLAR_PRIORITY_HOURS[:3])} "
                        f"var nosegt līdz {_fmt_number(solar_window_consumption, 1)} kWh/dienā no tipiskā patēriņa. "
                        f"Prioritizē elastīgās slodzes šajās stundās, lai izmantotu ap {_fmt_number(solar_self_use_potential, 1)} kWh/dienā uz vietas."
                    ),
                    "metric": f"{_fmt_number(solar_capacity_kw, 1)} kW SES",
                }
            )

    if installed_power_kw > 0:
        recommendations.append(
            {
                "tone": "success"
                if installed_power_kw <= selected_object["summary"]["currentAllowedLoadKw"]
                else "danger",
                "title": "Salīdzini uzstādīto jaudu ar limitu",
                "text": (
                    f"Ievadītais iekārtu parks veido aptuveni {_fmt_number(installed_power_kw, 1)} kW uzstādītās jaudas. "
                    f"{profile['installed_power_text']}"
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
    if has_solar:
        status_chips.append(
            {
                "tone": "success",
                "label": (
                    f"SES jauda {_fmt_number(solar_capacity_kw, 1)} kW"
                    if solar_capacity_kw > 0
                    else (
                        f"SES eksports {_fmt_number(solar_data.get('averageDailyExport', 0), 1)} kWh/dienā"
                        if solar_data.get("averageDailyExport", 0) > 0
                        else "SES profils ieslēgts"
                    )
                ),
            }
        )

    return {
        "installedPowerKw": round(installed_power_kw, 2),
        "solarCapacityKw": round(solar_capacity_kw, 2),
        "solarWindowConsumptionKwh": round(solar_window_consumption, 2),
        "solarSelfUsePotentialKwh": round(solar_self_use_potential, 2),
        "solarPriorityHours": solar_priority_hours,
        "averageSolarHourConsumption": round(average_solar_hour_consumption, 2),
        "shiftableEnergy": round(shiftable_energy, 2),
        "potentialSavings": _round_currency(potential_savings),
        "loadReductionKw": round(load_reduction_kw, 2),
        "loadReservePercent": round(load_reserve_percent, 1),
        "scenarioText": f"{intensity_text} {load_text}{solar_text}",
        "recommendations": recommendations,
        "statusChips": status_chips,
        "clientTypeLabel": profile["label"],
        "hasSolar": has_solar,
    }


def build_plan_rows(selected_object, tomorrow_prices, fixed_price_eur_mwh=None):
    """Build hourly action plan rows."""
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

        consumption = profile_map.get(hour, 0)
        row = {
            "hour": hour,
            "consumption": round(consumption, 2),
            "price": round(price_item["price"], 2),
            "action": action,
            "tone": tone,
        }
        if fixed_price_eur_mwh:
            row["fixedCost"] = round(consumption * fixed_price_eur_mwh / 1000, 4)
            row["marketCost"] = round(consumption * price_item["price"] / 1000, 4)
        rows.append(row)
    return rows


def build_price_comparison(selected_object, tomorrow_prices, fixed_price_eur_mwh):
    """Compare tomorrow's total cost at fixed price vs market (SPOT) price."""
    if not fixed_price_eur_mwh:
        return None

    profile_map = {item["hour"]: item["consumption"] for item in selected_object["hourlyProfile"]}
    price_map = {item["hour"]: item["price"] for item in tomorrow_prices["hourly"]}

    market_cost = sum(
        profile_map.get(hour, 0) * price / 1000
        for hour, price in price_map.items()
    )
    total_consumption = sum(profile_map.get(hour, 0) for hour in price_map)
    fixed_cost = total_consumption * fixed_price_eur_mwh / 1000

    return {
        "date": tomorrow_prices["date"],
        "marketCostEur": round(market_cost, 2),
        "fixedCostEur": round(fixed_cost, 2),
        "fixedPriceEurMwh": round(fixed_price_eur_mwh, 2),
        "fixedPriceEurKwh": round(fixed_price_eur_mwh / 1000, 4),
        "totalConsumptionKwh": round(total_consumption, 1),
        "savingsEur": round(market_cost - fixed_cost, 2),
    }


def build_cards(selected_object, insights):
    """Build KPI card summary."""
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


def build_solar_summary(selected_object, insights, has_solar):
    """Build SES-specific summary and chart data."""
    solar_data = selected_object.get("solar", {})
    export_profile = selected_object.get("exportHourlyProfile", [])
    export_map = {item["hour"]: item["export"] for item in export_profile}
    consumption_map = {item["hour"]: item["consumption"] for item in selected_object["hourlyProfile"]}
    hours = sorted(set(consumption_map) | set(export_map))
    solar_priority_hours = set(insights.get("solarPriorityHours", DEFAULT_SOLAR_PRIORITY_HOURS))
    solar_capacity_kw = insights.get("solarCapacityKw", 0)
    forecast_generation_map = _build_forecast_generation_map(hours, export_map, solar_capacity_kw)
    overlap_rows = [
        {
            "hour": hour,
            "consumption": round(consumption_map.get(hour, 0), 2),
            "export": round(export_map.get(hour, 0), 2),
            "forecastGeneration": round(forecast_generation_map.get(hour, 0), 2),
            "selfUsePotential": round(min(export_map.get(hour, 0), consumption_map.get(hour, 0)), 2),
            "capacityUsePotential": (
                round(min(consumption_map.get(hour, 0), forecast_generation_map.get(hour, 0)), 2)
                if solar_capacity_kw > 0 and hour in solar_priority_hours
                else 0.0
            ),
        }
        for hour in hours
    ]
    for item in overlap_rows:
        item["recommendedSelfUsePotential"] = round(
            min(item["consumption"], max(item["selfUsePotential"], item["capacityUsePotential"])),
            2,
        )
    top_self_use_hours = [
        item
        for item in sorted(overlap_rows, key=lambda row: row["recommendedSelfUsePotential"], reverse=True)[:3]
        if item["recommendedSelfUsePotential"] > 0
    ]
    self_use_potential = insights.get("solarSelfUsePotentialKwh", 0) if has_solar else 0

    return {
        "cards": [
            {
                "label": "Ievadītā SES jauda",
                "value": round(solar_capacity_kw, 1),
                "unit": "kW",
                "note": (
                    "Izmantota, lai precizētu pašpatēriņa ieteikumus."
                    if solar_capacity_kw > 0
                    else "Ievadi SES jaudu, lai ieteikumi balstītos arī uz uzstādīto jaudu."
                ),
            },
            {
                "label": "Vidējais SES eksports",
                "value": round(solar_data.get("averageDailyExport", 0), 1),
                "unit": "kWh/dienā",
                "note": "Cik enerģijas vidēji tiek nodots tīklā.",
            },
            {
                "label": "Pašpatēriņa potenciāls",
                "value": self_use_potential,
                "unit": "kWh/dienā",
                "note": (
                    "Aptuvenais apjoms, ko varētu novirzīt no eksporta uz iekšējo patēriņu."
                    if solar_data.get("averageDailyExport", 0) > 0
                    else "Aprēķins balstīts uz ievadīto SES jaudu un dienas vidus patēriņa profilu."
                ),
            },
            {
                "label": "Ieteicamās SES stundas",
                "value": len(top_self_use_hours),
                "unit": "st.",
                "note": ", ".join(item["hour"] for item in top_self_use_hours) if top_self_use_hours else "Nav noteiktas",
            },
        ],
        "recommendedHours": top_self_use_hours,
        "chart": {
            "items": overlap_rows,
            "secondaryValueKey": "forecastGeneration" if solar_capacity_kw > 0 else "export",
            "secondaryLabel": "Prognozētā SES izstrāde" if solar_capacity_kw > 0 else "SES eksports",
            "emptyMessage": (
                "Prognozētajai SES izstrādei nav pieejamu stundu datu."
                if solar_capacity_kw > 0
                else "SES eksportam nav pieejamu stundu datu."
            ),
        },
    }
