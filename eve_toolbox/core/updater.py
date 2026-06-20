"""
Update-System — prüft GitHub, lädt Updates herunter und installiert sie.

Ablauf:
1. version.json von GitHub (main Branch) laden
2. Mit lokaler Version vergleichen
3. Bei neuer Version: Backup erstellen
4. ZIP herunterladen, Signatur prüfen (Root→Release-Kette), validieren
5. Installieren (eve_toolbox/ + EXE + _internal/ ersetzen)
6. version.json + checksums.json + release_cert.json (signaturgeprüft)
   vom neuen Tag laden
7. Neustart empfehlen

Zusätzlich, unabhängig vom normalen Update-Ablauf (Block 3):
    check_stable_version() prüft stable_version.json — erkennt sowohl
    reguläre neue Versionen als auch den Sonderfall, dass die
    installierte Version zurückgezogen wurde (Rollback-Empfehlung
    oder -Erzwingung, siehe core.updater.check_stable_version).

Neue ZIP Struktur:
    eve_toolbox.zip
    ├── EVE_Toolbox.exe
    ├── _internal/
    ├── eve_toolbox/
    │   ├── main.py
    │   ├── core/
    │   └── ...
    ├── version.json
    ├── checksums.json
    ├── checksums.json.sig
    ├── release_cert.json
    └── dev_pubkey.pem

Separat auf GitHub Releases (nicht im ZIP-Inhalt, da sonst zirkulär):
    eve_toolbox.zip.sig — Signatur über die ZIP-Datei selbst

Separat im Hauptverzeichnis/Repo (nicht im ZIP, aber signaturgeprüft):
    stable_version.json + stable_version.json.sig — siehe
    check_stable_version()

Verantwortungstrennung (Block 2):
    Dieses Modul führt nur noch Installations- und Wiederherstellungs-
    AUFTRÄGE aus (download_and_install, repair_files, restore_backup).
    Es weiß nicht selbst, OB eine Reparatur nötig ist oder warum — das
    entscheidet core.integrity (Diagnose) bzw. main.py (Steuerung).
"""
from core import logger as _logger
_log = _logger.get("updater")

import json
import threading
import shutil
import zipfile
import os
import sys
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from core.config import APP_VERSION
from core import release_crypto as _crypto

# ── GitHub Konfiguration ──────────────────────────────────────
GITHUB_USER   = "Phantombite"   # Gross-P — case-sensitive!
GITHUB_REPO   = "eve-toolbox"
GITHUB_BRANCH = "main"

VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/"
    f"{GITHUB_REPO}/{GITHUB_BRANCH}/version.json"
)

REQUEST_TIMEOUT = 10

# ── Lokale Pfade ──────────────────────────────────────────────
# __file__ = APP_DIR/eve_toolbox/core/updater.py
APP_DIR         = Path(__file__).resolve().parent.parent.parent
EVE_TOOLBOX_DIR = APP_DIR / "eve_toolbox"
INTERNAL_DIR    = APP_DIR / "_internal"
EXE_FILE        = APP_DIR / "EVE_Toolbox.exe"
BACKUP_DIR      = Path.home() / ".eve_toolbox" / "backup"
BACKUP_ZIP      = BACKUP_DIR / "previous_version.zip"


def _safe_extractall(zip_file: zipfile.ZipFile, dest_dir: Path) -> None:
    """
    Entpackt eine ZIP-Datei NUR innerhalb von dest_dir — schützt gegen
    Path-Traversal (Einträge wie '../../etc/passwd' oder absolute Pfade
    in der ZIP), die zipfile.extractall() sonst klaglos akzeptieren würde.

    Dies ist eine zusätzliche Absicherungsschicht (Defense-in-Depth),
    unabhängig von der Signaturprüfung: Die Signatur beweist nur "diese
    ZIP stammt vom Release Key", nicht "jeder einzelne Pfad darin ist
    harmlos". Beide Prüfungen ergänzen sich, eine ersetzt die andere nicht.
    """
    dest_dir = dest_dir.resolve()
    for member in zip_file.namelist():
        target = (dest_dir / member).resolve()
        if not str(target).startswith(str(dest_dir) + os.sep) and target != dest_dir:
            raise ValueError(
                f"Unsicherer Pfad in ZIP erkannt, Entpacken abgebrochen: {member!r}"
            )
    zip_file.extractall(dest_dir)


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def _request(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes | None:
    try:
        req = Request(url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        _log.warning(f"Request fehlgeschlagen ({url}): {e}")
        return None


# ── Update prüfen ─────────────────────────────────────────────

def _fetch_version_info() -> dict | None:
    raw = _request(VERSION_URL)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        _log.error(f"version.json konnte nicht gelesen werden: {e}")
        return None


def check_for_update(callback) -> None:
    """Hintergrund-Check. Ruft callback(info | None) auf."""
    def _check():
        try:
            data = _fetch_version_info()
            if data and _parse_version(data.get("version", "0.0.0")) > _parse_version(APP_VERSION):
                callback(data)
            else:
                callback(None)
        except Exception:
            callback(None)
    threading.Thread(target=_check, daemon=True).start()


def check_sync() -> dict | None:
    """Synchroner Check — für Splash Screen."""
    try:
        data = _fetch_version_info()
        if data and _parse_version(data.get("version", "0.0.0")) > _parse_version(APP_VERSION):
            return data
        return None
    except Exception:
        return None


def get_remote_version() -> str | None:
    try:
        data = _fetch_version_info()
        return data.get("version") if data else None
    except Exception:
        return None


# ── Stable-Version-System (Block 3) ───────────────────────────
#
# Statt einer wachsenden "das ist alles defekt"-Liste gibt es nur EINE
# Quelle der Wahrheit: stable_version.json, signiert wie alles andere.
# Sie wird in BEIDE Richtungen verglichen:
#   installierte Version < stable  → normales Update (wie bisher)
#   installierte Version > stable  → die installierte Version wurde
#                                     zurückgezogen, Rollback empfohlen
#                                     oder erzwungen (siehe "mandatory")
#
# Sicherer Default: ist stable_version.json nicht erreichbar (Netzwerk,
# GitHub down, Datei fehlt), passiert NICHTS — kein Update, kein
# Rollback. "Kein Signal" darf niemals als "alles ist in Ordnung,
# downgrade jetzt" interpretiert werden.

STABLE_VERSION_FILENAME = "stable_version.json"
STABLE_VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/"
    f"{GITHUB_REPO}/{GITHUB_BRANCH}/{STABLE_VERSION_FILENAME}"
)


class StableVersionStatus:
    """Ergebnis von check_stable_version() — reine Diagnose, keine
    Aktion. main.py entscheidet anhand dessen, was zu tun ist."""
    def __init__(self):
        self.reachable      = False
        self.signature_valid = None
        self.stable_version  = None
        self.mandatory       = False
        self.rollback_needed = False   # installierte Version > stable
        self.rollback_info   = None    # version.json-ähnliches Dict für download_and_install


def check_stable_version() -> StableVersionStatus:
    """
    Lädt stable_version.json + .sig + release_cert.json, prüft die
    Signatur, vergleicht dann in beide Richtungen gegen APP_VERSION.
    Liefert reine Diagnose zurück — installiert/rollt NICHTS selbst zurück.
    """
    status = StableVersionStatus()

    raw = _request(STABLE_VERSION_URL)
    if raw is None:
        _log.debug("stable_version.json nicht erreichbar — kein Stable-Check möglich (sicherer Default: nichts tun)")
        return status
    status.reachable = True

    sig_raw = _request(STABLE_VERSION_URL + ".sig")
    if sig_raw is None:
        _log.warning("stable_version.json.sig nicht erreichbar — Signatur kann nicht geprüft werden, ignoriere Datei")
        return status

    cert_url = (
        f"https://raw.githubusercontent.com/{GITHUB_USER}/"
        f"{GITHUB_REPO}/{GITHUB_BRANCH}/{_crypto.RELEASE_CERT_FILENAME}"
    )
    cert_raw = _request(cert_url)
    if cert_raw is None:
        _log.warning("release_cert.json nicht erreichbar — stable_version.json kann nicht autorisiert werden")
        return status

    sig_b64 = sig_raw.decode("utf-8").strip()
    if not _crypto.verify_release_signature(raw, sig_b64, cert_bytes=cert_raw):
        _log.error("stable_version.json: Signatur UNGÜLTIG — wird ignoriert, kein Update/Rollback")
        status.signature_valid = False
        return status
    status.signature_valid = True

    try:
        data = json.loads(raw.decode("utf-8"))
        stable_version = data["version"]
        mandatory = bool(data.get("mandatory", False))
    except Exception as e:
        _log.error(f"stable_version.json: Inhalt ungültig: {e}")
        return status

    status.stable_version = stable_version
    status.mandatory = mandatory

    local_v  = _parse_version(APP_VERSION)
    stable_v = _parse_version(stable_version)

    if local_v < stable_v:
        # Wird hier nur protokolliert, nicht als eigenes Flag geführt —
        # der reguläre Update-Pfad läuft über check_sync()/check_for_update()
        # weiter unten in main.py, nicht über das Stable-Version-System.
        # Stable-Version dient ausschließlich dem Rollback-Fall.
        _log.info(f"Stable-Version v{stable_version} ist neuer als installierte v{APP_VERSION}")
    elif local_v > stable_v:
        status.rollback_needed = True
        _log.warning(
            f"Installierte Version v{APP_VERSION} ist neuer als die "
            f"aktuelle Stable-Version v{stable_version} — wurde vermutlich zurückgezogen"
        )
        # Für den Rollback braucht download_and_install() ein info-Dict
        # wie von version.json gewohnt — wir bauen es aus dem, was wir
        # über die Stable-Version wissen, plus der Standard-Download-URL.
        status.rollback_info = {
            "version": stable_version,
            "download_zip": (
                f"https://github.com/{GITHUB_USER}/{GITHUB_REPO}/"
                f"releases/download/v{stable_version}/eve_toolbox.zip"
            ),
        }
    else:
        _log.debug(f"Installierte Version v{APP_VERSION} entspricht der Stable-Version")

    return status


# ── Backup ────────────────────────────────────────────────────

def has_backup() -> bool:
    return BACKUP_ZIP.exists()


def get_backup_version() -> str | None:
    if not BACKUP_ZIP.exists():
        return None
    try:
        with zipfile.ZipFile(BACKUP_ZIP, "r") as z:
            ver_file = next((n for n in z.namelist() if n.endswith("version.json")), None)
            if ver_file:
                return json.loads(z.read(ver_file).decode("utf-8")).get("version")
    except Exception:
        pass
    return "Unbekannt"


def create_backup() -> bool:
    """
    Sichert aktuelle Installation:
    - eve_toolbox/ (Quellcode)
    - EVE_Toolbox.exe
    - _internal/
    - version.json, checksums.json, checksums.json.sig,
      release_cert.json, dev_pubkey.pem
    """
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
            backed_up = 0

            # eve_toolbox\ Quellcode
            if EVE_TOOLBOX_DIR.exists():
                for file in EVE_TOOLBOX_DIR.rglob("*"):
                    if file.is_file() and "__pycache__" not in str(file):
                        z.write(file, file.relative_to(APP_DIR))
                        backed_up += 1

            # _internal\
            if INTERNAL_DIR.exists():
                for file in INTERNAL_DIR.rglob("*"):
                    if file.is_file():
                        z.write(file, file.relative_to(APP_DIR))
                        backed_up += 1

            # EXE
            if EXE_FILE.exists():
                z.write(EXE_FILE, EXE_FILE.relative_to(APP_DIR))
                backed_up += 1

            # Einzelne Dateien
            for fname in ("version.json", "checksums.json", "checksums.json.sig",
                          _crypto.RELEASE_CERT_FILENAME, "dev_pubkey.pem"):
                f = APP_DIR / fname
                if f.exists():
                    z.write(f, f.relative_to(APP_DIR))
                    backed_up += 1

        _log.info(f"Backup erstellt: {BACKUP_ZIP} ({backed_up} Dateien)")
        return True
    except Exception as e:
        _log.error(f"Backup fehlgeschlagen: {e}")
        return False


# ── Wiederherstellung einzelner Dateien (Auftrag von main.py) ──
#
# Verantwortungstrennung: updater.py weiß NICHT, warum eine Datei
# wiederhergestellt werden soll (fehlt? manipuliert?) — es bekommt nur
# eine Liste von relativen Pfaden als Auftrag und führt ihn aus.
# main.py entscheidet anhand von core.integrity.IntegrityResult, welche
# Dateien das sind.

def _restore_single_file(rel_key: str, version: str) -> bool:
    """
    Lädt eine einzelne Datei vom exakt gleichen GitHub Tag wie die
    installierte Version. Wird NUR über repair_files() aufgerufen,
    nicht direkt von außen — die Signaturprüfung der zugehörigen
    checksums.json ist bereits in core.integrity passiert, BEVOR diese
    Funktion überhaupt aufgerufen wird (repair_files() verifiziert das
    nicht erneut, sondern vertraut auf den Aufrufer-Vertrag).
    """
    tag = f"v{version}" if version != "main" else GITHUB_BRANCH
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_USER}/"
        f"{GITHUB_REPO}/{tag}/{rel_key}"
    )
    target = APP_DIR / rel_key.replace("/", os.sep)
    try:
        _log.info(f"Stelle wieder her: {rel_key}")
        req = Request(url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=30) as resp:
            content = resp.read()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _log.info(f"Wiederhergestellt: {rel_key}")
        return True
    except Exception as e:
        _log.error(f"Wiederherstellung fehlgeschlagen für {rel_key}: {e}")
        return False


def repair_files(file_list: list[str], version: str, verified_signature: bool,
                  progress_callback=None) -> tuple[list[str], list[str]]:
    """
    Zentraler Reparatur-Auftrag: lädt jede Datei in file_list vom
    versionierten GitHub Tag neu herunter und überschreibt die lokale
    Kopie. Gibt (erfolgreich_reparierte, fehlgeschlagene) zurück.

    verified_signature MUSS explizit True sein — kein Default, keine
    implizite Annahme. Der Aufrufer bestätigt damit aktiv: "Die
    checksums.json, aus der file_list stammt, wurde bereits über
    core.release_crypto.verify_release_signature() erfolgreich geprüft."
    (core.integrity.run_check()/mini_check() tun das automatisch, bevor
    sie missing_files/corrupted_files befüllen.)

    Diese Funktion vertraut das nicht nur per Dokumentation — sie
    erzwingt es technisch: ein Aufruf mit verified_signature=False
    wirft RuntimeError, statt stillschweigend trotzdem zu installieren.
    Das verhindert, dass künftiger Code (auch von dir selbst, Monate
    später) versehentlich eine ungeprüfte Dateiliste durchwinkt, nur
    weil ein Docstring-Kommentar es so vorausgesetzt hatte.
    """
    if not verified_signature:
        raise RuntimeError(
            "repair_files() verweigert die Ausführung: verified_signature "
            "ist nicht True. file_list muss aus einem bereits signaturgeprüften "
            "IntegrityResult stammen (core.integrity.run_check()/mini_check())."
        )

    fixed, failed = [], []
    total = len(file_list)

    for i, rel_key in enumerate(file_list):
        if progress_callback:
            pct = int(i / total * 100) if total else 100
            progress_callback(pct, f"Repariere {rel_key.split('/')[-1]}...")

        if _restore_single_file(rel_key, version):
            fixed.append(rel_key)
        else:
            failed.append(rel_key)

    if progress_callback:
        progress_callback(100, f"{len(fixed)}/{total} Datei(en) reparariert")

    _log.info(f"repair_files: {len(fixed)} erfolgreich, {len(failed)} fehlgeschlagen")
    return fixed, failed


def restore_backup() -> tuple[bool, str]:
    """Stellt vorherige Version wieder her."""
    if not BACKUP_ZIP.exists():
        return False, "Kein Backup vorhanden."
    try:
        _log.info("Stelle Backup wieder her...")

        # Aktuellen Stand temporär sichern
        tmp = BACKUP_DIR / "restore_tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)

        for item in (EVE_TOOLBOX_DIR, INTERNAL_DIR, EXE_FILE):
            if item.exists():
                if item.is_dir():
                    shutil.copytree(item, tmp / item.name)
                else:
                    shutil.copy2(item, tmp / item.name)

        try:
            # Alles löschen
            if EVE_TOOLBOX_DIR.exists():
                shutil.rmtree(EVE_TOOLBOX_DIR)
            if INTERNAL_DIR.exists():
                shutil.rmtree(INTERNAL_DIR)
            if EXE_FILE.exists():
                EXE_FILE.unlink()

            # Backup einspielen
            with zipfile.ZipFile(BACKUP_ZIP, "r") as z:
                _safe_extractall(z, APP_DIR)

            shutil.rmtree(tmp, ignore_errors=True)
            _log.info("Backup wiederhergestellt")
            return True, "Vorherige Version wiederhergestellt. Bitte App neu starten."

        except Exception as e:
            _log.error(f"Wiederherstellung fehlgeschlagen, Rollback: {e}")
            # Rollback
            for item in tmp.iterdir():
                dest = APP_DIR / item.name
                if dest.exists():
                    if dest.is_dir():
                        shutil.rmtree(dest)
                    else:
                        dest.unlink()
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            return False, f"Fehler beim Wiederherstellen: {e}"

    except Exception as e:
        return False, f"Fehler: {e}"


# ── Neustart Hilfsfunktionen ─────────────────────────────────

def cleanup_old_files():
    """Löscht _old Dateien vom letzten Update."""
    old_exe      = APP_DIR / "EVE_Toolbox_old.exe"
    old_internal = APP_DIR / "_internal_old"

    if old_exe.exists():
        try:
            old_exe.unlink()
            _log.info("EVE_Toolbox_old.exe gelöscht")
        except Exception as e:
            _log.warning(f"Konnte EVE_Toolbox_old.exe nicht löschen: {e}")

    if old_internal.exists():
        try:
            shutil.rmtree(old_internal)
            _log.info("_internal_old gelöscht")
        except Exception as e:
            _log.warning(f"Konnte _internal_old nicht löschen: {e}")


def _restart_app():
    """Startet EVE_Toolbox.exe neu und beendet aktuellen Prozess."""
    exe = APP_DIR / "EVE_Toolbox.exe"
    if exe.exists():
        _log.info(f"Starte neu: {exe}")
        subprocess.Popen(
            [str(exe)],
            cwd=str(APP_DIR),
            creationflags=0x00000008  # DETACHED_PROCESS
        )
    else:
        _log.error("EVE_Toolbox.exe nicht gefunden für Neustart!")
    time.sleep(0.5)
    sys.exit(0)


# ── Download und Installation ─────────────────────────────────

def download_and_install(info: dict, progress_callback=None,
                          allow_downgrade: bool = False) -> tuple[bool, str]:
    """
    Lädt Update herunter und installiert es.

    Erwartete ZIP Struktur:
        eve_toolbox.zip
        ├── EVE_Toolbox.exe
        ├── _internal/
        ├── eve_toolbox/
        ├── version.json
        ├── checksums.json
        ├── checksums.json.sig
        ├── release_cert.json
        └── dev_pubkey.pem

    Sicherheit: Die ZIP-Datei selbst wird mit eve_toolbox.zip.sig
    (separat neben der ZIP auf GitHub Releases) signaturgeprüft, BEVOR
    sie entpackt/installiert wird. Ohne gültige Signatur wird die
    Installation komplett abgebrochen — kein Fallback, kein Teilinstall.

    Anti-Downgrade (unabhängig von der Signaturprüfung — eine gültige
    Signatur beweist nur "echtes Release", nicht "neuer als aktuell"):
    Standardmäßig wird abgelehnt, wenn info["version"] <= der aktuell
    installierten Version. Diese zweite, unabhängige Prüfung sitzt HIER
    in der Funktion selbst, nicht nur beim Aufrufer (check_for_update/
    check_sync) — falls die Funktion je direkt mit einem älteren info-
    Dict aufgerufen wird, schützt das davor, eine ältere aber gültig
    signierte Version unbemerkt zu installieren (Rollback-Angriff).

    allow_downgrade=True hebt diese Prüfung gezielt auf — wird NUR vom
    gewollten Stable-Version-Rollback genutzt (core.updater.
    check_stable_version), niemals vom normalen Update-Pfad.
    """
    download_url = info.get("download_zip")
    if not download_url:
        return False, "Kein download_zip in version.json."

    new_version = info.get("version", "?")

    if not allow_downgrade:
        if _parse_version(new_version) <= _parse_version(APP_VERSION):
            _log.error(
                f"Anti-Downgrade: v{new_version} ist nicht neuer als die "
                f"installierte Version v{APP_VERSION} — Installation abgelehnt."
            )
            return False, (
                f"Version {new_version} ist nicht neuer als die installierte "
                f"Version {APP_VERSION}. Installation abgelehnt."
            )

    import hashlib
    import secrets as _secrets

    # Zufälliger, nicht vorhersagbarer Dateiname für die Zeit, in der die
    # ZIP noch ungeprüft ist — kein fester Name wie "update_download.zip",
    # den ein anderer Prozess gezielt vorab platzieren/ersetzen könnte.
    tmp_zip = BACKUP_DIR / f"_dl_{_secrets.token_hex(8)}.tmp"

    def _prog(pct):
        if progress_callback:
            progress_callback(pct)

    try:
        _prog(5)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # ── Signatur + Zertifikat ZUERST laden (winzige Dateien) ──
        # Bevor überhaupt ein Byte der großen ZIP auf die Platte
        # geschrieben wird, müssen Signatur und Zertifikat bereits
        # vorliegen — verkürzt das Zeitfenster, in dem die ZIP
        # ungeprüft existiert, auf das technische Minimum (nur noch
        # die Downloadzeit selbst, nicht zusätzlich zwei weitere
        # Netzwerk-Roundtrips danach).
        sig_url = download_url + ".sig"
        cert_url = download_url.rsplit("/", 1)[0] + "/" + _crypto.RELEASE_CERT_FILENAME
        _log.info(f"Lade Signatur + Zertifikat vor dem ZIP-Download: {sig_url}")

        sig_raw = _request(sig_url)
        if sig_raw is None:
            return False, (
                "eve_toolbox.zip.sig konnte nicht geladen werden — "
                "Installation abgebrochen, bevor irgendetwas heruntergeladen wurde."
            )

        cert_raw = _request(cert_url)
        if cert_raw is None:
            return False, (
                "release_cert.json konnte nicht geladen werden — "
                "Installation abgebrochen, bevor irgendetwas heruntergeladen wurde."
            )
        _prog(10)

        # ── Download — Hash wird WÄHREND des Streamens berechnet ──
        # Kein zweites komplettes Lesen der Datei nötig, um den Hash zu
        # bekommen — spart Zeit und reduziert das Zeitfenster weiter.
        _log.info(f"Lade Update v{new_version}: {download_url}")
        hasher = hashlib.sha256()
        req = Request(download_url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=120) as resp:
            total      = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                while chunk := resp.read(65536):
                    f.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if total:
                        _prog(10 + int(downloaded / total * 48))

        _log.info(f"Download abgeschlossen: {downloaded} bytes")
        _prog(58)

        # ── ZIP-Signatur SOFORT prüfen — direkt nach dem letzten Byte ──
        # Schlägt eine der beiden Prüfungen fehl, wird NICHT installiert
        # — kein Fallback auf "vielleicht ist es trotzdem ok". Die Datei
        # wird in JEDEM Fehlerfall augenblicklich gelöscht.
        zip_bytes = tmp_zip.read_bytes()
        # Sicherheits-Gegenprobe: Hash des tatsächlich Geschriebenen muss
        # zum während des Streamens berechneten Hash passen (erkennt
        # Schreibfehler/Manipulation zwischen Stream und Re-Read).
        if hasher.hexdigest() != hashlib.sha256(zip_bytes).hexdigest():
            tmp_zip.unlink(missing_ok=True)
            return False, "Heruntergeladene Datei wurde nach dem Download verändert — abgebrochen."

        sig_b64 = sig_raw.decode("utf-8").strip()
        if not _crypto.verify_release_signature(zip_bytes, sig_b64, cert_bytes=cert_raw):
            tmp_zip.unlink(missing_ok=True)
            _log.error("ZIP-Signatur UNGÜLTIG — Installation abgebrochen, Datei verworfen")
            return False, (
                "Signatur der heruntergeladenen Datei ist UNGÜLTIG. "
                "Installation abgebrochen — die Datei wurde nicht verwendet."
            )
        _log.info("ZIP-Signatur gültig")
        _prog(60)

        # ── ZIP validieren ────────────────────────────────────
        if not zipfile.is_zipfile(tmp_zip):
            tmp_zip.unlink(missing_ok=True)
            return False, "Heruntergeladene Datei ist kein gültiges ZIP."

        with zipfile.ZipFile(tmp_zip, "r") as z:
            names = z.namelist()
            has_eve   = any(n.startswith("eve_toolbox/") for n in names)
            has_exe   = "EVE_Toolbox.exe" in names
            has_int   = any(n.startswith("_internal/") for n in names)
            _log.info(f"ZIP Inhalt: eve_toolbox={has_eve} EXE={has_exe} _internal={has_int}")
            if not has_eve:
                tmp_zip.unlink(missing_ok=True)
                return False, "ZIP enthält keinen eve_toolbox/ Ordner."

        _prog(65)

        # ── Installieren ──────────────────────────────────────
        _log.info("Installiere Update...")

        # eve_toolbox\ Quellcode direkt ersetzen (kein Neustart nötig)
        if EVE_TOOLBOX_DIR.exists():
            shutil.rmtree(EVE_TOOLBOX_DIR)

        # EXE und _internal umbenennen statt löschen
        # (können nicht gelöscht werden während sie laufen)
        old_exe      = APP_DIR / "EVE_Toolbox_old.exe"
        old_internal = APP_DIR / "_internal_old"

        if EXE_FILE.exists():
            EXE_FILE.rename(old_exe)
            _log.info("EVE_Toolbox.exe → EVE_Toolbox_old.exe")

        if INTERNAL_DIR.exists():
            INTERNAL_DIR.rename(old_internal)
            _log.info("_internal\\ → _internal_old\\")

        # ZIP entpacken — neue EXE + _internal + eve_toolbox\
        with zipfile.ZipFile(tmp_zip, "r") as z:
            _safe_extractall(z, APP_DIR)

        tmp_zip.unlink(missing_ok=True)
        _log.info("Update entpackt")
        _prog(85)

        # ── version.json aktualisieren ────────────────────────
        # Wird aus ZIP mitgeliefert — nur überschreiben wenn nicht vorhanden
        ver_file = APP_DIR / "version.json"
        if not ver_file.exists():
            ver_file.write_text(
                json.dumps({
                    "version":      new_version,
                    "notes":        info.get("notes", ""),
                    "download_zip": download_url,
                }, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
        _log.info(f"version.json: v{new_version}")

        # ── checksums.json + Signatur + Zertifikat vom neuen Tag laden ──
        # Vom versionierten Tag damit Integritätscheck sofort stimmt.
        # WICHTIG: Signatur wird geprüft, BEVOR die Datei geschrieben
        # wird — sonst könnte hier dieselbe Lücke entstehen, die die
        # Signaturprüfung in core.integrity eigentlich schließen soll.
        tag = f"v{new_version}"
        checksums_url = (
            f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{GITHUB_REPO}/{tag}/checksums.json"
        )
        sig_url = (
            f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{GITHUB_REPO}/{tag}/checksums.json.sig"
        )
        cert_url = (
            f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{GITHUB_REPO}/{tag}/{_crypto.RELEASE_CERT_FILENAME}"
        )
        _log.info(f"Lade checksums.json + Signatur + Zertifikat von {tag}...")
        checksums_raw = _request(checksums_url)
        sig_raw       = _request(sig_url)
        cert_raw      = _request(cert_url)

        if checksums_raw and sig_raw and cert_raw:
            sig_b64 = sig_raw.decode("utf-8").strip()
            if _crypto.verify_release_signature(checksums_raw, sig_b64, cert_bytes=cert_raw):
                (APP_DIR / "checksums.json").write_bytes(checksums_raw)
                (APP_DIR / "checksums.json.sig").write_bytes(sig_raw)
                (APP_DIR / _crypto.RELEASE_CERT_FILENAME).write_bytes(cert_raw)
                _log.info("checksums.json signaturgeprüft und gespeichert")
            else:
                _log.error(
                    "checksums.json vom neuen Tag hat UNGÜLTIGE Signatur — "
                    "wird verworfen. Nächster Integritätscheck nutzt die "
                    "im ZIP mitgelieferte Version (sofern vorhanden) oder "
                    "meldet einen Fehler, statt eine ungeprüfte Datei zu übernehmen."
                )
        else:
            _log.warning(
                "checksums.json oder checksums.json.sig von GitHub nicht "
                "verfügbar — Integritätscheck nutzt die im ZIP mitgelieferte Version."
            )

        _prog(100)
        _log.info(f"Update v{new_version} erfolgreich installiert")

        # Neustart — neue EXE starten, alte beendet sich
        _log.info("Starte neu mit neuer Version...")
        _restart_app()

        return True, f"Update auf v{new_version} erfolgreich."

    except Exception as e:
        _log.error(f"Update fehlgeschlagen: {e}")
        tmp_zip.unlink(missing_ok=True)
        if has_backup():
            _log.info("Versuche Backup wiederherzustellen...")
            restore_backup()
        return False, f"Update fehlgeschlagen: {e}"