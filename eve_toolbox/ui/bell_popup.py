"""
Glocken-Popup — zeigt aktuelle ungelesene Nachrichten kurz an.
Klick auf Nachricht → Notifications-Fenster öffnen.
"""
from core import logger as _logger
_log = _logger.get("bell_popup")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from core import notifications as nf
from core.i18n import t
from core.config import FACTIONS


class BellPopup(QWidget):
    open_notifications = pyqtSignal()          # Notifications-Fenster öffnen
    open_notification  = pyqtSignal(str)       # Direkt zu einer Nachricht
    marked_read        = pyqtSignal(list)      # Nachrichten als gelesen

    def __init__(self, notifications: list, settings: dict, parent=None):
        super().__init__(parent)
        self._notifications = notifications
        self._settings      = settings
        self._shown_ids: list[str] = []        # IDs die angezeigt wurden
        self._read_timer    = None

        self.setObjectName("SettingsPanel")
        self.setFixedWidth(300)
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        title = QLabel(t("notifications.title"))
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("background: transparent;")
        title.setObjectName("PanelTitle")
        hl.addWidget(title)
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("HLine"); lay.addWidget(sep)

        # Inhaltsbereich
        self._content = QWidget()
        self._content_lay = QVBoxLayout(self._content)
        self._content_lay.setContentsMargins(12, 10, 12, 10)
        self._content_lay.setSpacing(8)
        lay.addWidget(self._content)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("HLine"); lay.addWidget(sep2)

        # Footer — Notifications öffnen
        footer = QWidget()
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.addStretch()
        open_btn = QPushButton(t("notifications.all_notifications"))
        open_btn.setObjectName("AccentBtn")
        open_btn.setFixedHeight(28)
        open_btn.clicked.connect(self._on_open_all)
        fl.addWidget(open_btn)
        lay.addWidget(footer)

        self._refresh()

    def _refresh(self):
        # Alte Inhalte leeren
        while self._content_lay.count():
            w = self._content_lay.takeAt(0).widget()
            if w: w.deleteLater()

        f       = FACTIONS.get(self._settings.get("faction","caldari"), FACTIONS["caldari"])
        unread  = nf.get_unread(self._notifications)

        if not unread:
            lbl = QLabel(t("notifications.no_new"))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888; padding: 16px; background: transparent;")
            self._content_lay.addWidget(lbl)
            self.adjustSize()
            return

        # Max 3 anzeigen
        for notif in unread[:3]:
            self._shown_ids.append(notif["id"])
            card = self._make_card(notif, f)
            self._content_lay.addWidget(card)

        if len(unread) > 3:
            more = QLabel(f"  + {len(unread)-3} weitere Meldungen")
            more.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
            self._content_lay.addWidget(more)

        # Timer: nach 2 Sek als gelesen markieren
        if self._read_timer:
            self._read_timer.stop()
        self._read_timer = QTimer(self)
        self._read_timer.setSingleShot(True)
        self._read_timer.timeout.connect(self._auto_mark_read)
        self._read_timer.start(2000)

        self.adjustSize()

    def _make_card(self, notif: dict, f: dict) -> QWidget:
        card = QWidget()
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setStyleSheet(
            f"QWidget {{ border: 1px solid {f['accent']}; border-radius: 6px; "
            f"background: transparent; }}"
            f"QWidget:hover {{ background: rgba("
            f"{QColor(f['accent']).red()},"
            f"{QColor(f['accent']).green()},"
            f"{QColor(f['accent']).blue()},20); }}"
        )
        cl = QVBoxLayout(card)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(3)

        # Typ + Icon
        icon  = nf.TYPE_ICONS.get(notif.get("type","system"), "ℹ")
        tname = nf.get_type_labels().get(notif.get("type","system"), "Info")
        h_row = QHBoxLayout()
        type_lbl = QLabel(f"{icon}  {tname}")
        type_lbl.setStyleSheet(f"color: {f['accent']}; font-size: 10px; font-weight: 600; background: transparent;")
        h_row.addWidget(type_lbl)
        h_row.addStretch()
        time_lbl = QLabel(notif.get("timestamp","")[-5:])  # Nur HH:MM
        time_lbl.setStyleSheet("color: #888; font-size: 10px; background: transparent;")
        h_row.addWidget(time_lbl)
        cl.addLayout(h_row)

        title = QLabel(notif.get("title",""))
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        title.setWordWrap(True)
        title.setStyleSheet("background: transparent;")
        cl.addWidget(title)

        text = QLabel(notif.get("text",""))
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 10px; color: #888; background: transparent;")
        cl.addWidget(text)

        # Klick → direkt zur Nachricht
        nid = notif["id"]
        card.mousePressEvent = lambda e: self._on_notif_click(nid)
        return card

    def _on_notif_click(self, notif_id: str):
        """Klick auf Nachricht → als gelesen + Notifications öffnen."""
        self._notifications = nf.mark_read(self._notifications, notif_id)
        self.marked_read.emit(self._notifications)
        self.hide()
        self.open_notification.emit(notif_id)

    def _on_open_all(self):
        self._auto_mark_read()
        self.hide()
        self.open_notifications.emit()

    def _auto_mark_read(self):
        """Alle angezeigten als gelesen markieren."""
        changed = False
        for nid in self._shown_ids:
            for n in self._notifications:
                if n["id"] == nid and not n.get("read", False):
                    n["read"] = True
                    changed = True
        if changed:
            nf.save(self._notifications)
            self.marked_read.emit(self._notifications)
        self._shown_ids.clear()

    def hideEvent(self, event):
        """Beim Schließen als gelesen markieren."""
        self._auto_mark_read()
        super().hideEvent(event)

    def update_data(self, notifications: list):
        self._notifications = notifications
        self._shown_ids.clear()
        self._refresh()

    def set_faction(self, faction: str):
        self._settings["faction"] = faction
        self._refresh()