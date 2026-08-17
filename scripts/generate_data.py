import json
import math
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

import openpyxl


BASE_DIR = Path(__file__).resolve().parent.parent
CONSUMPTION_FILE = BASE_DIR / "ofisu komplekss.xlsx"
PRICE_FILE = BASE_DIR / "NP_Cenas_LV.xlsx"
OUTPUT_FILE = BASE_DIR / "data" / "app-data.json"

INTERVAL_RE = re.compile(r"^\d{2}:\d{2} - \d{2}:\d{2}$")


def round_up(value, step=5):
    return int(math.ceil(value / step) * step)


def percentile(values, ratio):
    if not values:
        return 0
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return values[lower]
    fraction = position - lower
    return values[lower] + (values[upper] - values[lower]) * fraction


def iso_date(value):
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)[:10]


def hour_label(interval_text):
    start = str(interval_text).split("-")[0].strip()
    return f"{start}:00"


def price_hour_label(interval_text):
    start = str(interval_text).split(" - ")[0].strip()
    return f"{start[:2]}:00"


def load_consumption_data():
    workbook = openpyxl.load_workbook(CONSUMPTION_FILE, data_only=True, read_only=True)
    objects = []

    for worksheet in workbook.worksheets:
        rows = worksheet.iter_rows(values_only=True)
        header = next(rows)
        column_count = len(header)
        object_name = None
        dates = []
        consumptions = []
        allowed_values = []
        daily_totals = defaultdict(lambda: {"consumption": 0.0, "cost": 0.0})
        hourly_profile = defaultdict(list)
        anomalies = []

        for row in rows:
            if not row[1]:
                continue

            record_date = iso_date(row[1])
            interval = str(row[2])
            consumption = float(row[3] or 0)
            market_price = float(row[7] or 0) if column_count == 9 else float(row[6] or 0)
            allowed_load = float((row[5] if row[5] is not None else row[4]) or 0) if column_count == 9 else float(row[4] or 0)

            if object_name is None:
                object_name = str(row[0]).split(" (")[0]

            dates.append(record_date)
            consumptions.append(consumption)
            allowed_values.append(allowed_load)

            day_data = daily_totals[record_date]
            day_data["consumption"] += consumption
            day_data["cost"] += (consumption * market_price) / 1000
            hourly_profile[hour_label(interval)].append(consumption)

        sorted_consumptions = sorted(consumptions)
        mean_consumption = sum(consumptions) / len(consumptions)
        variance = sum((value - mean_consumption) ** 2 for value in consumptions) / len(consumptions)
        std_deviation = math.sqrt(variance)
        anomaly_threshold = mean_consumption + 2 * std_deviation
        current_allowed_load = Counter(allowed_values).most_common(1)[0][0]
        recommended_allowed_load = round_up(max(max(consumptions) * 1.05, percentile(sorted_consumptions, 0.99) * 1.1))

        rows = worksheet.iter_rows(min_row=2, values_only=True)
        for row in rows:
            if not row[1]:
                continue
            consumption = float(row[3] or 0)
            interval = str(row[2])
            record_date = iso_date(row[1])
            reasons = []
            if consumption > current_allowed_load:
                reasons.append("Pārsniedz atļauto slodzi")
            elif consumption >= current_allowed_load * 0.9:
                reasons.append("Tuvu atļautajai slodzei")
            if consumption >= anomaly_threshold:
                reasons.append("Anomāli augsts patēriņš")
            if reasons:
                anomalies.append(
                    {
                        "date": record_date,
                        "hour": hour_label(interval),
                        "consumption": round(consumption, 2),
                        "reason": ", ".join(reasons),
                    }
                )

        hourly_profile_items = [
            {
                "hour": hour,
                "consumption": round(sum(values) / len(values), 2),
            }
            for hour, values in sorted(hourly_profile.items())
        ]
        daily_totals_items = [
            {
                "date": date,
                "consumption": round(values["consumption"], 2),
                "cost": round(values["cost"], 2),
            }
            for date, values in sorted(daily_totals.items())
        ]
        total_consumption = round(sum(consumptions), 2)
        total_cost = round(sum(item["cost"] for item in daily_totals_items), 2)

        objects.append(
            {
                "id": worksheet.title,
                "name": object_name or worksheet.title,
                "hourlyProfile": hourly_profile_items,
                "last30Days": daily_totals_items[-30:],
                "anomalies": sorted(anomalies, key=lambda item: item["consumption"], reverse=True)[:20],
                "summary": {
                    "periodStart": min(dates),
                    "periodEnd": max(dates),
                    "totalConsumption": total_consumption,
                    "totalCost": total_cost,
                    "averageHourlyConsumption": round(mean_consumption, 2),
                    "averageDailyConsumption": round(total_consumption / len(daily_totals_items), 2),
                    "peakHourlyConsumption": round(max(consumptions), 2),
                    "currentAllowedLoadKw": round(current_allowed_load, 2),
                    "recommendedAllowedLoadKw": round(recommended_allowed_load, 2),
                    "anomalyCount": len(anomalies),
                    "hoursAboveRecommendedLoad": sum(1 for value in consumptions if value > recommended_allowed_load),
                    "topPeakHours": sorted(hourly_profile_items, key=lambda item: item["consumption"], reverse=True)[:5],
                },
            }
        )

    return objects


def load_price_data():
    workbook = openpyxl.load_workbook(PRICE_FILE, data_only=True, read_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    rows = list(worksheet.iter_rows(values_only=True))
    date_row = rows[5]
    date_columns = []

    for index in range(2, len(date_row)):
        if isinstance(date_row[index], datetime):
            date_columns.append((index, date_row[index].date().isoformat()))

    prices_by_date = {date: [] for _, date in date_columns}

    for row in rows[7:]:
        interval = row[1]
        if not INTERVAL_RE.match(str(interval or "")):
            continue
        for index, date in date_columns:
            price = row[index]
            if price is not None:
                prices_by_date[date].append({"interval": interval, "price": float(price)})

    daily_averages = []
    hourly_by_date = {}
    for date, quarter_hours in prices_by_date.items():
        grouped = defaultdict(list)
        for item in quarter_hours:
            hour = price_hour_label(item["interval"])
            grouped[hour].append(item["price"])
        hourly_items = [
            {"hour": hour, "price": round(sum(values) / len(values), 2)}
            for hour, values in sorted(grouped.items())
        ]
        hourly_by_date[date] = hourly_items
        if hourly_items:
            price_values = [item["price"] for item in hourly_items]
            daily_averages.append(
                {
                    "date": date,
                    "averagePrice": round(sum(price_values) / len(price_values), 2),
                    "minPrice": round(min(price_values), 2),
                    "maxPrice": round(max(price_values), 2),
                }
            )

    latest_date = max(hourly_by_date)
    latest_hourly = hourly_by_date[latest_date]
    cheapest_hours = sorted(latest_hourly, key=lambda item: item["price"])[:3]
    expensive_hours = sorted(latest_hourly, key=lambda item: item["price"], reverse=True)[:3]

    return {
        "marketPricePeriod": {
            "startDate": min(prices_by_date),
            "endDate": max(prices_by_date),
        },
        "tomorrowPrices": {
            "date": latest_date,
            "hourly": latest_hourly,
            "averagePrice": round(sum(item["price"] for item in latest_hourly) / len(latest_hourly), 2),
            "cheapestHours": sorted(cheapest_hours, key=lambda item: item["hour"]),
            "expensiveHours": sorted(expensive_hours, key=lambda item: item["hour"]),
        },
        "priceHistory": daily_averages,
    }


def main():
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    price_data = load_price_data()
    result = {
        "generatedAt": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "marketPricePeriod": price_data["marketPricePeriod"],
        "tomorrowPrices": price_data["tomorrowPrices"],
        "priceHistory": price_data["priceHistory"],
        "objects": load_consumption_data(),
    }
    OUTPUT_FILE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Izveidots {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
