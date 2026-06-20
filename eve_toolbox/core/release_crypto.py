"""
EVE Toolbox — Vertrauenskette für Releases und Dev-Mode (Ed25519).

Konzept (zweistufige Kette, Root → Release):
    Statt "GitHub bestätigt GitHub" gilt jetzt:
        Root Key (offline, mehrere Backups, NIE auf dem Dev-PC liegend)
        signiert einmalig den Release Key  →  Release Key signiert
        Releases (checksums.json, ZIP) und den Dev-Token  →  Nur der
        ROOT Public Key ist fest im Programm eingebettet (TRUSTED_
        PUBLIC_KEYS_PEM)  →  GitHub ist nur noch Transportmedium.

    Warum zwei Stufen statt einem Schlüssel:
        Geht der Release Key verloren oder wird gestohlen, kann ein
        neuer Release Key erzeugt und vom Root Key neu autorisiert
        werden — bestehende Installationen vertrauen weiterhin dem
        eingebetteten Root Key und akzeptieren automatisch den neuen
        Release Key, SOBALD das zugehörige Autorisierungs-Zertifikat
        mitgeliefert wird. Niemand muss den Programmcode selbst neu
        verteilen, nur weil der Release Key gewechselt hat.

    Das Release-Key-Zertifikat (release_cert.json) enthält den PEM-Text
    des Release Public Key plus eine Signatur des Root Keys darüber.
    Es wird mit jedem Release mitgeliefert (wie checksums.json.sig).

Schlüsselrotation (Root-Ebene):
    TRUSTED_PUBLIC_KEYS_PEM ist eine Liste, nicht ein einzelner Schlüssel.
    Ein Zertifikat ist gültig, wenn es zu IRGENDEINEM Root Key in der
    Liste passt. Das deckt eine (seltene) Rotation des Root Keys selbst
    ab — der eigentliche Normalfall (Release Key wechseln) braucht das
    nicht, dafür reicht ein neues Zertifikat unter demselben Root Key.

Zwei getrennte Prüffunktionen, eine gemeinsame Grundlage:
    verify_release_signature() — prüft Release-Artefakte (checksums.json),
        verlangt zusätzlich ein gültiges Release-Key-Zertifikat
    verify_dev_token()         — prüft den lokalen Dev-Mode-Token,
        signiert direkt mit dem Release Key (gleiches Zertifikat)
    Beide nutzen denselben _verify_with_root_keys() darunter, bleiben
    aber als Funktionen eigenständig — sie prüfen unterschiedliche Daten
    mit unterschiedlicher Bedeutung, auch wenn der kryptographische
    Mechanismus identisch ist.

Warum Ed25519 statt RSA:
    Kürzere Signaturen (64 Bytes statt 512 Bytes bei RSA-4096), schneller,
    kein Padding-Schema nötig — Standardwahl für Software-Signierung.
"""
from __future__ import annotations

import base64
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

from core import logger as _logger
_log = _logger.get("release_crypto")


# ── Root Public Keys (im Programm eingebettet) ─────────────────
#
# Fest im Programmcode eingebettet — wird NICHT von GitHub nachgeladen.
# Das ist der eigentliche Kern der Vertrauenskette: ein Angreifer mit
# Kontrolle über das GitHub-Repo kann diese Liste nicht verändern, ohne
# selbst eine neue Programmversion zu signieren (was er ohne den
# Root-Schlüssel nicht kann — und der liegt offline, nicht auf
# irgendeinem online erreichbaren System).
#
# Format: jeder Eintrag ist der PEM-Text des öffentlichen ROOT-Schlüssels.
# Mehrere Einträge = Rotation des Root Keys selbst möglich (selten nötig).
#
# Ist diese Liste leer, schlägt jede Signaturprüfung bewusst fehl
# (sicherer Default: lieber blockieren als ungeprüft vertrauen). Wird
# automatisch befüllt, sobald security_generator.bat (Modus 3, Root Key
# erzeugen) den Eintrag zwischen den Markern unten einträgt.
#
# Die Marker-Kommentare AUTO-TRUSTED-KEYS-START/END werden von
# security_generator.bat genutzt, um diesen Block automatisch zu
# aktualisieren — nicht entfernen oder umbenennen.
# AUTO-TRUSTED-KEYS-START
TRUSTED_PUBLIC_KEYS_PEM = [
    """-----BEGIN PUBLIC KEY-----
MCowBQYDK2VwAyEAkX0oppjBENbtXpwhv3883gMkEtNfoTV1lYiQ4yvA69s=
-----END PUBLIC KEY-----""",
]
# AUTO-TRUSTED-KEYS-END

DEV_TOKEN_MESSAGE = b"EVEToolbox-DevMode"

# Pfade für das Release-Key-Zertifikat — wird mit jedem Release
# mitgeliefert (wie checksums.json.sig), liegt aber daneben, nicht im
# Programmcode, da sich der Release Key öfter ändern kann als der Code.
RELEASE_CERT_FILENAME = "release_cert.json"


class TrustError(Exception):
    """Allgemeiner Fehler bei der Signaturprüfung (z.B. keine Trusted Keys
    konfiguriert, Datei fehlt, Format ungültig)."""


def _load_root_keys() -> list[ed25519.Ed25519PublicKey]:
    keys = []
    for pem_text in TRUSTED_PUBLIC_KEYS_PEM:
        try:
            key = serialization.load_pem_public_key(pem_text.encode("utf-8"))
            if not isinstance(key, ed25519.Ed25519PublicKey):
                _log.warning("Root Key ist kein Ed25519-Schlüssel — ignoriert")
                continue
            keys.append(key)
        except Exception as e:
            _log.error(f"Root Key konnte nicht geladen werden: {e}")
    return keys


def _verify_with_root_keys(data: bytes, signature: bytes) -> bool:
    """
    Prüft, ob die Signatur zu IRGENDEINEM der im Code eingebetteten
    Root Keys passt. Gibt True/False zurück, wirft bewusst keine
    Exception nach außen.
    """
    keys = _load_root_keys()
    if not keys:
        _log.error("Keine Root Public Keys konfiguriert — Signatur kann nicht geprüft werden")
        return False

    for key in keys:
        try:
            key.verify(signature, data)
            return True
        except InvalidSignature:
            continue
        except Exception as e:
            _log.warning(f"Fehler bei Signaturprüfung gegen einen Root Key: {e}")
            continue
    return False


def _build_cert_payload(release_pubkey_pem: str) -> bytes:
    """
    Die Daten, die der Root Key tatsächlich signiert — nur der reine
    Public-Key-Text, ohne JSON-Drumherum, damit es keine Mehrdeutigkeit
    gibt, was genau signiert wurde (kein JSON-Encoding-Unterschiede-Risiko).
    """
    return release_pubkey_pem.strip().encode("utf-8")


def load_release_cert(cert_path: Path) -> ed25519.Ed25519PublicKey | None:
    """
    Lädt release_cert.json von der Platte. Dünner Wrapper um
    load_release_cert_bytes() für den lokalen Dateifall (Dev-Token).
    """
    try:
        cert_bytes = cert_path.read_bytes()
    except Exception as e:
        _log.error(f"release_cert.json konnte nicht gelesen werden: {e}")
        return None
    return load_release_cert_bytes(cert_bytes)


def load_release_cert_bytes(cert_bytes: bytes) -> ed25519.Ed25519PublicKey | None:
    """
    Prüft die Root-Signatur über ein bereits geladenes release_cert.json
    (als Bytes, z.B. direkt von einem GitHub-Download, ohne Zwischenschritt
    über die Festplatte). Gibt bei Erfolg den autorisierten Release Public
    Key zurück, sonst None — in JEDEM Fehlerfall wird der Release Key
    NICHT vertraut.
    """
    import json
    try:
        cert_data = json.loads(cert_bytes.decode("utf-8"))
        release_pubkey_pem = cert_data["release_pubkey"]
        root_signature = base64.b64decode(cert_data["root_signature"])
    except Exception as e:
        _log.error(f"release_cert.json konnte nicht geparst werden: {e}")
        return None

    payload = _build_cert_payload(release_pubkey_pem)
    if not _verify_with_root_keys(payload, root_signature):
        _log.error("release_cert.json: Root-Signatur UNGÜLTIG — Release Key wird NICHT vertraut")
        return None

    try:
        release_key = serialization.load_pem_public_key(release_pubkey_pem.encode("utf-8"))
        if not isinstance(release_key, ed25519.Ed25519PublicKey):
            _log.error("Release Key im Zertifikat ist kein Ed25519-Schlüssel")
            return None
    except Exception as e:
        _log.error(f"Release Key im Zertifikat konnte nicht geladen werden: {e}")
        return None

    _log.info("release_cert.json: Root-Signatur gültig, Release Key autorisiert")
    return release_key


# ── Release-Signaturen (checksums.json) ───────────────────────

def verify_release_signature(checksums_bytes: bytes, signature_b64: str,
                              cert_path: Path = None,
                              cert_bytes: bytes = None) -> bool:
    """
    Zweistufige Prüfung:
        1. release_cert.json laden (von Pfad ODER bereits geladenen
           Bytes — z.B. direkt von einem GitHub-Download), Root-Signatur
           darüber prüfen — liefert den autorisierten Release Key
        2. Mit GENAU diesem Release Key die eigentliche Signatur über
           checksums_bytes prüfen
    Schlägt Stufe 1 fehl, wird Stufe 2 gar nicht erst versucht — ein
    nicht autorisierter Release Key darf niemals als gültig durchgehen,
    selbst wenn er rein kryptographisch korrekt signiert hätte.

    Genau einer von cert_path/cert_bytes muss angegeben werden.
    """
    if cert_bytes is not None:
        release_key = load_release_cert_bytes(cert_bytes)
    elif cert_path is not None:
        release_key = load_release_cert(cert_path)
    else:
        _log.error("verify_release_signature: weder cert_path noch cert_bytes angegeben")
        return False

    if release_key is None:
        return False

    try:
        signature = base64.b64decode(signature_b64)
    except Exception as e:
        _log.error(f"Signatur konnte nicht dekodiert werden: {e}")
        return False

    try:
        release_key.verify(signature, checksums_bytes)
        _log.info("Release-Signatur (checksums.json) gültig — Release Key durch Root autorisiert")
        return True
    except InvalidSignature:
        _log.warning("Release-Signatur (checksums.json) UNGÜLTIG gegen autorisierten Release Key")
        return False
    except Exception as e:
        _log.warning(f"Fehler bei Release-Signaturprüfung: {e}")
        return False


# ── Dev-Token ──────────────────────────────────────────────────

def verify_dev_token(token_b64: str, cert_path: Path) -> bool:
    """
    Prüft den lokalen Dev-Mode-Token (dev_mode.flag) — signiert mit dem
    Release Key, dessen Autorisierung über dasselbe release_cert.json
    läuft wie bei Releases. Eigenständige Funktion, getrennt von
    verify_release_signature(), auch wenn beide denselben Mechanismus
    nutzen — ein gültiger Dev-Token bedeutet etwas anderes als ein
    gültiges Release.
    """
    release_key = load_release_cert(cert_path)
    if release_key is None:
        return False

    try:
        signature = base64.b64decode(token_b64.strip())
    except Exception as e:
        _log.warning(f"Dev-Token konnte nicht dekodiert werden: {e}")
        return False

    try:
        release_key.verify(signature, DEV_TOKEN_MESSAGE)
        _log.info("Dev-Token gültig — Release Key durch Root autorisiert")
        return True
    except InvalidSignature:
        _log.warning("Dev-Token UNGÜLTIG gegen autorisierten Release Key")
        return False
    except Exception as e:
        _log.warning(f"Fehler bei Dev-Token-Prüfung: {e}")
        return False


# ── Signieren (nur für security_generator.bat / release.bat) ──
#
# Diese Funktionen laufen NIE in der ausgelieferten App, nur in den
# Build-Skripten auf dem Entwickler-Rechner — dort liegt der private
# Schlüssel, der niemals ins Repo oder in die ZIP gehört.

def sign_data(data: bytes, private_key_path: Path) -> str:
    """Signiert beliebige Bytes mit dem privaten Ed25519-Schlüssel,
    gibt die Signatur Base64-kodiert zurück."""
    priv_bytes = private_key_path.read_bytes()
    priv_key = serialization.load_pem_private_key(priv_bytes, password=None)
    if not isinstance(priv_key, ed25519.Ed25519PrivateKey):
        raise TrustError("Privater Schlüssel ist kein Ed25519-Schlüssel.")
    signature = priv_key.sign(data)
    return base64.b64encode(signature).decode("utf-8")


def create_release_cert(release_pubkey_path: Path, root_privkey_path: Path,
                         cert_output_path: Path) -> None:
    """
    Erstellt release_cert.json: signiert den Release Public Key mit dem
    Root Private Key. Wird NUR von security_generator.bat aufgerufen,
    wenn der Root Key gerade vom sicheren Aufbewahrungsort eingesteckt
    ist — der Root Key wird hier gelesen, aber niemals dauerhaft auf
    der Festplatte des Dev-Rechners belassen (das regelt das Skript).
    """
    import json
    release_pubkey_pem = release_pubkey_path.read_text(encoding="utf-8").strip()
    payload = _build_cert_payload(release_pubkey_pem)
    root_signature_b64 = sign_data(payload, root_privkey_path)

    cert = {
        "release_pubkey": release_pubkey_pem,
        "root_signature": root_signature_b64,
    }
    cert_output_path.write_text(
        json.dumps(cert, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    _log.info("release_cert.json erstellt — Release Key vom Root autorisiert")


def generate_keypair(private_key_path: Path, public_key_path: Path) -> None:
    """Erzeugt ein neues Ed25519-Schlüsselpaar und schreibt beide
    Dateien im PEM-Format. Wird von security_generator.bat aufgerufen."""
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    private_key_path.write_bytes(priv_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    public_key_path.write_bytes(pub_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ))
    _log.info("Neues Ed25519-Schlüsselpaar erzeugt")