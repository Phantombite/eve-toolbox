-- characters.sqlite — Schema-Definition
--
-- Eigenes, von der CCP-SDE-Rohstruktur entkoppeltes Schema (siehe
-- characters_schema.md für die ausführliche Begründung). Wird von
-- core/data/sde_to_characters_db.py beim Aufbau der Datenbank
-- ausgeführt.
--
-- WICHTIG: SQLite prüft Foreign-Key-Constraints NICHT automatisch.
-- Jede Verbindung MUSS "PRAGMA foreign_keys = ON;" ausführen (siehe
-- core/data/db.py).
--
-- Mehrere Spalten verweisen NUR LOGISCH auf items.sqlite/universe.sqlite
-- (andere Datenbanken, kein echter SQL-Foreign-Key über Dateigrenzen
-- hinweg) — als Kommentar "-- REFERENCES tabelle(spalte), andere
-- Datenbank" markiert, rein zur Lesbarkeit.

PRAGMA foreign_keys = ON;

-- ── Meta ─────────────────────────────────────────────────────────────
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ── Rassen & Bloodlines ──────────────────────────────────────────────

CREATE TABLE races (
    id              INTEGER PRIMARY KEY,
    name_en         TEXT NOT NULL,
    name_de         TEXT NOT NULL,
    description_en  TEXT,
    icon_id         INTEGER,  -- REFERENCES icons(id), andere Datenbank (items.sqlite)
    ship_type_id    INTEGER   -- REFERENCES items(id), andere Datenbank
);

CREATE TABLE race_skills (
    race_id       INTEGER NOT NULL REFERENCES races(id),
    skill_item_id INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    value         INTEGER NOT NULL,
    PRIMARY KEY (race_id, skill_item_id)
);

CREATE TABLE bloodlines (
    id              INTEGER PRIMARY KEY,
    race_id         INTEGER NOT NULL REFERENCES races(id),
    name_en         TEXT NOT NULL,
    name_de         TEXT NOT NULL,
    description_en  TEXT,
    icon_id         INTEGER,  -- REFERENCES icons(id), andere Datenbank
    corporation_id  INTEGER,  -- REFERENCES npc_corporations(id), andere Datenbank (universe.sqlite)
    charisma        INTEGER NOT NULL,
    intelligence    INTEGER NOT NULL,
    memory          INTEGER NOT NULL,
    perception      INTEGER NOT NULL,
    willpower       INTEGER NOT NULL
);
CREATE INDEX idx_bloodlines_race ON bloodlines(race_id);

CREATE TABLE ancestries (
    id                    INTEGER PRIMARY KEY,
    bloodline_id          INTEGER NOT NULL REFERENCES bloodlines(id),
    name_en               TEXT NOT NULL,
    name_de               TEXT NOT NULL,
    description_en        TEXT,
    short_description_en  TEXT,
    icon_id               INTEGER,  -- REFERENCES icons(id), andere Datenbank
    charisma              INTEGER NOT NULL,
    intelligence          INTEGER NOT NULL,
    memory                INTEGER NOT NULL,
    perception            INTEGER NOT NULL,
    willpower             INTEGER NOT NULL
);
CREATE INDEX idx_ancestries_bloodline ON ancestries(bloodline_id);

-- ── Charakter-Attribute & -Titel ─────────────────────────────────────

CREATE TABLE character_attributes (
    id                    INTEGER PRIMARY KEY,
    name_en               TEXT NOT NULL,
    name_de               TEXT NOT NULL,
    description           TEXT,
    short_description_en  TEXT,
    notes                 TEXT,
    icon_id               INTEGER  -- REFERENCES icons(id), andere Datenbank
);

-- character_titles: id ist bewusst TEXT, nicht INTEGER — die SDE
-- verwendet hier UUID-Strings als Schlüssel (Sonderfall gegenüber
-- praktisch jeder anderen SDE-Datei). Der Builder MUSS dies explizit
-- behandeln, nicht implizit von einem Integer-Schlüssel ausgehen.
CREATE TABLE character_titles (
    id      TEXT PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_de TEXT NOT NULL
);

CREATE TABLE agent_types (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- ── Zertifikate & Masteries ──────────────────────────────────────────

CREATE TABLE certificate_tiers (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE certificates (
    id              INTEGER PRIMARY KEY,
    name_en         TEXT NOT NULL,
    name_de         TEXT NOT NULL,
    description_en  TEXT,
    group_id        INTEGER  -- eigener Zertifikat-Gruppen-Namespace, NICHT items.sqlite groups_
);

CREATE TABLE certificate_skill_requirements (
    certificate_id INTEGER NOT NULL REFERENCES certificates(id),
    skill_item_id  INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    tier_id        INTEGER NOT NULL REFERENCES certificate_tiers(id),
    level          INTEGER NOT NULL,
    PRIMARY KEY (certificate_id, skill_item_id, tier_id)
);
CREATE INDEX idx_cert_skill_req_skill ON certificate_skill_requirements(skill_item_id);

CREATE TABLE certificate_recommendations (
    certificate_id INTEGER NOT NULL REFERENCES certificates(id),
    ship_item_id   INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    PRIMARY KEY (certificate_id, ship_item_id)
);

CREATE TABLE masteries (
    ship_item_id INTEGER PRIMARY KEY  -- REFERENCES items(id), andere Datenbank
);

CREATE TABLE mastery_levels (
    ship_item_id INTEGER NOT NULL REFERENCES masteries(ship_item_id),
    level        INTEGER NOT NULL,
    PRIMARY KEY (ship_item_id, level)
);

CREATE TABLE mastery_level_certificates (
    ship_item_id   INTEGER NOT NULL,
    level          INTEGER NOT NULL,
    certificate_id INTEGER NOT NULL REFERENCES certificates(id),
    PRIMARY KEY (ship_item_id, level, certificate_id),
    FOREIGN KEY (ship_item_id, level) REFERENCES mastery_levels(ship_item_id, level)
);

-- ── Klon-Stufen ───────────────────────────────────────────────────────

CREATE TABLE clone_grades (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE clone_grade_skills (
    clone_grade_id INTEGER NOT NULL REFERENCES clone_grades(id),
    skill_item_id  INTEGER NOT NULL,  -- REFERENCES items(id), andere Datenbank
    level          INTEGER NOT NULL,
    PRIMARY KEY (clone_grade_id, skill_item_id)
);