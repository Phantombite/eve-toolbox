"""
core/data/repositories/character_repository.py — EINZIGE erlaubte
Zugriffsschicht auf characters.sqlite.

Gleiche Architekturregel wie ItemRepository/UniverseRepository (siehe
dortige Dokumentation) — bewusst nur generische Basis-Methoden, kein
modul-spezifischer Vorgriff (z.B. keine fertige "Skill-Plan-
Berechnung" — das gehört in ein künftiges Skill-Planer-Modul).
"""
from typing import Optional

from core.data.db import characters_connection


class CharacterRepository:
    """Lese-Zugriff auf characters.sqlite. Kein schreibender Zugriff —
    die Datenbank wird ausschließlich über core.data.db_updater/
    sde_to_characters_db neu aufgebaut."""

    # ── Rassen & Bloodlines ──────────────────────────────────────────

    def get_race(self, race_id: int) -> Optional[dict]:
        with characters_connection() as conn:
            row = conn.execute(
                "SELECT * FROM races WHERE id = ?", (race_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_races(self) -> list[dict]:
        """Überschaubare Anzahl (~11, inkl. NPC-/Sonderfraktionen wie
        Jove, Sleepers, Triglavian, Rogue Drones, ORE, Pirate, Upwell —
        nicht nur die 4 spielbaren Hauptrassen) — kein Paging nötig."""
        with characters_connection() as conn:
            rows = conn.execute("SELECT * FROM races ORDER BY name_en").fetchall()
            return [dict(r) for r in rows]

    def get_bloodlines_for_race(self, race_id: int) -> list[dict]:
        with characters_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM bloodlines WHERE race_id = ? ORDER BY name_en",
                (race_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_ancestries_for_bloodline(self, bloodline_id: int) -> list[dict]:
        with characters_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM ancestries WHERE bloodline_id = ? ORDER BY name_en",
                (bloodline_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Zertifikate & Masteries ──────────────────────────────────────

    def get_certificate(self, certificate_id: int) -> Optional[dict]:
        with characters_connection() as conn:
            row = conn.execute(
                "SELECT * FROM certificates WHERE id = ?", (certificate_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_certificate_skill_requirements(self, certificate_id: int) -> list[dict]:
        """Liefert die Skill-Anforderungen eines Zertifikats über alle
        5 Stufen (basic/standard/improved/advanced/elite), mit
        aufgelöstem Stufen-Namen (Join auf certificate_tiers)."""
        with characters_connection() as conn:
            rows = conn.execute(
                """
                SELECT csr.skill_item_id, ct.name AS tier_name, csr.level
                FROM certificate_skill_requirements csr
                JOIN certificate_tiers ct ON ct.id = csr.tier_id
                WHERE csr.certificate_id = ?
                """,
                (certificate_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_mastery_levels_for_ship(self, ship_item_id: int) -> list[dict]:
        """Liefert alle Mastery-Level eines Schiffstyps."""
        with characters_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM mastery_levels WHERE ship_item_id = ? ORDER BY level",
                (ship_item_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_mastery_level_certificates(self, ship_item_id: int,
                                         level: int) -> list[dict]:
        """Liefert die benötigten Zertifikate für ein bestimmtes
        Mastery-Level eines Schiffstyps, mit aufgelöstem
        Zertifikat-Namen."""
        with characters_connection() as conn:
            rows = conn.execute(
                """
                SELECT mlc.certificate_id, c.name_en, c.name_de
                FROM mastery_level_certificates mlc
                JOIN certificates c ON c.id = mlc.certificate_id
                WHERE mlc.ship_item_id = ? AND mlc.level = ?
                """,
                (ship_item_id, level),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Klon-Stufen ───────────────────────────────────────────────────

    def get_clone_grade(self, clone_grade_id: int) -> Optional[dict]:
        with characters_connection() as conn:
            row = conn.execute(
                "SELECT * FROM clone_grades WHERE id = ?", (clone_grade_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_clone_grade_skills(self, clone_grade_id: int) -> list[dict]:
        with characters_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM clone_grade_skills WHERE clone_grade_id = ?",
                (clone_grade_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Meta ─────────────────────────────────────────────────────────

    def get_sde_build_number(self) -> Optional[str]:
        with characters_connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'sde_build'"
            ).fetchone()
            return row[0] if row else None