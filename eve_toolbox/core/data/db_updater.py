"""
core/data/db_updater.py — "Update der Spieldatenbank"

Heißt bewusst db_updater.py, NICHT updater.py — core/updater.py ist
bereits der Name des bestehenden PROGRAMM-Update-Mechanismus (GitHub-
Version-Check, Signaturprüfung, Installation). Beide Module haben
nichts miteinander zu tun (Programm-Code vs. Spieldaten), der ähnliche
Name hatte beim Entwickeln schon einmal zu einer Verwechslung beim
Einfügen geführt — der eigenständige Name beugt dem für die Zukunft vor.

Prüft beim App-Start, ob CCP einen neueren SDE-Build veröffentlicht hat
als der, aus dem unsere drei lokalen Spieldatenbanken (items.sqlite,
universe.sqlite, characters.sqlite) zuletzt gebaut wurden. Der Check
selbst ist winzig (eine einzelne Zeile JSON, kein Download des
98MB-Archivs) — nur wenn sich die Build-Nummer unterscheidet (oder gar
keine lokale Datenbank existiert), wird das vollständige SDE-ZIP
EINMAL heruntergeladen und für ALLE DREI Datenbanken gemeinsam genutzt
(kein dreifacher Download derselben ~98MB).

Ablauf (siehe check_and_update()):
  1. Lokale Build-Nummer aus items.sqlite lesen (items.sqlite gilt als
     Referenz für "ist überhaupt etwas installiert" — in der Praxis
     werden alle drei Datenbanken immer gemeinsam gebaut/aktualisiert,
     daher reicht eine Referenz-Datenbank für den reinen Vergleich).
  2. Remote Build-Nummer von CCPs leichtem Endpunkt abrufen.
  3. Sind beide gleich -> fertig, nichts zu tun.
  4. Sind sie unterschiedlich (oder lokal fehlt) -> EIN volles SDE-ZIP
     für GENAU diesen Build herunterladen, entpacken (Vereinigung aller
     von den drei sde_to_*_db.py-Buildern benötigten Dateien).
  5. JEDE der drei Datenbanken wird SEPARAT gebaut und SEPARAT atomar
     ausgetauscht — schlägt z.B. nur der characters.sqlite-Build fehl
     (Validierungsfehler, Strukturbruch), werden items.sqlite/
     universe.sqlite trotzdem aktualisiert, sofern sie selbst
     erfolgreich waren. Jede einzelne Datenbank bleibt bei einem
     eigenen Fehler auf ihrem bisherigen, funktionierenden Stand.

Alle Netzwerk-Endpunkte sind ÖFFENTLICH und brauchen keine
Authentifizierung (kein EVE-SSO-Login, keine Client-ID) — es handelt
sich um CCPs offizielle Static-Data-Export-Infrastruktur.
"""
from core import logger as _logger
_log = _logger.get("db_updater")

import json
import os
import shutil
import sqlite3
import tempfile
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from typing import Callable, NamedTuple, Optional

from core.data.db import ITEMS_DB_PATH, UNIVERSE_DB_PATH, CHARACTERS_DB_PATH, DATA_DIR, _connect
from core.data.sde_to_items_db import build_items_db
from core.data.sde_to_universe_db import build_universe_db
from core.data.sde_to_characters_db import build_characters_db

LATEST_BUILD_URL = "https://developers.eveonline.com/static-data/tranquility/latest.jsonl"
SDE_ZIP_URL_TEMPLATE = (
    "https://developers.eveonline.com/static-data/tranquility/"
    "eve-online-static-data-{build}-jsonl.zip"
)
USER_AGENT = "EVE-Toolbox/0.1 (https://github.com/Phantombite/eve-toolbox)"
REQUEST_TIMEOUT_S = 30

# Dateien, die sde_to_items_db.py braucht.
_ITEMS_SDE_FILES = [
    "categories.jsonl", "groups.jsonl", "icons.jsonl",
    "metaGroups.jsonl", "marketGroups.jsonl", "types.jsonl",
    "typeMaterials.jsonl", "dogmaUnits.jsonl", "dogmaAttributeCategories.jsonl",
    "dogmaAttributes.jsonl", "dogmaEffects.jsonl", "typeDogma.jsonl",
    "blueprints.jsonl", "compressibleTypes.jsonl", "contrabandTypes.jsonl",
]
# Dateien, die sde_to_universe_db.py braucht.
_UNIVERSE_SDE_FILES = [
    "mapRegions.jsonl", "mapConstellations.jsonl", "mapSolarSystems.jsonl",
    "mapStars.jsonl", "mapSecondarySuns.jsonl", "mapPlanets.jsonl",
    "mapMoons.jsonl", "mapAsteroidBelts.jsonl", "mapStargates.jsonl",
    "npcCorporations.jsonl", "npcCorporationDivisions.jsonl",
    "stationServices.jsonl", "stationOperations.jsonl", "npcStations.jsonl",
    "planetResources.jsonl", "planetSchematics.jsonl", "sovereigntyUpgrades.jsonl",
    "controlTowerResources.jsonl", "agentsInSpace.jsonl", "landmarks.jsonl",
    "factions.jsonl", "corporationActivities.jsonl", "npcCharacters.jsonl",
]
# Dateien, die sde_to_characters_db.py braucht.
_CHARACTERS_SDE_FILES = [
    "races.jsonl", "bloodlines.jsonl", "ancestries.jsonl",
    "characterAttributes.jsonl", "characterTitles.jsonl", "agentTypes.jsonl",
    "certificates.jsonl", "masteries.jsonl", "cloneGrades.jsonl",
]
# Vereinigung aller benötigten Dateien — "_sde.jsonl" zusätzlich, auch
# wenn kein Builder es direkt einliest (es wird nur für die Build-
# Nummer-Bestätigung mitgeführt, siehe _download_and_extract_sde).
REQUIRED_SDE_FILES = sorted(set(
    ["_sde.jsonl"] + _ITEMS_SDE_FILES + _UNIVERSE_SDE_FILES + _CHARACTERS_SDE_FILES
))

ProgressCallback = Optional[Callable[[str], None]]


class _DbSpec(NamedTuple):
    """Beschreibt eine der drei Spieldatenbanken — Name (fürs Logging),
    Ziel-Pfad, und die Builder-Funktion, die aus einem SDE-Ordner eine
    fertige Datenbank baut."""
    label: str
    db_path: Path
    build_fn: Callable[..., None]


_DB_SPECS = [
    _DbSpec("items.sqlite", ITEMS_DB_PATH, build_items_db),
    _DbSpec("universe.sqlite", UNIVERSE_DB_PATH, build_universe_db),
    _DbSpec("characters.sqlite", CHARACTERS_DB_PATH, build_characters_db),
]


def _report(progress: ProgressCallback, message: str):
    _log.info(message)
    if progress:
        progress(message)


def get_local_build_number() -> Optional[str]:
    """Liest die zuletzt verarbeitete SDE-Build-Nummer aus der
    bestehenden items.sqlite (als Referenz-Datenbank, siehe Modul-
    Docstring), oder None falls die Datei nicht existiert oder die
    meta-Tabelle (noch) keinen Eintrag dafür hat."""
    if not ITEMS_DB_PATH.exists():
        return None
    try:
        conn = _connect(ITEMS_DB_PATH)
        try:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'sde_build'"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        # Datei existiert, ist aber keine gültige/lesbare SQLite-
        # Datenbank (z.B. durch einen früheren abgebrochenen, nicht-
        # atomaren Schreibvorgang, oder Datenkorruption). Wird wie
        # "kein lokaler Build" behandelt — ein vollständiger Neuaufbau
        # überschreibt die kaputte Datei.
        _log.warning(f"items.sqlite ist beschädigt/unlesbar ({e}) — "
                      f"wird beim nächsten Update neu aufgebaut.")
        return None


def get_remote_build_number() -> str:
    """Fragt CCPs leichten Endpunkt nach der aktuell neuesten SDE-
    Build-Nummer — eine einzelne JSON-Zeile, kein großer Download.
    Wirft die zugrundeliegende Exception weiter, falls das fehlschlägt
    (z.B. kein Internet) — der Aufrufer (check_and_update) entscheidet,
    wie damit umzugehen ist."""
    req = urllib.request.Request(
        LATEST_BUILD_URL, headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str(data["buildNumber"])


def _download_and_extract_sde(build_number: str, extract_dir: Path,
                                progress: ProgressCallback):
    """Lädt das SDE-ZIP für `build_number` EINMAL herunter und entpackt
    NUR die in REQUIRED_SDE_FILES gelisteten Dateien (Vereinigung aus
    allen drei sde_to_*_db.py-Bedarfslisten) nach `extract_dir` — wird
    von ALLEN DREI Datenbank-Buildern aus demselben Ordner gelesen,
    kein dreifacher Download/keine dreifache Extraktion derselben
    ~98MB-Archivdatei."""
    url = SDE_ZIP_URL_TEMPLATE.format(build=build_number)
    _report(progress, f"Lade Spieldaten herunter (Build {build_number}) …")

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    zip_path = extract_dir / "sde.zip"
    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(zip_path, "wb") as f:
            shutil.copyfileobj(resp, f)

    _report(progress, "Entpacke Spieldaten …")
    with zipfile.ZipFile(zip_path) as zf:
        available = set(zf.namelist())
        missing = [f for f in REQUIRED_SDE_FILES if f not in available]
        if missing:
            raise RuntimeError(
                f"SDE-Archiv (Build {build_number}) enthält nicht alle "
                f"erwarteten Dateien — fehlend: {missing}. Möglicherweise "
                f"hat CCP die Datei-Struktur geändert (siehe Schema-"
                f"Changelog); der Build-Code muss dann angepasst werden."
            )
        for filename in REQUIRED_SDE_FILES:
            zf.extract(filename, extract_dir)

    zip_path.unlink()  # ZIP selbst wird nicht mehr gebraucht, Platz sparen


def check_and_update(progress: ProgressCallback = None) -> bool:
    """Hauptfunktion — vom App-Start aufgerufen (siehe main_window.py).

    Liefert True, wenn NACH diesem Aufruf MINDESTENS items.sqlite
    existiert und nutzbar ist (egal ob neu gebaut oder bereits aktuell
    war), False, wenn sowohl der Update-Versuch fehlschlug ALS AUCH
    keine funktionierende alte items.sqlite vorhanden ist (z.B.
    allererster Start ohne Internetverbindung).

    Da die drei Datenbanken SEPARAT gebaut/ausgetauscht werden (siehe
    Modul-Docstring), kann es vorkommen, dass z.B. items.sqlite und
    universe.sqlite erfolgreich aktualisiert wurden, characters.sqlite
    aber auf dem alten Stand verblieb (eigener Validierungsfehler) —
    das wird geloggt, führt aber NICHT zu einem False-Rückgabewert,
    solange items.sqlite funktioniert.

    `progress`: optionaler Callback(str), der für eine UI-Fortschritts-
    anzeige aufgerufen wird (z.B. Startbildschirm-Statustext) — rein
    informativ, keine Rückgabewerte erwartet."""
    local_build = get_local_build_number()

    try:
        remote_build = get_remote_build_number()
    except Exception as e:
        _log.warning(f"Build-Check fehlgeschlagen ({e}) — "
                      f"verwende vorhandene lokale Datenbanken, falls da.")
        return ITEMS_DB_PATH.exists()

    if local_build == remote_build:
        _report(progress, f"Spieldatenbanken sind aktuell (Build {remote_build}).")
        return True

    _report(
        progress,
        f"Neue Spieldaten verfügbar (Build {remote_build}"
        + (f", bisher {local_build}" if local_build else ", erster Aufbau")
        + ") — aktualisiere …",
    )

    with tempfile.TemporaryDirectory(prefix="eve_toolbox_sde_") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        try:
            _download_and_extract_sde(remote_build, tmp_dir, progress)
        except Exception as e:
            _log.error(f"Download/Entpacken der Spieldaten fehlgeschlagen: {e}")
            _report(
                progress,
                "Aktualisierung der Spieldaten fehlgeschlagen — "
                + ("verwende weiterhin die bisherige Version."
                   if local_build else
                   "Markt-/Spieldaten-Funktionen sind ohne Internetverbindung "
                   "beim ersten Start nicht verfügbar."),
            )
            return ITEMS_DB_PATH.exists()

        DATA_DIR.mkdir(parents=True, exist_ok=True)
        results = {}
        for spec in _DB_SPECS:
            try:
                _report(progress, f"Baue {spec.label} auf …")
                tmp_db_path = tmp_dir / f"{spec.label}.new"
                spec.build_fn(
                    sde_dir=tmp_dir, target_path=tmp_db_path, build_number=remote_build
                )
                # Atomarer Austausch: os.replace ist auf den gängigen
                # Dateisystemen (NTFS, ext4, ...) eine atomare Operation
                # — es existiert zu KEINEM Zeitpunkt eine halb
                # geschriebene Datei an der Zielposition.
                os.replace(tmp_db_path, spec.db_path)
                results[spec.label] = True
                _log.info(f"{spec.label} erfolgreich aktualisiert.")
            except Exception as e:
                results[spec.label] = False
                _log.error(f"Update von {spec.label} fehlgeschlagen: {e} — "
                           f"bisherige Datei bleibt unverändert.")

        succeeded = [name for name, ok in results.items() if ok]
        failed = [name for name, ok in results.items() if not ok]
        if failed:
            _report(
                progress,
                f"Spieldatenbanken teilweise aktualisiert: {', '.join(succeeded) or 'keine'} "
                f"erfolgreich, {', '.join(failed)} fehlgeschlagen (alte Version behalten).",
            )
        else:
            _report(progress, f"Alle Spieldatenbanken erfolgreich aktualisiert "
                                f"(Build {remote_build}).")

        return ITEMS_DB_PATH.exists()