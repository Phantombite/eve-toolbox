import json
# EVE Toolbox — zentrale Konfiguration
# Status-Flags:
#   ready:       True = produktionsbereit, immer sichtbar
#   dev_ready:   True = in Entwicklung, sichtbar im Entwicklermodus
#   (kein Flag)  False/False = geplant, nur im Testmodus sichtbar

from core import logger as _logger
_log = _logger.get("config")

MODULES = [
    {
        "id":        "assets",
        "name":      "Assets",
        "desc":      "Alle Items aller Chars & Corps",
        "icon":      "package",
        "ready":     False,      # Produktionsbereit
        "dev_ready": False,      # In Entwicklung
        "status":    "geplant",  # "fertig" | "entwicklung" | "geplant"
    },
    {
        "id":        "markt",
        "name":      "Markt",
        "desc":      "Preise, Orders & Handel",
        "icon":      "chart-bar",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "skills",
        "name":      "Skills",
        "desc":      "Skill-Planung offline",
        "icon":      "brain",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "intel",
        "name":      "Intel",
        "desc":      "Echtzeit Systemüberwachung",
        "icon":      "radar",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "pi",
        "name":      "Planetary (PI)",
        "desc":      "Kolonien & Extraktion",
        "icon":      "plant",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "industrie",
        "name":      "Industrie",
        "desc":      "Blueprints & Kalkulation",
        "icon":      "hammer",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "routen",
        "name":      "Routen",
        "desc":      "Sichere Pfade & Planung",
        "icon":      "route",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "wallet",
        "name":      "Wallet",
        "desc":      "ISK, Transaktionen & Journal",
        "icon":      "cash",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
]

# ── Fraktionen ────────────────────────────────────────────────────────────────
# Neue Fraktion hinzufügen: einfach neuen Eintrag hier anfügen.
FACTIONS = {
    "caldari": {
        "name":          "Caldari",
        "category":      "faction",
        "accent":        "#185FA5",
        "border":        "#378ADD",
        "light":         "#E6F1FB",
        "text_on_accent":"#FFFFFF",
        "tab_active":    "#D0E8F8",
        "scrollbar":     "#378ADD",
        "input_focus":   "#185FA5",
        "button_hover":  "#1470BB",
    },
    "amarr": {
        "name":          "Amarr",
        "category":      "faction",
        "accent":        "#BA7517",
        "border":        "#EF9F27",
        "light":         "#FAEEDA",
        "text_on_accent":"#FFFFFF",
        "tab_active":    "#F5DFA8",
        "scrollbar":     "#EF9F27",
        "input_focus":   "#BA7517",
        "button_hover":  "#CF8520",
    },
    "gallente": {
        "name":          "Gallente",
        "category":      "faction",
        "accent":        "#3B6D11",
        "border":        "#639922",
        "light":         "#EAF3DE",
        "text_on_accent":"#FFFFFF",
        "tab_active":    "#C8E6A8",
        "scrollbar":     "#639922",
        "input_focus":   "#3B6D11",
        "button_hover":  "#477D14",
    },
    "minmatar": {
        "name":          "Minmatar",
        "category":      "faction",
        "accent":        "#993C1D",
        "border":        "#D85A30",
        "light":         "#FAECE7",
        "text_on_accent":"#FFFFFF",
        "tab_active":    "#F0C4B4",
        "scrollbar":     "#D85A30",
        "input_focus":   "#993C1D",
        "button_hover":  "#B04522",
    },
    "ore": {
        "name":          "ORE",
        "category":      "corporation",
        "accent":        "#B8860B",
        "border":        "#C9A448",
        "light":         "#F9F5EB",
        "text_on_accent":"#2B1A00",
        "tab_active":    "#EDE0C2",
        "scrollbar":     "#C9A448",
        "input_focus":   "#B8860B",
        "button_hover":  "#BF9223",
    },
    # ── Weitere Fraktionen/Corporations hier hinzufügen ──
}


def get_current_faction_colors() -> tuple[str, str]:
    """
    Liefert (accent, border) der AKTUELL eingestellten Fraktion.

    Sicher nutzbar auch an Stellen, an denen core.settings möglicherweise
    noch nicht geladen ist (z.B. core.crash_handler kann theoretisch ganz
    am Anfang des Programms feuern, bevor Settings existieren). Fällt
    bei JEDEM Problem auf den echten App-Standard zurück (DEFAULTS
    ["faction"] = "amarr"), NIEMALS auf eine Exception — ein Fehler beim
    Ermitteln der Fraktionsfarbe darf nicht dazu führen, dass z.B. der
    Fehler-Dialog selbst nicht angezeigt werden kann.
    """
    faction = "amarr"
    try:
        from core import settings as _cfg
        s = _cfg.load()
        faction = s.get("faction", "amarr")
    except Exception:
        pass
    f = FACTIONS.get(faction, FACTIONS["amarr"])
    return f["accent"], f["border"]

HOME_LAYOUTS = {
    "grid":       "Grid",
    "donut_text": "Donut mit Name",
    "donut_icon": "Donut nur Icons",
}

# Version wird aus version.json geladen — NUR dort ändern!
def _load_version() -> str:
    """
    Liest Version aus version.json.
    Sucht von config.py aus nach oben bis version.json gefunden.
    Funktioniert sowohl im Dev-Modus als auch als EXE.
    """
    import sys
    from pathlib import Path
    search_paths = [
        Path(__file__).resolve().parent.parent.parent / "version.json",       # dev: eve_toolbox/core/ → root
        Path(__file__).resolve().parent.parent.parent.parent / "version.json", # dev nested
        Path(sys.executable).parent / "version.json",                          # EXE: neben exe
        Path(sys.executable).parent.parent / "version.json",                   # EXE: ein Ordner hoch
        Path.cwd() / "version.json",                                            # Aktuelles Verzeichnis
    ]
    for path in search_paths:
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))["version"]
            except Exception as e:
                _log.warning(f"version.json bei {path} gefunden, aber nicht lesbar: {e}")
    _log.error(
        "version.json an keinem der bekannten Pfade gefunden/lesbar — "
        "APP_VERSION fällt auf 0.0.0 zurück."
    )
    return "0.0.0"

APP_VERSION = _load_version()
APP_NAME    = "EVE Toolbox"

DEFAULT_ORDER = [m["id"] for m in MODULES]


def is_module_active(mod: dict, dev_mode: bool = False, test_mode: bool = False) -> bool:
    """
    Liest Status direkt aus config — kein manuelles ready-Flag nötig.

    status="fertig"      → immer aktiv
    status="entwicklung" → aktiv im Dev-Modus
    status="geplant"     → aktiv im Test-Modus (nur wenn Dev aktiv)
    """
    status = mod.get("status", "geplant")
    if status == "fertig":
        return True
    if status == "entwicklung" and dev_mode:
        return True
    if status == "geplant" and dev_mode and test_mode:
        return True
    return False