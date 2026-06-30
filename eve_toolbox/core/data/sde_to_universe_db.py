"""
sde_to_universe_db.py — befüllt eine frisch angelegte universe.sqlite
(siehe db.build_fresh_universe_db) mit Daten aus den entpackten SDE-
JSONL-Dateien.

Analog zu sde_to_items_db.py: übersetzt CCPs Rohformat (CamelCase,
verschachtelte Listen) in unser eigenes, stabiles Schema (snake_case,
normalisierte Tabellen) — siehe core/data/universe_schema.sql für die
Zieltabellen und universe_schema.md für die ausführliche Begründung.

Erwartet einen Ordner mit den bereits ENTPACKTEN .jsonl-Dateien.

Reihenfolge der Build-Schritte folgt den Abhängigkeiten:
regions -> constellations -> solar_systems -> stars/celestial_bodies/
secondary_suns -> stargates -> npc_corporations -> stationen -> PI ->
Sonstiges. solar_systems.star_id wird per UPDATE nachgetragen (NACH
stars), da stars selbst solar_system_id braucht — klassisches
zirkuläres Beziehungsproblem, gleiche Lösung wie bei
market_groups.parent_id in sde_to_items_db.py.
"""
from core import logger as _logger
_log = _logger.get("sde_to_universe_db")

from datetime import datetime, timezone
from pathlib import Path

from core.data.db import build_fresh_universe_db, _connect
from core.data.sde_common import read_jsonl as _read_jsonl, localized_name as _name

# Tabellen, die NIEMALS von einem _build_*-Schritt aus der SDE befüllt
# werden dürfen — sie beschreiben dynamische, spielerabhängige Zustände
# (z.B. "wer besitzt aktuell welches System"), die es in der SDE
# schlicht nicht gibt und die stattdessen live über ESI befüllt werden
# müssten (analog zu Marktpreisen). Diese Liste ist eine TECHNISCHE
# Absicherung, kein bloßer Kommentar — _build_universe_db() prüft nach
# dem Befüllen aktiv, dass jede hier gelistete Tabelle leer ist, und
# bricht den gesamten Build ab, falls nicht (siehe
# _assert_forbidden_tables_empty). Verhindert, dass ein künftiger,
# versehentlich hinzugefügter _build_system_sovereignty()-Schritt
# (oder eine SDE-Datei, die CCP eines Tages mit ähnlichem Namen
# einführt) diese Tabelle stillschweigend mit falschen, weil
# statischen SDE-Daten befüllt.
_FORBIDDEN_SDE_TABLES = ["system_sovereignty"]


def build_universe_db(sde_dir: Path, target_path: Path, build_number: str) -> None:
    """Baut eine VOLLSTÄNDIG NEUE universe.sqlite unter `target_path`
    aus den JSONL-Dateien in `sde_dir`. `target_path` sollte ein
    temporärer Pfad sein — der atomare Austausch gegen die "echte"
    universe.sqlite passiert NICHT hier, sondern im Aufrufer
    (core/data/db_updater.py)."""
    _log.info(f"Baue universe.sqlite aus {sde_dir} (Build {build_number})")
    build_fresh_universe_db(target_path)
    conn = _connect(target_path)
    try:
        _build_regions(conn, sde_dir)
        _build_constellations(conn, sde_dir)
        _build_solar_systems(conn, sde_dir)
        _build_stars(conn, sde_dir)
        _link_solar_system_stars(conn)
        _build_secondary_suns(conn, sde_dir)
        _build_celestial_body_types(conn)
        _build_celestial_bodies(conn, sde_dir)
        _build_stargates(conn, sde_dir)
        _build_npc_corporations(conn, sde_dir)
        _build_npc_corporation_divisions(conn, sde_dir)
        _build_station_services(conn, sde_dir)
        _build_station_operations(conn, sde_dir)
        _build_npc_stations(conn, sde_dir)
        _build_planet_resources(conn, sde_dir)
        _build_planet_schematics(conn, sde_dir)
        _build_sovereignty_upgrades(conn, sde_dir)
        _build_control_tower_resources(conn, sde_dir)
        _build_agents_in_space(conn, sde_dir)
        _build_landmarks(conn, sde_dir)
        _build_factions(conn, sde_dir)
        _build_corporation_activities(conn, sde_dir)
        _build_npc_characters(conn, sde_dir)
        _assert_forbidden_tables_empty(conn)
        _write_meta(conn, build_number)
        _validate_built_database(conn)
        conn.commit()
    except Exception:
        conn.close()
        raise
    conn.close()
    _log.info(f"universe.sqlite erfolgreich befüllt: {target_path}")


def _write_meta(conn, build_number: str):
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("sde_build", build_number),
        ("schema_version", "1"),
        ("created_at", now),
    ]
    conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", rows)


def _pos(obj: dict) -> tuple:
    """Liest position.{x,y,z} aus einem SDE-Objekt, robust falls das
    Feld komplett fehlt (manche kleineren Objekte haben keine Position)."""
    p = obj.get("position", {})
    return (p.get("x"), p.get("y"), p.get("z"))


# ── Geografie ────────────────────────────────────────────────────────

def _build_regions(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "mapRegions.jsonl"):
        x, y, z = _pos(obj)
        rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"),
            obj.get("factionID"), x, y, z,
        ))
    conn.executemany(
        "INSERT INTO regions (id, name_en, name_de, faction_id, pos_x, pos_y, pos_z) "
        "VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"regions: {len(rows)} Zeilen")


def _build_constellations(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "mapConstellations.jsonl"):
        x, y, z = _pos(obj)
        rows.append((
            obj["_key"], obj["regionID"], _name(obj, "en"), _name(obj, "de"),
            obj.get("factionID"), obj.get("wormholeClassID"), x, y, z,
        ))
    conn.executemany(
        "INSERT INTO constellations "
        "(id, region_id, name_en, name_de, faction_id, wormhole_class_id, "
        "pos_x, pos_y, pos_z) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"constellations: {len(rows)} Zeilen")


def _build_solar_systems(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "mapSolarSystems.jsonl"):
        x, y, z = _pos(obj)
        pos2d = obj.get("position2D", {})
        rows.append((
            obj["_key"], obj["constellationID"], obj["regionID"],
            _name(obj, "en"), _name(obj, "de"),
            obj.get("securityStatus", 0.0), obj.get("securityClass"),
            obj.get("luminosity"), obj.get("radius"),
            bool(obj.get("border", False)), bool(obj.get("hub", False)),
            bool(obj.get("international", False)), bool(obj.get("regional", False)),
            x, y, z, pos2d.get("x"), pos2d.get("y"),
        ))
    conn.executemany(
        "INSERT INTO solar_systems "
        "(id, constellation_id, region_id, name_en, name_de, security_status, "
        "security_class, luminosity, radius, border, hub, international, "
        "regional, pos_x, pos_y, pos_z, pos2d_x, pos2d_y) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"solar_systems: {len(rows)} Zeilen")


def _build_stars(conn, sde_dir: Path):
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    rows = []
    skipped = []
    for obj in _read_jsonl(sde_dir / "mapStars.jsonl"):
        sys_id = obj["solarSystemID"]
        if sys_id not in existing_systems:
            skipped.append(obj["_key"])
            continue
        stats = obj.get("statistics", {})
        rows.append((
            obj["_key"], sys_id, obj.get("typeID"), obj.get("radius"),
            stats.get("age"), stats.get("life"), stats.get("luminosity"),
            stats.get("spectralClass"), stats.get("temperature"),
        ))
    if skipped:
        _log.warning(f"stars: {len(skipped)} mit unbekanntem solar_system_id übersprungen")
    conn.executemany(
        "INSERT INTO stars (id, solar_system_id, type_item_id, radius, age, "
        "life, luminosity, spectral_class, temperature) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"stars: {len(rows)} Zeilen")


def _link_solar_system_stars(conn):
    """Trägt solar_systems.star_id nach, NACHDEM stars befüllt ist —
    löst das zirkuläre Beziehungsproblem (Systeme brauchen Sterne,
    Sterne brauchen Systeme), analog zu market_groups.parent_id in
    sde_to_items_db.py."""
    rows = conn.execute("SELECT id, solar_system_id FROM stars").fetchall()
    conn.executemany(
        "UPDATE solar_systems SET star_id = ? WHERE id = ?",
        [(star_id, sys_id) for star_id, sys_id in rows],
    )
    _log.info(f"solar_systems.star_id: {len(rows)} nachgetragen")


def _build_secondary_suns(conn, sde_dir: Path):
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    rows = []
    skipped = []
    for obj in _read_jsonl(sde_dir / "mapSecondarySuns.jsonl"):
        sys_id = obj.get("solarSystemID")
        if sys_id not in existing_systems:
            skipped.append(obj["_key"])
            continue
        x, y, z = _pos(obj)
        rows.append((
            obj["_key"], sys_id, obj.get("typeID"),
            obj.get("effectBeaconTypeID"), x, y, z,
        ))
    if skipped:
        _log.warning(f"secondary_suns: {len(skipped)} übersprungen (unbekanntes System)")
    conn.executemany(
        "INSERT INTO secondary_suns (id, solar_system_id, type_item_id, "
        "effect_beacon_type_id, pos_x, pos_y, pos_z) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"secondary_suns: {len(rows)} Zeilen")


# ── Himmelskörper ────────────────────────────────────────────────────

_BODY_TYPE_IDS = {"planet": 1, "moon": 2, "asteroid_belt": 3}


def _build_celestial_body_types(conn):
    conn.executemany(
        "INSERT INTO celestial_body_types (id, name) VALUES (?,?)",
        [(bid, name) for name, bid in _BODY_TYPE_IDS.items()],
    )


def _build_celestial_bodies(conn, sde_dir: Path):
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    files_and_types = [
        ("mapPlanets.jsonl", "planet"),
        ("mapMoons.jsonl", "moon"),
        ("mapAsteroidBelts.jsonl", "asteroid_belt"),
    ]
    total_rows = 0
    total_skipped = 0
    for filename, body_type in files_and_types:
        body_type_id = _BODY_TYPE_IDS[body_type]
        rows = []
        skipped = 0
        for obj in _read_jsonl(sde_dir / filename):
            sys_id = obj.get("solarSystemID")
            if sys_id not in existing_systems:
                skipped += 1
                continue
            x, y, z = _pos(obj)
            stats = obj.get("statistics", {})
            attrs = obj.get("attributes", {})
            rows.append((
                obj["_key"], body_type_id, sys_id, obj.get("orbitID"),
                obj.get("orbitIndex"), obj.get("celestialIndex"),
                obj.get("typeID"), obj.get("radius"), x, y, z,
                stats.get("density"), stats.get("eccentricity"),
                stats.get("escapeVelocity"), stats.get("locked"),
                stats.get("massDust"), stats.get("massGas"),
                stats.get("orbitPeriod"), stats.get("orbitRadius"),
                stats.get("pressure"), stats.get("rotationRate"),
                stats.get("spectralClass"), stats.get("surfaceGravity"),
                stats.get("temperature"), attrs.get("heightMap1"),
                attrs.get("heightMap2"), attrs.get("shaderPreset"),
                attrs.get("population"),
            ))
        conn.executemany(
            "INSERT INTO celestial_bodies "
            "(id, body_type_id, solar_system_id, orbit_id, orbit_index, "
            "celestial_index, type_item_id, radius, pos_x, pos_y, pos_z, "
            "density, eccentricity, escape_velocity, locked, mass_dust, "
            "mass_gas, orbit_period, orbit_radius, pressure, rotation_rate, "
            "spectral_class, surface_gravity, temperature, height_map_1, "
            "height_map_2, shader_preset, population) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )
        total_rows += len(rows)
        total_skipped += skipped
        _log.info(f"celestial_bodies ({body_type}): {len(rows)} Zeilen, "
                  f"{skipped} übersprungen")
    if total_skipped:
        _log.warning(f"celestial_bodies: insgesamt {total_skipped} mit "
                      f"unbekanntem solar_system_id übersprungen")


# ── Sprungtore ───────────────────────────────────────────────────────

def _build_stargates(conn, sde_dir: Path):
    """Zwei Durchgänge wegen self-referencing destination_stargate_id:
    erst alle Stargates ohne Ziel-Stargate-Referenz einfügen (Ziel-
    System ist unkritisch, da solar_systems schon vollständig befüllt
    ist), dann destination_stargate_id per UPDATE nachtragen — gleiche
    Technik wie bei market_groups.parent_id."""
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "mapStargates.jsonl"):
        sys_id = obj["solarSystemID"]
        if sys_id not in existing_systems:
            skipped += 1
            continue
        dest = obj.get("destination", {})
        x, y, z = _pos(obj)
        rows.append((
            obj["_key"], sys_id, obj.get("typeID"),
            dest.get("solarSystemID"), dest.get("stargateID"), x, y, z,
        ))
    if skipped:
        _log.warning(f"stargates: {skipped} mit unbekanntem solar_system_id übersprungen")

    conn.executemany(
        "INSERT INTO stargates (id, solar_system_id, type_item_id, "
        "destination_system_id, destination_stargate_id, pos_x, pos_y, pos_z) "
        "VALUES (?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"stargates: {len(rows)} Zeilen")


# ── NPC-Korporationen & Stationen ───────────────────────────────────

def _build_npc_corporations(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "npcCorporations.jsonl"):
        rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"),
            obj.get("tickerName"),
            obj.get("description", {}).get("en") if isinstance(obj.get("description"), dict) else None,
            obj.get("stationID"), obj.get("ceoID"), obj.get("size"),
            obj.get("taxRate"), obj.get("minSecurity"),
            obj.get("minimumJoinStanding"), bool(obj.get("deleted", False)),
        ))
    conn.executemany(
        "INSERT INTO npc_corporations "
        "(id, name_en, name_de, ticker_name, description_en, station_id, "
        "ceo_id, size, tax_rate, min_security, minimum_join_standing, deleted) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"npc_corporations: {len(rows)} Zeilen")


def _build_npc_corporation_divisions(conn, sde_dir: Path):
    """Die meisten Einträge haben 'displayName' als einfachen String,
    aber mindestens einer ('Heraldry', _key=37) hat dieses Feld NICHT
    und stattdessen ein mehrsprachiges 'name'-Objekt — verifiziert
    anhand der aktuellen SDE-Daten. Beide Fälle werden abgedeckt,
    Fallback auf internal_name als letzte Instanz."""
    rows = []
    for obj in _read_jsonl(sde_dir / "npcCorporationDivisions.jsonl"):
        leader = obj.get("leaderTypeName")
        leader_en = leader.get("en") if isinstance(leader, dict) else None
        display_name = obj.get("displayName")
        if display_name is None:
            name_obj = obj.get("name")
            display_name = (name_obj.get("en") if isinstance(name_obj, dict)
                             else obj.get("internalName"))
        rows.append((obj["_key"], obj["internalName"], display_name, leader_en))
    conn.executemany(
        "INSERT INTO npc_corporation_divisions "
        "(id, internal_name, display_name, leader_type_name_en) VALUES (?,?,?,?)",
        rows,
    )
    _log.info(f"npc_corporation_divisions: {len(rows)} Zeilen")


def _build_station_services(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "stationServices.jsonl"):
        rows.append((obj["_key"], obj["serviceName"]["en"], obj["serviceName"]["de"]))
    conn.executemany(
        "INSERT INTO station_services (id, name_en, name_de) VALUES (?,?,?)",
        rows,
    )
    _log.info(f"station_services: {len(rows)} Zeilen")


def _build_station_operations(conn, sde_dir: Path):
    existing_services = {
        row[0] for row in conn.execute("SELECT id FROM station_services").fetchall()
    }
    rows = []
    service_link_rows = []
    skipped_services = 0
    for obj in _read_jsonl(sde_dir / "stationOperations.jsonl"):
        op_name = obj.get("operationName")
        op_name_en = op_name.get("en") if isinstance(op_name, dict) else None
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        rows.append((
            obj["_key"], obj.get("activityID"), op_name_en, desc_en,
            obj.get("border"), obj.get("corridor"), obj.get("fringe"),
            obj.get("hub"), obj.get("ratio"),
            obj.get("manufacturingFactor"), obj.get("researchFactor"),
        ))
        for service_id in obj.get("services", []):
            if service_id not in existing_services:
                skipped_services += 1
                continue
            service_link_rows.append((obj["_key"], service_id))

    if skipped_services:
        _log.warning(f"station_operation_services: {skipped_services} "
                      f"Referenzen auf unbekannte service_id übersprungen")

    conn.executemany(
        "INSERT INTO station_operations "
        "(id, activity_id, name_en, description_en, border, corridor, "
        "fringe, hub, ratio, manufacturing_factor, research_factor) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO station_operation_services "
        "(operation_id, service_id) VALUES (?,?)",
        service_link_rows,
    )
    _log.info(f"station_operations: {len(rows)} Zeilen, "
              f"station_operation_services: {len(service_link_rows)} Zeilen")


def _build_npc_stations(conn, sde_dir: Path):
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    existing_corporations = {
        row[0] for row in conn.execute("SELECT id FROM npc_corporations").fetchall()
    }
    existing_operations = {
        row[0] for row in conn.execute("SELECT id FROM station_operations").fetchall()
    }
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "npcStations.jsonl"):
        sys_id = obj["solarSystemID"]
        if sys_id not in existing_systems:
            skipped += 1
            continue
        owner_id = obj.get("ownerID")
        if owner_id is not None and owner_id not in existing_corporations:
            owner_id = None  # Owner unbekannt -> NULL statt FK-Verletzung
        op_id = obj.get("operationID")
        if op_id is not None and op_id not in existing_operations:
            op_id = None
        x, y, z = _pos(obj)
        rows.append((
            obj["_key"], sys_id, obj.get("celestialIndex"), obj.get("orbitID"),
            obj.get("orbitIndex"), owner_id, op_id, obj.get("typeID"),
            bool(obj.get("useOperationName", False)),
            obj.get("reprocessingEfficiency"), obj.get("reprocessingStationsTake"),
            obj.get("reprocessingHangarFlag"), x, y, z,
        ))
    if skipped:
        _log.warning(f"npc_stations: {skipped} mit unbekanntem solar_system_id übersprungen")
    conn.executemany(
        "INSERT INTO npc_stations "
        "(id, solar_system_id, celestial_index, orbit_id, orbit_index, "
        "owner_corporation_id, operation_id, type_item_id, use_operation_name, "
        "reprocessing_efficiency, reprocessing_stations_take, "
        "reprocessing_hangar_flag, pos_x, pos_y, pos_z) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"npc_stations: {len(rows)} Zeilen")


# ── Planetary Interaction ────────────────────────────────────────────

def _build_planet_resources(conn, sde_dir: Path):
    existing_bodies = {
        row[0] for row in conn.execute("SELECT id FROM celestial_bodies").fetchall()
    }
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "planetResources.jsonl"):
        body_id = obj["_key"]
        if body_id not in existing_bodies:
            skipped += 1
            continue
        rows.append((body_id, obj.get("power")))
    if skipped:
        _log.warning(f"planet_resources: {skipped} mit unbekanntem celestial_body_id übersprungen")
    conn.executemany(
        "INSERT INTO planet_resources (celestial_body_id, power) VALUES (?,?)",
        rows,
    )
    _log.info(f"planet_resources: {len(rows)} Zeilen")


def _build_planet_schematics(conn, sde_dir: Path):
    """WICHTIG (Korrektur einer ursprünglichen Fehlannahme): Das Feld
    'pins' in der SDE ist NUR eine Liste roher Slot-/Pin-IDs, OHNE
    Material-/Mengenangabe — die eigentlichen Input-/Output-Materialien
    stehen im separaten Feld 'types' (mit '_key'/'isInput'/'quantity'),
    verifiziert anhand der aktuellen SDE-Daten. Die Zieltabelle heißt
    weiterhin planet_schematic_pins (Konsistenz mit dem ursprünglichen
    Schema-Namen), liest aber inhaltlich aus 'types', nicht aus 'pins'."""
    schematic_rows = []
    pin_rows = []
    for obj in _read_jsonl(sde_dir / "planetSchematics.jsonl"):
        schematic_rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"), obj["cycleTime"]
        ))
        for type_entry in obj.get("types", []):
            pin_rows.append((
                obj["_key"], type_entry["_key"],
                bool(type_entry.get("isInput", False)), type_entry["quantity"],
            ))
    conn.executemany(
        "INSERT INTO planet_schematics (id, name_en, name_de, cycle_time) "
        "VALUES (?,?,?,?)",
        schematic_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO planet_schematic_pins "
        "(schematic_id, item_id, is_input, quantity) VALUES (?,?,?,?)",
        pin_rows,
    )
    _log.info(f"planet_schematics: {len(schematic_rows)} Zeilen, "
              f"planet_schematic_pins: {len(pin_rows)} Zeilen")


# ── Sonstiges ────────────────────────────────────────────────────────

def _build_sovereignty_upgrades(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "sovereigntyUpgrades.jsonl"):
        fuel = obj.get("fuel", {})
        rows.append((
            obj["_key"], obj.get("mutually_exclusive_group"),
            obj.get("power_allocation"), obj.get("workforce_allocation"),
            fuel.get("type_id"), fuel.get("hourly_upkeep"), fuel.get("startup_cost"),
        ))
    conn.executemany(
        "INSERT INTO sovereignty_upgrades "
        "(id, mutually_exclusive_group, power_allocation, workforce_allocation, "
        "fuel_item_id, fuel_hourly_upkeep, fuel_startup_cost) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"sovereignty_upgrades: {len(rows)} Zeilen")


def _build_control_tower_resources(conn, sde_dir: Path):
    tower_rows = []
    requirement_rows = []
    for obj in _read_jsonl(sde_dir / "controlTowerResources.jsonl"):
        tower_id = obj["_key"]
        tower_rows.append((tower_id,))
        for res in obj.get("resources", []):
            requirement_rows.append((
                tower_id, res["resourceTypeID"], res["purpose"], res["quantity"]
            ))
    conn.executemany(
        "INSERT INTO control_tower_resources (tower_item_id) VALUES (?)",
        tower_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO control_tower_resource_requirements "
        "(tower_item_id, resource_item_id, purpose, quantity) VALUES (?,?,?,?)",
        requirement_rows,
    )
    _log.info(f"control_tower_resources: {len(tower_rows)} Zeilen, "
              f"control_tower_resource_requirements: {len(requirement_rows)} Zeilen")


def _build_agents_in_space(conn, sde_dir: Path):
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "agentsInSpace.jsonl"):
        sys_id = obj.get("solarSystemID")
        if sys_id not in existing_systems:
            skipped += 1
            continue
        rows.append((
            obj["_key"], sys_id, obj.get("dungeonID"),
            obj.get("spawnPointID"), obj.get("typeID"),
        ))
    if skipped:
        _log.warning(f"agents_in_space: {skipped} mit unbekanntem solar_system_id übersprungen")
    conn.executemany(
        "INSERT INTO agents_in_space "
        "(id, solar_system_id, dungeon_id, spawn_point_id, type_item_id) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    _log.info(f"agents_in_space: {len(rows)} Zeilen")


def _build_landmarks(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "landmarks.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        pos = obj.get("position")
        if isinstance(pos, dict):
            x, y, z = pos.get("x"), pos.get("y"), pos.get("z")
        elif isinstance(pos, list) and len(pos) == 3:
            x, y, z = pos  # ältere Listen-Form, laut Changelog inzwischen Objekt
        else:
            x, y, z = None, None, None
        rows.append((obj["_key"], _name(obj, "en"), _name(obj, "de"), desc_en, x, y, z))
    conn.executemany(
        "INSERT INTO landmarks (id, name_en, name_de, description_en, "
        "pos_x, pos_y, pos_z) VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"landmarks: {len(rows)} Zeilen")


# ── Politik & Wirtschaft (nachträglich von characters.sqlite verschoben) ──

def _build_factions(conn, sde_dir: Path):
    """Verweise auf npc_corporations/solar_systems sind bereits befüllt
    (laufen früher im Build), daher hier als echte Foreign Keys möglich
    — anders als bei den meisten anderen Tabellen, die NUR logisch auf
    items.sqlite verweisen (andere Datei, kein echter FK möglich)."""
    existing_corporations = {
        row[0] for row in conn.execute("SELECT id FROM npc_corporations").fetchall()
    }
    existing_systems = {
        row[0] for row in conn.execute("SELECT id FROM solar_systems").fetchall()
    }
    faction_rows = []
    member_race_rows = []
    for obj in _read_jsonl(sde_dir / "factions.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        short_desc = obj.get("shortDescription")
        short_desc_en = short_desc.get("en") if isinstance(short_desc, dict) else None

        corp_id = obj.get("corporationID")
        if corp_id is not None and corp_id not in existing_corporations:
            corp_id = None
        militia_corp_id = obj.get("militiaCorporationID")
        if militia_corp_id is not None and militia_corp_id not in existing_corporations:
            militia_corp_id = None
        sys_id = obj.get("solarSystemID")
        if sys_id is not None and sys_id not in existing_systems:
            sys_id = None

        faction_rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"), desc_en, short_desc_en,
            corp_id, militia_corp_id, sys_id, obj.get("iconID"),
            obj.get("flatLogo"), obj.get("flatLogoWithName"),
            obj.get("sizeFactor"), bool(obj.get("uniqueName", False)),
        ))
        for race_id in obj.get("memberRaces", []):
            member_race_rows.append((obj["_key"], race_id))

    conn.executemany(
        "INSERT INTO factions "
        "(id, name_en, name_de, description_en, short_description_en, "
        "corporation_id, militia_corporation_id, solar_system_id, icon_id, "
        "flat_logo, flat_logo_with_name, size_factor, unique_name) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        faction_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO faction_member_races (faction_id, race_id) VALUES (?,?)",
        member_race_rows,
    )
    _log.info(f"factions: {len(faction_rows)} Zeilen, "
              f"faction_member_races: {len(member_race_rows)} Zeilen")


def _build_corporation_activities(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "corporationActivities.jsonl"):
        rows.append((obj["_key"], _name(obj, "en"), _name(obj, "de")))
    conn.executemany(
        "INSERT INTO corporation_activities (id, name_en, name_de) VALUES (?,?,?)",
        rows,
    )
    _log.info(f"corporation_activities: {len(rows)} Zeilen")


def _build_npc_characters(conn, sde_dir: Path):
    existing_corporations = {
        row[0] for row in conn.execute("SELECT id FROM npc_corporations").fetchall()
    }
    rows = []
    for obj in _read_jsonl(sde_dir / "npcCharacters.jsonl"):
        corp_id = obj.get("corporationID")
        if corp_id is not None and corp_id not in existing_corporations:
            corp_id = None
        rows.append((
            obj["_key"], _name(obj, "en"), corp_id, obj.get("locationID"),
            obj.get("bloodlineID"), obj.get("raceID"), obj.get("gender"),
            bool(obj.get("ceo", False)), obj.get("startDate"),
            bool(obj.get("uniqueName", False)),
        ))
    conn.executemany(
        "INSERT INTO npc_characters "
        "(id, name_en, corporation_id, location_id, bloodline_id, race_id, "
        "gender, is_ceo, start_date, unique_name) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"npc_characters: {len(rows)} Zeilen")


# ── Validierung ──────────────────────────────────────────────────────

def _assert_forbidden_tables_empty(conn) -> None:
    """Technische Durchsetzung von _FORBIDDEN_SDE_TABLES — prüft aktiv,
    dass keine dieser Tabellen versehentlich befüllt wurde, statt sich
    nur auf einen Kommentar/die Disziplin künftiger Code-Änderungen zu
    verlassen. Bricht den GESAMTEN Build ab, falls doch — besser ein
    klarer Fehler beim Bauen als eine stillschweigend falsch befüllte
    dynamische Tabelle, die später im UI als 'aktuell' missverstanden
    werden könnte."""
    for table in _FORBIDDEN_SDE_TABLES:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count > 0:
            raise RuntimeError(
                f"SICHERHEITSABBRUCH: Tabelle '{table}' enthält {count} "
                f"Zeile(n), obwohl sie als dynamisch/NICHT-aus-SDE-befüllbar "
                f"markiert ist (siehe _FORBIDDEN_SDE_TABLES). Ein _build_*-"
                f"Schritt hat vermutlich versehentlich diese Tabelle befüllt "
                f"— das ist ein Programmierfehler, kein Datenproblem."
            )
    _log.info(f"Bestätigt: {_FORBIDDEN_SDE_TABLES} sind leer, wie vorgeschrieben.")


class ValidationError(Exception):
    """Siehe sde_to_items_db.ValidationError für die ausführliche
    Begründung — gleiches Prinzip: verhindert, dass eine Datenbank mit
    stillschweigend falschen/leeren Werten (z.B. durch ein von CCP
    umbenanntes Feld) erfolgreich gebaut und übernommen wird."""
    pass


def _validate_built_database(conn) -> None:
    problems = []

    def check_min_rows(table: str, min_expected: int):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count < min_expected:
            problems.append(
                f"Tabelle '{table}' hat nur {count} Zeilen, erwartet "
                f"mindestens {min_expected} — möglicherweise hat sich ein "
                f"SDE-Feldname/Dateiformat geändert."
            )

    # Großzügige Mindestwerte, deutlich unter den real beim Bauen mit
    # Build 3409592 gesehenen Zahlen (siehe Logging beim Bauen).
    check_min_rows("regions", 80)
    check_min_rows("constellations", 1000)
    check_min_rows("solar_systems", 5000)
    check_min_rows("stars", 4000)
    check_min_rows("celestial_bodies", 50000)
    check_min_rows("stargates", 4000)
    check_min_rows("npc_corporations", 200)
    check_min_rows("npc_stations", 4000)

    # Stichprobe: The Forge (10000002) muss existieren und korrekt
    # benannt sein — bekanntestes, garantiert vorhandenes System.
    row = conn.execute(
        "SELECT name_en FROM regions WHERE id = 10000002"
    ).fetchone()
    if row is None or not row[0] or row[0].strip() == "" or row[0].startswith("["):
        problems.append(
            f"Region 'The Forge' (id=10000002) fehlt oder hat keinen "
            f"gültigen Namen ('{row[0] if row else None}') — das Feld "
            f"'name'/'name.en' hat sich vermutlich geändert."
        )

    total_systems = conn.execute("SELECT COUNT(*) FROM solar_systems").fetchone()[0]
    bad_names = conn.execute(
        "SELECT COUNT(*) FROM solar_systems WHERE name_en IS NULL "
        "OR name_en = '' OR name_en LIKE '[unnamed:%'"
    ).fetchone()[0]
    if total_systems > 0 and (bad_names / total_systems) > 0.05:
        problems.append(
            f"{bad_names} von {total_systems} Solar-Systemen "
            f"({bad_names/total_systems*100:.1f}%) haben einen leeren oder "
            f"Platzhalter-Namen — das 'name'-Feld hat sich vermutlich geändert."
        )

    if problems:
        problem_list = "\n  - ".join(problems)
        raise ValidationError(
            f"Die neu gebaute universe.sqlite hat die Plausibilitätsprüfung "
            f"NICHT bestanden — der Build wird verworfen, die bisherige "
            f"Datenbank bleibt unverändert. Gefundene Probleme:\n  - {problem_list}"
        )
    _log.info("Plausibilitätsprüfung der neuen universe.sqlite erfolgreich bestanden.")