-- universe.sqlite — Schema-Definition
--
-- Eigenes, von der CCP-SDE-Rohstruktur entkoppeltes Schema (siehe
-- universe_schema.md für die ausführliche Begründung und Herkunfts-
-- Dokumentation pro Spalte). Wird von core/data/sde_to_universe_db.py
-- beim Aufbau der Datenbank ausgeführt.
--
-- WICHTIG: SQLite prüft Foreign-Key-Constraints NICHT automatisch.
-- Jede Verbindung zu dieser Datenbank MUSS nach dem Öffnen
-- "PRAGMA foreign_keys = ON;" ausführen (siehe core/data/db.py).
--
-- Mehrere Spalten verweisen NUR LOGISCH auf items.sqlite (andere
-- Datenbank, kein echter SQL-Foreign-Key über Dateigrenzen hinweg) —
-- diese sind im Kommentar als "-- REFERENCES items(id), andere
-- Datenbank" markiert, rein zur Lesbarkeit.

PRAGMA foreign_keys = ON;

-- ── Meta ─────────────────────────────────────────────────────────────
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ── Geografische Hierarchie ──────────────────────────────────────────

CREATE TABLE regions (
    id        INTEGER PRIMARY KEY,
    name_en   TEXT NOT NULL,
    name_de   TEXT NOT NULL,
    faction_id INTEGER,  -- REFERENCES factions(id), andere Datenbank (characters.sqlite)
    pos_x     REAL,
    pos_y     REAL,
    pos_z     REAL
);

CREATE TABLE constellations (
    id                 INTEGER PRIMARY KEY,
    region_id          INTEGER NOT NULL REFERENCES regions(id),
    name_en            TEXT NOT NULL,
    name_de            TEXT NOT NULL,
    faction_id         INTEGER,  -- REFERENCES factions(id), andere Datenbank
    wormhole_class_id  INTEGER,
    pos_x REAL, pos_y REAL, pos_z REAL
);
CREATE INDEX idx_constellations_region ON constellations(region_id);

CREATE TABLE solar_systems (
    id               INTEGER PRIMARY KEY,
    constellation_id INTEGER NOT NULL REFERENCES constellations(id),
    region_id        INTEGER NOT NULL REFERENCES regions(id),
    name_en          TEXT NOT NULL,
    name_de          TEXT NOT NULL,
    security_status  REAL NOT NULL,
    security_class   TEXT,
    star_id          INTEGER,  -- REFERENCES stars(id) -- zirkulär, stars wird NACH solar_systems befüllt, daher keine echte FK-Constraint hier
    luminosity       REAL,
    radius           REAL,
    border           BOOLEAN NOT NULL DEFAULT 0,
    hub              BOOLEAN NOT NULL DEFAULT 0,
    international    BOOLEAN NOT NULL DEFAULT 0,
    regional         BOOLEAN NOT NULL DEFAULT 0,
    pos_x REAL, pos_y REAL, pos_z REAL,
    pos2d_x REAL, pos2d_y REAL
);
CREATE INDEX idx_solar_systems_region ON solar_systems(region_id);
CREATE INDEX idx_solar_systems_security ON solar_systems(security_status);
CREATE INDEX idx_solar_systems_name_en ON solar_systems(name_en);

-- ── Himmelskörper ─────────────────────────────────────────────────────

CREATE TABLE stars (
    id              INTEGER PRIMARY KEY,
    solar_system_id INTEGER NOT NULL REFERENCES solar_systems(id),
    type_item_id    INTEGER,  -- REFERENCES items(id), andere Datenbank
    radius          REAL,
    age             REAL,
    life            REAL,
    luminosity      REAL,
    spectral_class  TEXT,
    temperature     REAL
);
CREATE INDEX idx_stars_solar_system ON stars(solar_system_id);

CREATE TABLE secondary_suns (
    id                    INTEGER PRIMARY KEY,
    solar_system_id       INTEGER NOT NULL REFERENCES solar_systems(id),
    type_item_id          INTEGER,  -- REFERENCES items(id), andere Datenbank
    effect_beacon_type_id INTEGER,
    pos_x REAL, pos_y REAL, pos_z REAL
);

CREATE TABLE celestial_body_types (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE celestial_bodies (
    id               INTEGER PRIMARY KEY,
    body_type_id     INTEGER NOT NULL REFERENCES celestial_body_types(id),
    solar_system_id  INTEGER NOT NULL REFERENCES solar_systems(id),
    orbit_id         INTEGER,  -- = id des Elternkörpers (z.B. Planet für einen Mond) — kein echter FK, da self-referencing über mehrere "Typen" hinweg möglich
    orbit_index      INTEGER,
    celestial_index  INTEGER,
    type_item_id     INTEGER,  -- REFERENCES items(id), andere Datenbank
    radius           REAL,
    pos_x REAL, pos_y REAL, pos_z REAL,
    density          REAL,
    eccentricity     REAL,
    escape_velocity  REAL,
    locked           BOOLEAN,
    mass_dust        REAL,
    mass_gas         REAL,
    orbit_period     REAL,
    orbit_radius     REAL,
    pressure         REAL,
    rotation_rate    REAL,
    spectral_class   TEXT,
    surface_gravity  REAL,
    temperature      REAL,
    height_map_1     INTEGER,
    height_map_2     INTEGER,
    shader_preset    INTEGER,
    population       BOOLEAN
);
CREATE INDEX idx_celestial_bodies_system_type ON celestial_bodies(solar_system_id, body_type_id);
CREATE INDEX idx_celestial_bodies_orbit ON celestial_bodies(orbit_id);

-- ── Sprungtore & Routenplanung ────────────────────────────────────────

CREATE TABLE stargates (
    id                      INTEGER PRIMARY KEY,
    solar_system_id         INTEGER NOT NULL REFERENCES solar_systems(id),
    type_item_id            INTEGER,  -- REFERENCES items(id), andere Datenbank
    destination_system_id   INTEGER REFERENCES solar_systems(id),
    destination_stargate_id INTEGER,  -- REFERENCES stargates(id) -- self-referencing, siehe Builder-Reihenfolge
    pos_x REAL, pos_y REAL, pos_z REAL
);
CREATE INDEX idx_stargates_solar_system ON stargates(solar_system_id);
CREATE INDEX idx_stargates_destination ON stargates(destination_system_id);

-- ── Stationen & NPC-Korporationen ─────────────────────────────────────

CREATE TABLE npc_corporations (
    id                     INTEGER PRIMARY KEY,
    name_en                TEXT NOT NULL,
    name_de                TEXT NOT NULL,
    ticker_name            TEXT,
    description_en         TEXT,
    station_id             INTEGER,  -- = Hauptsitz, kein FK hier da npc_stations erst NACH dieser Tabelle befüllt wird
    ceo_id                 INTEGER,  -- REFERENCES characters(id), andere Datenbank
    size                   TEXT,
    tax_rate               REAL,
    min_security           REAL,
    minimum_join_standing  REAL,
    deleted                BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE npc_corporation_divisions (
    id                  INTEGER PRIMARY KEY,
    internal_name       TEXT NOT NULL,
    display_name        TEXT NOT NULL,
    leader_type_name_en TEXT
);

CREATE TABLE station_services (
    id      INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_de TEXT NOT NULL
);

CREATE TABLE station_operations (
    id                    INTEGER PRIMARY KEY,
    activity_id           INTEGER,
    name_en               TEXT,
    description_en        TEXT,
    border                REAL,
    corridor              REAL,
    fringe                REAL,
    hub                   REAL,
    ratio                 REAL,
    manufacturing_factor  REAL,
    research_factor       REAL
);

CREATE TABLE station_operation_services (
    operation_id INTEGER NOT NULL REFERENCES station_operations(id),
    service_id   INTEGER NOT NULL REFERENCES station_services(id),
    PRIMARY KEY (operation_id, service_id)
);

CREATE TABLE npc_stations (
    id                            INTEGER PRIMARY KEY,
    solar_system_id               INTEGER NOT NULL REFERENCES solar_systems(id),
    celestial_index               INTEGER,
    orbit_id                      INTEGER,
    orbit_index                   INTEGER,
    owner_corporation_id          INTEGER REFERENCES npc_corporations(id),
    operation_id                  INTEGER REFERENCES station_operations(id),
    type_item_id                  INTEGER,  -- REFERENCES items(id), andere Datenbank
    use_operation_name            BOOLEAN NOT NULL DEFAULT 0,
    reprocessing_efficiency       REAL,
    reprocessing_stations_take    REAL,
    reprocessing_hangar_flag      INTEGER,
    pos_x REAL, pos_y REAL, pos_z REAL
);
CREATE INDEX idx_npc_stations_solar_system ON npc_stations(solar_system_id);
CREATE INDEX idx_npc_stations_owner ON npc_stations(owner_corporation_id);

-- ── Planetary Interaction (PI) ────────────────────────────────────────

CREATE TABLE planet_resources (
    celestial_body_id INTEGER PRIMARY KEY REFERENCES celestial_bodies(id),
    power             INTEGER
);

CREATE TABLE planet_schematics (
    id          INTEGER PRIMARY KEY,
    name_en     TEXT NOT NULL,
    name_de     TEXT NOT NULL,
    cycle_time  INTEGER NOT NULL
);

CREATE TABLE planet_schematic_pins (
    schematic_id INTEGER NOT NULL REFERENCES planet_schematics(id),
    item_id      INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    is_input     BOOLEAN NOT NULL,
    quantity     INTEGER NOT NULL,
    PRIMARY KEY (schematic_id, item_id, is_input)
);

-- ── Sonstiges ─────────────────────────────────────────────────────────

CREATE TABLE sovereignty_upgrades (
    id                       INTEGER PRIMARY KEY,
    mutually_exclusive_group TEXT,
    power_allocation         INTEGER,
    workforce_allocation     INTEGER,
    fuel_item_id             INTEGER,  -- REFERENCES items(id), andere Datenbank
    fuel_hourly_upkeep       INTEGER,
    fuel_startup_cost        INTEGER
);

CREATE TABLE control_tower_resources (
    tower_item_id INTEGER PRIMARY KEY  -- REFERENCES items(id), andere Datenbank
);

CREATE TABLE control_tower_resource_requirements (
    tower_item_id    INTEGER NOT NULL REFERENCES control_tower_resources(tower_item_id),
    resource_item_id INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    purpose          INTEGER NOT NULL,
    quantity         INTEGER NOT NULL,
    PRIMARY KEY (tower_item_id, resource_item_id, purpose)
);

CREATE TABLE agents_in_space (
    id              INTEGER PRIMARY KEY,
    solar_system_id INTEGER NOT NULL REFERENCES solar_systems(id),
    dungeon_id      INTEGER,
    spawn_point_id  INTEGER,
    type_item_id    INTEGER  -- REFERENCES items(id), andere Datenbank
);

CREATE TABLE landmarks (
    id             INTEGER PRIMARY KEY,
    name_en        TEXT NOT NULL,
    name_de        TEXT NOT NULL,
    description_en TEXT,
    pos_x REAL, pos_y REAL, pos_z REAL
);

-- ── Politik & Wirtschaft (nachträglich von characters.sqlite verschoben) ──
-- Begründung: starke Verweise auf Universe-Konzepte (Korporationen,
-- Stationen, Systeme) statt auf Charakter-Erschaffung. Siehe
-- universe_schema.md für die ausführliche Begründung.

CREATE TABLE factions (
    id                      INTEGER PRIMARY KEY,
    name_en                 TEXT NOT NULL,
    name_de                 TEXT NOT NULL,
    description_en          TEXT,
    short_description_en    TEXT,
    corporation_id          INTEGER REFERENCES npc_corporations(id),
    militia_corporation_id  INTEGER REFERENCES npc_corporations(id),
    solar_system_id         INTEGER REFERENCES solar_systems(id),
    icon_id                 INTEGER,  -- REFERENCES icons(id), andere Datenbank (items.sqlite)
    flat_logo               TEXT,
    flat_logo_with_name     TEXT,
    size_factor             REAL,
    unique_name             BOOLEAN NOT NULL DEFAULT 0
);

CREATE TABLE faction_member_races (
    faction_id INTEGER NOT NULL REFERENCES factions(id),
    race_id    INTEGER NOT NULL,  -- REFERENCES races(id), andere Datenbank (characters.sqlite)
    PRIMARY KEY (faction_id, race_id)
);

CREATE TABLE corporation_activities (
    id      INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_de TEXT NOT NULL
);

CREATE TABLE npc_characters (
    id              INTEGER PRIMARY KEY,
    name_en         TEXT NOT NULL,
    corporation_id  INTEGER REFERENCES npc_corporations(id),
    location_id     INTEGER,
    bloodline_id    INTEGER,  -- REFERENCES bloodlines(id), andere Datenbank (characters.sqlite)
    race_id         INTEGER,  -- REFERENCES races(id), andere Datenbank (characters.sqlite)
    gender          TEXT,
    is_ceo          BOOLEAN NOT NULL DEFAULT 0,
    start_date      TEXT,
    unique_name     BOOLEAN NOT NULL DEFAULT 0
);
CREATE INDEX idx_npc_characters_corporation ON npc_characters(corporation_id);

-- ── DYNAMISCHE Tabelle — NIEMALS aus der SDE befüllen ──────────────────
--
-- system_sovereignty beschreibt, wer AKTUELL welches Sternensystem
-- besitzt — das ist KEIN statisches SDE-Konzept (ändert sich durch
-- Nullsec-Kriege potenziell täglich), sondern müsste live über den
-- ESI-Endpunkt /sovereignty/map/ befüllt werden, analog zu Markt-
-- preisen. sde_to_universe_db.py darf NIEMALS eine Funktion enthalten,
-- die diese Tabelle aus einer SDE-JSONL-Datei befüllt — siehe die
-- Absicherung in core/data/sde_to_universe_db.py
-- (_FORBIDDEN_SDE_TABLES), die das technisch erzwingt, nicht nur per
-- Kommentar dokumentiert.
CREATE TABLE system_sovereignty (
    solar_system_id      INTEGER PRIMARY KEY REFERENCES solar_systems(id),
    faction_id           INTEGER REFERENCES factions(id),
    owner_corporation_id INTEGER REFERENCES npc_corporations(id),
    alliance_id          INTEGER,  -- Spieler-Allianzen sind kein SDE-Konzept, nur ESI
    last_updated         TEXT
);