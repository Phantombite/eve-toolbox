"""
Generischer RAM-Cache mit Frische-Steuerung.

Gedacht für ESI-Daten, die von mehreren Modulen/Fenstern gleichzeitig
gebraucht werden (z.B. Marktpreise: 4 offene Marktfenster + Industrie +
Assets sollen sich denselben frischen Wert teilen, statt jeder einzeln bei
ESI anzufragen). Lebt ausschließlich im RAM (ein einfaches dict) — wird
NIE auf die Platte geschrieben und ist beim Beenden des Programms
automatisch weg, ganz ohne eigenen Aufräum-Code.

Größen-Beobachtung statt Verdrängung: Jede Änderung loggt (gesammelt, mit
kurzer Verzögerung — siehe _schedule_size_log) die aktuelle Gesamtgröße.
Es gibt BEWUSST keine automatische Verdrängung/Obergrenze — die reale
Größenentwicklung ist erst nach den ersten echten Modulen (Markt, Assets)
bekannt. Erst beobachten, dann ggf. begrenzen, falls die Zahlen das
nahelegen — nicht vorher gegen ein Problem bauen, das noch nicht
beobachtet wurde.

Locking-Design: ein schneller, kurz gehaltener Lock für reine dict-
Strukturzugriffe (_struct_lock), plus ein EIGENER Lock pro Cache-Key für
get_or_fetch()'s Netzwerk-Aufruf. Das verhindert zwei Probleme gleichzeitig:
  - "Thundering Herd": mehrere gleichzeitige Anfragen für DENSELBEN
    abgelaufenen Key lösen nicht mehrfach denselben teuren ESI-Call aus
    (nur der erste Anfrager fragt wirklich nach, die anderen warten kurz
    und bekommen danach denselben frischen Wert).
  - Unnötige Blockierung zwischen UNTERSCHIEDLICHEN Keys: ein Modul, das
    auf Marktpreise wartet, blockiert dabei nicht ein anderes Modul, das
    gleichzeitig auf z.B. Skill-Daten wartet — die haben unterschiedliche
    Keys und damit unterschiedliche, voneinander unabhängige Locks.
"""
import time
import json
import threading
from typing import Callable, Any, Optional

from core import logger as _logger
_log = _logger.get("esi_cache")

_struct_lock: threading.Lock = threading.Lock()
_store: dict[str, tuple[Any, float, int]] = {}  # key -> (value, expires_at, size_bytes)
_key_locks: dict[str, threading.Lock] = {}      # key -> eigener Lock

# ── Beobachtung der Cache-Größe (keine Verdrängung, kein Aufräumen —
# bewusst NICHT gebaut, solange wir nicht wissen, ob es nötig ist. Erst
# beobachten, dann ggf. später entscheiden.) ───────────────────────────
_LOG_DEBOUNCE_SECONDS = 1.5
_log_lock          = threading.Lock()
_log_timer: Optional[threading.Timer] = None
_pending_changed_keys: set[str] = set()


def _estimate_size(value: Any) -> int:
    """Grobe Schätzung der Speichergröße in Bytes. Nicht exakt (echtes
    Pro-Objekt-RAM-Tracking ist in Python aufwendig/unzuverlässig), aber
    korreliert für unsere Datenformen (Listen/Dicts aus ESI-JSON) gut
    genug, um die Größenentwicklung sinnvoll zu beobachten. Wird einmal
    beim Schreiben berechnet, nicht bei jeder Logging-Ausgabe neu."""
    try:
        return len(json.dumps(value))
    except Exception:
        return 1024  # Fallback-Schätzung, falls nicht JSON-serialisierbar


def _schedule_size_log(changed_key: str):
    """Startet/verlängert den Sammel-Timer. Mehrere Änderungen innerhalb
    von _LOG_DEBOUNCE_SECONDS erzeugen zusammen NUR EINEN Log-Eintrag,
    sobald keine weitere Änderung mehr nachkommt."""
    global _log_timer
    with _log_lock:
        _pending_changed_keys.add(changed_key)
        if _log_timer is not None:
            _log_timer.cancel()
        _log_timer = threading.Timer(_LOG_DEBOUNCE_SECONDS, _log_current_size)
        _log_timer.daemon = True
        _log_timer.start()


def _log_current_size():
    with _struct_lock:
        total_bytes = sum(size for _, _, size in _store.values())
        count = len(_store)
    with _log_lock:
        keys = sorted(_pending_changed_keys)
        _pending_changed_keys.clear()
    mb = total_bytes / (1024 * 1024)
    preview = ", ".join(keys[:5])
    if len(keys) > 5:
        preview += f", … (+{len(keys) - 5} weitere)"
    _log.info(f"Cache-Größe: {mb:.2f} MB ({count} Einträge) — geändert: {preview}")


def _get_key_lock(key: str) -> threading.Lock:
    with _struct_lock:
        lock = _key_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _key_locks[key] = lock
        return lock


def get(key: str) -> Optional[Any]:
    """Gibt den gecachten Wert zurück, falls vorhanden UND noch frisch.
    None sowohl wenn nie gesetzt als auch wenn abgelaufen."""
    with _struct_lock:
        entry = _store.get(key)
    if entry is None:
        return None
    value, expires_at, _size = entry
    if time.time() >= expires_at:
        return None
    return value


def set(key: str, value: Any, ttl: Optional[float] = None,
        expires_at: Optional[float] = None) -> None:
    """
    Speichert einen Wert. Entweder ttl (Sekunden ab jetzt) ODER expires_at
    (fester time.time()-Zeitpunkt, z.B. aus dem ESI Expires-Header über
    core.esi_client.ESIResult.expires_at) angeben — expires_at hat
    Vorrang, falls beides übergeben wird. Ohne Angabe: 300s Standard.
    """
    if expires_at is None:
        expires_at = time.time() + (ttl if ttl is not None else 300.0)
    size = _estimate_size(value)
    with _struct_lock:
        _store[key] = (value, expires_at, size)
    _schedule_size_log(key)


def get_or_fetch(key: str, fetch_fn: Callable[[], tuple[Any, Optional[float]]],
                  default_ttl: float = 300.0) -> Any:
    """
    Kombination aus get()+set(): gibt den Cache-Wert zurück, falls frisch
    — sonst ruft fetch_fn() auf (muss (value, expires_at_oder_None)
    zurückgeben, z.B. ein core.esi_client.get(...)-Aufruf gefolgt von
    (result.data, result.expires_at)) und merkt sich das Ergebnis.

    fetch_fn läuft NUR für den ersten Aufrufer, der einen abgelaufenen/
    fehlenden Eintrag trifft — alle anderen, die im selben Moment denselben
    Key anfragen, warten kurz und bekommen danach denselben frischen Wert
    statt selbst einen weiteren ESI-Call auszulösen.
    """
    cached = get(key)
    if cached is not None:
        return cached

    key_lock = _get_key_lock(key)
    with key_lock:
        # Erneut prüfen — ein anderer Aufrufer könnte den Eintrag bereits
        # gefüllt haben, während wir auf key_lock gewartet haben.
        cached = get(key)
        if cached is not None:
            return cached

        value, expires_at = fetch_fn()
        if expires_at is None:
            expires_at = time.time() + default_ttl
        size = _estimate_size(value)
        with _struct_lock:
            _store[key] = (value, expires_at, size)
        _schedule_size_log(key)
        return value


def invalidate(key: str) -> None:
    """Entfernt einen einzelnen Eintrag, erzwingt beim nächsten Zugriff
    einen frischen Abruf."""
    with _struct_lock:
        existed = _store.pop(key, None) is not None
    if existed:
        _schedule_size_log(key)


def clear_all() -> None:
    """Leert den gesamten Cache. Nicht zwingend nötig (RAM-only, verschwindet
    beim Prozessende ohnehin) — aber nützlich für gezielte Fälle wie
    Charakter-Wechsel oder Abmelden, wo alte Daten explizit verworfen
    werden sollen. Loggt sofort (kein Debounce — das ist ein bewusster,
    seltener Einschnitt, kein Anfrage-Burst)."""
    with _struct_lock:
        n = len(_store)
        _store.clear()
    with _log_lock:
        global _log_timer
        if _log_timer is not None:
            _log_timer.cancel()
            _log_timer = None
        _pending_changed_keys.clear()
    _log.info(f"Cache geleert ({n} Einträge entfernt) — Cache-Größe: 0.00 MB (0 Einträge)")