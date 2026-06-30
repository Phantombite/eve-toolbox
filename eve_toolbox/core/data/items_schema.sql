-- items.sqlite — Schema-Definition
--
-- Eigenes, von der CCP-SDE-Rohstruktur entkoppeltes Schema (siehe
-- items_schema.md für die ausführliche Begründung und Herkunfts-
-- Dokumentation pro Spalte). Wird von core/data/sde_to_items_db.py
-- beim Aufbau der Datenbank ausgeführt — diese Datei selbst enthält
-- KEINE Daten, nur die Struktur.
--
-- WICHTIG: SQLite prüft Foreign-Key-Constraints NICHT automatisch.
-- Jede Verbindung zu dieser Datenbank MUSS nach dem Öffnen
-- "PRAGMA foreign_keys = ON;" ausführen (siehe core/data/db.py).

PRAGMA foreign_keys = ON;

-- ── Meta (Debugging / Update-Steuerung) ─────────────────────────────
CREATE TABLE meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- ── Kern-Tabellen ────────────────────────────────────────────────────

CREATE TABLE categories (
    id        INTEGER PRIMARY KEY,
    name_en   TEXT NOT NULL,
    name_de   TEXT NOT NULL,
    published BOOLEAN NOT NULL
);

CREATE TABLE groups_ (
    id           INTEGER PRIMARY KEY,
    category_id  INTEGER REFERENCES categories(id),
    name_en      TEXT NOT NULL,
    name_de      TEXT NOT NULL,
    published    BOOLEAN NOT NULL
);
-- Hinweis: Tabellenname "groups_" mit Unterstrich, da "groups" ein
-- reserviertes SQL-Schlüsselwort ist und in manchen Kontexten zu
-- Verwirrung führen kann — auch wenn SQLite es in Anführungszeichen
-- erlauben würde, ist der eindeutige Name robuster.

CREATE TABLE icons (
    id        INTEGER PRIMARY KEY,
    icon_file TEXT NOT NULL
);

CREATE TABLE meta_groups (
    id      INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL,
    name_de TEXT NOT NULL
);

CREATE TABLE market_groups (
    id              INTEGER PRIMARY KEY,
    parent_id       INTEGER REFERENCES market_groups(id),
    name_en         TEXT NOT NULL,
    name_de         TEXT NOT NULL,
    description_en  TEXT,
    icon_id         INTEGER REFERENCES icons(id),
    has_types       BOOLEAN NOT NULL
);

CREATE TABLE items (
    id               INTEGER PRIMARY KEY,
    name_en          TEXT NOT NULL,
    name_de          TEXT NOT NULL,
    group_id         INTEGER REFERENCES groups_(id),
    market_group_id  INTEGER REFERENCES market_groups(id),
    meta_group_id    INTEGER REFERENCES meta_groups(id),
    icon_id          INTEGER REFERENCES icons(id),
    description_en   TEXT,
    volume           REAL,
    mass             REAL,
    capacity         REAL,
    portion_size     INTEGER NOT NULL,
    published        BOOLEAN NOT NULL,
    base_price       REAL
);
-- Index für die häufigste Markt-Browser-Abfrage: "alle handelbaren
-- Items einer Markt-Gruppe".
CREATE INDEX idx_items_market_group ON items(market_group_id, published);
-- Indizes für Namenssuche (Markt-Suchleiste).
CREATE INDEX idx_items_name_en ON items(name_en);
CREATE INDEX idx_items_name_de ON items(name_de);

-- ── Verknüpfungstabellen (normalisiert aus verschachtelten SDE-Listen) ──

CREATE TABLE item_materials (
    item_id          INTEGER NOT NULL REFERENCES items(id),
    material_item_id INTEGER NOT NULL REFERENCES items(id),
    quantity         INTEGER NOT NULL,
    PRIMARY KEY (item_id, material_item_id)
);

CREATE TABLE dogma_units (
    id               INTEGER PRIMARY KEY,
    name_en          TEXT NOT NULL,
    display_name_en  TEXT
);

CREATE TABLE dogma_attribute_categories (
    id      INTEGER PRIMARY KEY,
    name_en TEXT NOT NULL
);

CREATE TABLE dogma_attributes (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    display_name_en  TEXT,
    display_name_de  TEXT,
    description      TEXT,
    unit_id          INTEGER REFERENCES dogma_units(id),
    category_id      INTEGER REFERENCES dogma_attribute_categories(id),
    high_is_good     BOOLEAN NOT NULL,
    published        BOOLEAN NOT NULL
);

CREATE TABLE item_dogma_attributes (
    item_id      INTEGER NOT NULL REFERENCES items(id),
    attribute_id INTEGER NOT NULL REFERENCES dogma_attributes(id),
    value        REAL NOT NULL,
    PRIMARY KEY (item_id, attribute_id)
);
CREATE INDEX idx_item_dogma_attributes_attr ON item_dogma_attributes(attribute_id);

CREATE TABLE dogma_effects (
    id            INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    guid          TEXT,
    is_offensive  BOOLEAN NOT NULL,
    is_assistance BOOLEAN NOT NULL,
    published     BOOLEAN NOT NULL
);

CREATE TABLE item_dogma_effects (
    item_id     INTEGER NOT NULL REFERENCES items(id),
    effect_id   INTEGER NOT NULL REFERENCES dogma_effects(id),
    is_default  BOOLEAN NOT NULL,
    PRIMARY KEY (item_id, effect_id)
);

CREATE TABLE blueprints (
    blueprint_item_id    INTEGER PRIMARY KEY REFERENCES items(id),
    max_production_limit INTEGER NOT NULL
);

-- Lookup-Tabelle statt freiem TEXT — verhindert Tippfehler-Varianten
-- wie "Manufacturing" vs. "manufacturing" und macht den Wertebereich
-- explizit statt implizit über die Daten definiert. id-Werte werden
-- vom Builder beim ersten Auftreten eines neuen activity-Strings aus
-- der SDE vergeben (siehe sde_to_items_db.py) und in der meta-Tabelle
-- dokumentiert NICHT festgelegt — sie sind reine interne Kennungen,
-- kein offizieller CCP-Code.
CREATE TABLE activity_types (
    id      INTEGER PRIMARY KEY,
    name    TEXT NOT NULL UNIQUE
);

CREATE TABLE blueprint_activities (
    blueprint_item_id INTEGER NOT NULL REFERENCES blueprints(blueprint_item_id),
    activity_type_id  INTEGER NOT NULL REFERENCES activity_types(id),
    time_seconds      INTEGER NOT NULL,
    PRIMARY KEY (blueprint_item_id, activity_type_id)
);

CREATE TABLE blueprint_activity_materials (
    blueprint_item_id INTEGER NOT NULL,
    activity_type_id  INTEGER NOT NULL REFERENCES activity_types(id),
    material_item_id  INTEGER NOT NULL REFERENCES items(id),
    quantity          INTEGER NOT NULL,
    PRIMARY KEY (blueprint_item_id, activity_type_id, material_item_id),
    FOREIGN KEY (blueprint_item_id, activity_type_id)
        REFERENCES blueprint_activities(blueprint_item_id, activity_type_id)
);

CREATE TABLE blueprint_activity_products (
    blueprint_item_id INTEGER NOT NULL,
    activity_type_id  INTEGER NOT NULL REFERENCES activity_types(id),
    product_item_id   INTEGER NOT NULL REFERENCES items(id),
    quantity          INTEGER NOT NULL,
    probability       REAL,
    PRIMARY KEY (blueprint_item_id, activity_type_id, product_item_id),
    FOREIGN KEY (blueprint_item_id, activity_type_id)
        REFERENCES blueprint_activities(blueprint_item_id, activity_type_id)
);

CREATE TABLE blueprint_activity_skills (
    blueprint_item_id INTEGER NOT NULL,
    activity_type_id  INTEGER NOT NULL REFERENCES activity_types(id),
    skill_item_id     INTEGER NOT NULL REFERENCES items(id),
    level             INTEGER NOT NULL,
    PRIMARY KEY (blueprint_item_id, activity_type_id, skill_item_id),
    FOREIGN KEY (blueprint_item_id, activity_type_id)
        REFERENCES blueprint_activities(blueprint_item_id, activity_type_id)
);

-- ── Sonstige flache Tabellen ─────────────────────────────────────────

CREATE TABLE compressible_types (
    item_id            INTEGER PRIMARY KEY REFERENCES items(id),
    compressed_item_id INTEGER NOT NULL REFERENCES items(id)
);

CREATE TABLE contraband_types (
    item_id              INTEGER NOT NULL REFERENCES items(id),
    faction_id           INTEGER NOT NULL,
    attack_min_sec       REAL,
    confiscate_min_sec   REAL,
    fine_by_value        REAL,
    standing_loss        REAL,
    PRIMARY KEY (item_id, faction_id)
);