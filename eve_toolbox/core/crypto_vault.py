"""
EVE Toolbox — Verschlüsselter Datentresor (Vault) für Account-Daten.

Konzept:
    Alle sensiblen Account-Daten (Tokens UND Charakter-Metadaten wie Name,
    ID, Corp) liegen in EINER zentralen, verschlüsselten Datei im portablen
    Programmordner. Auf der Platte liegt IMMER nur die verschlüsselte Form.
    Entschlüsselt wird ausschließlich im Arbeitsspeicher (RAM), nach
    Eingabe des Master-Passworts — einmal pro Sitzung.

Regel für künftige Module (Assets, Skills, PI, Market-Orders, ...):
    Alles, was einem konkreten EVE-Account oder Charakter zugeordnet
    werden kann, gehört in diesen Vault — nicht in settings.json oder
    eine eigene Cache-Datei daneben. Das schließt ein:
        - Access/Refresh Tokens
        - Character ID, Name, Corporation, Alliance
        - Wallet-, Asset-, Skill-, PI-, Market-Order-Caches
        - jeden anderen Datensatz, der aus einem ESI-Call mit
          Account-Scope stammt
    NICHT in den Vault gehören rein anwendungsbezogene Einstellungen,
    die keinem Account zuordenbar sind:
        - Sprache, Theme, Fenstergröße/-position
        - UI-Layout-Präferenzen, Log-Level
    Diese bleiben in core.settings (settings.json), unverschlüsselt,
    da sie für sich genommen keine Account-Information offenbaren.
    Wer ein neues Modul baut und unsicher ist, in welche Kategorie ein
    Datenfeld fällt, stellt sich die Frage: "Verrät dieses Feld etwas
    über einen bestimmten EVE-Charakter oder Account?" — wenn ja: Vault.

Kryptographie:
    - Schlüsselableitung: Argon2id (aus dem `cryptography`-Paket, keine
      zusätzliche Abhängigkeit nötig)
    - Verschlüsselung: Fernet (AES-128-CBC + HMAC, authentifiziert)
    - Salt: zufällig pro Installation erzeugt, unverschlüsselt neben dem
      Vault gespeichert (Salt ist kein Geheimnis, nur Einzigartigkeit zählt)

Dateien im Programmordner (data/):
    data/vault.salt   — roher Salt (16 Bytes, Base64), KEIN Geheimnis
    data/vault.enc     — verschlüsselte Nutzdaten (alle Charaktere + Tokens)

Wichtig — was dieses Modul NICHT tut:
    - Es schreibt niemals unverschlüsselte Nutzdaten auf die Platte.
    - Es hält das Passwort selbst nirgends dauerhaft — nur den daraus
      abgeleiteten Schlüssel, ausschließlich im RAM, für die laufende
      Sitzung.
"""
from __future__ import annotations

import os
import json
import base64
import secrets
from pathlib import Path
from dataclasses import dataclass, field

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.exceptions import InvalidKey

from core import logger as _logger
_log = _logger.get("crypto_vault")


# ── Pfade ──────────────────────────────────────────────────────
# __file__ = APP_DIR/eve_toolbox/core/crypto_vault.py
APP_DIR  = Path(__file__).resolve().parent.parent.parent
DATA_DIR = APP_DIR / "data"

SALT_PATH = DATA_DIR / "vault.salt"
VAULT_PATH = DATA_DIR / "vault.enc"

# ── Argon2id Parameter ─────────────────────────────────────────
# Bewusst spürbar, aber alltagstauglich (Zielwert ~0.3-0.6s auf normaler
# Hardware). Werte können künftig versioniert angehoben werden, ohne
# bestehende Vaults zu brechen (Migration beim nächsten Passwortwechsel).
ARGON2_TIME_COST   = 3           # Iterationen
ARGON2_MEMORY_COST = 64 * 1024   # KiB = 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_KEY_LEN     = 32          # 256 Bit → Fernet braucht 32 Byte Rohschlüssel
SALT_LEN           = 16


class VaultError(Exception):
    """Allgemeiner Vault-Fehler (z.B. Datei beschädigt)."""


class WrongPassword(VaultError):
    """Passwort falsch oder Vault-Daten beschädigt — nicht unterscheidbar,
    aus Sicherheitsgründen (kein Orakel über die Ursache des Fehlers)."""


def vault_exists() -> bool:
    """Gibt True zurück, wenn bereits ein Vault (inkl. Salt) existiert."""
    return SALT_PATH.exists() and VAULT_PATH.exists()


def has_salt_only() -> bool:
    """Selten/Fehlerfall: Salt da, aber Vault-Datei fehlt (z.B. nach
    fehlgeschlagenem ersten Schreibvorgang)."""
    return SALT_PATH.exists() and not VAULT_PATH.exists()


# ── Schlüsselableitung ─────────────────────────────────────────

def _derive_key(password: str, salt: bytes) -> bytes:
    """Leitet aus Passwort + Salt einen 32-Byte-Schlüssel ab (Argon2id),
    kodiert ihn als urlsafe-Base64 für Fernet."""
    kdf = Argon2id(
        salt=salt,
        length=ARGON2_KEY_LEN,
        iterations=ARGON2_TIME_COST,
        lanes=ARGON2_PARALLELISM,
        memory_cost=ARGON2_MEMORY_COST,
    )
    raw_key = kdf.derive(password.encode("utf-8"))
    return base64.urlsafe_b64encode(raw_key)


def _load_or_create_salt() -> bytes:
    """Lädt den installationsweiten Salt, erzeugt ihn falls nicht vorhanden."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if SALT_PATH.exists():
        return base64.b64decode(SALT_PATH.read_text(encoding="utf-8").strip())

    salt = secrets.token_bytes(SALT_LEN)
    _atomic_write_text(SALT_PATH, base64.b64encode(salt).decode("utf-8"))
    _log.info("Neuer Vault-Salt erzeugt (Installation initialisiert)")
    return salt


# ── Atomares Schreiben (crash-sicher) ──────────────────────────

def _atomic_write_bytes(path: Path, data: bytes) -> None:
    """
    Schreibt Daten crash-sicher: zuerst in eine temporäre Datei im selben
    Verzeichnis, dann atomarer os.replace() auf den Zielnamen. Damit liegt
    auf der Platte zu jedem Zeitpunkt entweder die alte ODER die neue
    vollständige Version — niemals ein halb geschriebener Zustand.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + f".tmp{os.getpid()}")
    with open(tmp_path, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, path)  # atomar auf POSIX und Windows


def _atomic_write_text(path: Path, text: str) -> None:
    _atomic_write_bytes(path, text.encode("utf-8"))


# ── Vault-Datenstruktur ─────────────────────────────────────────
#
# Entschlüsselter Inhalt von vault.enc (JSON):
# {
#   "format_version": 1,
#   "characters": {
#       "<char_id>": {
#           "id": "...", "name": "...", "corp_id": ..., "corp_name": "...",
#           "portrait_64": "...", "portrait_128": "...",
#           "access_token": "...", "refresh_token": "...", "expires_at": ...
#       },
#       ...
#   }
# }
#
# Komplette Datei (inkl. Namen/IDs) ist verschlüsselt — nicht nur Tokens.
# So ist auch die Information "welche Charaktere besitzt der Nutzer" auf
# der Platte geschützt, nicht nur der Zugriffsschlüssel selbst.

FORMAT_VERSION = 1

# ── Migrationen ────────────────────────────────────────────────
#
# Registry für künftige Formatänderungen. Jeder Eintrag transformiert
# die Rohdaten von genau einer Version zur nächsten. Beim Entschlüsseln
# wird automatisch die passende Kette angewendet, bis FORMAT_VERSION
# erreicht ist — alte Vaults werden NICHT ausgesperrt, sondern beim
# nächsten Entsperren transparent hochgezogen und sofort wieder
# verschlüsselt gespeichert.
#
# Beispiel für einen künftigen Eintrag (Version 1 -> 2):
#   def _migrate_1_to_2(data: dict) -> dict:
#       for char in data["characters"].values():
#           char.setdefault("new_field", None)
#       return data
#   _MIGRATIONS[1] = _migrate_1_to_2

_MIGRATIONS: dict[int, callable] = {
    # aktuell leer — FORMAT_VERSION ist noch bei 1, keine Migration nötig.
}


def _migrate_to_current(data: dict) -> tuple[dict, bool]:
    """
    Wendet alle nötigen Migrationsschritte an, bis data['format_version']
    == FORMAT_VERSION erreicht ist. Gibt (migrierte_daten, hat_migriert)
    zurück — der zweite Wert sagt dem Aufrufer, ob persist() nach dem
    Entsperren nötig ist, um den neuen Stand sofort zu sichern.
    """
    version = data.get("format_version", 1)
    migrated = False

    while version < FORMAT_VERSION:
        step = _MIGRATIONS.get(version)
        if step is None:
            _log.error(
                f"Keine Migration von Vault-Version {version} auf "
                f"{version + 1} registriert — Daten bleiben auf altem Stand."
            )
            break
        _log.info(f"Migriere Vault-Format von Version {version} auf {version + 1}")
        data = step(data)
        version += 1
        data["format_version"] = version
        migrated = True

    return data, migrated


@dataclass
class UnlockedVault:
    """Hält den im RAM entschlüsselten Zustand für die laufende Sitzung.
    Wird NIE auf die Platte serialisiert."""
    fernet: Fernet
    characters: dict = field(default_factory=dict)

    # ── Charakter-Operationen (wirken nur im RAM-Objekt) ───────
    def get_character(self, char_id: str) -> dict | None:
        return self.characters.get(str(char_id))

    def list_characters(self) -> list[dict]:
        return list(self.characters.values())

    def upsert_character(self, char_id: str, data: dict) -> None:
        self.characters[str(char_id)] = data

    def remove_character(self, char_id: str) -> None:
        self.characters.pop(str(char_id), None)

    # ── Persistenz ──────────────────────────────────────────────
    def persist(self) -> None:
        """Verschlüsselt den aktuellen RAM-Stand und schreibt ihn
        atomar auf die Platte. Wird nach jeder Änderung aufgerufen
        (Login, Token-Refresh, Logout/Entfernen eines Charakters)."""
        payload = json.dumps({
            "format_version": FORMAT_VERSION,
            "characters": self.characters,
        }, ensure_ascii=False).encode("utf-8")
        token = self.fernet.encrypt(payload)
        _atomic_write_bytes(VAULT_PATH, token)

    # ── Sitzungsende ────────────────────────────────────────────
    def wipe(self) -> None:
        """Entfernt Referenzen auf entschlüsselte Daten aus dem RAM-Objekt.
        Python kann physisches Löschen aus dem Speicher nicht garantieren,
        aber die Daten sind danach nicht mehr über die Anwendung zugreifbar."""
        self.characters.clear()
        # Fernet-Objekt referenziert intern den abgeleiteten Schlüssel —
        # auch diese Referenz aufgeben.
        self.fernet = None  # type: ignore


# ── Öffentliche API ──────────────────────────────────────────────

def create_vault(password: str) -> UnlockedVault:
    """
    Legt einen neuen, leeren Vault an (Onboarding / erster Start).
    Erzeugt Salt + leere verschlüsselte Datei.
    """
    if vault_exists():
        raise VaultError("Vault existiert bereits — create_vault nicht erneut aufrufen.")

    salt = _load_or_create_salt()
    key  = _derive_key(password, salt)
    fernet = Fernet(key)

    vault = UnlockedVault(fernet=fernet, characters={})
    vault.persist()
    _log.info("Neuer Vault erstellt")
    return vault


def unlock_vault(password: str) -> UnlockedVault:
    """
    Entschlüsselt den bestehenden Vault mit dem gegebenen Passwort.
    Wirft WrongPassword bei falschem Passwort oder beschädigten Daten.
    Wendet bei Bedarf automatisch Format-Migrationen an (siehe
    _migrate_to_current) und speichert den migrierten Stand sofort.
    """
    if not vault_exists():
        raise VaultError("Kein Vault vorhanden — create_vault zuerst aufrufen.")

    salt = _load_or_create_salt()
    key  = _derive_key(password, salt)
    fernet = Fernet(key)

    try:
        raw = VAULT_PATH.read_bytes()
        payload = fernet.decrypt(raw)
        data = json.loads(payload.decode("utf-8"))
    except (InvalidToken, InvalidKey, ValueError, json.JSONDecodeError) as e:
        _log.warning("Vault-Entsperrung fehlgeschlagen (falsches Passwort oder defekte Datei)")
        raise WrongPassword("Passwort falsch oder Vault-Datei beschädigt.") from e

    data, needs_resave = _migrate_to_current(data)
    characters = data.get("characters", {})
    _log.info(f"Vault entsperrt — {len(characters)} Charakter(e) geladen")

    vault = UnlockedVault(fernet=fernet, characters=characters)
    if needs_resave:
        vault.persist()
        _log.info("Vault nach Migration sofort neu gespeichert")
    return vault


def change_password(old_password: str, new_password: str) -> UnlockedVault:
    """
    Entschlüsselt mit altem Passwort, verschlüsselt mit neuem Passwort neu.
    Salt bleibt erhalten (kein Geheimnis, muss nicht rotieren) — der
    abgeleitete Schlüssel ändert sich durch das neue Passwort ohnehin
    vollständig.
    """
    vault = unlock_vault(old_password)  # wirft WrongPassword falls falsch

    salt = _load_or_create_salt()
    new_key = _derive_key(new_password, salt)
    vault.fernet = Fernet(new_key)
    vault.persist()
    _log.info("Master-Passwort geändert, Vault neu verschlüsselt")
    return vault


# ── Sitzungs-Singleton ───────────────────────────────────────────
#
# Genau ein entsperrter Vault existiert pro laufendem Programm (kein
# Mehrbenutzer-Szenario). Andere Module (esi.py, UI) greifen über die
# Funktionen unten auf den aktuellen Sitzungszustand zu, statt jedes Mal
# selbst ein UnlockedVault-Objekt durchzureichen.

_session: UnlockedVault | None = None


def is_unlocked() -> bool:
    return _session is not None


def get_session() -> UnlockedVault:
    """Gibt den aktuell entsperrten Vault zurück. Wirft VaultError,
    falls noch nicht entsperrt — Aufrufer müssen vorher prüfen oder
    den Fehler explizit behandeln (z.B. Entschlüsselungs-Popup öffnen)."""
    if _session is None:
        raise VaultError("Vault ist gesperrt — kein Zugriff auf Account-Daten möglich.")
    return _session


def unlock_session(password: str) -> None:
    """Entsperrt die Sitzung global. Bei erstem Start ohne bestehenden
    Vault wird automatisch ein neuer angelegt."""
    global _session
    if vault_exists():
        _session = unlock_vault(password)  # wirft WrongPassword
    else:
        _session = create_vault(password)


def lock_session() -> None:
    """Sperrt die Sitzung — entfernt Referenzen aus dem RAM (best effort,
    siehe UnlockedVault.wipe)."""
    global _session
    if _session is not None:
        _session.wipe()
    _session = None


def delete_all_user_data(include_settings: bool = False) -> None:
    """
    Notausgang: löscht den Vault unwiderruflich (kein Wiederherstellungsweg —
    das wäre sonst kein echter Schutz). Optional auch App-Einstellungen
    und Benachrichtigungen — zusammen ergibt das den exakten Zustand
    vor dem allerersten Start (first_run greift wieder, Welcome-Screen
    erscheint erneut), nicht nur einen leeren Vault bei sonst
    unverändertem App-Zustand.
    """
    for p in (VAULT_PATH, SALT_PATH):
        try:
            if p.exists():
                p.unlink()
        except Exception as e:
            _log.error(f"Konnte {p} nicht löschen: {e}")

    if include_settings:
        from core import settings as _settings
        from core import notifications as _notifications
        for path_attr, module in (("SETTINGS_PATH", _settings), ("NOTIF_PATH", _notifications)):
            try:
                path = getattr(module, path_attr)
                if path.exists():
                    path.unlink()
            except Exception as e:
                _log.error(f"Konnte {path_attr} nicht löschen: {e}")

    _log.warning("Alle Userdaten gelöscht (Notausgang/Nutzerwunsch)")