"""Configuration: client profiles, constants, and environment settings."""
import os
import math


# Client profiles and business logic templates
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

DEFAULT_CONSUMPTION_SOURCE = "ofisu komplekss.xlsx"

# AI configuration from environment
LOCAL_AI_BASE_URL = os.getenv("LOCAL_AI_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
LOCAL_AI_MODEL = os.getenv("LOCAL_AI_MODEL", "llama3.1:8b")
LOCAL_AI_TIMEOUT_SECONDS_RAW = os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "180")
LOCAL_AI_ENABLED = os.getenv("LOCAL_AI_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
AI_PROMPT_VERSION = "v2-business-lv"

# Compute AI timeout
def _parse_number(value):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) and parsed > 0 else 0.0

LOCAL_AI_TIMEOUT_SECONDS = max(_parse_number(LOCAL_AI_TIMEOUT_SECONDS_RAW), 1.0)


def normalize_client_type(value):
    """Normalize client type to a known profile or default to 'office'."""
    if value in CLIENT_PROFILES:
        return value
    return "office"


def normalize_solar_setting(value, fallback=False):
    """Normalize solar flag from string or boolean."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"yes", "true", "1"}:
            return True
        if normalized in {"no", "false", "0"}:
            return False
    return bool(fallback)
