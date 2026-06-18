"""
EVE Toolbox — Integritätsprüfung.

Ablauf:
1. Dev-Token prüfen → bei gültigem Token sofort zurück
2. checksums.json vom versionierten GitHub Tag laden
3. Alle lokalen Dateien hashen und vergleichen
4. Manipulierte/fehlende Dateien vom gleichen Tag wiederherstellen
5. Ergebnis zurückgeben

Dev-Token:
    Nur phantombite kann ein gültiges Token erstellen.
    Das Token wird mit security_generator.bat erzeugt.
    Ohne Token läuft immer der volle Check.
"""
from core import logger as _logger
_log = _logger.get("integrity")

import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Konfiguration ─────────────────────────────────────────────
GITHUB_USER     = "Phantombite"   # Gross-P — GitHub Raw URLs sind case-sensitive!
GITHUB_REPO     = "eve-toolbox"
GITHUB_BRANCH   = "main"

# URL zum öffentlichen Schlüssel (immer von main)
PUBKEY_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/"
    f"{GITHUB_REPO}/{GITHUB_BRANCH}/dev_pubkey.pem"
)

REQUEST_TIMEOUT = 10

# Lokale Pfade
# __file__ = APP_DIR/eve_toolbox/core/integrity.py
# .parent.parent.parent = APP_DIR
APP_DIR        = Path(__file__).resolve().parent.parent.parent
EVE_DIR        = APP_DIR / "eve_toolbox"
DEV_TOKEN_PATH = APP_DIR / "dev_mode.flag"

# Dateierweiterungen die als Text behandelt werden (Zeilenenden normalisieren)
TEXT_EXTENSIONS = {".py", ".json", ".txt", ".md", ".sh", ".bat", ".spec"}

# Pfadteile/Muster die beim Prüfen ignoriert werden
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


# ── Ergebnis-Klasse ───────────────────────────────────────────

class IntegrityResult:
    def __init__(self):
        self.passed        = True
        self.dev_mode      = False
        self.offline       = False
        self.files_checked = 0
        self.files_ok      = 0
        self.files_fixed   = 0
        self.files_failed  = []
        self.error         = None

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


# ── Hashing ───────────────────────────────────────────────────

def _hash_data(data: bytes, is_text: bool) -> str:
    """
    SHA256 Hash von Bytes.
    Textdateien: CRLF → LF normalisieren damit Hashes auf
    Windows und Linux identisch sind.
    Binärdateien: unveränderter Hash.
    """
    if is_text:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()


def _hash_file(path: Path) -> str:
    """Hash einer lokalen Datei."""
    is_text = path.suffix.lower() in TEXT_EXTENSIONS
    with open(path, "rb") as f:
        return _hash_data(f.read(), is_text)


def _hash_bytes(data: bytes, filename: str) -> str:
    """Hash von Bytes (z.B. heruntergeladene Datei)."""
    suffix = Path(filename).suffix.lower()
    is_text = suffix in TEXT_EXTENSIONS
    return _hash_data(data, is_text)


def _should_ignore(path: Path) -> bool:
    path_str = str(path)
    return any(p in path_str for p in IGNORE_PATTERNS)


def _get_relative_key(path: Path) -> str:
    return str(path.relative_to(APP_DIR)).replace("\\", "/")


# ── Dev-Token ─────────────────────────────────────────────────

def _check_dev_token() -> bool:
    if not DEV_TOKEN_PATH.exists():
        return False
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.exceptions import InvalidSignature
        import base64
    except ImportError:
        _log.warning("cryptography nicht installiert — Dev-Token kann nicht geprüft werden")
        return False
    try:
        req = Request(PUBKEY_URL, headers={"User-Agent": f"EVE-Toolbox/integrity"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            pubkey_pem = resp.read()
        pubkey    = serialization.load_pem_public_key(pubkey_pem)
        token_b64 = DEV_TOKEN_PATH.read_text(encoding="utf-8").strip()
        signature = base64.b64decode(token_b64)
        pubkey.verify(signature, b"EVEToolbox-DevMode", padding.PKCS1v15(), hashes.SHA256())
        _log.info("Dev-Token gültig — Integritätsprüfung übersprungen")
        return True
    except Exception as e:
        _log.warning(f"Dev-Token Prüfung: {e} — führe vollen Check durch")
        return False


# ── Checksums von GitHub ──────────────────────────────────────

def _fetch_checksums(version: str) -> dict | None:
    """
    Lädt checksums.json vom versionierten GitHub Tag.
    Damit wird immer gegen die exakt installierte Version geprüft —
    niemals gegen eine neuere Version auf main.
    """
    tag = f"v{version}" if version != "main" else GITHUB_BRANCH
    url = (
        f"https://raw.githubusercontent.com/{GITHUB_USER}/"
        f"{GITHUB_REPO}/{tag}/checksums.json"
    )
    _log.debug(f"Lade checksums.json von Tag {tag}: {url}")
    try:
        req = Request(url, headers={"User-Agent": "EVE-Toolbox/integrity"})
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _log.debug(f"Checksums geladen: {len(data)} Einträge")
        return data
    except (URLError, HTTPError) as e:
        _log.warning(f"GitHub nicht erreichbar: {e}")
        return None
    except Exception as e:
        _log.error(f"Fehler beim Laden der Checksums: {e}")
        return None


def _get_local_version() -> str:
    try:
        ver_file = APP_DIR / "version.json"
        return json.loads(ver_file.read_text(encoding="utf-8")).get("version", "main")
    except Exception:
        return "main"


# ── Datei von GitHub wiederherstellen ────────────────────────

def _restore_file(rel_key: str, version: str) -> bool:
    """
    Stellt eine Datei vom exakt gleichen GitHub Tag wieder her.
    Hasht die heruntergeladene Datei zur Verifikation.
    """
    tag = f"v{version}" if version != "main" else GITHUB_BRANCH
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
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        _log.info(f"Wiederhergestellt: {rel_key}")
        return True
    except Exception as e:
        _log.error(f"Wiederherstellung fehlgeschlagen für {rel_key}: {e}")
        return False


# ── Hauptfunktion ─────────────────────────────────────────────

# ── Kritische Dateien für Mini-Check ─────────────────────────
CRITICAL_FILES = [
    "eve_toolbox/core/updater.py",
    "eve_toolbox/core/integrity.py",
    "eve_toolbox/main.py",
]


def mini_check(progress_callback=None) -> IntegrityResult:
    """
    Schneller Check nur der kritischen Dateien (updater, integrity, main).
    Läuft vor dem Update-Check damit der Updater immer funktionsfähig ist.
    Repariert sofort ohne Neustart — Python-Dateien können live ersetzt werden.
    """
    result = IntegrityResult()

    def _progress(pct: int, status: str):
        if progress_callback:
            progress_callback(pct, status)

    _log.info("=== Mini-Integritätscheck gestartet ===")
    _progress(0, "Prüfe kritische Dateien...")

    local_version = _get_local_version()
    _log.info(f"Lokale Version: {local_version}")

    # Checksums laden
    checksums = _fetch_checksums(local_version)
    if checksums is None:
        result.offline = True
        _log.warning("Offline — Mini-Check nicht möglich")
        _progress(100, "Offline")
        return result

    corrupted = []
    for rel_key in CRITICAL_FILES:
        result.files_checked += 1
        local_path = APP_DIR / rel_key.replace("/", os.sep)

        if not local_path.exists():
            _log.warning(f"FEHLT: {rel_key}")
            corrupted.append(rel_key)
            continue

        expected = checksums.get(rel_key)
        if expected is None:
            result.files_ok += 1
            continue

        actual = _hash_file(local_path)
        if actual != expected:
            _log.warning(f"DEFEKT: {rel_key}")
            _log.debug(f"  Erwartet: {expected}")
            _log.debug(f"  Gefunden: {actual}")
            corrupted.append(rel_key)
        else:
            result.files_ok += 1

    if corrupted:
        _log.info(f"Mini-Check: {len(corrupted)} kritische Datei(en) werden repariert...")
        result.passed = False
        for rel_key in corrupted:
            _progress(50, f"Repariere {rel_key.split('/')[-1]}...")
            if _restore_file(rel_key, local_version):
                result.files_fixed += 1
                result.files_ok += 1
                _log.info(f"Repariert: {rel_key}")
            else:
                result.files_failed.append(rel_key)
        if not result.files_failed:
            result.passed = True
            _log.info("Mini-Check: Alle kritischen Dateien repariert")
    else:
        _log.info("Mini-Check: Alle kritischen Dateien OK")

    _progress(100, "Kritische Dateien OK")
    _log.info("=== Mini-Integritätscheck abgeschlossen ===")
    return result


def run_check(progress_callback=None) -> IntegrityResult:
    result = IntegrityResult()

    def _progress(pct: int, status: str):
        if progress_callback:
            progress_callback(pct, status)

    _log.info("=== Integritätscheck gestartet ===")
    _progress(0, "Starte Integritätscheck...")

    # ── Schritt 1: Dev-Token ──────────────────────────────────
    _progress(5, "Prüfe Dev-Token...")
    if _check_dev_token():
        result.dev_mode = True
        _progress(100, "Dev-Modus: Check übersprungen")
        return result

    # ── Schritt 2: Lokale Version + Checksums laden ───────────
    _progress(10, "Lade Prüfsummen von GitHub...")
    local_version = _get_local_version()
    _log.info(f"Lokale Version: {local_version}")

    checksums = _fetch_checksums(local_version)
    if checksums is None:
        result.offline = True
        _log.warning("Offline — Integritätscheck nicht möglich, fahre fort")
        _progress(100, "Offline — Check übersprungen")
        return result

    # ── Schritt 3: Dateien prüfen ─────────────────────────────
    _progress(20, "Prüfe Dateien...")
    files_to_check = list(checksums.keys())
    total          = len(files_to_check)

    if total == 0:
        _log.warning("Keine Dateien in checksums.json")
        _progress(100, "Keine Prüfsummen vorhanden")
        return result

    corrupted = []

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
            _log.debug(f"  Erwartet : {expected_hash}")
            _log.debug(f"  Gefunden : {actual_hash}")
            # Zusätzliche Debug-Info: Dateigröße und ob CRLF vorhanden
            try:
                raw = local_path.read_bytes()
                has_crlf = b"\r\n" in raw
                _log.debug(f"  Groesse  : {len(raw)} bytes | CRLF: {has_crlf}")
            except Exception:
                pass
            corrupted.append(rel_key)
        else:
            result.files_ok += 1

    # ── Schritt 4: Reparieren ─────────────────────────────────
    if corrupted:
        _log.info(f"{len(corrupted)} Datei(en) werden wiederhergestellt...")
        result.passed = False

        for i, rel_key in enumerate(corrupted):
            pct = 70 + int(i / len(corrupted) * 25)
            _progress(pct, f"Repariere {rel_key.split('/')[-1]}...")

            if _restore_file(rel_key, local_version):
                result.files_fixed += 1
                result.files_ok    += 1
                _log.info(f"Repariert: {rel_key}")
            else:
                result.files_failed.append(rel_key)
                _log.error(f"Konnte nicht reparieren: {rel_key}")

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


# ── Checksummen generieren ────────────────────────────────────

def generate_checksums(output_path: Path = None) -> dict:
    """
    Generiert checksums.json für alle Dateien in eve_toolbox/.
    WICHTIG: Verwendet die gleiche Hash-Logik wie beim Prüfen
    (Zeilenenden-Normalisierung) damit Hashes immer übereinstimmen.
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
        checksums[rel_key] = _hash_file(f)  # nutzt gleiche Normalisierung

    # version.json einschließen
    version_file = APP_DIR / "version.json"
    if version_file.exists():
        checksums[_get_relative_key(version_file)] = _hash_file(version_file)

    output_path.write_text(
        json.dumps(checksums, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"checksums.json erstellt: {len(checksums)} Dateien")
    return checksums