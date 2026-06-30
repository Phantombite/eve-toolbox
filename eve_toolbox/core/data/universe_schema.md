# universe.sqlite — Schema-Entwurf

Gleiche Prinzipien wie items_schema.md: eigenes, von der SDE-Rohstruktur
entkoppeltes Schema, snake_case, normalisierte Tabellen statt
verschachtelter JSON-Listen, vollständige Erfassung (auf Wunsch des
Entwicklers: "wissen ist macht" — keine Detailwerte werden vorab
weggefiltert, auch wenn ihr Nutzen erst bei einem künftigen Modul wie
PI klar wird).

## Meta-Tabelle (identisch zu items.sqlite)

### meta
| Spalte | Typ  |
|--------|------|
| key    | TEXT PK |
| value  | TEXT |
Bekannte Keys: `sde_build`, `schema_version`, `created_at`.

## Geografische Hierarchie

### regions
(bereits bekannt aus items.sqlite-Diskussion, jetzt vollständig in
universe.sqlite, da hier der fachlich richtige Ort ist)
| Spalte   | Typ  | Quelle (SDE)          |
|----------|------|------------------------|
| id       | INTEGER PK | mapRegions._key   |
| name_en  | TEXT | mapRegions.name.en     |
| name_de  | TEXT | mapRegions.name.de     |
| faction_id | INTEGER NULL | mapRegions.factionID |
| pos_x, pos_y, pos_z | REAL | mapRegions.position.{x,y,z} |

### constellations
| Spalte        | Typ  | Quelle (SDE)                |
|-----------------|------|-------------------------------|
| id              | INTEGER PK | mapConstellations._key   |
| region_id       | INTEGER FK -> regions.id | mapConstellations.regionID |
| name_en         | TEXT | mapConstellations.name.en    |
| name_de         | TEXT | mapConstellations.name.de    |
| faction_id      | INTEGER NULL | mapConstellations.factionID |
| wormhole_class_id | INTEGER NULL | mapConstellations.wormholeClassID |
| pos_x, pos_y, pos_z | REAL | mapConstellations.position.{x,y,z} |

### solar_systems
| Spalte           | Typ     | Quelle (SDE)                  |
|--------------------|---------|----------------------------------|
| id                 | INTEGER PK | mapSolarSystems._key        |
| constellation_id   | INTEGER FK -> constellations.id | .constellationID |
| region_id          | INTEGER FK -> regions.id | .regionID (denormalisiert für schnellere Abfragen ohne Join über constellation) |
| name_en            | TEXT    | .name.en                       |
| name_de            | TEXT    | .name.de                       |
| security_status    | REAL    | .securityStatus                |
| security_class     | TEXT NULL | .securityClass               |
| star_id            | INTEGER FK -> stars.id NULL | .starID         |
| luminosity         | REAL NULL | .luminosity                  |
| radius             | REAL NULL | .radius                      |
| border             | BOOLEAN | .border (default false)        |
| hub                | BOOLEAN | .hub (default false)           |
| international      | BOOLEAN | .international (default false) |
| regional           | BOOLEAN | .regional (default false)      |
| pos_x, pos_y, pos_z | REAL   | .position.{x,y,z}               |
| pos2d_x, pos2d_y   | REAL NULL | .position2D.{x,y} (für 2D-Kartendarstellung, z.B. Dotlan-ähnliche Karte) |
Index: (region_id), (security_status) — für Routenplanung/Kartenfilter.

`planetIDs`/`stargateIDs` aus der SDE werden NICHT als Liste gespeichert
— die Beziehung existiert bereits andersrum (jeder Planet/jedes
Stargate hat selbst ein `solarSystemID`-Feld), eine zusätzliche
Liste wäre redundante, potenziell inkonsistente Doppelspeicherung.

## Himmelskörper

### stars
| Spalte          | Typ  | Quelle (SDE)            |
|-------------------|------|---------------------------|
| id                | INTEGER PK | mapStars._key        |
| solar_system_id   | INTEGER FK -> solar_systems.id | .solarSystemID |
| type_item_id      | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |
| radius            | REAL | .radius                   |
| age               | REAL NULL | .statistics.age      |
| life              | REAL NULL | .statistics.life      |
| luminosity        | REAL NULL | .statistics.luminosity |
| spectral_class    | TEXT NULL | .statistics.spectralClass |
| temperature       | REAL NULL | .statistics.temperature |

### secondary_suns
(deutlich einfachere Struktur als reguläre Sterne — Effekt-Beacons in
manchen Systemen, kein eigener statistics-Block)
| Spalte                | Typ  | Quelle (SDE)                 |
|-------------------------|------|--------------------------------|
| id                      | INTEGER PK | mapSecondarySuns._key    |
| solar_system_id         | INTEGER FK -> solar_systems.id | .solarSystemID |
| type_item_id            | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |
| effect_beacon_type_id   | INTEGER NULL | .effectBeaconTypeID      |
| pos_x, pos_y, pos_z     | REAL | .position.{x,y,z}              |

### celestial_body_types  (Lookup-Tabelle, ersetzt freien TEXT)
| Spalte | Typ  |
|--------|------|
| id     | INTEGER PK |
| name   | TEXT UNIQUE ('planet' \| 'moon' \| 'asteroid_belt') |
Feste, kleine Wertemenge — anders als bei activity_types (items.sqlite)
sind hier nur genau 3 Werte möglich, id-Zuordnung kann daher fix sein:
1=planet, 2=moon, 3=asteroid_belt.

### celestial_bodies
GEMEINSAME Tabelle für Planeten, Monde UND Asteroidengürtel — alle drei
teilen praktisch identische `statistics`-Felder in der SDE (verifiziert
anhand der aktuellen Daten), ein `body_type_id`-Unterscheidungsfeld macht
eine Aufspaltung in drei fast identische Tabellen unnötig.
| Spalte             | Typ     | Quelle (SDE)                      |
|----------------------|---------|--------------------------------------|
| id                  | INTEGER PK | mapPlanets/mapMoons/mapAsteroidBelts._key |
| body_type_id        | INTEGER FK -> celestial_body_types.id | (welche Quelldatei) |
| solar_system_id     | INTEGER FK -> solar_systems.id | .solarSystemID |
| orbit_id            | INTEGER NULL | .orbitID (= id des Elternkörpers, z.B. Planet für einen Mond) |
| orbit_index         | INTEGER NULL | .orbitIndex |
| celestial_index     | INTEGER NULL | .celestialIndex |
| type_item_id        | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |
| radius              | REAL NULL | .radius |
| pos_x, pos_y, pos_z | REAL    | .position.{x,y,z} |
| density             | REAL NULL | .statistics.density |
| eccentricity        | REAL NULL | .statistics.eccentricity |
| escape_velocity     | REAL NULL | .statistics.escapeVelocity |
| locked              | BOOLEAN NULL | .statistics.locked |
| mass_dust           | REAL NULL | .statistics.massDust |
| mass_gas            | REAL NULL | .statistics.massGas |
| orbit_period        | REAL NULL | .statistics.orbitPeriod |
| orbit_radius        | REAL NULL | .statistics.orbitRadius |
| pressure            | REAL NULL | .statistics.pressure |
| rotation_rate       | REAL NULL | .statistics.rotationRate |
| spectral_class      | TEXT NULL | .statistics.spectralClass |
| surface_gravity     | REAL NULL | .statistics.surfaceGravity |
| temperature         | REAL NULL | .statistics.temperature |
| height_map_1        | INTEGER NULL | .attributes.heightMap1 (nur Planeten/Monde) |
| height_map_2        | INTEGER NULL | .attributes.heightMap2 (nur Planeten/Monde) |
| shader_preset       | INTEGER NULL | .attributes.shaderPreset (nur Planeten/Monde) |
| population          | BOOLEAN NULL | .attributes.population (nur Planeten — ob bewohnt) |
Index: (solar_system_id, body_type_id), (orbit_id) — für "alle Monde
eines Planeten", "alle Himmelskörper eines Systems".

## Sprungtore & Routenplanung

### stargates
| Spalte                  | Typ     | Quelle (SDE)                |
|---------------------------|---------|--------------------------------|
| id                       | INTEGER PK | mapStargates._key         |
| solar_system_id          | INTEGER FK -> solar_systems.id | .solarSystemID |
| type_item_id             | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |
| destination_system_id    | INTEGER FK -> solar_systems.id | .destination.solarSystemID |
| destination_stargate_id  | INTEGER FK -> stargates.id | .destination.stargateID |
| pos_x, pos_y, pos_z      | REAL    | .position.{x,y,z}            |
Index: (solar_system_id), (destination_system_id) — beide Richtungen
für Pfadsuche (Dotlan-Alternative) gebraucht.

## Stationen & NPC-Korporationen

### npc_corporations
| Spalte                    | Typ     | Quelle (SDE)              |
|-----------------------------|---------|------------------------------|
| id                         | INTEGER PK | npcCorporations._key    |
| name_en                    | TEXT    | .name.en                    |
| name_de                    | TEXT    | .name.de                    |
| ticker_name                | TEXT NULL | .tickerName               |
| description_en             | TEXT NULL | .description.en           |
| station_id                 | INTEGER NULL | .stationID (Hauptsitz)  |
| ceo_id                     | INTEGER NULL | .ceoID                  |
| size                       | TEXT NULL | .size                     |
| tax_rate                   | REAL NULL | .taxRate                  |
| min_security               | REAL NULL | .minSecurity              |
| minimum_join_standing      | REAL NULL | .minimumJoinStanding      |
| deleted                    | BOOLEAN | .deleted (default false)    |

### npc_corporation_divisions
| Spalte             | Typ  | Quelle (SDE)                  |
|----------------------|------|---------------------------------|
| id                  | INTEGER PK | npcCorporationDivisions._key |
| internal_name       | TEXT | .internalName                  |
| display_name        | TEXT | .displayName                   |
| leader_type_name_en | TEXT NULL | .leaderTypeName.en        |

### station_operations
| Spalte          | Typ  | Quelle (SDE)                |
|-------------------|------|-------------------------------|
| id               | INTEGER PK | stationOperations._key   |
| activity_id      | INTEGER NULL | .activityID            |
| name_en          | TEXT NULL | .operationName.en (Achtung: Feldname laut Changelog umbenannt von operationNameID) |
| description_en   | TEXT NULL | .description.en          |
| border           | REAL NULL | .border                   |
| corridor         | REAL NULL | .corridor                  |
| fringe           | REAL NULL | .fringe (falls vorhanden, analog zu border/corridor) |
| hub              | REAL NULL | .hub (falls vorhanden)     |
| ratio            | REAL NULL | .ratio (falls vorhanden)   |

### station_services
| Spalte         | Typ  | Quelle (SDE)              |
|------------------|------|------------------------------|
| id              | INTEGER PK | stationServices._key   |
| name_en         | TEXT | .serviceName.en            |
| name_de         | TEXT | .serviceName.de            |

### npc_stations
KEIN eigenes name-Feld in der SDE (verifiziert: 0 von 5210 Stationen
haben eines) — der Anzeigename wird aus System + Orbit + Owner-
Korporation zusammengesetzt, das ist Aufgabe der Repository-Schicht
zur Abfragezeit, nicht der reinen Datenspeicherung.
| Spalte                         | Typ     | Quelle (SDE)                |
|----------------------------------|---------|--------------------------------|
| id                              | INTEGER PK | npcStations._key          |
| solar_system_id                 | INTEGER FK -> solar_systems.id | .solarSystemID |
| celestial_index                 | INTEGER NULL | .celestialIndex          |
| orbit_id                        | INTEGER NULL | .orbitID                 |
| orbit_index                     | INTEGER NULL | .orbitIndex               |
| owner_corporation_id            | INTEGER FK -> npc_corporations.id NULL | .ownerID |
| operation_id                    | INTEGER FK -> station_operations.id NULL | .operationID |
| type_item_id                    | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |
| use_operation_name              | BOOLEAN | .useOperationName (default false) |
| reprocessing_efficiency         | REAL NULL | .reprocessingEfficiency  |
| reprocessing_stations_take      | REAL NULL | .reprocessingStationsTake |
| reprocessing_hangar_flag        | INTEGER NULL | .reprocessingHangarFlag  |
| pos_x, pos_y, pos_z             | REAL    | .position.{x,y,z}            |
Index: (solar_system_id), (owner_corporation_id).

## Planetary Interaction (PI)

### planet_resources
(Hinweis: SDE-Feld ist nur `power` — sehr schlanke Datei, möglicherweise
ein Teil-Datensatz / könnte sich künftig erweitern, additiv aufnehmbar)
| Spalte            | Typ  | Quelle (SDE)              |
|---------------------|------|------------------------------|
| celestial_body_id  | INTEGER PK FK -> celestial_bodies.id | planetResources._key |
| power              | INTEGER NULL | .power                  |

### planet_schematics
(PI-"Rezepte" — Input-/Output-Materialien für PI-Produktionsketten,
analog zu blueprint_activity_materials/products in items.sqlite)
| Spalte        | Typ  | Quelle (SDE)             |
|-----------------|------|----------------------------|
| id             | INTEGER PK | planetSchematics._key |
| name_en        | TEXT | .name.en                  |
| name_de        | TEXT | .name.de                  |
| cycle_time     | INTEGER | .cycleTime               |

### planet_schematic_pins
| Spalte             | Typ     | Quelle (SDE)         |
|----------------------|---------|------------------------|
| schematic_id        | INTEGER FK -> planet_schematics.id | pins[]._key |
| item_id             | INTEGER NULL -- REFERENCES items(id), andere Datenbank | pins[]._key |
| is_input            | BOOLEAN | pins[].isInput          |
| quantity            | INTEGER | pins[].quantity         |
PK: (schematic_id, item_id, is_input) — ein Schema kann denselben Typ
theoretisch nicht doppelt als Input UND Output haben, aber die
Kombination aus allen drei Spalten ist sicher eindeutig.

## Sonstiges

### sovereignty_upgrades
| Spalte                    | Typ  | Quelle (SDE)                      |
|-----------------------------|------|--------------------------------------|
| id                         | INTEGER PK | sovereigntyUpgrades._key        |
| mutually_exclusive_group   | TEXT NULL | .mutually_exclusive_group         |
| power_allocation           | INTEGER NULL | .power_allocation               |
| workforce_allocation       | INTEGER NULL | .workforce_allocation           |
| fuel_item_id               | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .fuel.type_id |
| fuel_hourly_upkeep         | INTEGER NULL | .fuel.hourly_upkeep              |
| fuel_startup_cost          | INTEGER NULL | .fuel.startup_cost               |

### control_tower_resources
(Welche Treibstoffe/Ressourcen ein Control Tower (POS) braucht)
| Spalte    | Typ  | Quelle (SDE)   |
|-----------|------|------------------|
| tower_item_id | INTEGER PK -- REFERENCES items(id), andere Datenbank | controlTowerResources._key |

### control_tower_resource_requirements
| Spalte             | Typ     |
|----------------------|---------|
| tower_item_id        | INTEGER FK -> control_tower_resources.tower_item_id |
| resource_item_id     | INTEGER -- REFERENCES items(id), andere Datenbank |
| purpose              | INTEGER | (numerischer Code, Bedeutung laut ESI/SDE-Doku noch zu klären) |
| quantity             | INTEGER |
PK: (tower_item_id, resource_item_id, purpose)

### agents_in_space
| Spalte             | Typ  | Quelle (SDE)             |
|----------------------|------|----------------------------|
| id                  | INTEGER PK | agentsInSpace._key   |
| solar_system_id     | INTEGER FK -> solar_systems.id | .solarSystemID |
| dungeon_id          | INTEGER NULL | .dungeonID            |
| spawn_point_id      | INTEGER NULL | .spawnPointID          |
| type_item_id        | INTEGER NULL -- REFERENCES items(id), andere Datenbank | .typeID |

### landmarks
(Lore-Sehenswürdigkeiten wie das EVE Gate — niedrige Priorität, aber
vollständigkeitshalber mit aufgenommen, da Datei bereits klein ist)
| Spalte             | Typ  | Quelle (SDE)            |
|----------------------|------|---------------------------|
| id                  | INTEGER PK | landmarks._key       |
| name_en             | TEXT | .name.en                  |
| name_de             | TEXT | .name.de                  |
| description_en      | TEXT NULL | .description.en      |
| pos_x, pos_y, pos_z | REAL NULL | .position.{x,y,z} (mit x/y/z-Konvertierung, laut Changelog von Liste zu Objekt geändert) |

## Politik & Wirtschaft (nachträglich von characters.sqlite verschoben)

Begründung der Verschiebung: factions/npc_characters/corporation_
activities haben starke Verweise auf Universe-Konzepte (Korporationen,
Stationen, Systeme) — sie beschreiben "wer prägt/besitzt was in der
Spielwelt", nicht "wie wird ein Charakter erschaffen" (das bleibt in
characters.sqlite: races, bloodlines, ancestries, ...). Erkannt anhand
der echten SDE-Feldstruktur, nicht vorab angenommen (siehe gemeinsame
Diskussion mit Dragnax und externem Review).

### factions
| Spalte                   | Typ     | Quelle (SDE)                |
|----------------------------|---------|--------------------------------|
| id                        | INTEGER PK | factions._key             |
| name_en                   | TEXT    | .name.en                     |
| name_de                   | TEXT    | .name.de                     |
| description_en            | TEXT NULL | .description.en            |
| short_description_en      | TEXT NULL | .shortDescription.en       |
| corporation_id             | INTEGER FK -> npc_corporations.id NULL | .corporationID |
| militia_corporation_id     | INTEGER FK -> npc_corporations.id NULL | .militiaCorporationID |
| solar_system_id            | INTEGER FK -> solar_systems.id NULL | .solarSystemID (Heimatsystem) |
| icon_id                    | INTEGER FK -> icons.id NULL | .iconID |
| flat_logo                  | TEXT NULL | .flatLogo |
| flat_logo_with_name        | TEXT NULL | .flatLogoWithName |
| size_factor                | REAL NULL | .sizeFactor |
| unique_name                | BOOLEAN | .uniqueName (default false) |

### faction_member_races  (Verknüpfungstabelle, aus memberRaces[] normalisiert)
| Spalte     | Typ  | Quelle (SDE)   |
|------------|------|-----------------|
| faction_id | INTEGER FK -> factions.id | memberRaces[] |
| race_id    | INTEGER -- REFERENCES races(id), andere Datenbank (characters.sqlite) | memberRaces[] |
PK: (faction_id, race_id)

### corporation_activities
| Spalte  | Typ  | Quelle (SDE)                |
|---------|------|-------------------------------|
| id      | INTEGER PK | corporationActivities._key |
| name_en | TEXT | .name.en                      |
| name_de | TEXT | .name.de                      |

### npc_characters
| Spalte           | Typ     | Quelle (SDE)              |
|--------------------|---------|------------------------------|
| id                | INTEGER PK | npcCharacters._key      |
| name_en           | TEXT    | .name (Achtung: oft einfacher String, nicht immer mehrsprachiges Objekt — beim Builder prüfen) |
| corporation_id     | INTEGER FK -> npc_corporations.id NULL | .corporationID |
| location_id        | INTEGER NULL | .locationID (Station, kein FK da Stations- vs. Struktur-ID gemischt sein können) |
| bloodline_id       | INTEGER -- REFERENCES bloodlines(id), andere Datenbank (characters.sqlite) | .bloodlineID |
| race_id            | INTEGER -- REFERENCES races(id), andere Datenbank (characters.sqlite) | .raceID |
| gender             | TEXT NULL | .gender |
| is_ceo             | BOOLEAN | .ceo (default false) |
| start_date         | TEXT NULL | .startDate (ISO-Zeitstempel als Text, kein numerisches Datum nötig) |
| unique_name        | BOOLEAN | .uniqueName (default false) |
Index: (corporation_id) — für "alle NPCs einer Korporation" (z.B. CEO-Anzeige).

### system_sovereignty  (DYNAMISCH — siehe Hinweis unten, NICHT aus der SDE befüllt)
| Spalte               | Typ  |
|------------------------|------|
| solar_system_id       | INTEGER PRIMARY KEY REFERENCES solar_systems(id) |
| faction_id            | INTEGER NULL REFERENCES factions(id) |
| owner_corporation_id  | INTEGER NULL REFERENCES npc_corporations(id) |  -- vermutlich eher Allianz/Spieler-Korp, siehe Hinweis
| alliance_id           | INTEGER NULL |  -- Spieler-Allianzen sind kein SDE-Konzept, nur ESI
| last_updated          | TEXT NULL |  -- Zeitstempel des letzten ESI-Abrufs

WICHTIGER HINWEIS zu system_sovereignty: Diese Tabelle wird vom
SDE-Builder (sde_to_universe_db.py) NICHT befüllt — "wer besitzt
aktuell welches System" ist KEIN statisches SDE-Konzept, sondern
ändert sich durch Nullsec-Kriege potenziell täglich. Analog zu
Markt-Preisen (live von ESI, nicht aus der SDE) wird diese Tabelle erst
befüllt, wenn ein künftiges Modul den ESI-Endpunkt /sovereignty/map/
live abfragt — die Tabelle existiert hier nur als VORBEREITETER PLATZ
im Schema, bewusst getrennt von den echten SDE-Tabellen (faction_id
etc. bleiben bis dahin NULL/leer). Spieler-Allianzen (alliance_id)
sind ohnehin kein SDE-Konzept — sie entstehen erst durch echte
Spieleraktivität, nicht durch CCPs statischen Datenexport.

## Wichtiger Hinweis: Verweise auf items.sqlite

Mehrere Tabellen hier (type_item_id, owner_corporation_id über
Skill-/Schiffstypen, planet_schematic_pins.item_id, etc.) verweisen
NUR LOGISCH auf Einträge in items.sqlite — es gibt KEINEN echten SQL-
Foreign-Key über Datenbankgrenzen hinweg (SQLite unterstützt das nicht
nativ ohne ATTACH DATABASE, siehe die frühere Architektur-Diskussion
zu "mehrere Datenbanken vs. eine"). Solche logischen Verweise sind im
Schema einheitlich als `-- REFERENCES items(id), andere Datenbank`
dokumentiert (Kommentar, keine ausführbare SQL-Constraint) — rein zur
Lesbarkeit, nicht zur technischen Durchsetzung. Das gleiche Prinzip
gilt für Verweise auf characters.sqlite (race_id, bloodline_id).

## Architekturregel: Repository-Schicht (gilt projektweit, nicht nur hier)

KEIN UI-Code und KEIN Modul-Code (Markt, Industrie, Routenplanung, ...)
führt jemals direkt SQL gegen universe.sqlite (oder items.sqlite) aus.
Jeder Zugriff läuft ausschließlich über eine Repository-Klasse
(z.B. UniverseRepository, ItemRepository):

    UI/Modul-Code → Repository-Klasse → SQLite

Diese Regel ist NICHT verhandelbar pro Einzelfall ("dieses eine Mal
schnell direkt SQL schreiben") — sie ist eine feste Architektur-
entscheidung des Projekts (siehe gemeinsame Abstimmung mit Dragnax und
externem Review). Begründung: hält die Datenbank austauschbar (z.B.
falls items.sqlite/universe.sqlite später doch zusammengelegt werden
sollten — nur die Repository-Schicht müsste sich dann ändern, kein
einziger UI/Modul-Code), und zentralisiert Cross-Database-Auflösungen
(ATTACH DATABASE oder getrennte Abfragen) an einer einzigen, bekannten
Stelle statt verteilt über die ganze Codebasis.