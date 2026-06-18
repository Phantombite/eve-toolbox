"""
EVE Toolbox — Zentrales Logging System.

- Schreibt immer in ~/.eve_toolbox/logs/eve_toolbox.log
- Konsolen-Output nur wenn EVE_TOOLBOX_DEBUG=1 gesetzt ist
- Automatische Rotation: max 3 Dateien à 2MB
- Vorbereitet für Bug-Report Funktion (letzten Log einsenden)
"""
import logging
import logging.handlers
import os
import sys
from pathlib import Path

# ── Log-Verzeichnis ───────────────────────────────────────────
LOG_DIR  = Path.home() / ".eve_toolbox" / "logs"
LOG_FILE = LOG_DIR / "eve_toolbox.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ── Debug-Modus ───────────────────────────────────────────────
DEBUG_MODE = os.environ.get("EVE_TOOLBOX_DEBUG", "0") == "1"

# ── Format ────────────────────────────────────────────────────
FILE_FORMAT    = "%(asctime)s [%(levelname)-8s] %(name)s — %(message)s"
CONSOLE_FORMAT = "[%(asctime)s][%(name)s] %(message)s"
DATE_FORMAT    = "%H:%M:%S"

# ── Root Logger einrichten ────────────────────────────────────
_root = logging.getLogger("EVEToolbox")
_root.setLevel(logging.DEBUG)
_root.handlers.clear()

# Datei-Handler — immer aktiv, rotiert bei 2MB, max 3 Dateien
_file_handler = logging.handlers.RotatingFileHandler(
    LOG_FILE,
    maxBytes=2 * 1024 * 1024,  # 2MB
    backupCount=3,
    encoding="utf-8"
)
_file_handler.setLevel(logging.DEBUG)
_file_handler.setFormatter(logging.Formatter(FILE_FORMAT, DATE_FORMAT))
_root.addHandler(_file_handler)

# Konsolen-Handler — nur im Debug-Modus
if DEBUG_MODE:
    _console_handler = logging.StreamHandler(sys.stdout)
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, DATE_FORMAT))
    _root.addHandler(_console_handler)


def get(name: str) -> logging.Logger:
    """
    Gibt einen benannten Logger zurück.
    Verwendung: log = logger.get(__name__)
    """
    return _root.getChild(name)


def get_log_path() -> Path:
    """Gibt den Pfad zur aktuellen Log-Datei zurück — für Bug-Reports."""
    return LOG_FILE


def get_all_logs() -> str:
    """
    Liest alle Log-Dateien und gibt sie als String zurück.
    Für zukünftige Bug-Report Funktion.
    """
    content = []
    # Neueste zuerst
    for i in range(3, -1, -1):
        if i == 0:
            path = LOG_FILE
        else:
            path = LOG_FILE.with_suffix(f".log.{i}")
        if path.exists():
            try:
                content.append(f"=== {path.name} ===")
                content.append(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                pass
    return "\n".join(content)