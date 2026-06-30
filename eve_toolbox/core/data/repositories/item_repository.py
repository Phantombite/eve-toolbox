"""
core/data/repositories/item_repository.py — EINZIGE erlaubte
Zugriffsschicht auf items.sqlite.

Architekturregel (siehe items_schema.md/universe_schema.md/
characters_schema.md, gemeinsam mit Dragnax und externem Review
festgelegt): KEIN UI-Code und KEIN Modul-Code führt jemals direkt SQL
gegen items.sqlite aus.

    UI/Modul-Code → ItemRepository → SQLite

Diese Klasse enthält BEWUSST nur generische Basis-Methoden (nach ID
suchen, nach Name suchen, Beziehungen entlang der Schema-Fremdschlüssel
abfragen) — KEINE modul-spezifische Logik (z.B. keine Markt-Preis-
Berechnung, keine Blueprint-Kostenkalkulation). Diese Zurückhaltung ist
Absicht: Es existiert noch kein einziges Modul, das diese Klasse nutzt
— Spezialmethoden für ein noch nicht gebautes Modul zu raten würde
vermutlich zu ständigem Umbauen führen, sobald das echte Modul dann
andere Anforderungen hat, als hier vermutet wurden. Jedes künftige
Modul ergänzt bei Bedarf eigene, modul-spezifische Methoden HIER (oder
in einer eigenen, spezialisierten Repository-Unterklasse) — die
Basis-Methoden bleiben davon unberührt.

Jede Methode öffnet ihre eigene kurzlebige Verbindung über
core.data.db.items_connection() und schließt sie wieder — kein
gehaltener State, keine Connection-Pool-Komplexität, da SQLite-Zugriffe
hier ohnehin schnell und lokal sind.
"""
from typing import Optional

from core.data.db import items_connection


class ItemRepository:
    """Lese-Zugriff auf items.sqlite. Schreibender Zugriff existiert
    bewusst nicht — die Datenbank wird ausschließlich über
    core.data.db_updater/sde_to_items_db neu aufgebaut, nie von einem
    Modul aus verändert."""

    # ── Items ────────────────────────────────────────────────────────

    def get_item(self, item_id: int) -> Optional[dict]:
        """Liefert einen einzelnen Item-Datensatz (alle Spalten aus
        der items-Tabelle) als dict, oder None falls nicht vorhanden."""
        with items_connection() as conn:
            row = conn.execute(
                "SELECT * FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            return dict(row) if row else None

    def search_items_by_name(self, query: str, lang: str = "en",
                              published_only: bool = True,
                              limit: int = 50) -> list[dict]:
        """Sucht Items, deren Name `query` als Teilstring enthält
        (case-insensitive, über SQLite LIKE). `lang` wählt zwischen
        name_en/name_de. `published_only=True` (Standard) blendet
        unveröffentlichte Items aus (siehe Dragnax-Entscheidung: der
        Markt-Browser soll wie der In-Game-Markt nur published Items
        zeigen, vgl. items_schema.md)."""
        column = "name_de" if lang == "de" else "name_en"
        sql = f"SELECT * FROM items WHERE {column} LIKE ?"
        params = [f"%{query}%"]
        if published_only:
            sql += " AND published = 1"
        sql += f" ORDER BY {column} LIMIT ?"
        params.append(limit)
        with items_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def get_items_by_market_group(self, market_group_id: int,
                                    published_only: bool = True) -> list[dict]:
        """Liefert alle Items einer bestimmten Markt-Gruppe (direkte
        FK-Beziehung items.market_group_id, NICHT rekursiv über
        Untergruppen — das Auflösen der Markt-Gruppen-Hierarchie ist
        Aufgabe des Aufrufers über get_market_group_children())."""
        sql = "SELECT * FROM items WHERE market_group_id = ?"
        params = [market_group_id]
        if published_only:
            sql += " AND published = 1"
        with items_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ── Markt-Gruppen (Baum-Struktur) ────────────────────────────────

    def get_market_group(self, market_group_id: int) -> Optional[dict]:
        with items_connection() as conn:
            row = conn.execute(
                "SELECT * FROM market_groups WHERE id = ?", (market_group_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_market_group_children(self, parent_id: Optional[int]) -> list[dict]:
        """Liefert die direkten Kind-Gruppen einer Markt-Gruppe.
        parent_id=None liefert die Top-Level-Gruppen (z.B. 'Ships',
        'Blueprints & Reactions') — Basis-Baustein, um den Markt-
        Gruppen-Baum schrittweise (Ebene für Ebene) aufzuklappen,
        ohne die gesamte Hierarchie auf einmal zu laden."""
        with items_connection() as conn:
            if parent_id is None:
                rows = conn.execute(
                    "SELECT * FROM market_groups WHERE parent_id IS NULL "
                    "ORDER BY name_en"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM market_groups WHERE parent_id = ? "
                    "ORDER BY name_en",
                    (parent_id,),
                ).fetchall()
            return [dict(r) for r in rows]

    # ── Blueprints ───────────────────────────────────────────────────

    def get_blueprint_for_product(self, product_item_id: int,
                                    activity_name: str = "manufacturing"
                                    ) -> Optional[dict]:
        """Findet das Blueprint, dessen Aktivität `activity_name`
        (Standard: 'manufacturing') `product_item_id` als Ergebnis
        liefert — z.B. 'welches Blueprint baut Item X'."""
        with items_connection() as conn:
            row = conn.execute(
                """
                SELECT bap.blueprint_item_id
                FROM blueprint_activity_products bap
                JOIN activity_types at ON at.id = bap.activity_type_id
                WHERE bap.product_item_id = ? AND at.name = ?
                """,
                (product_item_id, activity_name),
            ).fetchone()
            return dict(row) if row else None

    def get_blueprint_materials(self, blueprint_item_id: int,
                                  activity_name: str = "manufacturing"
                                  ) -> list[dict]:
        """Liefert alle Input-Materialien einer Blueprint-Aktivität,
        mit aufgelöstem Item-Namen (Join auf items)."""
        with items_connection() as conn:
            rows = conn.execute(
                """
                SELECT bam.material_item_id, i.name_en, i.name_de, bam.quantity
                FROM blueprint_activity_materials bam
                JOIN activity_types at ON at.id = bam.activity_type_id
                JOIN items i ON i.id = bam.material_item_id
                WHERE bam.blueprint_item_id = ? AND at.name = ?
                """,
                (blueprint_item_id, activity_name),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_reprocessing_materials(self, item_id: int) -> list[dict]:
        """Liefert, was man beim Reprocessing von `item_id` bekommt
        (z.B. Erz -> Mineralien), mit aufgelöstem Material-Namen."""
        with items_connection() as conn:
            rows = conn.execute(
                """
                SELECT im.material_item_id, i.name_en, i.name_de, im.quantity
                FROM item_materials im
                JOIN items i ON i.id = im.material_item_id
                WHERE im.item_id = ?
                """,
                (item_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Meta ─────────────────────────────────────────────────────────

    def get_sde_build_number(self) -> Optional[str]:
        """Liefert die SDE-Build-Nummer, aus der diese Datenbank
        gebaut wurde (aus der meta-Tabelle) — nützlich für eine
        Diagnose-/Über-Anzeige im UI ('Spieldaten Stand: Build X')."""
        with items_connection() as conn:
            row = conn.execute(
                "SELECT value FROM meta WHERE key = 'sde_build'"
            ).fetchone()
            return row[0] if row else None