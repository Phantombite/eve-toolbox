"""
core/data/sde_common.py — gemeinsame Hilfsfunktionen für alle
sde_to_*_db.py Builder (items, universe, später characters/lore).

Ausgelagert, damit sde_to_items_db.py und sde_to_universe_db.py nicht
sich gegenseitig "private" (mit Unterstrich beginnende) Funktionen
importieren müssen — sauberer, expliziter gemeinsamer Code statt
impliziter Abhängigkeit zwischen zwei eigentlich unabhängigen Modulen.
"""
import json
from pathlib import Path


def read_jsonl(path: Path):
    """Generator: liefert jede Zeile einer .jsonl-Datei als dict.
    Überspringt leere Zeilen (am Dateiende manchmal vorhanden)."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def localized_name(obj: dict, lang: str, fallback_key: str | None = None) -> str:
    """Liest obj['name'][lang], mit robustem Fallback: manche SDE-
    Objekte haben kein 'name'-Feld als Dict (z.B. wenn nur 1 Sprache
    exportiert wurde) oder die gewünschte Sprache fehlt einzeln."""
    name_obj = obj.get("name")
    if isinstance(name_obj, dict):
        if lang in name_obj:
            return name_obj[lang]
        if "en" in name_obj:
            return name_obj["en"]  # Englisch als Fallback für fehlende Übersetzung
    if isinstance(name_obj, str):
        return name_obj
    if fallback_key:
        return f"[{fallback_key}:{obj.get('_key')}]"
    return f"[unnamed:{obj.get('_key')}]"