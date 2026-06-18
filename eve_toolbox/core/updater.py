"""
Update-System — prüft GitHub, installiert Updates, verwaltet Backup.

Ablauf eines Updates:
1. version.json von GitHub laden und mit lokaler Version vergleichen
2. Bei neuer Version: Backup der aktuellen Installation erstellen
3. ZIP von GitHub Release herunterladen
4. ZIP entpacken und eve_toolbox/ ersetzen
5. checksums.json von GitHub neu laden (damit Integritätscheck stimmt)
6. Neustart empfehlen

ZIP Struktur auf GitHub Release muss sein:
    eve_toolbox.zip
    └── eve_toolbox/
        ├── main.py
        ├── core/
        ├── ui/
        └── ...
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
GITHUB_USER     = "Phantombite"
GITHUB_REPO     = "eve-toolbox"
GITHUB_BRANCH   = "main"

VERSION_URL     = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/version.json"
CHECKSUMS_URL   = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/checksums.json"

REQUEST_TIMEOUT = 10

# ── Lokale Pfade ──────────────────────────────────────────────
# __file__ = EVE_Toolbox/eve_toolbox/core/updater.py
# .parent        = core/
# .parent.parent = eve_toolbox/
# .parent.parent.parent = EVE_Toolbox/  ← APP_DIR
APP_DIR         = Path(__file__).resolve().parent.parent.parent
EVE_TOOLBOX_DIR = APP_DIR / "eve_toolbox"
BACKUP_DIR      = Path.home() / ".eve_toolbox" / "backup"
BACKUP_ZIP      = BACKUP_DIR / "previous_version.zip"
SETTINGS_FILE   = Path.home() / ".eve_toolbox" / "settings.json"


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except Exception:
        return (0, 0, 0)


def _request(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes | None:
    """Einfacher GET Request. Gibt bytes oder None zurück."""
    try:
        req = Request(url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except Exception as e:
        _log.warning(f"Request fehlgeschlagen ({url}): {e}")
        return None


# ── Update prüfen ─────────────────────────────────────────────

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
    """Synchroner Check — blockiert kurz. Für Splash Screen."""
    try:
        data = _fetch_version_info()
        if data and _parse_version(data.get("version", "0.0.0")) > _parse_version(APP_VERSION):
            return data
        return None
    except Exception:
        return None


def get_remote_version() -> str | None:
    """Gibt nur die Remote-Versionsnummer zurück oder None."""
    try:
        data = _fetch_version_info()
        return data.get("version") if data else None
    except Exception:
        return None


def _fetch_version_info() -> dict | None:
    """Lädt version.json von GitHub."""
    raw = _request(VERSION_URL)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception as e:
        _log.error(f"version.json konnte nicht gelesen werden: {e}")
        return None


# ── Backup ────────────────────────────────────────────────────

def has_backup() -> bool:
    return BACKUP_ZIP.exists()


def get_backup_version() -> str | None:
    """Liest die Version aus dem Backup-ZIP."""
    if not BACKUP_ZIP.exists():
        return None
    try:
        with zipfile.ZipFile(BACKUP_ZIP, "r") as z:
            names = z.namelist()
            # version.json im Backup suchen
            ver_file = next((n for n in names if n.endswith("version.json")), None)
            if ver_file:
                data = json.loads(z.read(ver_file).decode("utf-8"))
                return data.get("version")
    except Exception:
        pass
    return "Unbekannt"


def create_backup() -> bool:
    """Sichert aktuelle Installation als ZIP. Überschreibt vorheriges Backup."""
    try:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        if not EVE_TOOLBOX_DIR.exists():
            _log.warning("eve_toolbox Ordner nicht gefunden — kein Backup erstellt")
            return False

        with zipfile.ZipFile(BACKUP_ZIP, "w", zipfile.ZIP_DEFLATED) as z:
            # eve_toolbox/ sichern
            for file in EVE_TOOLBOX_DIR.rglob("*"):
                if file.is_file() and "__pycache__" not in str(file):
                    z.write(file, file.relative_to(APP_DIR))
            # version.json sichern
            ver = APP_DIR / "version.json"
            if ver.exists():
                z.write(ver, ver.relative_to(APP_DIR))

        _log.info(f"Backup erstellt: {BACKUP_ZIP}")
        return True
    except Exception as e:
        _log.error(f"Backup fehlgeschlagen: {e}")
        return False


def restore_backup() -> tuple[bool, str]:
    """
    Stellt vorherige Version wieder her.
    Gibt (success, message) zurück.
    """
    if not BACKUP_ZIP.exists():
        return False, "Kein Backup vorhanden."
    try:
        # Temporäre Sicherung der aktuellen Version
        tmp = BACKUP_DIR / "restore_tmp"
        if tmp.exists():
            shutil.rmtree(tmp)
        if EVE_TOOLBOX_DIR.exists():
            shutil.copytree(EVE_TOOLBOX_DIR, tmp)

        try:
            # Backup einspielen
            if EVE_TOOLBOX_DIR.exists():
                shutil.rmtree(EVE_TOOLBOX_DIR)
            with zipfile.ZipFile(BACKUP_ZIP, "r") as z:
                z.extractall(APP_DIR)

            shutil.rmtree(tmp, ignore_errors=True)
            _log.info("Backup wiederhergestellt")
            return True, "Vorherige Version wurde wiederhergestellt. Bitte App neu starten."

        except Exception as e:
            # Rollback
            _log.error(f"Wiederherstellung fehlgeschlagen, mache Rollback: {e}")
            if tmp.exists():
                if EVE_TOOLBOX_DIR.exists():
                    shutil.rmtree(EVE_TOOLBOX_DIR)
                shutil.copytree(tmp, EVE_TOOLBOX_DIR)
            return False, f"Fehler beim Wiederherstellen: {e}"

    except Exception as e:
        return False, f"Fehler: {e}"


# ── Download und Installation ─────────────────────────────────

def download_and_install(info: dict, progress_callback=None) -> tuple[bool, str]:
    """
    Lädt Update herunter und installiert es.
    progress_callback(percent: int) optional.
    Gibt (success, message) zurück.

    Erwartete ZIP Struktur:
        eve_toolbox/
            main.py
            core/
            ui/
            ...
    """
    download_url = info.get("download_zip")
    if not download_url:
        _log.error("Kein download_zip in version.json")
        return False, "Kein Download-Link in version.json gefunden."

    new_version = info.get("version", "?")
    tmp_zip     = BACKUP_DIR / "update_download.zip"

    try:
        # ── Schritt 1: Backup (wird von main.py erledigt) ───
        # Kein doppeltes Backup hier
        if progress_callback: progress_callback(15)

        # ── Schritt 2: Download ──────────────────────────────
        _log.info(f"Lade Update v{new_version} herunter: {download_url}")
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        req = Request(download_url, headers={"User-Agent": f"EVE-Toolbox/{APP_VERSION}"})
        with urlopen(req, timeout=60) as resp:
            total      = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(tmp_zip, "wb") as f:
                while chunk := resp.read(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total and progress_callback:
                        pct = 15 + int(downloaded / total * 50)
                        progress_callback(pct)

        if progress_callback: progress_callback(65)
        _log.info(f"Download abgeschlossen: {downloaded} bytes")

        # ── Schritt 3: ZIP prüfen ────────────────────────────
        if not zipfile.is_zipfile(tmp_zip):
            tmp_zip.unlink(missing_ok=True)
            return False, "Heruntergeladene Datei ist kein gültiges ZIP."

        # Prüfen ob eve_toolbox/ im ZIP enthalten ist
        with zipfile.ZipFile(tmp_zip, "r") as z:
            names = z.namelist()
            has_eve_dir = any(n.startswith("eve_toolbox/") for n in names)
            if not has_eve_dir:
                tmp_zip.unlink(missing_ok=True)
                return False, "ZIP enthält keinen eve_toolbox/ Ordner — falsches Format."

        if progress_callback: progress_callback(70)

        # ── Schritt 4: Installieren ──────────────────────────
        _log.info("Installiere Update...")
        if EVE_TOOLBOX_DIR.exists():
            shutil.rmtree(EVE_TOOLBOX_DIR)

        with zipfile.ZipFile(tmp_zip, "r") as z:
            z.extractall(APP_DIR)

        tmp_zip.unlink(missing_ok=True)
        if progress_callback: progress_callback(85)

        # ── Schritt 5: version.json aktualisieren ────────────
        ver_file = APP_DIR / "version.json"
        ver_file.write_text(
            json.dumps({
                "version":      new_version,
                "notes":        info.get("notes", ""),
                "download_zip": download_url,
            }, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        _log.info(f"version.json auf v{new_version} aktualisiert")

        # ── Schritt 6: Neue checksums.json von GitHub laden ──
        _log.info("Lade neue checksums.json von GitHub...")
        checksums_raw = _request(CHECKSUMS_URL)
        if checksums_raw:
            checksums_file = APP_DIR / "checksums.json"
            checksums_file.write_bytes(checksums_raw)
            _log.info("checksums.json aktualisiert")
        else:
            _log.warning("checksums.json konnte nicht geladen werden — Integritätscheck beim nächsten Start möglicherweise fehlerhaft")

        if progress_callback: progress_callback(100)
        _log.info(f"Update v{new_version} erfolgreich installiert")
        return True, f"Update auf v{new_version} erfolgreich. Bitte App neu starten."

    except Exception as e:
        _log.error(f"Update fehlgeschlagen: {e}")
        tmp_zip.unlink(missing_ok=True)

        # Versuche Backup wiederherzustellen
        if has_backup():
            _log.info("Versuche Backup wiederherzustellen...")
            restore_backup()

        return False, f"Update fehlgeschlagen: {e}"