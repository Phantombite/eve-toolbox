import json
# EVE Toolbox — zentrale Konfiguration
# Status-Flags:
#   ready:       True = produktionsbereit, immer sichtbar
#   dev_ready:   True = in Entwicklung, sichtbar im Entwicklermodus
#   (kein Flag)  False/False = geplant, nur im Testmodus sichtbar

from core import logger as _logger
_log = _logger.get("config")

from core.i18n import t

MODULES = [
    {
        "id":        "assets",
        "icon":      "package",
        "ready":     False,      # Produktionsbereit
        "dev_ready": False,      # In Entwicklung
        "status":    "geplant",  # "fertig" | "entwicklung" | "geplant"
    },
    {
        "id":        "markt",
        "icon":      "chart-bar",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "skills",
        "icon":      "brain",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "intel",
        "icon":      "radar",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "pi",
        "icon":      "plant",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "industrie",
        "icon":      "hammer",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "routen",
        "icon":      "route",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
    {
        "id":        "wallet",
        "icon":      "cash",
        "ready":     False,
        "dev_ready": False,
        "status":    "geplant",
    },
]


def get_module_name(mod_id: str) -> str:
    """Übersetzter Anzeigename eines Hauptmoduls. Einzige Quelle:
    i18n-Sprachdateien (modules.<id>.name) — MODULES selbst trägt nur
    die ID, damit Namen ausschließlich in de.json/en.json gepflegt
    werden müssen, nicht zusätzlich im Code."""
    return t(f"modules.{mod_id}.name")


def get_module_desc(mod_id: str) -> str:
    """Übersetzte Kurzbeschreibung eines Hauptmoduls (modules.<id>.desc),
    siehe get_module_name für das Prinzip."""
    return t(f"modules.{mod_id}.desc")

# ── Modul-Unterfunktionen (Außenring) ──────────────────────────────────────────
# Pro Hauptmodul-ID eine Liste von Unterfunktionen, Slot 0 = erster Eintrag,
# Slot 1 = zweiter, usw. Module ohne (weiteren) Eintrag hier zeigen an den
# übrigen Positionen einen Außenring aus leeren Slots — siehe
# DonutWidget.paintEvent. User-Anpassung (Slot-Tausch per Drag & Drop) wird
# PRO MODUL gespeichert (nicht pro Ring-Position), damit eine Umsortierung
# der Hauptkategorien die Unterfunktions-Zuordnung automatisch mitnimmt —
# die Ausrichtung/Geometrie des Rings folgt dagegen der aktuellen Slot-
# Position der Hauptkategorie.
#
# Bewusst LEER — die testweise eingefügten Placeholder-Einträge (1:1-Ersatz
# der alten Hauptkategorie-Seiten, plus zusätzliche Test-Slots zum Prüfen
# der Ausbreitungsanimation) wurden entfernt, nachdem der Außenring-
# Mechanismus und die Animation fertig getestet waren. Echte Unterfunktionen
# werden hier ergänzt, sobald sie eigene UI-Seiten haben (siehe
# ui/main_window.py:_open_subfunction).
MODULE_SUBFUNCTIONS = {}

# Anzahl der Unterfunktions-Slots pro Hauptmodul — gilt layoutübergreifend
# für JEDES Home-Layout (Donut-Außenring hat 16 Winkel-Slots, Grid-Karten-
# rückseite hat ein 4×4-Raster = ebenfalls 16). Eine einzige Zahl, damit
# beide Layouts garantiert dieselbe Slot-Anzahl verwenden.
SUB_SLOT_COUNT = 16


def get_full_sub_slot_perm(settings: dict, module_id: str,
                            n_slots: int = SUB_SLOT_COUNT) -> list:
    """Liefert die aktuell gespeicherte Slot-Belegung eines Moduls als
    volle Liste der Länge n_slots, bestehend aus Basis-Indizes (Position
    in MODULE_SUBFUNCTIONS[module_id]) oder -1 für einen leeren Slot.
    -1 ist ein EXPLIZITER Marker (nicht einfach eine Lücke in einer
    kürzeren Liste) — das ist wichtig, damit die absolute Slot-Position
    einer Unterfunktion erhalten bleibt, auch wenn vor ihr nur leere
    Slots liegen (ein simples Herausfiltern der Lücken würde sie beim
    nächsten Laden wieder nach vorne rutschen lassen).

    Bereinigt dabei ungültige/doppelte gespeicherte Werte (z.B. nach
    Entfernen einer Unterfunktion aus MODULE_SUBFUNCTIONS im Code) und
    hängt neue, noch nicht zugeordnete Basis-Indizes an die erste freie
    Position an, statt sie zu verwerfen.

    EINZIGE Quelle für diese Logik — sowohl Donut (DonutWidget, Ring-
    Darstellung) als auch Grid (ModuleCard, Flip-Kartenrückseite) lesen
    und schreiben über diese Funktion, damit beide Layouts garantiert
    dieselbe Slot-Zuordnung zeigen (settings['sub_order'] ist bewusst
    geteilt, nicht pro Layout getrennt) — nur WIE ein Slot gezeichnet
    wird (Geometrie, Animation) bleibt layoutspezifisch."""
    base = MODULE_SUBFUNCTIONS.get(module_id, [])
    stored = settings.get("sub_order", {}).get(module_id, [])
    seen = set()
    slots = [-1] * n_slots
    for slot_idx, bi in enumerate(stored):
        if slot_idx >= n_slots:
            break
        if isinstance(bi, int) and 0 <= bi < len(base) and bi not in seen:
            slots[slot_idx] = bi
            seen.add(bi)
    for bi in range(len(base)):
        if bi not in seen:
            free = next((k for k in range(n_slots) if slots[k] == -1), None)
            if free is not None:
                slots[free] = bi
                seen.add(bi)
    return slots


def get_ordered_subfunctions(settings: dict, module_id: str,
                              n_slots: int = SUB_SLOT_COUNT) -> list:
    """Unterfunktionen-Slots eines Hauptmoduls in gespeicherter Reihen-
    folge — liefert IMMER genau n_slots Einträge zurück, jeder Eintrag
    ist entweder das echte, übersetzte Sub-Objekt (siehe get_subfunction)
    oder None (unbelegter Slot). So lässt sich jede Position mit jeder
    anderen tauschen — auch leer↔belegt — OHNE Phantom-Objekte zu
    erzeugen, die irgendwo fälschlich als echtes Modul behandelt werden
    könnten (Navigation/Klick-Erkennung prüfen weiterhin nur auf "ist
    der Eintrag an dieser Position nicht None"). Siehe
    get_full_sub_slot_perm für das Prinzip der geteilten Datenquelle."""
    base = MODULE_SUBFUNCTIONS.get(module_id, [])
    perm = get_full_sub_slot_perm(settings, module_id, n_slots)
    return [get_subfunction(module_id, base[bi]["id"]) if bi >= 0 else None
            for bi in perm]


def swap_subfunctions(settings: dict, module_id: str, src_slot: int, dst_slot: int,
                       n_slots: int = SUB_SLOT_COUNT) -> bool:
    """Tauscht zwei Unterfunktions-SLOTS (per Index, nicht ID) innerhalb
    EINES Hauptmoduls — auch leer↔belegt ist gültig, da jede Position
    als Tauschpartner zählt, nicht nur belegte. Speichert die neue
    Reihenfolge als VOLLSTÄNDIGE Liste über alle Slots
    (settings['sub_order'][module_id]), mit -1 als explizitem Leer-
    Marker für unbelegte Positionen — wichtig: die absolute Slot-
    Position einer Unterfunktion muss erhalten bleiben, auch wenn vor
    ihr nur leere Slots liegen.

    Schreibt NUR in `settings` (kein Speichern auf Platte, kein UI-
    Update) — das bleibt Sache des Aufrufers (siehe HomeDonut.
    swap_subfunctions / ModuleCard für die jeweiligen layoutspezifischen
    Wrapper, die zusätzlich cfg.save() und ein Repaint auslösen).
    Geteilt zwischen Donut und Grid, damit beide garantiert dieselbe
    Tausch-Logik verwenden. Gibt True zurück bei erfolgreichem Tausch,
    False bei ungültigen Indizes (nichts wurde verändert)."""
    if not (0 <= src_slot < n_slots) or not (0 <= dst_slot < n_slots):
        return False
    slots = get_full_sub_slot_perm(settings, module_id, n_slots)
    slots[src_slot], slots[dst_slot] = slots[dst_slot], slots[src_slot]
    sub_order = settings.setdefault("sub_order", {})
    sub_order[module_id] = slots
    return True


def get_subfunction(module_id: str, sub_id: str) -> dict | None:
    """Liefert den Unterfunktions-Eintrag für ein Hauptmodul + Unter-
    funktions-ID, oder None falls nicht vorhanden. Das zurückgegebene
    Dict enthält weiterhin 'id' und 'name' (Aufrufer ändern sich
    dadurch nicht) — 'name' wird aber live aus den i18n-Sprachdateien
    übersetzt (modules.<module_id>.sub.<sub_id>), MODULE_SUBFUNCTIONS
    selbst trägt nur noch die ID. Zentrale Stelle, damit ui/home_donut.py
    und ui/main_window.py nicht jeweils selbst übersetzen müssen."""
    for entry in MODULE_SUBFUNCTIONS.get(module_id, []):
        if entry.get("id") == sub_id:
            return {**entry, "name": t(f"modules.{module_id}.sub.{sub_id}")}
    return None

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
    "grid":       "settings.layout_grid",
    "donut_icon": "settings.layout_donut",
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