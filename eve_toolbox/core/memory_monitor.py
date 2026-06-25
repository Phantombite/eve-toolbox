"""
Periodische Beobachtung der echten Gesamt-RAM-Nutzung des Prozesses (RSS
— "Resident Set Size", der tatsächlich belegte physische Speicher).

Läuft unabhängig vom Größen-Logging in core.esi_cache: der Cache zeigt
NUR, was WIR selbst absichtlich im Cache halten — dieser Monitor zeigt
die ehrliche Gesamtsumme (Qt, Python-Interpreter, entschlüsselte Vault-
Sitzung, Cache, wirklich alles), unabhängig davon, wodurch sie zustande
kommt. Beide Log-Quellen ergänzen sich: der Cache zeigt das "Was",
dieser Monitor die ehrliche Summe als Kontrollwert.

Cross-Plattform über psutil (Windows/Linux/macOS identisch behandelt) —
bewusst KEINE eigene, plattformspezifische Logik, da das Programm auf
allen drei Plattformen laufen soll.
"""
from typing import Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    _PSUTIL_AVAILABLE = False

from PyQt6.QtCore import QTimer

from core import logger as _logger
_log = _logger.get("memory_monitor")

_timer: Optional[QTimer] = None
_process = None  # erst in start() erzeugt, nur falls psutil verfügbar ist

DEFAULT_INTERVAL_MINUTES = 5.0


def start(interval_minutes: float = DEFAULT_INTERVAL_MINUTES) -> None:
    """
    Startet die periodische Protokollierung. Muss aus dem Haupt-Thread
    heraus aufgerufen werden (QTimer-Anforderung) — idealerweise einmal,
    direkt nachdem das Hauptfenster sichtbar ist. Mehrfacher Aufruf ist
    sicher (zweiter Aufruf wird ignoriert, kein doppelter Timer).

    Fehlt psutil (z.B. nicht installiert), wird die Beobachtung einfach
    deaktiviert — eine fehlende, rein optionale Beobachtungs-Abhängigkeit
    darf niemals den Start des restlichen Programms stören oder den
    globalen Exception-Hook auslösen.
    """
    global _timer, _process
    if not _PSUTIL_AVAILABLE:
        _log.warning(
            "psutil ist nicht installiert — RAM-Beobachtung deaktiviert "
            "(kein Einfluss auf den Rest des Programms). Installieren mit: "
            "pip install psutil"
        )
        return
    if _timer is not None:
        return
    _process = psutil.Process()
    _log_once()  # sofortiger erster Eintrag als Referenzpunkt
    _timer = QTimer()
    _timer.setInterval(int(interval_minutes * 60 * 1000))
    _timer.timeout.connect(_log_once)
    _timer.start()
    _log.debug(f"RAM-Beobachtung gestartet (alle {interval_minutes:.0f} Minuten)")


def stop() -> None:
    """Stoppt die periodische Protokollierung, falls aktiv."""
    global _timer
    if _timer is not None:
        _timer.stop()
        _timer = None


def _log_once() -> None:
    if _process is None:
        return
    try:
        rss_mb = _process.memory_info().rss / (1024 * 1024)
        _log.info(f"Gesamt-RAM-Nutzung des Prozesses (RSS): {rss_mb:.1f} MB")
    except Exception as e:
        _log.warning(f"RAM-Nutzung konnte nicht ermittelt werden: {e}")