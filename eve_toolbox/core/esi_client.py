"""
Allgemeiner ESI-Aufruf-Helfer für Modul-Code (Markt, Assets, Skills, ...).

Abgrenzung zu core.esi: core.esi kümmert sich um den OAuth-Login-Flow und
die Token-Verwaltung (inkl. automatischem Refresh über get_valid_token()).
Dieses Modul nutzt core.esi nur, um an einen gültigen Token zu kommen — der
eigentliche Zweck hier ist eine generische, robuste GET/POST-Funktion für
beliebige ESI-Endpunkte, mit:

  - öffentlich (character_id=None, kein Token) ODER authentifiziert
    (character_id=<id>, Token wird automatisch geholt/gerefresht)
  - automatischer Pagination (X-Pages Header), wenn gewünscht
  - Beachtung des ESI-Fehlerbudgets (X-Esi-Error-Limit-Remain/-Reset) —
    wartet von selbst, bevor das Budget auf 0 läuft, statt blind weiter
    anzufragen und in eine 420-Sperre zu laufen
  - Rückgabe des Expires-Headers (als ESIResult.expires_at), damit
    Aufrufer (typischerweise core.esi_cache) wissen, wie lange das
    Ergebnis laut CCP gültig bleibt, bevor ein erneutes Abfragen
    überhaupt sinnvoll ist — vorzeitiges Neuabfragen kann laut ESI
    Best Practices sogar zu einer Sperre führen, ist also kein reiner
    Optimierungs-Tipp, sondern eine echte Regel.
  - klare ESIError-Exceptions statt stillem {}/[]-Rückgabewert, damit
    Aufrufer zwischen "keine Daten" und "Anfrage fehlgeschlagen"
    unterscheiden können
  - schickt automatisch den seit 2025 verpflichtenden X-Compatibility-
    Date Header mit (core.esi_config.ESI_COMPATIBILITY_DATE) — ESI
    versioniert nicht mehr über die URL, sondern über dieses Datum
"""
import json
import time
import threading
import email.utils
import urllib.request
import urllib.error
import urllib.parse

from core import logger as _logger
_log = _logger.get("esi_client")

from core.esi_config import ESI_BASE_URL, ESI_COMPATIBILITY_DATE
from core.config import APP_VERSION


class ESIError(Exception):
    """Strukturierter ESI-Fehler. status=HTTP-Code (None bei Netzwerk-
    fehlern ohne Antwort), retry_after=Sekunden falls von ESI mitgeteilt."""
    def __init__(self, message: str, status: int | None = None,
                 retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class ESIResult:
    """Ergebnis eines ESI-Aufrufs inkl. Cache-relevanter Metadaten."""
    def __init__(self, data, expires_at: float | None, status: int):
        self.data = data
        self.expires_at = expires_at  # time.time()-Zeitstempel oder None
        self.status = status


# ── Fehlerbudget (pro Prozess — ESI's Limit gilt pro IP/App, nicht pro
# Thread, daher ein einziger geteilter Zustand mit Lock) ───────────────
_budget_lock          = threading.Lock()
_error_budget_remain  = 100
_error_budget_reset_at = 0.0


def _check_error_budget():
    """Wartet kurz, falls das Fehlerbudget fast aufgebraucht ist, statt
    blind weiter anzufragen und in eine 420-Sperre zu laufen."""
    with _budget_lock:
        remain, reset_at = _error_budget_remain, _error_budget_reset_at
    if remain <= 2 and time.time() < reset_at:
        wait = reset_at - time.time()
        _log.warning(f"ESI-Fehlerbudget fast aufgebraucht ({remain} übrig) — warte {wait:.1f}s")
        time.sleep(max(0.0, wait))


def _update_error_budget(headers: dict):
    global _error_budget_remain, _error_budget_reset_at
    remain = headers.get("X-Esi-Error-Limit-Remain")
    reset  = headers.get("X-Esi-Error-Limit-Reset")
    if remain is not None and reset is not None:
        try:
            with _budget_lock:
                _error_budget_remain   = int(remain)
                _error_budget_reset_at = time.time() + int(reset)
        except (TypeError, ValueError):
            pass


def _parse_expires(headers: dict) -> float | None:
    """Parst den HTTP Expires-Header zu einem time.time()-Zeitstempel."""
    raw = headers.get("Expires")
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        return dt.timestamp()
    except Exception:
        return None


def call(method: str, path: str, character_id: str | None = None,
         params: dict | None = None, json_body=None,
         paginate: bool = False, timeout: float = 20.0) -> ESIResult:
    """
    Allgemeiner ESI-Aufruf.

    character_id=None      -> öffentlicher Aufruf, kein Token nötig.
    character_id=<char_id>  -> authentifiziert. Holt automatisch einen
                                gültigen (ggf. frisch gerefreshten) Token
                                über core.esi.get_valid_token(). Wirft
                                core.crypto_vault.VaultError unverändert
                                weiter, falls der Vault gesperrt ist (das
                                ist ein anderer Fehlerfall als ein ESI-
                                Problem, Aufrufer sollen ihn separat
                                behandeln können, z.B. Entsperr-Hinweis).
    paginate=True           -> folgt automatisch dem X-Pages Header und
                                gibt eine zusammengeführte Liste zurück.
                                Nur für Listen-Endpunkte sinnvoll.

    Wirft ESIError bei HTTP-Fehlern (4xx/5xx) oder Netzwerkproblemen.
    """
    from core import esi as _esi_auth

    access_token = None
    if character_id is not None:
        access_token = _esi_auth.get_valid_token(str(character_id))
        if access_token is None:
            raise ESIError(
                f"Kein gültiger Token für Charakter {character_id} "
                f"(Token ungültig oder Refresh fehlgeschlagen)."
            )

    all_data = []
    page = 1
    total_pages = 1
    last_expires_at = None
    last_status = 200

    while True:
        _check_error_budget()

        query = dict(params or {})
        if paginate:
            query["page"] = page

        url = ESI_BASE_URL + path
        if query:
            url += "?" + urllib.parse.urlencode(query)

        headers = {
            "Accept":                "application/json",
            "User-Agent":            f"EVE-Toolbox/{APP_VERSION}",
            "X-Compatibility-Date":  ESI_COMPATIBILITY_DATE,
        }
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        body_bytes = None
        if json_body is not None:
            body_bytes = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = dict(resp.headers)
                last_status  = resp.status
                raw = resp.read()
                data = json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            resp_headers = dict(e.headers) if e.headers else {}
            _update_error_budget(resp_headers)
            retry_after = resp_headers.get("Retry-After")
            if e.code == 420:
                _log.error(
                    f"ESI-Fehlerbudget überschritten (420) bei {method} {path} "
                    f"— Retry-After={retry_after}"
                )
            else:
                _log.warning(f"ESI-Fehler {e.code} bei {method} {path}: {e.reason}")
            raise ESIError(
                f"ESI antwortete mit {e.code} ({e.reason}) für {path}",
                status=e.code,
                retry_after=float(retry_after) if retry_after else None,
            ) from e
        except Exception as e:
            _log.error(f"ESI-Aufruf fehlgeschlagen ({method} {path}): {e}")
            raise ESIError(f"Netzwerkfehler bei {path}: {e}") from e

        _update_error_budget(resp_headers)
        last_expires_at = _parse_expires(resp_headers)

        if paginate and isinstance(data, list):
            all_data.extend(data)
            try:
                total_pages = int(resp_headers.get("X-Pages", 1))
            except (TypeError, ValueError):
                total_pages = 1
            if page >= total_pages:
                break
            page += 1
        else:
            all_data = data
            break

    return ESIResult(data=all_data, expires_at=last_expires_at, status=last_status)


def get(path: str, character_id: str | None = None, params: dict | None = None,
        paginate: bool = False) -> ESIResult:
    """Kurzform für call('GET', ...) — der weit häufigste Fall."""
    return call("GET", path, character_id=character_id, params=params, paginate=paginate)