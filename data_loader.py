"""Data loading, dataset management, and source file selection."""
import json
import subprocess
import sys
from pathlib import Path

from config import DEFAULT_CONSUMPTION_SOURCE


BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "app-data.json"
PRICE_FILE = BASE_DIR / "NP_Cenas_LV.xlsx"
SOURCE_STATE_FILE = BASE_DIR / "data" / "selected-source.json"

_DATA_CACHE = None
_DATA_MTIME = None


def get_available_consumption_sources():
    """List all Excel consumption data files in the workspace."""
    return sorted(
        [
            path
            for path in BASE_DIR.glob("*.xlsx")
            if path.is_file() and path.name != PRICE_FILE.name and not path.name.startswith("~$")
        ],
        key=lambda item: item.name.lower(),
    )


def get_active_consumption_source():
    """Get currently active consumption source file."""
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


def _source_label(path):
    """Generate human-readable label from file name."""
    return path.stem.replace("_", " ")


def get_available_source_options():
    """Get active source and all available sources as dicts."""
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
    """Set active consumption source and invalidate cache."""
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
    """Regenerate JSON dataset if source files are newer or missing."""
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
            timeout=120,
        )


def load_dataset():
    """Load and cache JSON dataset, regenerating if needed."""
    global _DATA_CACHE, _DATA_MTIME

    ensure_dataset()
    current_mtime = DATA_FILE.stat().st_mtime
    if _DATA_CACHE is None or _DATA_MTIME != current_mtime:
        _DATA_CACHE = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        _DATA_MTIME = current_mtime
    return _DATA_CACHE
