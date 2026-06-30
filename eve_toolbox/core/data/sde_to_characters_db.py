"""
sde_to_characters_db.py — befüllt eine frisch angelegte
characters.sqlite (siehe db.build_fresh_characters_db) mit Daten aus
den entpackten SDE-JSONL-Dateien.

Analog zu sde_to_items_db.py/sde_to_universe_db.py: übersetzt CCPs
Rohformat in unser eigenes, stabiles Schema — siehe
core/data/characters_schema.sql für die Zieltabellen und
characters_schema.md für die ausführliche Begründung.

WICHTIG (siehe characters_schema.md/.sql): characterTitles._key ist
ein UUID-STRING in der SDE, kein Integer wie in praktisch jeder
anderen SDE-Datei — _build_character_titles() behandelt das explizit
(obj["_key"] wird NICHT implizit als Integer angenommen).

Erwartet einen Ordner mit den bereits ENTPACKTEN .jsonl-Dateien.
"""
from core import logger as _logger
_log = _logger.get("sde_to_characters_db")

from datetime import datetime, timezone
from pathlib import Path

from core.data.db import build_fresh_characters_db, _connect
from core.data.sde_common import read_jsonl as _read_jsonl, localized_name as _name


def build_characters_db(sde_dir: Path, target_path: Path, build_number: str) -> None:
    """Baut eine VOLLSTÄNDIG NEUE characters.sqlite unter `target_path`
    aus den JSONL-Dateien in `sde_dir`. `target_path` sollte ein
    temporärer Pfad sein — der atomare Austausch gegen die "echte"
    characters.sqlite passiert NICHT hier, sondern im Aufrufer
    (core/data/db_updater.py)."""
    _log.info(f"Baue characters.sqlite aus {sde_dir} (Build {build_number})")
    build_fresh_characters_db(target_path)
    conn = _connect(target_path)
    try:
        _build_races(conn, sde_dir)
        _build_bloodlines(conn, sde_dir)
        _build_ancestries(conn, sde_dir)
        _build_character_attributes(conn, sde_dir)
        _build_character_titles(conn, sde_dir)
        _build_agent_types(conn, sde_dir)
        _build_certificate_tiers(conn)
        _build_certificates(conn, sde_dir)
        _build_masteries(conn, sde_dir)
        _build_clone_grades(conn, sde_dir)
        _write_meta(conn, build_number)
        _validate_built_database(conn)
        conn.commit()
    except Exception:
        conn.close()
        raise
    conn.close()
    _log.info(f"characters.sqlite erfolgreich befüllt: {target_path}")


def _write_meta(conn, build_number: str):
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        ("sde_build", build_number),
        ("schema_version", "1"),
        ("created_at", now),
    ]
    conn.executemany("INSERT INTO meta (key, value) VALUES (?, ?)", rows)


# ── Rassen & Bloodlines ──────────────────────────────────────────────

def _build_races(conn, sde_dir: Path):
    race_rows = []
    skill_rows = []
    for obj in _read_jsonl(sde_dir / "races.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        race_rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"), desc_en,
            obj.get("iconID"), obj.get("shipTypeID"),
        ))
        for skill in obj.get("skills", []):
            skill_rows.append((obj["_key"], skill["_key"], skill["_value"]))

    conn.executemany(
        "INSERT INTO races (id, name_en, name_de, description_en, "
        "icon_id, ship_type_id) VALUES (?,?,?,?,?,?)",
        race_rows,
    )
    conn.executemany(
        "INSERT INTO race_skills (race_id, skill_item_id, value) VALUES (?,?,?)",
        skill_rows,
    )
    _log.info(f"races: {len(race_rows)} Zeilen, race_skills: {len(skill_rows)} Zeilen")


def _build_bloodlines(conn, sde_dir: Path):
    existing_races = {row[0] for row in conn.execute("SELECT id FROM races").fetchall()}
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "bloodlines.jsonl"):
        race_id = obj["raceID"]
        if race_id not in existing_races:
            skipped += 1
            continue
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        rows.append((
            obj["_key"], race_id, _name(obj, "en"), _name(obj, "de"), desc_en,
            obj.get("iconID"), obj.get("corporationID"),
            obj["charisma"], obj["intelligence"], obj["memory"],
            obj["perception"], obj["willpower"],
        ))
    if skipped:
        _log.warning(f"bloodlines: {skipped} mit unbekanntem race_id übersprungen")
    conn.executemany(
        "INSERT INTO bloodlines "
        "(id, race_id, name_en, name_de, description_en, icon_id, "
        "corporation_id, charisma, intelligence, memory, perception, willpower) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"bloodlines: {len(rows)} Zeilen")


def _build_ancestries(conn, sde_dir: Path):
    existing_bloodlines = {
        row[0] for row in conn.execute("SELECT id FROM bloodlines").fetchall()
    }
    rows = []
    skipped = 0
    for obj in _read_jsonl(sde_dir / "ancestries.jsonl"):
        bl_id = obj["bloodlineID"]
        if bl_id not in existing_bloodlines:
            skipped += 1
            continue
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        short_desc = obj.get("shortDescription")
        short_desc_en = short_desc.get("en") if isinstance(short_desc, dict) else None
        rows.append((
            obj["_key"], bl_id, _name(obj, "en"), _name(obj, "de"),
            desc_en, short_desc_en, obj.get("iconID"),
            obj["charisma"], obj["intelligence"], obj["memory"],
            obj["perception"], obj["willpower"],
        ))
    if skipped:
        _log.warning(f"ancestries: {skipped} mit unbekanntem bloodline_id übersprungen")
    conn.executemany(
        "INSERT INTO ancestries "
        "(id, bloodline_id, name_en, name_de, description_en, "
        "short_description_en, icon_id, charisma, intelligence, memory, "
        "perception, willpower) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"ancestries: {len(rows)} Zeilen")


# ── Charakter-Attribute & -Titel ─────────────────────────────────────

def _build_character_attributes(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "characterAttributes.jsonl"):
        rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"),
            obj.get("description"), obj.get("shortDescription"),
            obj.get("notes"), obj.get("iconID"),
        ))
    conn.executemany(
        "INSERT INTO character_attributes "
        "(id, name_en, name_de, description, short_description_en, notes, icon_id) "
        "VALUES (?,?,?,?,?,?,?)",
        rows,
    )
    _log.info(f"character_attributes: {len(rows)} Zeilen")


def _build_character_titles(conn, sde_dir: Path):
    """WICHTIG: _key ist hier ein UUID-STRING, kein Integer (verifiziert
    anhand der aktuellen SDE-Daten) — wird explizit als str() behandelt,
    nicht implizit wie bei jeder anderen SDE-Datei mit Integer-Keys."""
    rows = []
    for obj in _read_jsonl(sde_dir / "characterTitles.jsonl"):
        rows.append((str(obj["_key"]), _name(obj, "en"), _name(obj, "de")))
    conn.executemany(
        "INSERT INTO character_titles (id, name_en, name_de) VALUES (?,?,?)",
        rows,
    )
    _log.info(f"character_titles: {len(rows)} Zeilen")


def _build_agent_types(conn, sde_dir: Path):
    rows = []
    for obj in _read_jsonl(sde_dir / "agentTypes.jsonl"):
        # name ist hier ein einfacher String, kein mehrsprachiges Objekt
        # (verifiziert anhand der aktuellen SDE-Daten) — _name() würde
        # trotzdem korrekt funktionieren (Fallback auf String-Fall),
        # aber direkter Zugriff ist hier klarer, da kein .en/.de nötig.
        rows.append((obj["_key"], obj["name"]))
    conn.executemany(
        "INSERT INTO agent_types (id, name) VALUES (?,?)",
        rows,
    )
    _log.info(f"agent_types: {len(rows)} Zeilen")


# ── Zertifikate & Masteries ──────────────────────────────────────────

_CERTIFICATE_TIERS = ["basic", "standard", "improved", "advanced", "elite"]


def _build_certificate_tiers(conn):
    conn.executemany(
        "INSERT INTO certificate_tiers (id, name) VALUES (?,?)",
        [(i + 1, name) for i, name in enumerate(_CERTIFICATE_TIERS)],
    )


def _build_certificates(conn, sde_dir: Path):
    tier_name_to_id = {name: i + 1 for i, name in enumerate(_CERTIFICATE_TIERS)}

    cert_rows = []
    skill_req_rows = []
    recommendation_rows = []
    for obj in _read_jsonl(sde_dir / "certificates.jsonl"):
        desc = obj.get("description")
        desc_en = desc.get("en") if isinstance(desc, dict) else None
        cert_rows.append((
            obj["_key"], _name(obj, "en"), _name(obj, "de"), desc_en,
            obj.get("groupID"),
        ))
        for skill_entry in obj.get("skillTypes", []):
            skill_id = skill_entry["_key"]
            for tier_name in _CERTIFICATE_TIERS:
                level = skill_entry.get(tier_name)
                if level is not None:
                    skill_req_rows.append((
                        obj["_key"], skill_id, tier_name_to_id[tier_name], level
                    ))
        for ship_id in obj.get("recommendedFor", []):
            recommendation_rows.append((obj["_key"], ship_id))

    conn.executemany(
        "INSERT INTO certificates (id, name_en, name_de, description_en, group_id) "
        "VALUES (?,?,?,?,?)",
        cert_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO certificate_skill_requirements "
        "(certificate_id, skill_item_id, tier_id, level) VALUES (?,?,?,?)",
        skill_req_rows,
    )
    conn.executemany(
        "INSERT OR IGNORE INTO certificate_recommendations "
        "(certificate_id, ship_item_id) VALUES (?,?)",
        recommendation_rows,
    )
    _log.info(f"certificates: {len(cert_rows)} Zeilen, "
              f"certificate_skill_requirements: {len(skill_req_rows)} Zeilen, "
              f"certificate_recommendations: {len(recommendation_rows)} Zeilen")


def _build_masteries(conn, sde_dir: Path):
    """masteries.jsonl hat eine DREIFACH verschachtelte Struktur:
    {_key: shipID, _value: [{_key: level, _value: [certID, certID, ...]}]}
    — wird auf 3 Tabellen normalisiert (masteries, mastery_levels,
    mastery_level_certificates)."""
    existing_certificates = {
        row[0] for row in conn.execute("SELECT id FROM certificates").fetchall()
    }
    ship_rows = []
    level_rows = []
    cert_link_rows = []
    skipped_certs = 0
    for obj in _read_jsonl(sde_dir / "masteries.jsonl"):
        ship_id = obj["_key"]
        ship_rows.append((ship_id,))
        for level_entry in obj.get("_value", []):
            level = level_entry["_key"]
            level_rows.append((ship_id, level))
            for cert_id in level_entry.get("_value", []):
                if cert_id not in existing_certificates:
                    skipped_certs += 1
                    continue
                cert_link_rows.append((ship_id, level, cert_id))
    if skipped_certs:
        _log.warning(f"mastery_level_certificates: {skipped_certs} Referenzen "
                      f"auf unbekannte certificate_id übersprungen")
    conn.executemany(
        "INSERT INTO masteries (ship_item_id) VALUES (?)", ship_rows
    )
    conn.executemany(
        "INSERT INTO mastery_levels (ship_item_id, level) VALUES (?,?)", level_rows
    )
    conn.executemany(
        "INSERT OR IGNORE INTO mastery_level_certificates "
        "(ship_item_id, level, certificate_id) VALUES (?,?,?)",
        cert_link_rows,
    )
    _log.info(f"masteries: {len(ship_rows)} Zeilen, "
              f"mastery_levels: {len(level_rows)} Zeilen, "
              f"mastery_level_certificates: {len(cert_link_rows)} Zeilen")


# ── Klon-Stufen ───────────────────────────────────────────────────────

def _build_clone_grades(conn, sde_dir: Path):
    grade_rows = []
    skill_rows = []
    for obj in _read_jsonl(sde_dir / "cloneGrades.jsonl"):
        grade_rows.append((obj["_key"], obj["name"]))
        for skill in obj.get("skills", []):
            skill_rows.append((obj["_key"], skill["typeID"], skill["level"]))
    conn.executemany(
        "INSERT INTO clone_grades (id, name) VALUES (?,?)", grade_rows
    )
    conn.executemany(
        "INSERT OR IGNORE INTO clone_grade_skills "
        "(clone_grade_id, skill_item_id, level) VALUES (?,?,?)",
        skill_rows,
    )
    _log.info(f"clone_grades: {len(grade_rows)} Zeilen, "
              f"clone_grade_skills: {len(skill_rows)} Zeilen")


# ── Validierung ──────────────────────────────────────────────────────

class ValidationError(Exception):
    """Siehe sde_to_items_db.ValidationError für die ausführliche
    Begründung — gleiches Prinzip: verhindert, dass eine Datenbank mit
    stillschweigend falschen/leeren Werten erfolgreich gebaut und
    übernommen wird."""
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
    # Build 3409592 gesehenen Zahlen.
    check_min_rows("races", 4)
    check_min_rows("bloodlines", 15)
    check_min_rows("ancestries", 30)
    check_min_rows("character_attributes", 5)
    check_min_rows("character_titles", 30)
    check_min_rows("certificates", 100)
    check_min_rows("masteries", 100)
    check_min_rows("clone_grades", 1)

    # Stichprobe: Caldari (id=1) muss existieren und korrekt benannt sein.
    row = conn.execute("SELECT name_en FROM races WHERE id = 1").fetchone()
    if row is None or not row[0] or row[0].strip() == "" or row[0].startswith("["):
        problems.append(
            f"Rasse 'Caldari' (id=1) fehlt oder hat keinen gültigen Namen "
            f"('{row[0] if row else None}') — das 'name'-Feld hat sich "
            f"vermutlich geändert."
        )

    total_bloodlines = conn.execute("SELECT COUNT(*) FROM bloodlines").fetchone()[0]
    bad_names = conn.execute(
        "SELECT COUNT(*) FROM bloodlines WHERE name_en IS NULL "
        "OR name_en = '' OR name_en LIKE '[unnamed:%'"
    ).fetchone()[0]
    if total_bloodlines > 0 and (bad_names / total_bloodlines) > 0.05:
        problems.append(
            f"{bad_names} von {total_bloodlines} Bloodlines "
            f"({bad_names/total_bloodlines*100:.1f}%) haben einen leeren "
            f"oder Platzhalter-Namen — das 'name'-Feld hat sich vermutlich "
            f"geändert."
        )

    if problems:
        problem_list = "\n  - ".join(problems)
        raise ValidationError(
            f"Die neu gebaute characters.sqlite hat die Plausibilitätsprüfung "
            f"NICHT bestanden — der Build wird verworfen, die bisherige "
            f"Datenbank bleibt unverändert. Gefundene Probleme:\n  - {problem_list}"
        )
    _log.info("Plausibilitätsprüfung der neuen characters.sqlite erfolgreich bestanden.")