"""
core/data/repositories/universe_repository.py — EINZIGE erlaubte
Zugriffsschicht auf universe.sqlite.

Gleiche Architekturregel wie ItemRepository (siehe dortige
Dokumentation) — bewusst nur generische Basis-Methoden, kein
modul-spezifischer Vorgriff (z.B. keine Routenplanungs-Algorithmen,
auch wenn stargates/destination_system_id dafür die Grundlage wären —
das Pathfinding selbst gehört in ein künftiges Routenplanungs-Modul,
nicht hierher).
"""
from typing import Optional

from core.data.db import universe_connection


class UniverseRepository:
    """Lese-Zugriff auf universe.sqlite. Kein schreibender Zugriff —
    die Datenbank wird ausschließlich über core.data.db_updater/
    sde_to_universe_db neu aufgebaut."""

    # ── Geografische Hierarchie ──────────────────────────────────────

    def get_region(self, region_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM regions WHERE id = ?", (region_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_regions(self) -> list[dict]:
        """Liefert alle Regionen — überschaubare Anzahl (~114), daher
        kein Paging nötig, im Gegensatz zu z.B. Items."""
        with universe_connection() as conn:
            rows = conn.execute("SELECT * FROM regions ORDER BY name_en").fetchall()
            return [dict(r) for r in rows]

    def get_solar_system(self, system_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM solar_systems WHERE id = ?", (system_id,)
            ).fetchone()
            return dict(row) if row else None

    def search_solar_systems_by_name(self, query: str, lang: str = "en",
                                       limit: int = 50) -> list[dict]:
        column = "name_de" if lang == "de" else "name_en"
        with universe_connection() as conn:
            rows = conn.execute(
                f"SELECT * FROM solar_systems WHERE {column} LIKE ? "
                f"ORDER BY {column} LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_solar_systems_in_region(self, region_id: int) -> list[dict]:
        with universe_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM solar_systems WHERE region_id = ? ORDER BY name_en",
                (region_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Stargates / Konnektivität ────────────────────────────────────

    def get_stargates_in_system(self, system_id: int) -> list[dict]:
        """Liefert alle Stargates eines Systems, inkl. aufgelöstem
        Zielsystem-Namen — die Basis-Grundlage für ein künftiges
        Routenplanungs-Modul, das eigene Pathfinding-Logik DARAUF
        aufbauen würde, nicht hier."""
        with universe_connection() as conn:
            rows = conn.execute(
                """
                SELECT sg.*, ds.name_en AS destination_name_en
                FROM stargates sg
                LEFT JOIN solar_systems ds ON ds.id = sg.destination_system_id
                WHERE sg.solar_system_id = ?
                """,
                (system_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Stationen ────────────────────────────────────────────────────

    def get_station(self, station_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM npc_stations WHERE id = ?", (station_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_stations_in_system(self, system_id: int) -> list[dict]:
        with universe_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM npc_stations WHERE solar_system_id = ?",
                (system_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_npc_corporation(self, corporation_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM npc_corporations WHERE id = ?", (corporation_id,)
            ).fetchone()
            return dict(row) if row else None

    # ── Politik & Fraktionen ─────────────────────────────────────────

    def get_faction(self, faction_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM factions WHERE id = ?", (faction_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_all_factions(self) -> list[dict]:
        with universe_connection() as conn:
            rows = conn.execute("SELECT * FROM factions ORDER BY name_en").fetchall()
            return [dict(r) for r in rows]

    def get_system_sovereignty(self, system_id: int) -> Optional[dict]:
        """Liefert den AKTUELLEN Besitzstatus eines Systems — siehe
        universe_schema.md: diese Tabelle wird NICHT aus der SDE
        befüllt (technisch erzwungen, siehe
        sde_to_universe_db._FORBIDDEN_SDE_TABLES), sondern müsste von
        einem künftigen Modul live über ESI (/sovereignty/map/)
        befüllt werden. Liefert daher aktuell praktisch immer None,
        bis so ein Modul existiert — die Methode ist bereits hier,
        damit ein künftiges Modul nicht selbst SQL gegen diese Tabelle
        schreiben muss."""
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM system_sovereignty WHERE solar_system_id = ?",
                (system_id,),
            ).fetchone()
            return dict(row) if row else None

    # ── Planetary Interaction ────────────────────────────────────────

    def get_planet_schematic(self, schematic_id: int) -> Optional[dict]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT * FROM planet_schematics WHERE id = ?", (schematic_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_planet_schematic_pins(self, schematic_id: int) -> list[dict]:
        """Liefert die Input-/Output-Materialien eines PI-Schemas."""
        with universe_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM planet_schematic_pins WHERE schematic_id = ?",
                (schematic_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Meta ─────────────────────────────────────────────────────────

    def get_sde_build_number(self) -> Optional[str]:
        with universe_connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'sde_build'"
            ).fetchone()
            return row[0] if row else None