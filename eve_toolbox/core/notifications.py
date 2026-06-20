"""
Benachrichtigungssystem — lädt, speichert und verwaltet Nachrichten.
"""
import json
from datetime import datetime, date
from pathlib import Path
from core.i18n import t

NOTIF_PATH = Path.home() / ".eve_toolbox" / "notifications.json"

# Nachrichtentypen
TYPE_UPDATE  = "update"
TYPE_SYSTEM  = "system"
TYPE_NEWS    = "news"
TYPE_WARNING = "warning"

TYPE_ICONS = {
    TYPE_UPDATE:  "🔄",
    TYPE_SYSTEM:  "⚙",
    TYPE_NEWS:    "📰",
    TYPE_WARNING: "⚠",
}


def get_type_labels() -> dict:
    """
    Als Funktion statt fixem Dict, damit t() bei jedem Aufruf die
    aktuell gewählte Sprache nutzt (ein Modul-Level-Dict würde nur
    einmal beim Import ausgewertet, bevor die Sprache feststeht).
    Update/System/News sind in DE und EN identisch — nur "Warnung"/
    "Warning" unterscheidet sich tatsächlich.
    """
    return {
        TYPE_UPDATE:  "Update",
        TYPE_SYSTEM:  "System",
        TYPE_NEWS:    "News",
        TYPE_WARNING: t("notifications.type_warning"),
    }

# Beispiel-Nachrichten (werden beim ersten Start gesetzt)
DEFAULT_NOTIFICATIONS = [
    {
        "id":          "welcome_001",
        "type":        TYPE_SYSTEM,
        "title":       "Willkommen bei EVE Toolbox!",
        "text":        "EVE Toolbox 0.1.0-alpha ist gestartet. Module werden schrittweise freigeschaltet.",
        "valid_until": "2099-12-31",
        "read":        False,
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    },
]


def load() -> list:
    """Lädt Nachrichten aus Datei."""
    if NOTIF_PATH.exists():
        try:
            with open(NOTIF_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # Erste Initialisierung
    save(DEFAULT_NOTIFICATIONS)
    return list(DEFAULT_NOTIFICATIONS)


def save(notifications: list) -> None:
    """Speichert Nachrichten."""
    NOTIF_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(NOTIF_PATH, "w", encoding="utf-8") as f:
        json.dump(notifications, f, indent=2, ensure_ascii=False)


def get_unread(notifications: list) -> list:
    """Gibt ungelesene, noch gültige Nachrichten zurück."""
    today = date.today().isoformat()
    return [
        n for n in notifications
        if not n.get("read", False)
        and n.get("valid_until", "2099-12-31") >= today
    ]


def get_current(notifications: list) -> list:
    """Gibt alle noch gültigen Nachrichten zurück (auch gelesene)."""
    today = date.today().isoformat()
    return [
        n for n in notifications
        if n.get("valid_until", "2099-12-31") >= today
    ]


def mark_read(notifications: list, notif_id: str) -> list:
    """Markiert eine Nachricht als gelesen."""
    for n in notifications:
        if n["id"] == notif_id:
            n["read"] = True
    save(notifications)
    return notifications


def mark_all_read(notifications: list) -> list:
    """Markiert alle Nachrichten als gelesen."""
    for n in notifications:
        n["read"] = True
    save(notifications)
    return notifications


def add_notification(notifications: list, notif_id: str, ntype: str,
                     title: str, text: str, valid_until: str = "2099-12-31") -> list:
    """Fügt eine neue Nachricht hinzu (falls noch nicht vorhanden)."""
    if any(n["id"] == notif_id for n in notifications):
        return notifications
    notifications.append({
        "id":          notif_id,
        "type":        ntype,
        "title":       title,
        "text":        text,
        "valid_until": valid_until,
        "read":        False,
        "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    save(notifications)
    return notifications