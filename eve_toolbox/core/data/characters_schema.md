# characters.sqlite — Schema-Entwurf

Gleiche Prinzipien wie items_schema.md/universe_schema.md: eigenes,
von der SDE-Rohstruktur entkoppeltes Schema, snake_case, normalisierte
Tabellen statt verschachtelter JSON-Listen, vollständige Erfassung.

Umfasst NUR die klar zu "Charakter-Erschaffung/Ausbildung" gehörenden
SDE-Dateien — factions/npcCharacters/corporationActivities wurden nach
echter Datensichtung nach universe.sqlite verschoben (siehe dortige
Begründung), da sie stärkere Verweise auf Universe-Konzepte
(Korporationen, Stationen, Systeme) als auf Charakter-Erschaffung
haben.

## Meta-Tabelle (identisch zu items.sqlite/universe.sqlite)

### meta
| Spalte | Typ  |
|--------|------|
| key    | TEXT PK |
| value  | TEXT |
Bekannte Keys: `sde_build`, `schema_version`, `created_at`.

## Rassen & Bloodlines

### races
| Spalte         | Typ     | Quelle (SDE)         |
|------------------|---------|------------------------|
| id              | INTEGER PK | races._key         |
| name_en         | TEXT    | .name.en               |
| name_de         | TEXT    | .name.de               |
| description_en  | TEXT NULL | .description.en      |
| icon_id         | INTEGER NULL -- REFERENCES icons(id), andere Datenbank (items.sqlite) | .iconID |
| ship_type_id    | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .shipTypeID |

### race_skills  (Standard-Skillpunkte pro Rasse, aus races.skills[] normalisiert)
| Spalte     | Typ     | Quelle (SDE)       |
|------------|---------|----------------------|
| race_id    | INTEGER FK -> races.id | skills[]._key   |
| skill_item_id | INTEGER NOT NULL -- REFERENCES items(id), andere Datenbank | skills[]._key |
| value      | INTEGER | skills[]._value        |
PK: (race_id, skill_item_id)

### bloodlines
| Spalte         | Typ     | Quelle (SDE)             |
|------------------|---------|----------------------------|
| id              | INTEGER PK | bloodlines._key        |
| race_id         | INTEGER FK -> races.id | .raceID            |
| name_en         | TEXT    | .name.en                  |
| name_de         | TEXT    | .name.de                  |
| description_en  | TEXT NULL | .description.en         |
| icon_id         | INTEGER NULL -- REFERENCES icons(id), andere Datenbank | .iconID |
| corporation_id  | INTEGER NULL -- REFERENCES npc_corporations(id), andere Datenbank (universe.sqlite) | .corporationID |
| charisma        | INTEGER | .charisma                  |
| intelligence    | INTEGER | .intelligence              |
| memory          | INTEGER | .memory                    |
| perception      | INTEGER | .perception                |
| willpower       | INTEGER | .willpower                 |

### ancestries
| Spalte         | Typ     | Quelle (SDE)               |
|------------------|---------|-------------------------------|
| id              | INTEGER PK | ancestries._key           |
| bloodline_id    | INTEGER FK -> bloodlines.id | .bloodlineID          |
| name_en         | TEXT    | .name.en                     |
| name_de         | TEXT    | .name.de                     |
| description_en  | TEXT NULL | .description.en            |
| short_description_en | TEXT NULL | .shortDescription.en  |
| icon_id         | INTEGER NULL -- REFERENCES icons(id), andere Datenbank | .iconID |
| charisma        | INTEGER | .charisma                     |
| intelligence    | INTEGER | .intelligence                 |
| memory          | INTEGER | .memory                       |
| perception      | INTEGER | .perception                   |
| willpower       | INTEGER | .willpower                    |

## Charakter-Attribute & -Titel

### character_attributes
(Intelligence/Charisma/etc. selbst als Konzept — NICHT die Werte eines
einzelnen Charakters, sondern die Definition/Beschreibung des Attributs)
| Spalte             | Typ  | Quelle (SDE)              |
|----------------------|------|-----------------------------|
| id                  | INTEGER PK | characterAttributes._key |
| name_en             | TEXT | .name.en                   |
| name_de             | TEXT | .name.de                   |
| description         | TEXT NULL | .description (HTML-Text, einsprachig in der SDE) |
| short_description_en | TEXT NULL | .shortDescription       |
| notes               | TEXT NULL | .notes                    |
| icon_id             | INTEGER NULL -- REFERENCES icons(id), andere Datenbank | .iconID |

### character_titles
| Spalte | Typ  | Quelle (SDE)            |
|--------|------|---------------------------|
| id     | TEXT PRIMARY KEY | characterTitles._key (UUID-String, NICHT Integer — Sonderfall in dieser SDE-Datei) |
| name_en | TEXT | .name.en                  |
| name_de | TEXT | .name.de                  |

### agent_types
(sehr kleine Lookup-Liste, z.B. "NonAgent")
| Spalte | Typ  | Quelle (SDE)        |
|--------|------|-----------------------|
| id     | INTEGER PK | agentTypes._key  |
| name   | TEXT | .name (einfacher String, kein mehrsprachiges Objekt) |

## Zertifikate & Masteries

### certificates
| Spalte         | Typ     | Quelle (SDE)            |
|------------------|---------|----------------------------|
| id              | INTEGER PK | certificates._key      |
| name_en         | TEXT    | .name.en                  |
| name_de         | TEXT    | .name.de                  |
| description_en  | TEXT NULL | .description.en         |
| group_id        | INTEGER NULL | .groupID (Achtung: eigener Zertifikat-Gruppen-Namespace, NICHT items.sqlite groups_) |

### certificate_tiers  (Lookup-Tabelle, ersetzt freien TEXT — gleiche
### Begründung wie celestial_body_types/activity_types)
| Spalte | Typ  |
|--------|------|
| id     | INTEGER PK |
| name   | TEXT UNIQUE ('basic' \| 'standard' \| 'improved' \| 'advanced' \| 'elite') |
Feste, bekannte 5-Werte-Menge — anders als bei activity_types (deren
Werte erst beim Bauen aus der SDE entdeckt werden) sind hier alle 5
Stufen von vornherein bekannt, daher feste ID-Zuordnung möglich:
1=basic, 2=standard, 3=improved, 4=advanced, 5=elite.

### certificate_skill_requirements  (aus certificates.skillTypes[] normalisiert)
Fünf Stufen pro Skill (basic/standard/improved/advanced/elite) — werden
NICHT als 5 Spalten in einer Zeile gespeichert, sondern als 5 einzelne
Zeilen mit einer `tier_id`-Spalte, damit Abfragen wie "alle Skills für
Stufe X" ohne Spalten-Auswahl-Logik möglich sind.
| Spalte         | Typ     | Quelle (SDE)              |
|------------------|---------|------------------------------|
| certificate_id  | INTEGER FK -> certificates.id | skillTypes[]._key   |
| skill_item_id   | INTEGER -- REFERENCES items(id), andere Datenbank | skillTypes[]._key |
| tier_id         | INTEGER FK -> certificate_tiers.id | skillTypes[].basic / .standard / .improved / .advanced / .elite (Feldname bestimmt tier_id) |
| level           | INTEGER | entsprechender Wert             |
PK: (certificate_id, skill_item_id, tier_id)

### certificate_recommendations  (aus certificates.recommendedFor[] normalisiert)
| Spalte         | Typ  | Quelle (SDE)                |
|------------------|------|--------------------------------|
| certificate_id  | INTEGER FK -> certificates.id | recommendedFor[]   |
| ship_item_id    | INTEGER -- REFERENCES items(id), andere Datenbank | recommendedFor[] |
PK: (certificate_id, ship_item_id)

### masteries
(Schiffstyp -> Mastery-Level -> benötigte Zertifikate)
| Spalte         | Typ  | Quelle (SDE)         |
|------------------|------|------------------------|
| ship_item_id    | INTEGER PRIMARY KEY -- REFERENCES items(id), andere Datenbank | masteries._key |

### mastery_levels
| Spalte         | Typ     | Quelle (SDE)                |
|------------------|---------|--------------------------------|
| ship_item_id    | INTEGER FK -> masteries.ship_item_id | _value[]._key (0,1,2,...) |
| level           | INTEGER | _value[]._key                   |
PK: (ship_item_id, level)

### mastery_level_certificates  (aus _value[]._value[] normalisiert)
| Spalte         | Typ  | Quelle (SDE)              |
|------------------|------|------------------------------|
| ship_item_id    | INTEGER | _value[]._key (= ship)    |
| level           | INTEGER | _value[]._key (= Mastery-Level) |
| certificate_id  | INTEGER FK -> certificates.id | _value[]._value[]   |
PK: (ship_item_id, level, certificate_id)
FK: (ship_item_id, level) -> mastery_levels

## Klon-Stufen

### clone_grades
(Skill-Sets für verschiedene Klon-Qualitätsstufen, z.B. "Alpha Caldari"
— analog zu races.skills, aber pro Klon-Stufe statt pro Rasse)
| Spalte | Typ  | Quelle (SDE)          |
|--------|------|--------------------------|
| id     | INTEGER PK | cloneGrades._key   |
| name   | TEXT | .name (einfacher String) |

### clone_grade_skills
| Spalte         | Typ     | Quelle (SDE)              |
|------------------|---------|------------------------------|
| clone_grade_id  | INTEGER FK -> clone_grades.id | skills[].typeID     |
| skill_item_id   | INTEGER -- REFERENCES items(id), andere Datenbank | skills[].typeID |
| level           | INTEGER | skills[].level                |
PK: (clone_grade_id, skill_item_id)

## Wichtiger Hinweis: Verweise auf andere Datenbanken

Mehrere Spalten hier verweisen NUR LOGISCH auf items.sqlite
(skill_item_id, ship_item_id, ...) oder universe.sqlite
(bloodlines.corporation_id) — gleiches Prinzip wie in
items_schema.md/universe_schema.md: Kommentar-Dokumentation
(`-- REFERENCES tabelle(spalte), andere Datenbank`), kein echter SQL-
Foreign-Key über Dateigrenzen hinweg.

## Architekturregel: Repository-Schicht (gilt projektweit, identisch
## zu items.sqlite/universe.sqlite — siehe dortige Dokumentation)

KEIN UI-Code und KEIN Modul-Code führt jemals direkt SQL gegen
characters.sqlite aus — ausschließlich über eine CharacterRepository-
Klasse, analog zu ItemRepository/UniverseRepository.