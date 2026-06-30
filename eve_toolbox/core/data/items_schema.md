# items.sqlite — Schema-Entwurf

Eigenes, von der SDE-Rohstruktur entkoppeltes Schema. Ziel: CCP kann die
SDE-Struktur ändern, ohne dass Module (Markt, Industrie, Assets, ...)
etwas davon merken — nur der Build-Schritt (sde_to_db.py) muss dann
angepasst werden.

Alle Namen sind in `snake_case` (Python-/SQL-Konvention), nicht
CamelCase (SDE-Konvention) — bewusste Trennung, damit beim Lesen klar
ist, ob man im SDE-Rohformat oder im eigenen Schema ist.

## Meta-Tabelle (Debugging/Update-Steuerung)

### meta
| Spalte | Typ  |
|--------|------|
| key    | TEXT PK |
| value  | TEXT |

Bekannte Keys: `sde_build` (zuletzt verarbeitete CCP-Build-Nummer,
Grundlage für den Auto-Update-Check), `schema_version` (Versions-
nummer UNSERES Schemas, falls wir es später selbst ändern müssen),
`created_at` (Zeitstempel des letzten erfolgreichen Aufbaus).

## Kern-Tabellen (1 Zeile pro Entität)

### categories
| Spalte      | Typ     | Quelle (SDE)        |
|-------------|---------|----------------------|
| id          | INTEGER PK | categories._key   |
| name_en     | TEXT    | categories.name.en  |
| name_de     | TEXT    | categories.name.de  |
| published   | BOOLEAN | categories.published |

### groups
| Spalte       | Typ     | Quelle (SDE)         |
|--------------|---------|-----------------------|
| id           | INTEGER PK | groups._key        |
| category_id  | INTEGER FK -> categories.id | groups.categoryID |
| name_en      | TEXT    | groups.name.en       |
| name_de      | TEXT    | groups.name.de       |
| published    | BOOLEAN | groups.published     |

### market_groups
| Spalte            | Typ     | Quelle (SDE)              |
|--------------------|---------|----------------------------|
| id                 | INTEGER PK | marketGroups._key       |
| parent_id          | INTEGER FK -> market_groups.id NULL (NULL bei Top-Level) | marketGroups.parentGroupID |
| name_en            | TEXT    | marketGroups.name.en       |
| name_de            | TEXT    | marketGroups.name.de       |
| description_en     | TEXT NULL | marketGroups.description.en |
| icon_id            | INTEGER FK -> icons.id NULL | marketGroups.iconID |
| has_types          | BOOLEAN | marketGroups.hasTypes      |

### icons
| Spalte    | Typ  | Quelle (SDE)      |
|-----------|------|--------------------|
| id        | INTEGER PK | icons._key   |
| icon_file | TEXT | icons.iconFile     |

### meta_groups
| Spalte   | Typ  | Quelle (SDE)        |
|----------|------|----------------------|
| id       | INTEGER PK | metaGroups._key |
| name_en  | TEXT | metaGroups.name.en   |
| name_de  | TEXT | metaGroups.name.de   |

### items  (= types.jsonl, zentrale Tabelle)
| Spalte           | Typ     | Quelle (SDE)            |
|-------------------|---------|--------------------------|
| id                | INTEGER PK | types._key            |
| name_en           | TEXT    | types.name.en           |
| name_de           | TEXT    | types.name.de           |
| group_id          | INTEGER FK -> groups.id | types.groupID |
| market_group_id   | INTEGER FK -> market_groups.id (NULL = nicht handelbar) | types.marketGroupID |
| meta_group_id     | INTEGER FK -> meta_groups.id (NULL möglich) | types.metaGroupID |
| icon_id           | INTEGER FK -> icons.id (NULL möglich) | types.iconID |
| description_en    | TEXT    | types.description.en (NULL möglich) |
| volume            | REAL    | types.volume (NULL möglich) |
| mass              | REAL    | types.mass (NULL möglich) |
| capacity          | REAL    | types.capacity (NULL möglich) |
| portion_size      | INTEGER | types.portionSize       |
| published         | BOOLEAN | types.published         |
| base_price        | REAL    | types.basePrice (NULL möglich) |

Index: (market_group_id, published) — für "alle handelbaren Items
einer Markt-Gruppe" (häufigste Markt-Browser-Abfrage).
Index: name_en, name_de — für Namenssuche.

## Verknüpfungstabellen (mehrere Zeilen pro Item — normalisiert aus
## verschachtelten SDE-Listen)

### item_materials  (= typeMaterials.jsonl, "was bekommt man beim Reprocessing")
| Spalte           | Typ     |
|-------------------|---------|
| item_id           | INTEGER FK -> items.id |
| material_item_id  | INTEGER FK -> items.id |
| quantity          | INTEGER |
PK: (item_id, material_item_id)

### dogma_attributes  (Attribut-DEFINITIONEN, nicht die Werte selbst)
| Spalte           | Typ     | Quelle (SDE)                    |
|--------------------|---------|------------------------------------|
| id                 | INTEGER PK | dogmaAttributes._key           |
| name               | TEXT    | dogmaAttributes.name (techn. Code-Name, z.B. "damage", IMMER vorhanden) |
| display_name_en    | TEXT NULL | dogmaAttributes.displayName.en (fehlt oft, z.B. bei internen/booleschen Flags) |
| display_name_de    | TEXT NULL | dogmaAttributes.displayName.de |
| description        | TEXT NULL | dogmaAttributes.description    |
| unit_id            | INTEGER FK -> dogma_units.id NULL | dogmaAttributes.unitID |
| category_id        | INTEGER FK -> dogma_attribute_categories.id NULL | dogmaAttributes.attributeCategoryID |
| high_is_good       | BOOLEAN | dogmaAttributes.highIsGood          |
| published          | BOOLEAN | dogmaAttributes.published           |

### dogma_units
| Spalte    | Typ  |
|-----------|------|
| id        | INTEGER PK |
| name_en   | TEXT |
| display_name_en | TEXT (NULL möglich) |

### dogma_attribute_categories
| Spalte    | Typ  |
|-----------|------|
| id        | INTEGER PK |
| name_en   | TEXT |

### item_dogma_attributes  (= typeDogma.jsonl, DIE WERTE pro Item)
| Spalte        | Typ  |
|----------------|------|
| item_id        | INTEGER FK -> items.id |
| attribute_id   | INTEGER FK -> dogma_attributes.id |
| value          | REAL |
PK: (item_id, attribute_id)
Index: attribute_id — für "alle Items mit Attribut X sortiert nach Wert"

### dogma_effects
| Spalte    | Typ  | Quelle (SDE) |
|-----------|------|---------------|
| id        | INTEGER PK | dogmaEffects._key |
| name      | TEXT | dogmaEffects.name (techn. Code-Name, z.B. "shieldBoosting" — KEIN displayName-Feld in der SDE für Effekte vorhanden, nur der technische Name) |
| guid      | TEXT | dogmaEffects.guid (z.B. "effects.ShieldBoosting") |
| is_offensive | BOOLEAN | dogmaEffects.isOffensive |
| is_assistance | BOOLEAN | dogmaEffects.isAssistance |
| published | BOOLEAN | dogmaEffects.published |

### item_dogma_effects  (= typeDogma.jsonl, effects-Teil)
| Spalte       | Typ     |
|---------------|---------|
| item_id       | INTEGER FK -> items.id |
| effect_id     | INTEGER FK -> dogma_effects.id |
| is_default    | BOOLEAN |
PK: (item_id, effect_id)

### blueprints
| Spalte                  | Typ     | Quelle (SDE)                  |
|---------------------------|---------|----------------------------------|
| blueprint_item_id         | INTEGER PK FK -> items.id | blueprints.blueprintTypeID |
| max_production_limit      | INTEGER | blueprints.maxProductionLimit  |

### activity_types  (Lookup-Tabelle, ersetzt freien TEXT zur Vermeidung von Tippfehler-Varianten)
| Spalte | Typ  |
|--------|------|
| id     | INTEGER PK |
| name   | TEXT UNIQUE (z.B. 'manufacturing', 'copying', 'invention', 'research_material', 'research_time', 'reaction') |
id-Vergabe erfolgt dynamisch beim Bauen (erstes Auftreten in der SDE
bestimmt die Nummer) — interne Kennung, kein offizieller CCP-Code.

### blueprint_activities  (1 Zeile pro Aktivität pro Blueprint)
| Spalte             | Typ     |
|----------------------|---------|
| blueprint_item_id    | INTEGER FK -> blueprints.blueprint_item_id |
| activity_type_id     | INTEGER FK -> activity_types.id |
| time_seconds         | INTEGER |
PK: (blueprint_item_id, activity_type_id)

### blueprint_activity_materials  (Input-Materialien einer Aktivität)
| Spalte             | Typ     |
|----------------------|---------|
| blueprint_item_id    | INTEGER |
| activity_type_id     | INTEGER FK -> activity_types.id |
| material_item_id     | INTEGER FK -> items.id |
| quantity             | INTEGER |
PK: (blueprint_item_id, activity_type_id, material_item_id)
FK: (blueprint_item_id, activity_type_id) -> blueprint_activities

### blueprint_activity_products  (Output einer Aktivität)
| Spalte             | Typ     |
|----------------------|---------|
| blueprint_item_id    | INTEGER |
| activity_type_id     | INTEGER FK -> activity_types.id |
| product_item_id      | INTEGER FK -> items.id |
| quantity             | INTEGER |
| probability          | REAL (NULL möglich, nur bei invention relevant) |
PK: (blueprint_item_id, activity_type_id, product_item_id)

### blueprint_activity_skills  (benötigte Skills pro Aktivität)
| Spalte             | Typ     |
|----------------------|---------|
| blueprint_item_id    | INTEGER |
| activity_type_id     | INTEGER FK -> activity_types.id |
| skill_item_id        | INTEGER FK -> items.id |
| level                | INTEGER |
PK: (blueprint_item_id, activity_type_id, skill_item_id)

## Sonstige flache Tabellen (1:1, keine Verschachtelung)

### compressible_types  (= compressibleTypes.jsonl)
| Spalte               | Typ  |
|------------------------|------|
| item_id                | INTEGER PK FK -> items.id |
| compressed_item_id     | INTEGER FK -> items.id |

### contraband_types  (= contrabandTypes.jsonl — in welchen Faction-Räumen ein Item geächtet ist)
| Spalte                  | Typ  | Quelle (SDE)            |
|---------------------------|------|---------------------------|
| item_id                  | INTEGER FK -> items.id | contrabandTypes._key |
| faction_id               | INTEGER | factions[]._key      |
| attack_min_sec           | REAL NULL | factions[].attackMinSec |
| confiscate_min_sec       | REAL NULL | factions[].confiscateMinSec |
| fine_by_value            | REAL NULL | factions[].fineByValue |
| standing_loss            | REAL NULL | factions[].standingLoss |
PK: (item_id, faction_id)

### skins, skin_licenses, skin_materials — bewusst NICHT in items.sqlite
(siehe Begründung unten)

## Was aus dieser Datenbank bewusst AUSGELASSEN wird

- **skins / skinLicenses / skinMaterials / skinr*** (8 Dateien, kosmetische
  Schiffsskins): Für Markt/Industrie/Assets nicht relevant, da Skins
  zwar handelbar sind, aber unsere geplanten Module (Preisvergleich,
  Blueprint-Kalkulation) sich nicht inhaltlich mit ihnen befassen.
  Werden NICHT in der ersten Version von items.sqlite abgebildet, können
  aber bei Bedarf später als eigene Tabellen ergänzt werden, OHNE dass
  bestehende Tabellen sich ändern müssen (additive Erweiterung).
- **graphics / graphicMaterialSets**: Rein visuelle 3D-Modell-Referenzen,
  kein Programmteil benötigt das aktuell.
- **dynamicItemAttributes, typeElements, typeLists**: Sehr spezielle,
  seltene Sonderfälle (Abyssal-Module mit randomisierten Werten u.ä.) —
  zurückgestellt, bis ein konkretes Modul sie wirklich braucht.

Diese Auslassungen sind ADDITIV nachrüstbar: das Schema oben muss sich
dafür nicht ändern, nur neue Tabellen kommen hinzu.