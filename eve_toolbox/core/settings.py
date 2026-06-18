"""
Einstellungen — liest und speichert Nutzereinstellungen als JSON.
"""
from core import logger as _logger
_log = _logger.get("settings")

import json
import os
from pathlib import Path

SETTINGS_PATH = Path.home() / ".eve_toolbox" / "settings.json"

DEFAULTS = {
    "faction":           "caldari",
    "home_layout":       "donut_icon",
    "theme":             "dark",
    "language":     "en",
    "dev_mode":     False,
    "test_mode":    False,        # Nur aktiv wenn dev_mode=True
    "font_size":    13,
    "window_width": 1200,
    "window_height":750,
    "module_order": [],
    "edit_locked":       True,
    "first_run":         True,
    "update_on_start":   True,
    "update_auto_install": True,
}


def load() -> dict:
    from core import i18n
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in DEFAULTS.items():
                data.setdefault(k, v)
            # Modi immer beim Start deaktivieren
            data["edit_locked"] = True
            data["dev_mode"]    = False
            data["test_mode"]   = False
            i18n.set_language(data.get("language", "de"))
            return data
        except Exception:
            pass
    i18n.set_language(DEFAULTS.get("language", "de"))
    return dict(DEFAULTS)


def save(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)