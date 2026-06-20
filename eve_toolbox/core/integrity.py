"""
EVE Toolbox — Integritätsprüfung (reiner Prüfer, keine Reparatur).

Architektur (Block 2 — Vertrauenskette unabhängig von GitHub):
    GitHub ist nur noch Transportmedium, kein Vertrauensanker.
    1. checksums.json + checksums.json.sig + release_cert.json vom
       versionierten Tag laden
    2. release_cert.json gegen den fest eingebetteten ROOT Public Key
       prüfen (core.release_crypto.TRUSTED_PUBLIC_KEYS_PEM) — liefert
       den vom Root autorisierten Release Key
    3. checksums.json.sig gegen GENAU diesen Release Key prüfen —
       BEVOR irgendein Datei-Hash verglichen wird
    4. Erst bei gültiger zweistufiger Signatur: lokale Dateien hashen
       und vergleichen
    5. Ergebnis (welche Dateien fehlen/abweichen) wird zurückgegeben —
       integrity.py reparariert selbst NICHTS mehr. Das übernimmt
       ausschließlich core.updater.repair_files(), aufgerufen von main.py.

Verantwortungstrennung (Punkt 3 der Roadmap):
    integrity.py  → weiß "was ist los" (fehlt / manipuliert / ok)
    updater.py    → bekommt nur Aufträge ("installiere X", "stelle Y wieder her")
    main.py       → entscheidet anhand des IntegrityResult, ob updater.py
                    aufgerufen wird

Dev-Token:
    Nutzt core.release_crypto.verify_dev_token() — dieselbe Root→Release
    Vertrauenskette wie für Release-Signaturen, aber als eigenständige
    Funktion (ein Dev-Token bedeutet etwas anderes als eine gültige
    Release-Signatur, auch wenn der kryptographische Unterbau identisch
    ist). Läuft komplett offline, kein Netzwerkzugriff nötig.
"""
from core import logger as _logger
_log = _logger.get("integrity")

import hashlib
import json
import os
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from core import release_crypto as _crypto

# ── Konfiguration ─────────────────────────────────────────────
GITHUB_USER     = "Phantombite"   # Gross-P — GitHub Raw URLs sind case-sensitive!
GITHUB_REPO     = "eve-toolbox"
GITHUB_BRANCH   = "main"

REQUEST_TIMEOUT = 10

# Lokale Pfade
# __file__ = APP_DIR/eve_toolbox/core/integrity.py
# .parent.parent.parent = APP_DIR
APP_DIR        = Path(__file__).resolve().parent.parent.parent
EVE_DIR        = APP_DIR / "eve_toolbox"
DEV_TOKEN_PATH = APP_DIR / "dev_mode.flag"
RELEASE_CERT_PATH = APP_DIR / _crypto.RELEASE_CERT_FILENAME

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
    "data",  # Vault-Ordner (Salt + verschlüsselte Account-Daten) — Nutzerdaten, kein Programmcode
    "_embed_pubkey.py",  # Reines Build-Tool für security_generator.bat, kein App-Code
    ".bak",
}


# ── Ergebnis-Klasse ───────────────────────────────────────────

class IntegrityResult:
    """
    Reines Diagnose-Ergebnis. Enthält KEINE Reparatur-Aktionen mehr —
    nur die Liste der betroffenen Dateien (missing_files / corrupted_files),
    die main.py bei Bedarf an core.updater.repair_files() weitergibt.
    """
    def __init__(self):
        self.passed          = True
        self.dev_mode        = False
        self.offline         = False
        self.signature_valid = None  # None = nicht geprüft, True/False = Ergebnis
        self.files_checked   = 0
        self.files_ok        = 0
        self.missing_files   = []   # Dateien, die lokal fehlen
        self.corrupted_files = []   # Dateien, deren Hash nicht passt
        self.error           = None

    @property
    def needs_repair(self) -> bool:
        return bool(self.missing_files or self.corrupted_files)

    def __str__(self):
        if self.dev_mode:
            return "Dev-Modus: Integritätsprüfung übersprungen"
        if self.offline:
            return "Offline: Integritätsprüfung nicht möglich"
        if self.signature_valid is False:
            return "FEHLER: Signatur von checksums.json ungültig — Prüfung abgebrochen"
        if self.error:
            return f"Fehler: {self.error}"
        if self.needs_repair:
            n = len(self.missing_files) + len(self.corrupted_files)
            return f"PRÜFUNG: {n} Datei(en) benötigen Reparatur"
        return f"OK: {self.files_ok}/{self.files_checked} Dateien geprüft"


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


def _should_ignore(path: Path) -> bool:
    path_str = str(path)
    return any(p in path_str for p in IGNORE_PATTERNS)


def _get_relative_key(path: Path) -> str:
    return str(path.relative_to(APP_DIR)).replace("\\", "/")


# ── Dev-Token ─────────────────────────────────────────────────

def check_dev_token() -> bool:
    """
    Prüft den lokalen Dev-Token über core.release_crypto — komplett
    offline, kein Netzwerkzugriff mehr nötig. Zweistufig: zuerst wird
    release_cert.json gegen den im Programmcode eingebetteten Root Key
    geprüft (release_crypto.TRUSTED_PUBLIC_KEYS_PEM), danach der
    Dev-Token gegen den im Zertifikat autorisierten Release Key.
    """
    if not DEV_TOKEN_PATH.exists():
        return False
    if not RELEASE_CERT_PATH.exists():
        _log.warning("release_cert.json fehlt — Dev-Token kann nicht geprüft werden")
        return False
    try:
        token_b64 = DEV_TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception as e:
        _log.warning(f"Dev-Token konnte nicht gelesen werden: {e}")
        return False

    valid = _crypto.verify_dev_token(token_b64, RELEASE_CERT_PATH)
    if valid:
        _log.info("Dev-Token gültig — Integritätsprüfung übersprungen")
    else:
        _log.warning("Dev-Token ungültig — führe vollen Check durch")
    return valid


# ── Checksums von GitHub laden + Signatur prüfen ──────────────

def _fetch_bytes(url: str, timeout: int = REQUEST_TIMEOUT) -> bytes | None:
    try:
        req = Request(url, headers={"User-Agent": "EVE-Toolbox/integrity"})
        with urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (URLError, HTTPError) as e:
        _log.warning(f"GitHub nicht erreichbar ({url}): {e}")
        return None
    except Exception as e:
        _log.error(f"Fehler beim Laden von {url}: {e}")
        return None


def _fetch_checksums_with_signature(version: str) -> tuple[dict | None, bool]:
    """
    Lädt checksums.json, checksums.json.sig UND release_cert.json vom
    versionierten GitHub Tag, prüft die zweistufige Signatur (Root
    autorisiert Release Key, Release Key signiert checksums.json) BEVOR
    die Datei überhaupt als JSON benutzt wird. Gibt
    (checksums_dict_oder_None, signature_war_gueltig) zurück.

    Reihenfolge ist hier bewusst strikt: Wird irgendeine der drei
    Dateien nicht gefunden oder ist die Kette ungültig, wird
    checksums.json NICHT geparst oder verwendet.
    """
    tag = f"v{version}" if version != "main" else GITHUB_BRANCH
    base = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{tag}"

    checksums_raw = _fetch_bytes(f"{base}/checksums.json")
    if checksums_raw is None:
        return None, False

    sig_raw = _fetch_bytes(f"{base}/checksums.json.sig")
    if sig_raw is None:
        _log.warning("checksums.json.sig nicht erreichbar — Signatur kann nicht geprüft werden")
        return None, False

    cert_raw = _fetch_bytes(f"{base}/{_crypto.RELEASE_CERT_FILENAME}")
    if cert_raw is None:
        _log.warning("release_cert.json nicht erreichbar — Release Key kann nicht autorisiert werden")
        return None, False

    signature_b64 = sig_raw.decode("utf-8").strip()
    if not _crypto.verify_release_signature(checksums_raw, signature_b64, cert_bytes=cert_raw):
        _log.error("checksums.json: Signatur UNGÜLTIG — wird verworfen, nicht verwendet")
        return None, False

    try:
        data = json.loads(checksums_raw.decode("utf-8"))
    except Exception as e:
        _log.error(f"checksums.json (signiert, aber kein gültiges JSON): {e}")
        return None, True  # Signatur war gültig, aber Inhalt kaputt — getrennt gemeldet

    _log.debug(f"checksums.json signiert + geladen: {len(data)} Einträge")
    return data, True


def get_local_version() -> str:
    try:
        ver_file = APP_DIR / "version.json"
        return json.loads(ver_file.read_text(encoding="utf-8")).get("version", "main")
    except Exception:
        return "main"


# ── Kritische Dateien für Mini-Check ─────────────────────────
CRITICAL_FILES = [
    "eve_toolbox/core/updater.py",
    "eve_toolbox/core/integrity.py",
    "eve_toolbox/core/release_crypto.py",
    "eve_toolbox/main.py",
]


def mini_check(progress_callback=None) -> IntegrityResult:
    """
    Schneller Check nur der kritischen Dateien (updater, integrity,
    release_crypto, main). Läuft vor dem Update-Check damit der Updater
    immer funktionsfähig ist. Meldet nur — reparariert NICHT mehr selbst
    (siehe Moduldocstring). main.py entscheidet, ob core.updater.
    repair_files() mit dem Ergebnis aufgerufen wird.
    """
    result = IntegrityResult()

    def _progress(pct: int, status: str):
        if progress_callback:
            progress_callback(pct, status)

    _log.info("=== Mini-Integritätscheck gestartet ===")
    _progress(0, "Prüfe kritische Dateien...")

    local_version = get_local_version()
    _log.info(f"Lokale Version: {local_version}")

    checksums, sig_ok = _fetch_checksums_with_signature(local_version)
    result.signature_valid = sig_ok

    if checksums is None:
        if sig_ok:
            # Signatur war gültig, aber Inhalt unbrauchbar — echter Fehler
            result.error = "checksums.json signiert, aber Inhalt ungültig"
        else:
            result.offline = True
            _log.warning("Offline oder Signatur ungültig — Mini-Check nicht möglich")
        _progress(100, "Offline" if result.offline else "Fehler")
        return result

    for rel_key in CRITICAL_FILES:
        result.files_checked += 1
        local_path = APP_DIR / rel_key.replace("/", os.sep)

        if not local_path.exists():
            _log.warning(f"FEHLT: {rel_key}")
            result.missing_files.append(rel_key)
            continue

        expected = checksums.get(rel_key)
        if expected is None:
            result.files_ok += 1
            continue

        actual = _hash_file(local_path)
        if actual != expected:
            _log.warning(f"DEFEKT: {rel_key}")
            result.corrupted_files.append(rel_key)
        else:
            result.files_ok += 1

    result.passed = not result.needs_repair
    _progress(100, str(result))
    _log.info(f"=== Mini-Integritätscheck abgeschlossen: {result} ===")
    return result


def run_check(progress_callback=None) -> IntegrityResult:
    """
    Vollständiger Check aller Dateien in checksums.json. Reine Diagnose —
    siehe Moduldocstring zur Verantwortungstrennung.
    """
    result = IntegrityResult()

    def _progress(pct: int, status: str):
        if progress_callback:
            progress_callback(pct, status)

    _log.info("=== Integritätscheck gestartet ===")
    _progress(0, "Starte Integritätscheck...")

    # ── Schritt 1: Dev-Token ──────────────────────────────────
    _progress(5, "Prüfe Dev-Token...")
    if check_dev_token():
        result.dev_mode = True
        _progress(100, "Dev-Modus: Check übersprungen")
        return result

    # ── Schritt 2: Checksums + Signatur laden ─────────────────
    _progress(10, "Lade signierte Prüfsummen...")
    local_version = get_local_version()
    _log.info(f"Lokale Version: {local_version}")

    checksums, sig_ok = _fetch_checksums_with_signature(local_version)
    result.signature_valid = sig_ok

    if checksums is None:
        if sig_ok:
            result.error = "checksums.json signiert, aber Inhalt ungültig"
            _log.error(result.error)
        else:
            result.offline = True
            _log.warning("Offline oder Signatur ungültig — Integritätscheck nicht möglich, fahre fort")
        _progress(100, "Offline — Check übersprungen" if result.offline else "Fehler")
        return result

    # ── Schritt 3: Dateien prüfen ─────────────────────────────
    _progress(20, "Prüfe Dateien...")
    files_to_check = list(checksums.keys())
    total          = len(files_to_check)

    if total == 0:
        _log.warning("Keine Dateien in checksums.json")
        _progress(100, "Keine Prüfsummen vorhanden")
        return result

    for i, rel_key in enumerate(files_to_check):
        pct = 20 + int(i / total * 75)
        _progress(pct, f"Prüfe {rel_key.split('/')[-1]}...")

        expected_hash = checksums[rel_key]
        local_path    = APP_DIR / rel_key.replace("/", os.sep)
        result.files_checked += 1

        if not local_path.exists():
            _log.warning(f"FEHLT: {rel_key}")
            result.missing_files.append(rel_key)
            continue

        if _should_ignore(local_path):
            result.files_ok += 1
            continue

        actual_hash = _hash_file(local_path)

        if actual_hash != expected_hash:
            _log.warning(f"MANIPULIERT: {rel_key}")
            _log.debug(f"  Erwartet : {expected_hash}")
            _log.debug(f"  Gefunden : {actual_hash}")
            result.corrupted_files.append(rel_key)
        else:
            result.files_ok += 1

    result.passed = not result.needs_repair
    if result.needs_repair:
        n = len(result.missing_files) + len(result.corrupted_files)
        _log.warning(f"{n} Datei(en) benötigen Reparatur (fehlend: {len(result.missing_files)}, "
                     f"manipuliert: {len(result.corrupted_files)})")
    else:
        _log.info("Alle Dateien OK")

    _progress(100, str(result))
    _log.info(f"=== Integritätscheck abgeschlossen: {result} ===")
    return result


# ── Checksummen generieren (für security_generator.bat / release.bat) ──

def generate_checksums(output_path: Path = None) -> dict:
    """
    Generiert checksums.json für alle Dateien in eve_toolbox/.
    WICHTIG: Verwendet die gleiche Hash-Logik wie beim Prüfen
    (Zeilenenden-Normalisierung) damit Hashes immer übereinstimmen.
    Signierung passiert NICHT hier, sondern separat über
    core.release_crypto.sign_data() in den .bat-Skripten — diese
    Funktion erzeugt nur die unsignierten Rohdaten.
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