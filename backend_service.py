import json
import math
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "app-data.json"
PRICE_FILE = BASE_DIR / "NP_Cenas_LV.xlsx"
SOURCE_STATE_FILE = BASE_DIR / "data" / "selected-source.json"
DEFAULT_CONSUMPTION_SOURCE = "ofisu komplekss.xlsx"
CLIENT_PROFILES = {
    "office": {
        "label": "Ofiss",
        "profile_label": "biroja profilam",
        "intensity_thresholds": (140, 220),
        "default_flexible_share": 0.12,
        "expensive_load_share": 0.30,
        "equipment_flexible_hours": 2.0,
        "shift_title": "Pārcel biroja elastīgo slodzi uz lētajām stundām",
        "shift_hint": "Prioritāte ir ventilācija, dzesēšana, siltumsūkņi un uzlādes punkti.",
        "load_title": "Optimizē pieslēguma slodzi biroja grafikam",
        "load_hint": "Biroja tipa objektā pīķi parasti veido rīta ieslēgšanās un HVAC darba režīmi.",
        "alert_title": "Iestati anomāliju brīdinājumus biroja patēriņam",
        "model_title": "Precizē biroja ēkas energoefektivitātes modeli",
        "missing_intensity": "Pievieno telpu platību un iekārtu parametrus, lai modelis novērtētu biroja energoefektivitāti.",
        "installed_power_text": "Šo apjomu vari izmantot, lai plānotu HVAC, apgaismojuma un citu biroja slodžu pārcelšanu pa stundām.",
    },
    "manufacturing": {
        "label": "Ražotne",
        "profile_label": "ražošanas profilam",
        "intensity_thresholds": (220, 380),
        "default_flexible_share": 0.08,
        "expensive_load_share": 0.18,
        "equipment_flexible_hours": 1.5,
        "shift_title": "Pārcel ražošanas ciklus uz lētākām stundām",
        "shift_hint": "Skaties uz kompresoriem, sūkņiem, akumulācijas procesiem un iekšējo patēriņu, kas var izmantot SES izstrādi.",
        "load_title": "Optimizē pieslēguma slodzi ražotnes režīmam",
        "load_hint": "Ražotnēs ieteikums fokusējas uz maiņu grafiku, iekārtu starta pīķiem un SES pašpatēriņu.",
        "alert_title": "Iestati anomāliju brīdinājumus ražošanas procesiem",
        "model_title": "Precizē ražotnes energoefektivitātes modeli",
        "missing_intensity": "Pievieno telpu platību un galveno iekārtu parametrus, lai modelis novērtētu ražotnes energoefektivitāti.",
        "installed_power_text": "Šo apjomu vari izmantot, lai salāgotu ražošanas iekārtu grafiku ar SES izstrādi un lētajām stundām.",
    },
    "retail": {
        "label": "Tirdzniecības centrs",
        "profile_label": "tirdzniecības profilam",
        "intensity_thresholds": (260, 420),
        "default_flexible_share": 0.10,
        "expensive_load_share": 0.22,
        "equipment_flexible_hours": 1.8,
        "shift_title": "Pārbīdi tirdzniecības centra slodzi ārpus dārgākajām stundām",
        "shift_hint": "Lielākais ieguvums parasti ir aukstuma iekārtās, ventilācijā, apgaismojumā un uzkopšanas procesos pēc darba laika.",
        "load_title": "Optimizē pieslēguma slodzi tirdzniecības plūsmai",
        "load_hint": "Tirdzniecības objektiem svarīgi nošķirt klientu pīķa stundas no tehnisko sistēmu darba grafika.",
        "alert_title": "Iestati anomāliju brīdinājumus tirdzniecības patēriņam",
        "model_title": "Precizē tirdzniecības centra energoefektivitātes modeli",
        "missing_intensity": "Pievieno telpu platību un iekārtu parametrus, lai modelis novērtētu tirdzniecības objekta energoefektivitāti.",
        "installed_power_text": "Šo apjomu vari izmantot, lai balansētu aukstuma, ventilācijas un apgaismojuma sistēmu slodzi pa stundām.",
    },
}
SOLAR_OPTIONS = [
    {"value": "yes", "label": "Jā"},
    {"value": "no", "label": "Nē"},
]
DEFAULT_SOLAR_PRIORITY_HOURS = ["10:00", "11:00", "12:00", "13:00", "14:00"]
DEFAULT_SOLAR_SHAPE = {
    "06:00": 0.08,
    "07:00": 0.18,
    "08:00": 0.34,
    "09:00": 0.55,
    "10:00": 0.74,
    "11:00": 0.9,
    "12:00": 1.0,
    "13:00": 0.96,
    "14:00": 0.82,
    "15:00": 0.62,
    "16:00": 0.4,
    "17:00": 0.22,
    "18:00": 0.1,
}
LOCAL_AI_BASE_URL = os.getenv("LOCAL_AI_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
LOCAL_AI_MODEL = os.getenv("LOCAL_AI_MODEL", "llama3.1:8b")
LOCAL_AI_TIMEOUT_SECONDS_RAW = os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "180")
LOCAL_AI_ENABLED = os.getenv("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
AI_PROMPT_VERSION = "v2-business-lv"

_DATA_CACHE = None
_DATA_MTIME = None
_AI_CACHE = {}


def _parse_number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0


LOCAL_AI_TIMEOUT_SECONDS = max(_parse_number(LOCAL_AI_TIMEOUT_SECONDS_RAW), 1.0)


def _round_currency(value):
    return round(value, 2)


def _fmt_number(value, digits=1):
    return f"{value:.{digits}f}".replace(".", ",")


def normalize_client_type(value):
    if value in CLIENT_PROFILES:
        return value
    return "office"


def normalize_solar_setting(value, fallback=False):
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"yes", "true", "1"}:
            return True
        if normalized in {"no", "false", "0"}:
            return False
    return bool(fallback)


def _resolve_solar_priority_hours(solar_data):
    hours = [item["hour"] for item in solar_data.get("topExportHours", []) if item.get("hour")]
    return hours[:5] or DEFAULT_SOLAR_PRIORITY_HOURS


def _estimate_solar_window_consumption(hourly_map, solar_hours, solar_capacity_kw):
    if solar_capacity_kw <= 0:
        return 0.0
    return round(sum(min(hourly_map.get(hour, 0), solar_capacity_kw) for hour in solar_hours), 2)


def _average_consumption_for_hours(hourly_map, hours):
    if not hours:
        return 0.0
    values = [hourly_map.get(hour, 0) for hour in hours]
    return round(sum(values) / len(values), 2)


def _extract_json_object(raw_text):
    stripped = (raw_text or "").strip()
    if not stripped:
        raise ValueError("Empty AI response")

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI response does not contain JSON")

    return json.loads(stripped[start : end + 1])


def _extract_summary_text(raw_text):
    stripped = (raw_text or "").strip()
    if not stripped:
        return ""

    summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"', stripped)
    if summary_match:
        try:
            return json.loads(f'"{summary_match.group(1)}"')
        except json.JSONDecodeError:
            return summary_match.group(1)
    return stripped


def _normalize_ai_priority(value):
    normalized = (value or "").strip().lower()
    if normalized in {"high", "augsta", "augsts", "augsts.", "high priority"}:
        return "augsta"
    if normalized in {"medium", "mid", "vidēja", "videja"}:
        return "vidēja"
    if normalized in {"low", "zema", "zems"}:
        return "zema"
    return "vidēja"


def _normalize_ai_actions(actions):
    normalized_actions = []
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("action") or "").strip()
        reason = str(item.get("reason") or item.get("description") or "").strip()
        if not reason:
            responsibility = str(item.get("responsibility") or "").strip()
            deadline = str(item.get("deadline") or "").strip()
            reason_parts = []
            if responsibility:
                reason_parts.append(f"Atbildīgais: {responsibility}.")
            if deadline:
                reason_parts.append(f"Termiņš: {deadline}.")
            reason = " ".join(reason_parts).strip()
        impact = str(item.get("impact") or item.get("metric") or item.get("priority") or "").strip()
        if not title or not reason:
            continue
        normalized_actions.append(
            {
                "title": title[:120],
                "reason": reason[:320],
                "impact": impact[:80],
            }
        )
        if len(normalized_actions) >= 4:
            break
    return normalized_actions


def _normalize_ai_tomorrow_plan(items):
    normalized_items = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        time = str(item.get("time") or item.get("window") or item.get("timing") or "").strip()
        action = str(item.get("action") or item.get("title") or "").strip()
        why = str(item.get("why") or item.get("reason") or item.get("note") or "").strip()
        if not action:
            continue
        normalized_items.append(
            {
                "time": time[:40],
                "action": action[:120],
                "why": why[:220],
            }
        )
        if len(normalized_items) >= 3:
            break
    return normalized_items


def _clean_business_summary(text):
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
    cleaned = str(name or "").strip()
    if cleaned.isupper():
        return cleaned.capitalize()
    return cleaned


def _select_business_summary(candidate, fallback):
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


def _build_ai_prompt(context):
    return (
        "Tu esi enerģijas pārvaldības AI konsultants Latvijā. "
        "Analizē dotos aprēķinus un sagatavo īsu, biznesisku rekomendāciju tikai no sniegtajiem datiem. "
        "Neizdomā jaunus skaitļus. Ja dati nav pietiekami, to skaidri pasaki. "
        "Atbildi tikai JSON formātā ar struktūru: "
        '{"summary":"...", "priority":"augsta|vidēja|zema", "actions":[{"title":"...", "reason":"...", "impact":"..."}], "tomorrowPlan":[{"time":"...", "action":"...", "why":"..."}]}. '
        "Raksti gludā biznesa latviešu valodā. "
        "Summary lai ir 2 īsi teikumi un ne garāks par 220 rakstzīmēm. "
        "Izveido ne vairāk kā 3 actions un 3 tomorrowPlan ierakstus. "
        f"Dati: {json.dumps(context, ensure_ascii=False)}"
    )


def _call_local_ai(prompt):
    payload = json.dumps(
        {
            "model": LOCAL_AI_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "num_predict": 220,
            },
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{LOCAL_AI_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=LOCAL_AI_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _build_ai_consultant(selected_object, insights, inputs, tomorrow_prices, has_solar, solar_summary, rank, portfolio_size):
    if not LOCAL_AI_ENABLED:
        return {
            "status": "disabled",
            "provider": "local-ollama",
            "model": LOCAL_AI_MODEL,
            "headline": "AI konsultants ir izslēgts",
            "summary": "Lai aktivizētu dinamisku AI konsultantu, iestati LOCAL_AI_ENABLED=1 un palaid lokālu Ollama modeli.",
            "actions": [],
            "priority": "vidēja",
        }

    solar_chart = solar_summary.get("chart", {})
    recommended_hours = [item["hour"] for item in solar_summary.get("recommendedHours", [])[:3]]
    default_summary = _build_default_ai_summary(selected_object, insights, has_solar, recommended_hours)
    default_actions = _build_default_ai_actions(insights, tomorrow_prices, has_solar, recommended_hours)
    default_tomorrow_plan = _build_default_tomorrow_plan(tomorrow_prices, has_solar, recommended_hours)
    context = {
        "prompt_version": AI_PROMPT_VERSION,
        "objekts": f"{selected_object['name']} ({selected_object['id']})",
        "klienta_tips": insights["clientTypeLabel"],
        "portfela_vieta": f"{rank}/{portfolio_size}",
        "gada_paterins_kwh": round(selected_object["summary"]["totalConsumption"], 0),
        "gada_izmaksas_eur": round(selected_object["summary"]["totalCost"], 0),
        "stundas_pikis_kwh": round(selected_object["summary"]["peakHourlyConsumption"], 1),
        "anomālijas": selected_object["summary"]["anomalyCount"],
        "ietaupijums_eur_diena": insights["potentialSavings"],
        "parbidama_slodze_kwh": insights["shiftableEnergy"],
        "slodzes_samazinajums_kw": insights["loadReductionKw"],
        "letakas_stundas": [item["hour"] for item in tomorrow_prices["cheapestHours"][:3]],
        "dargakas_stundas": [item["hour"] for item in tomorrow_prices["expensiveHours"][:3]],
        "ses_aktivs": has_solar,
        "ses_jauda_kw": inputs["solarCapacityKw"],
        "ses_eksports_kwh_diena": round(selected_object.get("solar", {}).get("averageDailyExport", 0), 1),
        "ses_paspaterins_kwh_diena": solar_summary["cards"][2]["value"] if len(solar_summary.get("cards", [])) >= 3 else 0,
        "ses_stundas": recommended_hours,
        "esošie_ieteikumi": [item["title"] for item in insights["recommendations"][:3]],
    }
    cache_key = json.dumps(context, ensure_ascii=False, sort_keys=True)
    cached = _AI_CACHE.get(cache_key)
    if cached is not None:
        return cached

    raw_response = None
    try:
        raw_response = _call_local_ai(_build_ai_prompt(context))
        parsed = _extract_json_object(raw_response.get("response", ""))
        result = {
            "status": "ready",
            "provider": "local-ollama",
            "model": LOCAL_AI_MODEL,
            "headline": "AI konsultanta kopsavilkums",
            "summary": _select_business_summary(str(parsed.get("summary") or "").strip(), default_summary),
            "actions": _normalize_ai_actions(parsed.get("actions")) or default_actions,
            "tomorrowPlan": _normalize_ai_tomorrow_plan(parsed.get("tomorrowPlan")) or default_tomorrow_plan,
            "priority": _normalize_ai_priority(parsed.get("priority")),
        }
    except urllib.error.URLError:
        result = {
            "status": "unavailable",
            "provider": "local-ollama",
            "model": LOCAL_AI_MODEL,
            "headline": "AI konsultants nav pieejams",
            "summary": (
                f"Lai ģenerētu dinamiskus AI ieteikumus, palaid lokālu Ollama servisu uz {LOCAL_AI_BASE_URL} "
                f"ar modeli '{LOCAL_AI_MODEL}'. Šobrīd panelis rāda klasiskos aprēķinu ieteikumus."
            ),
            "actions": default_actions,
            "tomorrowPlan": default_tomorrow_plan,
            "priority": "vidēja",
        }
    except (json.JSONDecodeError, ValueError):
        raw_text = str((raw_response or {}).get("response") or "").strip()
        if raw_text:
            result = {
                "status": "ready",
                "provider": "local-ollama",
                "model": LOCAL_AI_MODEL,
                "headline": "AI konsultanta kopsavilkums",
                "summary": _select_business_summary(_extract_summary_text(raw_text), default_summary),
                "actions": default_actions,
                "tomorrowPlan": default_tomorrow_plan,
                "priority": "vidēja",
            }
        else:
            result = {
                "status": "error",
                "provider": "local-ollama",
                "model": LOCAL_AI_MODEL,
                "headline": "AI konsultants neatbildēja korekti",
                "summary": (
                    "Lokālais AI modelis neatgrieza izmantojamu atbildi JSON formātā. "
                    "Pārbaudi, vai modelis ir ielādēts un spēj atbildēt strukturētā formā."
                ),
                "actions": default_actions,
                "tomorrowPlan": default_tomorrow_plan,
                "priority": "vidēja",
            }
    except TimeoutError:
        result = {
            "status": "unavailable",
            "provider": "local-ollama",
            "model": LOCAL_AI_MODEL,
            "headline": "AI konsultants atbild pārāk ilgi",
            "summary": (
                "Lokālais AI modelis šim datoram atbild pārāk lēni. "
                "Panelis turpina rādīt klasiskos aprēķinu ieteikumus, kamēr AI atbilde nav pieejama laikā."
            ),
            "actions": default_actions,
            "tomorrowPlan": default_tomorrow_plan,
            "priority": "vidēja",
        }

    _AI_CACHE[cache_key] = result
    if len(_AI_CACHE) > 64:
        _AI_CACHE.pop(next(iter(_AI_CACHE)))
    return result


def _build_forecast_generation_map(hours, export_map, solar_capacity_kw):
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


def _source_label(path):
    return path.stem.replace("_", " ")


def get_available_consumption_sources():
    return sorted(
        [
            path
            for path in BASE_DIR.glob("*.xlsx")
            if path.is_file() and path.name != PRICE_FILE.name and not path.name.startswith("~$")
        ],
        key=lambda item: item.name.lower(),
    )


def get_active_consumption_source():
    available_sources = get_available_consumption_sources()
    if not available_sources:
        raise FileNotFoundError("Nav atrasts neviens patēriņa datu Excel fails.")

    selected_name = DEFAULT_CONSUMPTION_SOURCE
    if SOURCE_STATE_FILE.exists():
        try:
            selected_name = json.loads(SOURCE_STATE_FILE.read_text(encoding="utf-8")).get("fileName") or selected_name
        except (json.JSONDecodeError, OSError):
            selected_name = DEFAULT_CONSUMPTION_SOURCE

    for path in available_sources:
        if path.name == selected_name:
            return path

    return next((path for path in available_sources if path.name == DEFAULT_CONSUMPTION_SOURCE), available_sources[0])


def get_available_source_options():
    active_source = get_active_consumption_source()
    return {
        "activeSource": {
            "fileName": active_source.name,
            "label": _source_label(active_source),
        },
        "availableSources": [
            {
                "fileName": path.name,
                "label": _source_label(path),
            }
            for path in get_available_consumption_sources()
        ],
    }


def set_active_consumption_source(file_name):
    available_sources = {path.name: path for path in get_available_consumption_sources()}
    selected_source = available_sources.get(file_name)
    if selected_source is None:
        raise KeyError(f"Source file '{file_name}' not found")

    SOURCE_STATE_FILE.parent.mkdir(exist_ok=True)
    SOURCE_STATE_FILE.write_text(json.dumps({"fileName": selected_source.name}, ensure_ascii=False, indent=2), encoding="utf-8")

    global _DATA_CACHE, _DATA_MTIME
    _DATA_CACHE = None
    _DATA_MTIME = None

    ensure_dataset(force=True)
    return selected_source


def ensure_dataset(force=False):
    active_source = get_active_consumption_source()
    data_missing = not DATA_FILE.exists()
    source_newer = False
    source_changed = False
    source_files = [
        active_source,
        PRICE_FILE,
        BASE_DIR / "scripts" / "generate_data.py",
        SOURCE_STATE_FILE,
    ]

    if not data_missing:
        data_mtime = DATA_FILE.stat().st_mtime
        source_newer = any(path.exists() and path.stat().st_mtime > data_mtime for path in source_files)
        try:
            source_changed = json.loads(DATA_FILE.read_text(encoding="utf-8")).get("sourceFile") != active_source.name
        except (json.JSONDecodeError, OSError):
            source_changed = True

    if force or data_missing or source_newer or source_changed:
        subprocess.run(
            [sys.executable, str(BASE_DIR / "scripts" / "generate_data.py"), "--source", str(active_source)],
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


def _build_insights(selected_object, inputs, tomorrow_prices, client_type, has_solar):
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


def _build_solar_summary(selected_object, insights, has_solar):
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


def get_bootstrap_data():
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
        "clientTypeOptions": [
            {"value": key, "label": value["label"]}
            for key, value in CLIENT_PROFILES.items()
        ],
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


def get_dashboard_data(object_id, query_args):
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

    insights = _build_insights(selected_object, inputs, data["tomorrowPrices"], client_type, has_solar)
    portfolio = get_bootstrap_data()["portfolio"]
    rank = next((index + 1 for index, item in enumerate(portfolio) if item["id"] == object_id), None)
    plan_rows = _plan_rows(selected_object, data["tomorrowPrices"])
    solar_summary = _build_solar_summary(selected_object, insights, has_solar)
    ai_consultant = _build_ai_consultant(
        selected_object,
        insights,
        inputs,
        data["tomorrowPrices"],
        has_solar,
        solar_summary,
        rank,
        len(portfolio),
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
        "cards": _build_cards(selected_object, insights),
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
        "alerts": selected_object["anomalies"][:12],
        "solarSummary": solar_summary,
        "benchmark": {
            "portfolioRank": rank,
            "portfolioSize": len(portfolio),
            "installedPowerKw": insights["installedPowerKw"],
            "loadReductionKw": insights["loadReductionKw"],
            "shiftableEnergy": insights["shiftableEnergy"],
            "solarCapacityKw": insights["solarCapacityKw"],
        },
    }
