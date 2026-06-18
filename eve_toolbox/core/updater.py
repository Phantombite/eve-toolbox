"""
Update-System — prüft GitHub, lädt Updates herunter und installiert sie.

Ablauf:
1. version.json von GitHub (main Branch) laden
2. Mit lokaler Version vergleichen
3. Bei neuer Version: Backup erstellen
4. ZIP herunterladen und validieren
5. Installieren (eve_toolbox\ + EXE + _internal\ ersetzen)
6. version.json + checksums.json vom neuen Tag laden
7. Neustart empfehlen

Neue ZIP Struktur:
    eve_toolbox.zip
    ├── EVE_Toolbox.exe
    ├── _internal\
    ├── eve_toolbox\
    │   ├── main.py
    │   ├── core\
    │   └── ...
    ├── version.json
    ├── checksums.json
    └── dev_pubkey.pem
"""
from core import logger as _logger
_log = _logger.get("updater")

import json
import threading
import shutil
import zipfile
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from core.config import APP_VERSION

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
    - eve_toolbox\ (Quellcode)
    - EVE_Toolbox.exe
    - _internal\
    - version.json, checksums.json, dev_pubkey.pem
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
            for fname in ("version.json", "checksums.json", "dev_pubkey.pem"):
                f = APP_DIR / fname
                if f.exists():
                    z.write(f, f.relative_to(APP_DIR))
                    backed_up += 1

        _log.info(f"Backup erstellt: {BACKUP_ZIP} ({backed_up} Dateien)")
        return True
    except Exception as e:
        _log.error(f"Backup fehlgeschlagen: {e}")
        return False


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
                z.extractall(APP_DIR)

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


# ── Download und Installation ─────────────────────────────────

def download_and_install(info: dict, progress_callback=None) -> tuple[bool, str]:
    """
    Lädt Update herunter und installiert es.

    Erwartete ZIP Struktur:
        eve_toolbox.zip
        ├── EVE_Toolbox.exe
        ├── _internal\
        ├── eve_toolbox\
        ├── version.json
        ├── checksums.json
        └── dev_pubkey.pem
    """
    download_url = info.get("download_zip")
    if not download_url:
        return False, "Kein download_zip in version.json."

    new_version = info.get("version", "?")
    tmp_zip     = BACKUP_DIR / "update_download.zip"

    def _prog(pct):
        if progress_callback:
            progress_callback(pct)

    try:
        _prog(5)

        # ── Download ──────────────────────────────────────────
        _log.info(f"Lade Update v{new_version}: {download_url}")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        req = Request(download_url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=120) as resp:
            total      = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                while chunk := resp.read(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        _prog(5 + int(downloaded / total * 55))

        _log.info(f"Download abgeschlossen: {downloaded} bytes")
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

        # Alte Dateien löschen
        if EVE_TOOLBOX_DIR.exists():
            shutil.rmtree(EVE_TOOLBOX_DIR)
        if INTERNAL_DIR.exists():
            shutil.rmtree(INTERNAL_DIR)
        if EXE_FILE.exists():
            EXE_FILE.unlink()

        # ZIP entpacken
        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(APP_DIR)

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

        # ── checksums.json vom neuen Tag laden ────────────────
        # Vom versionierten Tag damit Integritätscheck sofort stimmt
        tag          = f"v{new_version}"
        checksums_url = (
            f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{GITHUB_REPO}/{tag}/checksums.json"
        )
        _log.info(f"Lade checksums.json von {tag}...")
        checksums_raw = _request(checksums_url)
        if checksums_raw:
            (APP_DIR / "checksums.json").write_bytes(checksums_raw)
            _log.info("checksums.json vom Tag geladen")
        else:
            # Fallback: aus ZIP
            _log.warning("checksums.json von GitHub nicht verfügbar — nutze ZIP-Version")

        _prog(100)
        _log.info(f"Update v{new_version} erfolgreich installiert")
        return True, f"Update auf v{new_version} erfolgreich. Bitte App neu starten."

    except Exception as e:
        _log.error(f"Update fehlgeschlagen: {e}")
        tmp_zip.unlink(missing_ok=True)
        if has_backup():
            _log.info("Versuche Backup wiederherzustellen...")
            restore_backup()
        return False, f"Update fehlgeschlagen: {e}"