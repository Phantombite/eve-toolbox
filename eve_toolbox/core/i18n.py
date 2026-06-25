"""
Übersetzungssystem — lädt Sprachdateien und gibt Texte zurück.
Nutzung:
    from core.i18n import t
    label = t("settings.title")          # "Einstellungen" oder "Settings"
    label = t("splash.update_found", version="0.5.0")  # mit Platzhalter
"""
import json
from pathlib import Path

from core import logger as _logger
_log = _logger.get("i18n")

# Sucht i18n Ordner an mehreren möglichen Stellen
def _find_lang_dir() -> Path:
    import sys
    candidates = [
        Path(__file__).resolve().parent.parent / "i18n",           # normal: core/../i18n
        Path(sys.executable).parent / "_internal" / "i18n",        # PyInstaller EXE
        Path(sys.executable).parent / "i18n",                      # EXE Ordner
        Path(__file__).resolve().parent.parent.parent / "i18n",    # ein Ordner höher
    ]
    for c in candidates:
        if c.exists() and list(c.glob("*.json")):
            return c
    # Fallback: erstellen
    fallback = Path(__file__).resolve().parent.parent / "i18n"
    fallback.mkdir(exist_ok=True)
    return fallback

_LANG_DIR = _find_lang_dir()
_DEFAULT   = "de"
_cache:  dict = {}
_lang:   str  = _DEFAULT


def set_language(code: str) -> None:
    """Setzt die aktive Sprache. Lädt Sprachdatei in Cache."""
    global _lang, _cache
    path = _LANG_DIR / f"{code}.json"
    if not path.exists():
        _log.warning(f"Sprachdatei {code}.json nicht gefunden — falle zurück auf {_DEFAULT}")
        path = _LANG_DIR / f"{_DEFAULT}.json"
        code = _DEFAULT
    try:
        _cache = json.loads(path.read_text(encoding="utf-8"))
        _lang  = code
        _log.debug(f"Sprache gesetzt: {code}")
    except Exception as e:
        _log.error(
            f"Sprachdatei {path.name} konnte nicht geladen werden ({e}) — "
            f"alle Texte zeigen jetzt [key]-Platzhalter statt Übersetzungen."
        )
        _cache = {}
        _lang  = _DEFAULT


def get_language() -> str:
    return _lang


def available_languages() -> list[dict]:
    """Gibt alle verfügbaren Sprachen zurück."""
    langs = []
    for f in sorted(_LANG_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            meta = data.get("_meta", {})
            langs.append({
                "code":     meta.get("code", f.stem),
                "name":     meta.get("language", f.stem),
            })
        except Exception as e:
            _log.warning(f"Sprachdatei {f.name} konnte nicht gelesen werden, wird ignoriert: {e}")
    return langs


def t(key: str, **kwargs) -> str:
    """
    Gibt übersetzten Text zurück.
    key = "section.subsection.key" z.B. "settings.title"
    kwargs = Platzhalter z.B. version="0.5.0" → {version} wird ersetzt
    """
    if not _cache:
        set_language(_DEFAULT)

    # Key traversieren: "settings.title" → _cache["settings"]["title"]
    parts = key.split(".")
    val   = _cache
    try:
        for p in parts:
            val = val[p]
        text = str(val)
    except (KeyError, TypeError):
        # Fallback: Key selbst zurückgeben damit man sieht was fehlt
        text = f"[{key}]"

    # Platzhalter ersetzen: {version} → kwargs["version"]
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, ValueError):
            pass

    return text


# Beim Import direkt laden (Standardsprache Deutsch)
set_language(_DEFAULT)