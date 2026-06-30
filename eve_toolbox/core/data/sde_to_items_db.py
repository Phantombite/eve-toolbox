"""
sde_to_items_db.py — befüllt eine frisch angelegte items.sqlite
(siehe db.build_fresh_items_db) mit Daten aus den entpackten SDE-
JSONL-Dateien.

Übersetzt CCPs Rohformat (CamelCase, verschachtelte Listen) in unser
eigenes, stabiles Schema (snake_case, normalisierte Tabellen) — siehe
core/data/items_schema.sql für die Zieltabellen und
items_schema.md für die ausführliche Begründung.

Erwartet einen Ordner mit den bereits ENTPACKTEN .jsonl-Dateien (das
Herunterladen + Entpacken des SDE-ZIPs erledigt core/data/db_updater.py
separat — dieses Modul kennt nur noch fertige Dateien auf der Platte).

Nutzung (intern, von core/data/db_updater.py aufgerufen):
    from core.data.sde_to_items_db import build_items_db
    build_items_db(sde_dir=Path(...), target_path=Path(...), build_number="3409592")
"""
from core import logger as _logger
_log = _logger.get("sde_to_items_db")

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from core.data.db import build_fresh_items_db, _connect
from core.data.sde_common import read_jsonl as _read_jsonl, localized_name as _name


def build_items_db(sde_dir: Path, target_path: Path, build_number: str) -> None:
    """Baut eine VOLLSTÄNDIG NEUE items.sqlite unter `target_path` aus
    den JSONL-Dateien in `sde_dir`. `target_path` sollte ein temporärer
    Pfad sein — der atomare Austausch gegen die "echte" items.sqlite
    passiert NICHT hier, sondern im Aufrufer (core/data/db_updater.py),
    erst nachdem diese Funktion ohne Fehler durchgelaufen ist."""
    _log.info(f"Baue items.sqlite aus {sde_dir} (Build {build_number})")
    build_fresh_items_db(target_path)
    conn = _connect(target_path)
    try:
        _build_categories(conn, sde_dir)
        _build_groups(conn, sde_dir)
        _build_icons(conn, sde_dir)
        _build_meta_groups(conn, sde_dir)
        _build_market_groups(conn, sde_dir)
        _build_items(conn, sde_dir)
        _build_item_materials(conn, sde_dir)
        _build_dogma_units(conn, sde_dir)
        _build_dogma_attribute_categories(conn, sde_dir)
        _build_dogma_attributes(conn, sde_dir)
        _build_dogma_effects(conn, sde_dir)
        _build_item_dogma(conn, sde_dir)
        _build_blueprints(conn, sde_dir)
        _build_compressible_types(conn, sde_dir)
        _build_contraband_types(conn, sde_dir)
        _write_meta(conn, build_number)
        # Validierung VOR dem commit: schlägt sie fehl, wird die ganze
        # Transaktion verworfen (siehe except-Zweig) — eine Datenbank,
        # die die Plausibilitätsprüfung nicht besteht, wird NIEMALS
        # fertig auf die Platte geschrieben, geschweige denn später
        # gegen die echte items.sqlite ausgetauscht.
        _validate_built_database(conn)
        conn.commit()
    except Exception:
        conn.close()
        raise  # Aufrufer löscht die kaputte temporäre Datei, siehe updater.py
    conn.close()
    _log.info(f"items.sqlite erfolgreich befüllt: {target_path}")


class ValidationError(Exception):
    """Wird ausgelöst, wenn die fertig gebaute Datenbank eine oder
    mehrere Plausibilitätsprüfungen nicht besteht — z.B. weil CCP ein
    Feld in der SDE umbenannt/entfernt hat (siehe Schema-Changelog der
    SDE selbst, das genau solche Änderungen über Zeit dokumentiert) und
    unser Builder das Feld dadurch stillschweigend als 'leer' statt als
    Fehler behandelt hätte. OHNE diese Prüfung würde eine SOLCHE
    Datenbank erfolgreich gebaut, aber mit leeren/falschen Werten,
    OHNE dass irgendwo ein Fehler auftaucht — das wäre schlimmer als
    ein klarer Absturz, da es unbemerkt bliebe, bis ein Nutzer sich
    über falsche Markt-Daten wundert."""
    pass


def _validate_built_database(conn: sqlite3.Connection) -> None:
    """Prüft eine Reihe einfacher, harter Plausibilitätsregeln gegen
    die GERADE gebaute (noch nicht committete) Datenbank. Jede Regel
    vergleicht gegen einen GROSSZÜGIGEN Mindestwert (deutlich unter dem,
    was wir beim Bauen mit Build 3409592 tatsächlich gesehen haben,
    siehe Kommentare) — das Spiel wächst über Zeit, die Zahlen sollen
    also nur erkennen, ob etwas GRUNDLEGEND fehlgeschlagen ist (z.B.
    eine Tabelle bleibt komplett leer, weil ein Feldname sich geändert
    hat), nicht jede kleine, normale Schwankung melden."""
    problems = []

    def check_min_rows(table: str, min_expected: int):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count < min_expected:
            problems.append(
                f"Tabelle '{table}' hat nur {count} Zeilen, erwartet "
                f"mindestens {min_expected} — möglicherweise hat sich ein "
                f"SDE-Feldname/Dateiformat geändert."
            )

    # Werte unter den tatsächlichen Zahlen aus Build 3409592 (siehe
    # Logging beim Bauen), mit deutlichem Sicherheitsabstand nach unten,
    # da das Spiel über Zeit wächst, aber nicht schrumpft.
    check_min_rows("items", 30000)               # real: 52630
    check_min_rows("categories", 20)               # real: 48
    check_min_rows("groups_", 800)                 # real: 1605
    check_min_rows("market_groups", 1000)           # real: 2102
    check_min_rows("icons", 2000)                   # real: 4648
    check_min_rows("dogma_attributes", 1000)        # real: 2855
    check_min_rows("dogma_effects", 1000)           # real: 3411
    check_min_rows("item_dogma_attributes", 200000) # real: 643236
    check_min_rows("blueprints", 2000)              # real: 5081
    check_min_rows("blueprint_activity_materials", 10000)  # real: 36496

    # Stichproben-Check: ein bekanntes, garantiert existierendes Item
    # (Tritanium, id=34) muss korrekt benannt UND als handelbar markiert
    # sein. Das deckt z.B. ab, wenn sich der Feldname für 'name' oder
    # 'marketGroupID' geändert hätte und _build_items dadurch überall
    # den Platzhalter "[unnamed:...]" (siehe _name()-Fallback) bzw. NULL
    # eingetragen hätte, ohne dass die reine Zeilenanzahl-Prüfung oben
    # das gemerkt hätte (die Zeile EXISTIERT ja weiterhin, nur mit
    # falschem Inhalt).
    row = conn.execute(
        "SELECT name_en, market_group_id FROM items WHERE id = 34"
    ).fetchone()
    if row is None:
        problems.append("Tritanium (id=34) fehlt komplett in der items-Tabelle.")
    else:
        name_en, market_group_id = row
        if not name_en or name_en.strip() == "" or name_en.startswith("[unnamed:"):
            problems.append(
                f"Tritanium (id=34) hat keinen gültigen Namen ('{name_en}') — "
                f"das Feld 'name'/'name.en' hat sich vermutlich in der "
                f"SDE-Struktur geändert."
            )
        if market_group_id is None:
            problems.append(
                "Tritanium (id=34) hat keine market_group_id, obwohl es "
                "ein bekanntes, handelbares Item ist — das Feld "
                "'marketGroupID' hat sich vermutlich geändert."
            )

    # Globaler Check: wie viele Items haben einen leeren/Platzhalter-
    # Namen? Ein paar wenige (interne/unbenannte Test-Objekte) sind
    # normal, aber ein hoher Anteil würde auf ein verändertes
    # 'name'-Feld in der GESAMTEN types.jsonl-Datei hindeuten.
    total_items = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    bad_names = conn.execute(
        "SELECT COUNT(*) FROM items WHERE name_en IS NULL OR name_en = '' "
        "OR name_en LIKE '[unnamed:%'"
    ).fetchone()[0]
    if total_items > 0 and (bad_names / total_items) > 0.05:
        problems.append(
            f"{bad_names} von {total_items} Items ({bad_names/total_items*100:.1f}%) "
            f"haben einen leeren oder Platzhalter-Namen — deutlich mehr "
            f"als die üblichen vereinzelten internen Objekte, das "
            f"'name'-Feld hat sich vermutlich geändert."
        )

    if problems:
        problem_list = "\n  - ".join(problems)
        raise ValidationError(
            f"Die neu gebaute Spieldatenbank hat die Plausibilitätsprüfung "
            f"NICHT bestanden — der Build wird verworfen, die bisherige "
            f"Datenbank bleibt unverändert. Gefundene Probleme:\n  - {problem_list}"
        )
    _log.info("Plausibilitätsprüfung der neuen Datenbank erfolgreich bestanden.")


def _write_meta(conn, build_number: str):
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("sde_build", build_number),
        ("schema_version", "1"),
        ("created_at", now),
    ]
    conn.executemany(
        "INSERT INTO meta (key, value) VALUES (?, ?)", rows
    )


def _build_categories(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "categories.jsonl"):
        rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"),
            bool(obj.get("published", False)),
        ))
    conn.executemany(
        "INSERT INTO categories (id, name_en, name_de, published) VALUES (?,?,?,?)",
        rows,
    )
    _log.info(f"categories: {len(rows)} Zeilen")


def _build_groups(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "groups.jsonl"):
        rows.append((
            obj["_key"], obj.get("categoryID"),
            _name(obj, "en"), _name(obj, "de"),
            bool(obj.get("published", False)),
        ))
    conn.executemany(
        "INSERT INTO groups_ (id, category_id, name_en, name_de, published) "
        "VALUES (?,?,?,?,?)",
        rows,
    )
    _log.info(f"groups_: {len(rows)} Zeilen")


def _build_icons(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "icons.jsonl"):
        icon_file = obj.get("iconFile")
        if icon_file is None:
            continue  # ein paar wenige Icon-Einträge haben kein iconFile
        rows.append((obj["_key"], icon_file))
    conn.executemany("INSERT INTO icons (id, icon_file) VALUES (?,?)", rows)
    _log.info(f"icons: {len(rows)} Zeilen")


def _build_meta_groups(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "metaGroups.jsonl"):
        rows.append((obj["_key"], _name(obj, "en"), _name(obj, "de")))
    conn.executemany(
        "INSERT INTO meta_groups (id, name_en, name_de) VALUES (?,?,?)", rows
    )
    _log.info(f"meta_groups: {len(rows)} Zeilen")


def _build_market_groups(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "marketGroups.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        rows.append((
            obj["_key"], obj.get("parentGroupID"),
            _name(obj, "en"), _name(obj, "de"), desc_en,
            obj.get("iconID"), bool(obj.get("hasTypes", False)),
        ))
    # market_groups referenziert sich SELBST über parent_id (Kind-
    # Gruppen können in der SDE-Datei VOR ihrer Eltern-Gruppe stehen).
    # SQLite prüft Foreign-Key-Constraints SOFORT bei jedem INSERT —
    # ein direktes Einfügen in Datei-Reihenfolge würde fehlschlagen,
    # sobald ein Kind vor seinem Elternteil eingefügt wird.
    # PRAGMA foreign_keys=OFF hilft hier NICHT, da es nur außerhalb
    # einer laufenden Transaktion wirkt (SQLite-Eigenheit) — innerhalb
    # des laufenden Builds (eine durchgehende Transaktion über alle
    # _build_*-Schritte) bliebe es wirkungslos. Daher zweistufig:
    # 1) alle Zeilen OHNE parent_id einfügen (NULL, verletzt nie einen
    #    Foreign Key), 2) die echten parent_id-Werte per UPDATE
    #    nachtragen — zu diesem Zeitpunkt existieren ALLE Zeilen
    #    bereits, also kann kein Parent mehr fehlen.
    conn.executemany(
        "INSERT INTO market_groups "
        "(id, parent_id, name_en, name_de, description_en, icon_id, has_types) "
        "VALUES (?, NULL, ?, ?, ?, ?, ?)",
        [(r[0], r[2], r[3], r[4], r[5], r[6]) for r in rows],
    )
    parent_updates = [(r[1], r[0]) for r in rows if r[1] is not None]
    conn.executemany(
        "UPDATE market_groups SET parent_id = ? WHERE id = ?", parent_updates
    )
    _log.info(f"market_groups: {len(rows)} Zeilen ({len(parent_updates)} mit Parent)")


def _build_items(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "types.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"),
            obj.get("groupID"), obj.get("marketGroupID"), obj.get("metaGroupID"),
            obj.get("iconID"), desc_en,
            obj.get("volume"), obj.get("mass"), obj.get("capacity"),
            obj.get("portionSize", 1), bool(obj.get("published", False)),
            obj.get("basePrice"),
        ))
    conn.executemany(
        "INSERT INTO items "
        "(id, name_en, name_de, group_id, market_group_id, meta_group_id, "
        "icon_id, description_en, volume, mass, capacity, portion_size, "
        "published, base_price) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"items: {len(rows)} Zeilen")


def _build_item_materials(conn, sde_dir: Path):
    existing_items = {
        row[0] for row in conn.execute("SELECT id FROM items").fetchall()
    }
    rows = []
    skipped = []
    for obj in _read_jsonl(sde_dir / "typeMaterials.jsonl"):
        item_id = obj["_key"]
        if item_id not in existing_items:
            skipped.append(item_id)
            continue
        for mat in obj.get("materials", []):
            if mat["materialTypeID"] not in existing_items:
                skipped.append(mat["materialTypeID"])
                continue
            rows.append((item_id, mat["materialTypeID"], mat["quantity"]))
    if skipped:
        _log.warning(f"item_materials: {len(skipped)} Referenzen auf "
                      f"nicht-existierende Items übersprungen")
    conn.executemany(
        "INSERT INTO item_materials (item_id, material_item_id, quantity) "
        "VALUES (?,?,?)",
        rows,
    )
    _log.info(f"item_materials: {len(rows)} Zeilen")


def _build_dogma_units(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "dogmaUnits.jsonl"):
        display = obj.get("displayName")
        display_en = display.get("en") if isinstance(display, dict) else None
        rows.append((obj["_key"], _name(obj, "en"), display_en))
    conn.executemany(
        "INSERT INTO dogma_units (id, name_en, display_name_en) VALUES (?,?,?)",
        rows,
    )
    _log.info(f"dogma_units: {len(rows)} Zeilen")


def _build_dogma_attribute_categories(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "dogmaAttributeCategories.jsonl"):
        rows.append((obj["_key"], _name(obj, "en")))
    conn.executemany(
        "INSERT INTO dogma_attribute_categories (id, name_en) VALUES (?,?)",
        rows,
    )
    _log.info(f"dogma_attribute_categories: {len(rows)} Zeilen")


def _build_dogma_attributes(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "dogmaAttributes.jsonl"):
        display = obj.get("displayName")
        display_en = display.get("en") if isinstance(display, dict) else None
        display_de = display.get("de") if isinstance(display, dict) else None
        rows.append((
            obj["_key"], obj.get("name", f"attr_{obj['_key']}"),
            display_en, display_de, obj.get("description"),
            obj.get("unitID"), obj.get("attributeCategoryID"),
            bool(obj.get("highIsGood", False)), bool(obj.get("published", False)),
        ))
    conn.executemany(
        "INSERT INTO dogma_attributes "
        "(id, name, display_name_en, display_name_de, description, "
        "unit_id, category_id, high_is_good, published) VALUES (?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"dogma_attributes: {len(rows)} Zeilen")


def _build_dogma_effects(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "dogmaEffects.jsonl"):
        rows.append((
            obj["_key"], obj.get("name", f"effect_{obj['_key']}"),
            obj.get("guid"),
            bool(obj.get("isOffensive", False)), bool(obj.get("isAssistance", False)),
            bool(obj.get("published", False)),
        ))
    conn.executemany(
        "INSERT INTO dogma_effects "
        "(id, name, guid, is_offensive, is_assistance, published) VALUES (?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"dogma_effects: {len(rows)} Zeilen")


def _build_item_dogma(conn, sde_dir: Path):
    """typeDogma.jsonl enthält PRO ITEM sowohl dogmaAttributes als auch
    dogmaEffects (beide Felder optional, manche Items haben nur eins
    von beiden oder keins) — beide Zieltabellen werden hier zusammen
    befüllt, da sie aus derselben Quelldatei kommen."""
    attr_rows, effect_rows = [], []
    for obj in _read_jsonl(sde_dir / "typeDogma.jsonl"):
        item_id = obj["_key"]
        for attr in obj.get("dogmaAttributes", []):
            attr_rows.append((item_id, attr["attributeID"], attr["value"]))
        for eff in obj.get("dogmaEffects", []):
            effect_rows.append((
                item_id, eff["effectID"], bool(eff.get("isDefault", False))
            ))
    conn.executemany(
        "INSERT INTO item_dogma_attributes (item_id, attribute_id, value) "
        "VALUES (?,?,?)",
        attr_rows,
    )
    conn.executemany(
        "INSERT INTO item_dogma_effects (item_id, effect_id, is_default) "
        "VALUES (?,?,?)",
        effect_rows,
    )
    _log.info(f"item_dogma_attributes: {len(attr_rows)} Zeilen, "
              f"item_dogma_effects: {len(effect_rows)} Zeilen")


def _build_blueprints(conn, sde_dir: Path):
    """blueprints.jsonl hat eine verschachtelte 'activities'-Struktur,
    z.B. {"manufacturing": {"time": 600, "materials": [...], "products": [...]},
    "copying": {"time": 480}, ...} — wird auf 4 Tabellen normalisiert.

    Die activity-Bezeichnung selbst (z.B. "manufacturing") wird NICHT
    als freier TEXT in jeder Zeile wiederholt, sondern über eine
    Lookup-Tabelle (activity_types) referenziert — verhindert Tippfehler-
    Varianten wie "Manufacturing" vs. "manufacturing" und macht den
    Wertebereich explizit. Die id-Zuordnung wird HIER beim Bauen
    dynamisch vergeben (erstes Auftreten in der SDE-Datei bestimmt die
    Reihenfolge) — das ist eine interne Kennung, kein offizieller
    CCP-Code, daher gibt es keine "richtige" feste Nummer dafür.

    WICHTIG: blueprints.jsonl referenziert vereinzelt typeIDs (Material/
    Produkt), die NICHT in types.jsonl existieren — eine bekannte, kleine
    Inkonsistenz in CCPs eigenem SDE-Export (verifiziert anhand der
    aktuellen Build 3409592: betrifft ca. 20 von mehreren tausend
    Referenzen). Solche Zeilen werden defensiv übersprungen und
    geloggt, statt den GESAMTEN Datenbankaufbau wegen einer einzelnen
    fehlerhaften Fremd-Referenz abzubrechen."""
    existing_items = {
        row[0] for row in conn.execute("SELECT id FROM items").fetchall()
    }

    bp_rows, activity_rows = [], []
    material_rows, product_rows, skill_rows = [], [], []
    skipped = []
    activity_name_to_id: dict[str, int] = {}

    def get_activity_id(name: str) -> int:
        if name not in activity_name_to_id:
            activity_name_to_id[name] = len(activity_name_to_id) + 1
        return activity_name_to_id[name]

    for obj in _read_jsonl(sde_dir / "blueprints.jsonl"):
        bp_id = obj["blueprintTypeID"]
        bp_rows.append((bp_id, obj.get("maxProductionLimit", 1)))

        for activity_name, activity_data in obj.get("activities", {}).items():
            activity_id = get_activity_id(activity_name)
            time_s = activity_data.get("time", 0)
            activity_rows.append((bp_id, activity_id, time_s))

            for mat in activity_data.get("materials", []):
                if mat["typeID"] not in existing_items:
                    skipped.append(("material", bp_id, activity_name, mat["typeID"]))
                    continue
                material_rows.append((
                    bp_id, activity_id, mat["typeID"], mat["quantity"]
                ))
            for prod in activity_data.get("products", []):
                if prod["typeID"] not in existing_items:
                    skipped.append(("product", bp_id, activity_name, prod["typeID"]))
                    continue
                product_rows.append((
                    bp_id, activity_id, prod["typeID"], prod["quantity"],
                    prod.get("probability"),
                ))
            for skill in activity_data.get("skills", []):
                if skill["typeID"] not in existing_items:
                    skipped.append(("skill", bp_id, activity_name, skill["typeID"]))
                    continue
                skill_rows.append((
                    bp_id, activity_id, skill["typeID"], skill["level"]
                ))

    if skipped:
        _log.warning(
            f"blueprints: {len(skipped)} Referenzen auf nicht-existierende "
            f"Items übersprungen (bekannte SDE-Lücke): {skipped[:10]}"
            + (" ..." if len(skipped) > 10 else "")
        )

    conn.executemany(
        "INSERT INTO activity_types (id, name) VALUES (?,?)",
        [(aid, name) for name, aid in activity_name_to_id.items()],
    )
    _log.info(f"activity_types: {list(activity_name_to_id.items())}")

    # INSERT OR IGNORE statt INSERT: die SDE-Quelle enthält vereinzelt
    # echte Duplikate (z.B. derselbe Skill zweimal in derselben
    # Blueprint-Aktivität gelistet) — inhaltlich redundant, nicht
    # widersprüchlich, daher wird das zweite Vorkommen sicher verworfen
    # statt den gesamten Build abzubrechen.
    conn.executemany(
        "INSERT OR IGNORE INTO blueprints (blueprint_item_id, max_production_limit) "
        "VALUES (?,?)",
        bp_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_activities "
        "(blueprint_item_id, activity_type_id, time_seconds) VALUES (?,?,?)",
        activity_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_activity_materials "
        "(blueprint_item_id, activity_type_id, material_item_id, quantity) VALUES (?,?,?,?)",
        material_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_activity_products "
        "(blueprint_item_id, activity_type_id, product_item_id, quantity, probability) "
        "VALUES (?,?,?,?,?)",
        product_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO blueprint_activity_skills "
        "(blueprint_item_id, activity_type_id, skill_item_id, level) VALUES (?,?,?,?)",
        skill_rows,
    )
    _log.info(
        f"blueprints: {len(bp_rows)}, activities: {len(activity_rows)}, "
        f"materials: {len(material_rows)}, products: {len(product_rows)}, "
        f"skills: {len(skill_rows)}"
    )


def _build_compressible_types(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "compressibleTypes.jsonl"):
        rows.append((obj["_key"], obj["compressedTypeID"]))
    conn.executemany(
        "INSERT INTO compressible_types (item_id, compressed_item_id) VALUES (?,?)",
        rows,
    )
    _log.info(f"compressible_types: {len(rows)} Zeilen")


def _build_contraband_types(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "contrabandTypes.jsonl"):
        item_id = obj["_key"]
        for faction in obj.get("factions", []):
            rows.append((
                item_id, faction["_key"],
                faction.get("attackMinSec"), faction.get("confiscateMinSec"),
                faction.get("fineByValue"), faction.get("standingLoss"),
            ))
    conn.executemany(
        "INSERT INTO contraband_types "
        "(item_id, faction_id, attack_min_sec, confiscate_min_sec, "
        "fine_by_value, standing_loss) VALUES (?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"contraband_types: {len(rows)} Zeilen")