"""
ESI OAuth2 PKCE Login für EVE Online.
Ablauf:
1. code_verifier + code_challenge generieren
2. Browser öffnen → EVE Login
3. Lokaler HTTP-Server fängt Callback ab
4. Code gegen Token tauschen
5. Charakter-Info abrufen (inkl. Corp-Name)
6. Token sicher speichern
"""
import os
import json
import base64
import hashlib
import secrets
import threading
import urllib.parse
import urllib.request
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler

from core import logger as _logger
_log = _logger.get("esi")

from core.esi_config import (
    ESI_CLIENT_ID, ESI_AUTH_URL, ESI_TOKEN_URL,
    ESI_BASE_URL, ESI_LOCAL_PORT, ESI_LOCAL_CB, ESI_SCOPES
)
from core import crypto_vault as _vault

# Tokens UND Charakter-Metadaten liegen jetzt verschlüsselt im zentralen
# Vault (core/crypto_vault.py), nicht mehr als Klartext-JSON im
# Windows-Profil. Die Funktionen unten setzen voraus, dass die Sitzung
# bereits entsperrt ist (_vault.is_unlocked()) — Aufrufer aus der UI
# müssen das vorher sicherstellen (Entschlüsselungs-Popup).


# ── PKCE Hilfsfunktionen ──────────────────────────────────────

def _generate_pkce() -> tuple[str, str]:
    """Erstellt code_verifier und code_challenge (S256)."""
    verifier  = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest    = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def _build_auth_url(challenge: str, state: str) -> str:
    """Baut die EVE SSO URL."""
    params = {
        "response_type":         "code",
        "redirect_uri":          ESI_LOCAL_CB,
        "client_id":             ESI_CLIENT_ID,
        "scope":                 " ".join(ESI_SCOPES),
        "code_challenge":        challenge,
        "code_challenge_method": "S256",
        "state":                 state,
    }
    return ESI_AUTH_URL + "?" + urllib.parse.urlencode(params)


# ── Lokaler Callback-Server ───────────────────────────────────

class _CallbackHandler(BaseHTTPRequestHandler):
    """Fängt den EVE SSO Callback ab."""

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        code  = params.get("code",  [None])[0]
        state = params.get("state", [None])[0]
        _log.debug(f"Callback empfangen — code={'JA' if code else 'NEIN'} state={'JA' if state else 'NEIN'}")

        # Nur echte Login-Callbacks verarbeiten (mit code Parameter)
        if not code:
            _log.debug("Leerer Callback ignoriert (Favicon/Prefetch?)")
            self.send_response(204)  # No Content
            self.end_headers()
            return

        # Erfolgsseite im Browser
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"""
        <html><body style="font-family:sans-serif;text-align:center;padding:60px;
        background:#0d0d1a;color:white;">
        <h2 style="color:#7B2FBE;">EVE Toolbox</h2>
        <p style="font-size:18px;">Login erfolgreich!</p>
        <p style="color:#888;">Du kannst dieses Fenster schliessen.</p>
        </body></html>""")

        self.server.auth_code  = code
        self.server.auth_state = state
        self.server._done      = True

    def log_message(self, *args):
        pass


def _exchange_code(code: str, verifier: str) -> dict:
    """Tauscht Authorization Code gegen Tokens."""
    data = urllib.parse.urlencode({
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  ESI_LOCAL_CB,
        "client_id":     ESI_CLIENT_ID,
        "code_verifier": verifier,
    }).encode()

    req = urllib.request.Request(
        ESI_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _refresh_token(refresh: str) -> dict:
    """Holt neuen Access Token mit Refresh Token."""
    data = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "refresh_token": refresh,
        "client_id":     ESI_CLIENT_ID,
    }).encode()

    req = urllib.request.Request(
        ESI_TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def _esi_get(endpoint: str, access_token: str = None) -> dict:
    """Einfacher ESI GET Request."""
    url = ESI_BASE_URL + endpoint
    headers = {"Accept": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


def _get_char_info(access_token: str) -> dict:
    """Liest Charakter-Name, ID, Corp aus dem JWT Token + ESI."""
    # JWT Payload decodieren
    parts   = access_token.split(".")
    payload = parts[1] + "=="
    decoded = json.loads(base64.urlsafe_b64decode(payload))

    # sub = "CHARACTER:EVE:12345678"
    char_id   = decoded.get("sub", "").split(":")[-1]
    char_name = decoded.get("name", "Unbekannt")

    # Charakter-Info (corp_id) via ESI
    char_info = _esi_get(f"/characters/{char_id}/", access_token)
    corp_id   = char_info.get("corporation_id", 0)

    # Corp-Name via ESI (öffentlich, kein Token nötig)
    corp_name = ""
    if corp_id:
        corp_info = _esi_get(f"/corporations/{corp_id}/")
        corp_name = corp_info.get("name", str(corp_id))

    # Portrait via ESI
    portrait  = _esi_get(f"/characters/{char_id}/portrait/", access_token)

    return {
        "id":           char_id,
        "name":         char_name,
        "corp_id":      corp_id,
        "corp_name":    corp_name,   # Jetzt immer ein String
        "portrait_64":  portrait.get("px64x64", ""),
        "portrait_128": portrait.get("px128x128", ""),
    }


# ── Token Speichern/Laden ─────────────────────────────────────
#
# Alle Funktionen hier wirken auf den aktuell entsperrten Vault
# (core.crypto_vault.get_session()). Ist die Sitzung gesperrt, wird
# core.crypto_vault.VaultError geworfen — die UI fängt das ab und
# zeigt das Entschlüsselungs-Popup.

def save_token(char_id: str, token_data: dict, char_info: dict):
    """Speichert Token + komplette Charakter-Info im verschlüsselten Vault.
    Schreibt sofort verschlüsselt auf die Platte (kein Klartext-Zwischenstand)."""
    vault = _vault.get_session()
    data = {**token_data, **char_info}
    vault.upsert_character(char_id, data)
    vault.persist()


def load_tokens() -> list[dict]:
    """Lädt alle gespeicherten Charaktere/Tokens aus dem entsperrten Vault."""
    vault = _vault.get_session()
    return vault.list_characters()


def delete_token(char_id: str):
    """Löscht einen Charakter aus dem Vault und schreibt sofort verschlüsselt."""
    vault = _vault.get_session()
    vault.remove_character(char_id)
    vault.persist()


def get_valid_token(char_id: str) -> str | None:
    """
    Gibt gültigen Access Token zurück.
    Refresht automatisch wenn abgelaufen — der neue Token wird sofort
    wieder verschlüsselt im Vault persistiert.
    """
    import time
    vault = _vault.get_session()
    data = vault.get_character(char_id)
    if data is None:
        return None

    expires_at = data.get("expires_at", 0)
    if time.time() < expires_at - 60:
        return data.get("access_token")

    # Refresh
    try:
        new_tokens = _refresh_token(data["refresh_token"])
        data["access_token"]  = new_tokens["access_token"]
        data["refresh_token"] = new_tokens.get("refresh_token", data["refresh_token"])
        data["expires_at"]    = time.time() + new_tokens.get("expires_in", 1199)
        vault.upsert_character(char_id, data)
        vault.persist()
        return data["access_token"]
    except Exception:
        return None


# ── Haupt-Login Funktion ──────────────────────────────────────

# Globale Login-Verwaltung
_active_server   = None
_current_login_id = 0   # Zähler — nur der aktuellste Login wird verarbeitet

def login(on_success=None, on_error=None):
    """
    Startet den EVE SSO Login.
    on_success(char_info: dict) — Charakter erfolgreich eingeloggt
    on_error(msg: str)          — Fehler aufgetreten
    """
    global _active_server, _current_login_id
    import webbrowser
    import time

    # Alten Server sauber beenden
    if _active_server is not None:
        _log.debug(f"Schließe alten Server für Login {_current_login_id}")
        try:
            _active_server._done = True
            _active_server.server_close()
        except Exception as e:
            _log.warning(f"Fehler beim Schließen: {e}")
        _active_server = None

    # Neue Login-ID — alle älteren Callbacks werden ignoriert
    _current_login_id += 1
    my_login_id = _current_login_id
    _log.info(f"Login gestartet — ID {my_login_id}")

    verifier, challenge = _generate_pkce()
    state               = secrets.token_urlsafe(16)
    auth_url            = _build_auth_url(challenge, state)

    # Lokalen Server starten — mit Retry falls Port noch belegt
    import socket as _socket
    server = None
    for attempt in range(30):  # max 3 Sekunden warten
        try:
            server = HTTPServer(("localhost", ESI_LOCAL_PORT), _CallbackHandler)
            server.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            _active_server = server
            _log.debug(f"Server gestartet auf Port {ESI_LOCAL_PORT} (Versuch {attempt+1})")
            break
        except OSError as e:
            _log.debug(f"Port noch belegt, warte... ({attempt+1}/30) — {e}")
            time.sleep(0.1)
            server = None
    if server is None:
        _log.error(f"Port {ESI_LOCAL_PORT} nicht verfügbar")
        if on_error:
            on_error(f"Port {ESI_LOCAL_PORT} nicht verfügbar")
        return
    server.auth_code  = None
    server.auth_state = None
    server._done      = False

    def _serve():
        _log.debug(f"Server-Thread {my_login_id} gestartet")
        while not server._done:
            try:
                server.handle_request()
            except Exception as e:
                _log.warning(f"Server-Thread {my_login_id} Exception: {e}")
                break
        _log.debug(f"Server-Thread {my_login_id} beendet (done={server._done})")

    t = threading.Thread(target=_serve, daemon=True)
    t.start()

    _log.info(f"Öffne Browser für Login {my_login_id}")
    webbrowser.open_new_tab(auth_url)

    # Warten bis Callback kommt (max 30 Sekunden)
    _log.debug(f"Warte auf Callback für Login {my_login_id}...")
    timeout = time.time() + 30
    while not server._done and time.time() < timeout:
        time.sleep(0.1)
    _log.debug(f"Warten beendet — done={server._done} code={'JA' if server.auth_code else 'NEIN'}")

    # Nur diesen Server schließen wenn er noch der aktive ist
    if _active_server is server:
        try:
            server.server_close()
        except Exception:
            pass
        _active_server = None
        _log.debug(f"Server für Login {my_login_id} geschlossen")
    else:
        _log.debug(f"Server für Login {my_login_id} wurde bereits von neuem Login übernommen")
        try:
            server.server_close()
        except Exception:
            pass

    if not server.auth_code:
        _log.info(f"Login {my_login_id} abgebrochen oder Timeout")
        if on_error:
            on_error("Login abgebrochen oder Timeout.")
        return

    # Prüfen ob dieser Login noch der aktuellste ist
    if my_login_id != _current_login_id:
        _log.debug(f"Login {my_login_id} veraltet — ignoriert (aktuell: {_current_login_id})")
        return

    # State prüfen
    if server.auth_state != state:
        if on_error:
            on_error("Sicherheitsfehler: State stimmt nicht überein.")
        return

    # Code gegen Token tauschen
    try:
        tokens = _exchange_code(server.auth_code, verifier)
    except Exception as e:
        if on_error:
            on_error(f"Token-Austausch fehlgeschlagen: {e}")
        return

    # Charakter-Info abrufen
    try:
        char_info = _get_char_info(tokens["access_token"])
    except Exception as e:
        if on_error:
            on_error(f"Charakter-Info fehlgeschlagen: {e}")
        return

    # Ablaufzeit berechnen
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 1199)

    # Speichern
    save_token(char_info["id"], tokens, char_info)

    _log.info(f"Login {my_login_id} erfolgreich: {char_info.get('name')}")
    if on_success:
        on_success(char_info)