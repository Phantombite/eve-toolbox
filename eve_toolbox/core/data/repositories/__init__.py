"""
core/data/repositories/ — Repository-Schicht für alle Spieldatenbanken.

Einzige erlaubte Zugriffsschicht auf items.sqlite/universe.sqlite/
characters.sqlite (siehe jeweilige *_repository.py-Module für die
ausführliche Architekturregel-Begründung):

    UI/Modul-Code → *Repository-Klasse → SQLite

Re-exportiert die drei Repository-Klassen hier, damit Aufrufer
schreiben können:
    from core.data.repositories import ItemRepository
statt des längeren:
    from core.data.repositories.item_repository import ItemRepository
"""
from core.data.repositories.item_repository import ItemRepository
from core.data.repositories.universe_repository import UniverseRepository
from core.data.repositories.character_repository import CharacterRepository

__all__ = ["ItemRepository", "UniverseRepository", "CharacterRepository"]