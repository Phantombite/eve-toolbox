"""
Zentrale Datenbank-Zugriffsschicht für items.sqlite UND universe.sqlite.

KEIN UI-Code, KEIN Modul-Code (Markt, Industrie, ...) führt jemals
direkt SQL gegen diese Datenbanken aus — alle Zugriffe laufen über die
Repository-Klassen in core/data/repositories/*.py, die intern dieses
Modul nutzen. Das hält die Datenbanken austauschbar (z.B. falls sie
später doch zusammengelegt werden sollten, siehe Architektur-
Diskussion) — nur die Repository-Schicht müsste sich dann ändern, kein
UI-Code.

Pfad-Konvention identisch zu core/settings.py: appdata-Ordner relativ
zum Programmverzeichnis (portable Distribution, kein Nutzer-Home-Pfad).
"""
from core import logger as _logger
_log = _logger.get("db")

import sqlite3
from pathlib import Path
from contextlib import contextmanager

# __file__ = APP_DIR/eve_toolbox/core/data/db.py
APP_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = APP_DIR / "appdata" / "data"
ITEMS_DB_PATH = DATA_DIR / "items.sqlite"
UNIVERSE_DB_PATH = DATA_DIR / "universe.sqlite"
CHARACTERS_DB_PATH = DATA_DIR / "characters.sqlite"

SCHEMA_DIR = Path(__file__).resolve().parent
ITEMS_SCHEMA_PATH = SCHEMA_DIR / "items_schema.sql"
UNIVERSE_SCHEMA_PATH = SCHEMA_DIR / "universe_schema.sql"
CHARACTERS_SCHEMA_PATH = SCHEMA_DIR / "characters_schema.sql"


def _connect(path: Path) -> sqlite3.Connection:
    """Öffnet eine Verbindung mit korrekt aktivierten Foreign-Key-
    Constraints — SQLite prüft diese NICHT automatisch, daher MUSS
    jede Verbindung in dieser Codebasis ausschließlich über diese
    Funktion entstehen, nie über ein direktes sqlite3.connect()
    anderswo im Projekt."""
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _db_connection(db_path: Path, db_label: str):
    """Generischer Kontextmanager für eine Lese-Verbindung zu einer der
    Spieldatenbanken. Wirft FileNotFoundError mit klarer Meldung, falls
    die Datenbank noch nie aufgebaut wurde — Aufrufer (Repositories)
    sollten das gezielt behandeln, statt einen kryptischen sqlite3-
    Fehler durchsickern zu lassen."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_label} existiert nicht unter {db_path} — die "
            f"Spieldatenbank wurde noch nicht aufgebaut. Das passiert "
            f"beim ersten App-Start automatisch (siehe core/data/db_updater.py)."
        )
    conn = _connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def items_connection():
    """Kontextmanager für eine Lese-Verbindung zur aktuellen items.sqlite."""
    with _db_connection(ITEMS_DB_PATH, "items.sqlite") as conn:
        yield conn


@contextmanager
def universe_connection():
    """Kontextmanager für eine Lese-Verbindung zur aktuellen universe.sqlite."""
    with _db_connection(UNIVERSE_DB_PATH, "universe.sqlite") as conn:
        yield conn


@contextmanager
def characters_connection():
    """Kontextmanager für eine Lese-Verbindung zur aktuellen characters.sqlite."""
    with _db_connection(CHARACTERS_DB_PATH, "characters.sqlite") as conn:
        yield conn


def _build_fresh_db(target_path: Path, schema_path: Path, db_label: str) -> None:
    """Legt eine KOMPLETT NEUE, leere Datenbank unter `target_path` an
    (Schema aus `schema_path`, inkl. PRAGMA foreign_keys). Befüllt sie
    NICHT mit Daten — das macht der jeweilige sde_to_*_db.py-Builder.

    `target_path` ist bewusst ein Parameter, kein fester Pfad: der
    Aufbau-Prozess schreibt zuerst in eine TEMPORÄRE Datei und ersetzt
    erst NACH vollständigem, fehlerfreiem Aufbau die echte Datenbank
    (atomarer Austausch, siehe core/data/db_updater.py) — so kann ein
    Absturz mitten im Aufbau niemals eine halb beschriebene, kaputte
    Datenbank an der "echten" Stelle zurücklassen."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        target_path.unlink()  # alte Reste einer fehlgeschlagenen Build entfernen

    conn = _connect(target_path)
    try:
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
    _log.info(f"Leere {db_label} mit Schema angelegt: {target_path}")


def build_fresh_items_db(target_path: Path) -> None:
    """Dünner Wrapper um _build_fresh_db für items.sqlite — siehe
    sde_to_items_db.py für den Befüllungs-Schritt."""
    _build_fresh_db(target_path, ITEMS_SCHEMA_PATH, "items.sqlite")


def build_fresh_universe_db(target_path: Path) -> None:
    """Dünner Wrapper um _build_fresh_db für universe.sqlite — siehe
    sde_to_universe_db.py für den Befüllungs-Schritt."""
    _build_fresh_db(target_path, UNIVERSE_SCHEMA_PATH, "universe.sqlite")


def build_fresh_characters_db(target_path: Path) -> None:
    """Dünner Wrapper um _build_fresh_db für characters.sqlite — siehe
    sde_to_characters_db.py für den Befüllungs-Schritt."""
    _build_fresh_db(target_path, CHARACTERS_SCHEMA_PATH, "characters.sqlite")