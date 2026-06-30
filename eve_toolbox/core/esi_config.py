"""
ESI Konfiguration — Client ID und Scopes für EVE Online SSO.
Scopes werden modular erweitert sobald neue Module aktiviert werden.
"""
import base64

# ── Client ID (verschlüsselt) ─────────────────────────────────
# Verschlüsselung: XOR + Base64 — verhindert einfaches Kopieren
_K = b"EVEToolbox2026phantombite"
_C = "cGYkYF5XWgNcGwMBBg9GCwMPEVpVAVtFViBmI2cJDFQ="

def _get_client_id() -> str:
    b = base64.b64decode(_C)
    return bytes([b[i] ^ _K[i % len(_K)] for i in range(len(b))]).decode()

ESI_CLIENT_ID  = _get_client_id()

# Für lokalen HTTP-Server (Callback)
ESI_LOCAL_PORT = 12500
ESI_LOCAL_CB   = f"http://localhost:{ESI_LOCAL_PORT}/callback"

# SSO Endpoints
ESI_AUTH_URL   = "https://login.eveonline.com/v2/oauth/authorize"
ESI_TOKEN_URL  = "https://login.eveonline.com/v2/oauth/token"
# Kein "/latest" mehr im Pfad — ESI versioniert seit 2025 nicht mehr über
# die URL, sondern ausschließlich über den X-Compatibility-Date Header
# (siehe ESI_COMPATIBILITY_DATE unten). Die alten /latest/-Pfade laufen
# laut CCP zwar noch "auf absehbare Zeit" weiter, aber ohne den Header
# bekäme man trotzdem nur das älteste verfügbare Verhalten.
ESI_BASE_URL   = "https://esi.evetech.net"

# Pflicht-Header bei JEDER Anfrage an esi.evetech.net (nicht bei den
# SSO-Endpunkten oben, die sind ein komplett getrenntes System ohne
# dieses Konzept). Ersetzt die frühere /latest/-Versionierung in der
# URL. Muss von Zeit zu Zeit aktualisiert werden, sobald CCP neue
# Compatibility-Dates veröffentlicht — siehe /meta/compatibility-dates.
ESI_COMPATIBILITY_DATE = "2026-06-09"

# ── Scopes pro Modul ──────────────────────────────────────────
# Neue Scopes hier eintragen wenn das jeweilige Modul aktiviert wird.
# Nutzer werden dann beim nächsten Start einmalig um neue Berechtigung gebeten.

SCOPES_CORE = [
    "publicData",                    # Charaktername, Portrait, Corp (öffentlich)
    "esi-location.read_online.v1",   # Online-Status Anzeige in Topbar
]

# Zukünftige Module — noch nicht aktiv:
# SCOPES_ASSETS    = ["esi-assets.read_assets.v1", "esi-assets.read_corporation_assets.v1"]
# SCOPES_WALLET    = ["esi-wallet.read_character_wallet.v1"]
# SCOPES_MARKET    = ["esi-markets.read_character_orders.v1", "esi-markets.structure_markets.v1"]
# SCOPES_SKILLS    = ["esi-skills.read_skills.v1", "esi-skills.read_skillqueue.v1"]
# SCOPES_INDUSTRY  = ["esi-industry.read_character_jobs.v1", "esi-industry.read_character_mining.v1"]
# SCOPES_PLANETS   = ["esi-planets.manage_planets.v1", "esi-planets.read_customs_offices.v1"]
# SCOPES_CLONES    = ["esi-clones.read_clones.v1", "esi-clones.read_implants.v1"]
# SCOPES_FITTINGS  = ["esi-fittings.read_fittings.v1", "esi-fittings.write_fittings.v1"]
# SCOPES_LOCATION  = ["esi-location.read_location.v1", "esi-location.read_ship_type.v1"]
# SCOPES_UNIVERSE  = ["esi-universe.read_structures.v1"]
# SCOPES_NOTIFY    = ["esi-characters.read_notifications.v1"]
# SCOPES_BLUEPRINT = ["esi-characters.read_blueprints.v1"]
# SCOPES_WAYPOINT  = ["esi-ui.write_waypoint.v1"]
# SCOPES_FLEET     = ["esi-fleets.read_fleet.v1", "esi-fleets.write_fleet.v1"]
# SCOPES_KILLMAIL  = ["esi-killmails.read_killmails.v1"]
# SCOPES_CORP      = ["esi-corporations.read_corporation_membership.v1",
#                     "esi-corporations.read_structures.v1"]

# ── Aktive Scope-Liste (wird beim Login verwendet) ────────────
ESI_SCOPES = [
    *SCOPES_CORE,
    # Module hier einfügen sobald sie aktiviert werden:
    # *SCOPES_ASSETS,
    # *SCOPES_WALLET,
    # usw.
]