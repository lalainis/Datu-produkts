"""AI consultant integration with local Ollama."""
import json
import re
import urllib.error
import urllib.request

from config import (
    LOCAL_AI_BASE_URL,
    LOCAL_AI_ENABLED,
    LOCAL_AI_MODEL,
    LOCAL_AI_TIMEOUT_SECONDS,
    AI_PROMPT_VERSION,
)


_AI_CACHE = {}


def _extract_json_object(raw_text):
    """Extract JSON object from raw text, handling markdown wrapping."""
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
    """Extract summary field from raw AI response."""
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
    """Normalize priority string to a known value."""
    normalized = (value or "").strip().lower()
    if normalized in {"high", "augsta", "augsts", "augsts.", "high priority"}:
        return "augsta"
    if normalized in {"medium", "mid", "vidēja", "videja"}:
        return "vidēja"
    if normalized in {"low", "zema", "zems"}:
        return "zema"
    return "vidēja"


def _normalize_ai_actions(actions):
    """Normalize and validate AI-generated action items."""
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
    """Normalize and validate AI-generated tomorrow plan items."""
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


def _build_ai_prompt(context, simplified=False):
    """Build AI prompt from context dict. Use simplified=True for fallback retry."""
    if simplified:
        return (
            "Enerģijas konsultants. Analizē enerģijas datus un atbild tikai JSON formātā:\n"
            '{"summary":"[1-2 teikumi par galveno ietaupījuma iespēju]", '
            '"priority":"augsta|vidēja|zema", '
            '"actions":[{"title":"...", "reason":"...", "impact":"..."}], '
            '"tomorrowPlan":[{"time":"...", "action":"...", "why":"..."}]}\n'
            f"Dati: {json.dumps(context, ensure_ascii=False)}"
        )
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


def _call_local_ai(prompt, temperature=0.2):
    """Call local Ollama AI service with specified temperature."""
    payload = json.dumps(
        {
            "model": LOCAL_AI_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": temperature,
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


def _call_local_ai_with_retry(context, default_actions, default_tomorrow_plan, default_summary):
    """Call AI with retry logic: progressive simplification and temperature adjustment."""
    retry_configs = [
        {"prompt_fn": lambda: _build_ai_prompt(context, simplified=False), "temperature": 0.2, "attempt": 1},
        {"prompt_fn": lambda: _build_ai_prompt(context, simplified=False), "temperature": 0.1, "attempt": 2},
        {"prompt_fn": lambda: _build_ai_prompt(context, simplified=True), "temperature": 0.1, "attempt": 3},
    ]

    last_error = None
    last_response = None

    for config in retry_configs:
        try:
            prompt = config["prompt_fn"]()
            response = _call_local_ai(prompt, temperature=config["temperature"])
            parsed = _extract_json_object(response.get("response", ""))
            if parsed:
                return {
                    "status": "ready",
                    "parsed": parsed,
                    "raw_response": response,
                    "attempt": config["attempt"],
                }
        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            last_response = response
            continue
        except urllib.error.URLError as e:
            raise e

    # If structured JSON parsing failed, try text extraction fallback
    if last_response:
        raw_text = str((last_response or {}).get("response") or "").strip()
        if raw_text:
            return {
                "status": "partial",
                "raw_text": raw_text,
                "raw_response": last_response,
                "attempt": "fallback_text",
            }

    # All retries exhausted
    return {
        "status": "failed",
        "error": str(last_error),
        "defaults": {
            "actions": default_actions,
            "tomorrowPlan": default_tomorrow_plan,
            "summary": default_summary,
        },
    }


def build_ai_consultant(selected_object, insights, inputs, tomorrow_prices, has_solar, solar_summary, rank, portfolio_size, default_actions, default_tomorrow_plan, default_summary):
    """Build AI consultant response with fallback to defaults if unavailable."""
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

    recommended_hours = [item["hour"] for item in solar_summary.get("recommendedHours", [])[:3]]
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

    try:
        retry_result = _call_local_ai_with_retry(context, default_actions, default_tomorrow_plan, default_summary)

        if retry_result["status"] == "ready":
            # Successfully parsed JSON from AI response
            parsed = retry_result["parsed"]
            result = {
                "status": "ready",
                "provider": "local-ollama",
                "model": LOCAL_AI_MODEL,
                "headline": "AI konsultanta kopsavilkums",
                "summary": str(parsed.get("summary") or "").strip() or default_summary,
                "actions": _normalize_ai_actions(parsed.get("actions")) or default_actions,
                "tomorrowPlan": _normalize_ai_tomorrow_plan(parsed.get("tomorrowPlan")) or default_tomorrow_plan,
                "priority": _normalize_ai_priority(parsed.get("priority")),
            }
        elif retry_result["status"] == "partial":
            # Successfully extracted summary text from partial response
            raw_text = retry_result["raw_text"]
            result = {
                "status": "ready",
                "provider": "local-ollama",
                "model": LOCAL_AI_MODEL,
                "headline": "AI konsultanta kopsavilkums",
                "summary": _extract_summary_text(raw_text) or default_summary,
                "actions": default_actions,
                "tomorrowPlan": default_tomorrow_plan,
                "priority": "vidēja",
            }
        else:
            # All retries exhausted, use defaults
            result = {
                "status": "error",
                "provider": "local-ollama",
                "model": LOCAL_AI_MODEL,
                "headline": "AI konsultants neatbildēja korekti",
                "summary": (
                    "Lokālais AI modelis (pēc 3 mēģinājumiem ar dažādiem parametriem) "
                    "neatgrieza izmantojamu atbildi. Panelis rāda klasiskos aprēķinu ieteikumus."
                ),
                "actions": default_actions,
                "tomorrowPlan": default_tomorrow_plan,
                "priority": "vidēja",
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
