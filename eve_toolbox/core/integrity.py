"""
EVE Toolbox — Integritätsprüfung.

Ablauf:
1. Lädt checksums.json von GitHub
2. Berechnet SHA256 für alle lokalen Dateien
3. Vergleicht mit GitHub-Hashes
4. Stellt manipulierte/fehlende Dateien automatisch wieder her
5. Dev-Token vorhanden? → Prüfung wird übersprungen

Dev-Token Erklärung:
    Nur phantombite kann ein gültiges Token erstellen (privater Schlüssel).
    Das Token wird mit generate_dev_token.bat erzeugt.
    Ohne Token läuft immer der volle Check — für alle Nutzer.
"""
from core import logger as _logger
_log = _logger.get("integrity")

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Konfiguration ─────────────────────────────────────────────
GITHUB_USER     = "phantombite"
GITHUB_REPO     = "eve-toolbox"
GITHUB_BRANCH   = "main"

# CHECKSUMS_URL wird zur Laufzeit aus lokaler version.json gebaut
# Damit prüft jede Version gegen ihre eigene checksums.json
# Kein falsches Reparieren wenn neuere Version auf GitHub liegt
CHECKSUMS_URL   = None  # wird in _fetch_checksums() gesetzt

# URL zum öffentlichen Schlüssel für Dev-Token Verifikation
PUBKEY_URL      = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/"
    f"{GITHUB_REPO}/{GITHUB_BRANCH}/dev_pubkey.pem"
)

REQUEST_TIMEOUT = 10

# Lokale Pfade
# APP_DIR = Ordner der die eve_toolbox/ Unterordner enthält
# __file__ = EVE_Toolbox/eve_toolbox/core/integrity.py
# .parent       = core/
# .parent.parent = eve_toolbox/
# .parent.parent.parent = EVE_Toolbox/  <-- das ist APP_DIR
APP_DIR         = Path(__file__).resolve().parent.parent.parent
EVE_DIR         = APP_DIR / "eve_toolbox"
DEV_TOKEN_PATH  = APP_DIR / "dev_mode.flag"

# Dateien die NICHT geprüft werden (Nutzerdaten, Caches etc.)
IGNORE_PATTERNS = {
    "__pycache__",
    ".pyc",
    ".pyo",
    "settings.json",
    "dev_mode.flag",
    ".log",
    "tokens",
    "backup",
}


# ── Ergebnis-Klassen ──────────────────────────────────────────

class IntegrityResult:
    """Ergebnis einer Integritätsprüfung."""

    def __init__(self):
        self.passed        = True    # Alles OK
        self.dev_mode      = False   # Dev-Token gefunden und gültig
        self.offline       = False   # GitHub nicht erreichbar
        self.files_checked = 0       # Anzahl geprüfter Dateien
        self.files_ok      = 0       # Dateien OK
        self.files_fixed   = 0       # Dateien repariert
        self.files_failed  = []      # Dateien die nicht repariert werden konnten
        self.error         = None    # Allgemeiner Fehler (String)

    def __str__(self):
        if self.dev_mode:
            return "Dev-Modus: Integritätsprüfung übersprungen"
        if self.offline:
            return "Offline: Integritätsprüfung nicht möglich"
        if self.error:
            return f"Fehler: {self.error}"
        if self.files_failed:
            return f"FEHLER: {len(self.files_failed)} Datei(en) konnten nicht repariert werden"
        return (f"OK: {self.files_ok}/{self.files_checked} Dateien geprüft"
                + (f", {self.files_fixed} repariert" if self.files_fixed else ""))


# ── Dev-Token Prüfung ─────────────────────────────────────────

def _check_dev_token() -> bool:
    """
    Prüft ob ein gültiges Dev-Token vorhanden ist.
    Token = RSA Signatur der Nachricht "EVEToolbox-DevMode" mit privatem Schlüssel.
    Verifikation mit öffentlichem Schlüssel von GitHub.
    """
    if not DEV_TOKEN_PATH.exists():
        return False

    try:
        # Versuche cryptography zu importieren
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature
        import base64
    except ImportError:
        # cryptography nicht installiert — Token kann nicht geprüft werden
        _log.warning("cryptography nicht installiert — Dev-Token kann nicht geprüft werden")
        return False

    try:
        # Öffentlichen Schlüssel von GitHub laden
        req = Request(PUBKEY_URL, headers={"User-Agent": f"EVE-Toolbox/integrity"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            pubkey_pem = resp.read()

        pubkey = serialization.load_pem_public_key(pubkey_pem)

        # Token lesen (Base64 kodierte Signatur)
        token_b64 = DEV_TOKEN_PATH.read_text(encoding="utf-8").strip()
        signature = base64.b64decode(token_b64)

        # Signatur prüfen
        message = b"EVEToolbox-DevMode"
        pubkey.verify(
            signature,
            message,
            padding.PKCS1v15(),
            hashes.SHA256()
        )

        _log.info("Dev-Token gültig — Integritätsprüfung übersprungen")
        return True

    except InvalidSignature:
        _log.warning("Dev-Token UNGÜLTIG — führe vollen Integritätscheck durch")
        return False
    except Exception as e:
        _log.warning(f"Dev-Token Prüfung fehlgeschlagen: {e} — führe vollen Check durch")
        return False


# ── Checksummen laden ─────────────────────────────────────────

def _fetch_checksums() -> dict | None:
    """
    Lädt checksums.json von GitHub fuer die aktuell installierte Version.
    Verwendet den Git-Tag der lokalen Version damit nicht gegen
    eine neuere Version geprueft wird.
    """
    try:
        # Lokale Version aus version.json lesen
        ver_file = APP_DIR / "version.json"
        if ver_file.exists():
            local_version = json.loads(ver_file.read_text(encoding="utf-8")).get("version", "main")
        else:
            local_version = "main"

        # URL mit Version-Tag bauen
        url = (
            f"https://raw.githubusercontent.com/{GITHUB_USER}/"
            f"{GITHUB_REPO}/v{local_version}/checksums.json"
        )
        _log.debug(f"Lade Checksums fuer v{local_version}: {url}")

        req = Request(url, headers={"User-Agent": f"EVE-Toolbox/integrity"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _log.debug(f"Checksums geladen: {len(data)} Eintraege")
        return data
    except (URLError, HTTPError) as e:
        _log.warning(f"GitHub nicht erreichbar: {e}")
        return None
    except Exception as e:
        _log.error(f"Fehler beim Laden der Checksums: {e}")
        return None


# ── Lokale Datei-Hashes ───────────────────────────────────────

def _hash_file(path: Path) -> str:
    """
    Berechnet SHA256 Hash einer Datei.
    Normalisiert Zeilenenden (CRLF -> LF) fuer Textdateien
    damit Hashes auf Windows und Linux identisch sind.
    Binaerdateien (PNG etc.) werden unveraendert gehasht.
    """
    sha  = hashlib.sha256()
    TEXT = {".py", ".json", ".txt", ".md", ".sh", ".bat", ".iss", ".spec"}
    is_text = path.suffix.lower() in TEXT

    with open(path, "rb") as f:
        data = f.read()

    if is_text:
        data = data.replace(b'\r\n', b'\n')

    sha.update(data)
    return sha.hexdigest()


def _should_ignore(path: Path) -> bool:
    """Gibt True zurück wenn eine Datei nicht geprüft werden soll."""
    path_str = str(path)
    for pattern in IGNORE_PATTERNS:
        if pattern in path_str:
            return True
    return False


def _get_relative_key(path: Path) -> str:
    """
    Gibt den Schlüssel für checksums.json zurück.
    Relativ zu APP_DIR, immer mit Forward-Slashes.
    Beispiel: eve_toolbox/core/config.py
    """
    return str(path.relative_to(APP_DIR)).replace("\\", "/")


# ── Datei von GitHub wiederherstellen ────────────────────────

def _restore_file(rel_key: str, progress_callback=None, version: str = None) -> bool:
    """
    Stellt eine einzelne Datei vom versionierten GitHub Tag wieder her.
    rel_key = z.B. "eve_toolbox/core/config.py"
    version = z.B. "0.4.1" — wird als Tag v0.4.1 genutzt
    """
    # Versionierten Tag nutzen damit immer die richtige Version wiederhergestellt wird
    tag = f"v{version}" if version else GITHUB_BRANCH
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_USER}/"
        f"{GITHUB_REPO}/{tag}/{rel_key}"
    )

    target = APP_DIR / rel_key.replace("/", os.sep)

    try:
        _log.info(f"Stelle wieder her: {rel_key}")
        req = Request(url, headers={"User-Agent": "EVE-Toolbox/integrity"})
        with urlopen(req, timeout=30) as resp:
            content = resp.read()

        # Verzeichnis anlegen falls nötig
        target.parent.mkdir(parents=True, exist_ok=True)

        # Datei schreiben
        target.write_bytes(content)
        _log.info(f"Wiederhergestellt: {rel_key}")
        return True

    except Exception as e:
        _log.error(f"Wiederherstellung fehlgeschlagen für {rel_key}: {e}")
        return False


# ── Hauptfunktion ─────────────────────────────────────────────

def run_check(progress_callback=None) -> IntegrityResult:
    """
    Führt den kompletten Integritätscheck durch.

    progress_callback(percent: int, status: str) — optionaler Fortschritts-Callback

    Ablauf:
    1. Dev-Token prüfen → bei gültigem Token sofort zurück
    2. Checksums von GitHub laden → bei Offline sofort zurück
    3. Alle lokalen Dateien hashen und vergleichen
    4. Manipulierte/fehlende Dateien wiederherstellen
    5. Ergebnis zurückgeben
    """
    result = IntegrityResult()

    def _progress(pct: int, status: str):
        if progress_callback:
            progress_callback(pct, status)

    _log.info("=== Integritätscheck gestartet ===")
    _progress(0, "Starte Integritätscheck...")

    # ── Schritt 1: Dev-Token prüfen ───────────────────────────
    _progress(5, "Prüfe Dev-Token...")
    if _check_dev_token():
        result.dev_mode = True
        _log.info("Dev-Modus aktiv — Check übersprungen")
        _progress(100, "Dev-Modus: Check übersprungen")
        return result

    # ── Schritt 2: Checksums von GitHub laden ─────────────────
    _progress(10, "Lade Prüfsummen von GitHub...")

    # Lokale Version lesen fuer versionierte URLs
    try:
        ver_file = APP_DIR / "version.json"
        local_version = json.loads(ver_file.read_text(encoding="utf-8")).get("version", "main")
    except Exception:
        local_version = "main"
    _log.debug(f"Lokale Version: {local_version}")

    checksums = _fetch_checksums()

    if checksums is None:
        result.offline = True
        _log.warning("Offline — Integritätscheck nicht möglich, fahre fort")
        _progress(100, "Offline — Check übersprungen")
        return result

    # ── Schritt 3: Lokale Dateien prüfen ──────────────────────
    _progress(20, "Prüfe Dateien...")

    # Alle zu prüfenden Dateien aus checksums.json
    files_to_check = list(checksums.keys())
    total          = len(files_to_check)

    if total == 0:
        _log.warning("Keine Dateien in checksums.json — überspringe")
        _progress(100, "Keine Prüfsummen vorhanden")
        return result

    corrupted = []   # Liste der manipulierten/fehlenden Dateien

    for i, rel_key in enumerate(files_to_check):
        pct = 20 + int(i / total * 50)
        _progress(pct, f"Prüfe {rel_key.split('/')[-1]}...")

        expected_hash = checksums[rel_key]
        local_path    = APP_DIR / rel_key.replace("/", os.sep)

        result.files_checked += 1

        if not local_path.exists():
            _log.warning(f"FEHLT: {rel_key}")
            corrupted.append(rel_key)
            continue

        if _should_ignore(local_path):
            result.files_ok += 1
            continue

        actual_hash = _hash_file(local_path)

        if actual_hash != expected_hash:
            _log.warning(f"MANIPULIERT: {rel_key}")
            _log.debug(f"  Erwartet:  {expected_hash}")
            _log.debug(f"  Gefunden:  {actual_hash}")
            corrupted.append(rel_key)
        else:
            result.files_ok += 1

    # ── Schritt 4: Manipulierte Dateien wiederherstellen ──────
    if corrupted:
        _log.info(f"{len(corrupted)} Datei(en) werden wiederhergestellt...")
        result.passed = False

        for i, rel_key in enumerate(corrupted):
            pct = 70 + int(i / len(corrupted) * 25)
            _progress(pct, f"Repariere {rel_key.split('/')[-1]}...")

            if _restore_file(rel_key, version=local_version):
                result.files_fixed += 1
                result.files_ok    += 1
                _log.info(f"Repariert: {rel_key}")
            else:
                result.files_failed.append(rel_key)
                _log.error(f"Konnte nicht reparieren: {rel_key}")

        # Wenn alle repariert: passed wieder True
        if not result.files_failed:
            result.passed = True
            _log.info("Alle Dateien erfolgreich repariert")
        else:
            _log.error(f"{len(result.files_failed)} Datei(en) konnten nicht repariert werden")
    else:
        _log.info("Alle Dateien OK")

    _progress(100, str(result))
    _log.info(f"=== Integritätscheck abgeschlossen: {result} ===")
    return result


# ── Checksummen generieren (lokal, für phantombite) ──────────

def generate_checksums(output_path: Path = None) -> dict:
    """
    Generiert checksums.json für alle Dateien in eve_toolbox/.
    Wird von generate_checksums.bat aufgerufen.
    Nur phantombite führt das aus — die Datei kommt dann auf GitHub.
    """
    if output_path is None:
        output_path = APP_DIR / "checksums.json"

    checksums = {}
    files     = sorted(EVE_DIR.rglob("*"))

    for f in files:
        if not f.is_file():
            continue
        if _should_ignore(f):
            continue

        rel_key            = _get_relative_key(f)
        checksums[rel_key] = _hash_file(f)

    # Auch version.json einschließen
    version_file = APP_DIR / "version.json"
    if version_file.exists():
        checksums[_get_relative_key(version_file)] = _hash_file(version_file)

    output_path.write_text(
        json.dumps(checksums, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"checksums.json erstellt: {len(checksums)} Dateien")
    return checksums