"""
Info-Panel — zeigt alle Benachrichtigungen an.
"""
from core import logger as _logger
_log = _logger.get("info_panel")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QScrollArea, QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from core import notifications as nf
from core.config import FACTIONS


class NotifCard(QWidget):
    """Einzelne Benachrichtigungskarte."""
    def __init__(self, notif: dict, faction: str, parent=None):
        super().__init__(parent)
        self.notif = notif
        f = FACTIONS.get(faction, FACTIONS["caldari"])

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(4)

        # Header: Icon + Typ + Zeit + Gelesen-Status
        h_row = QHBoxLayout()
        icon = nf.TYPE_ICONS.get(notif.get("type","system"), "ℹ")
        type_label = nf.get_type_labels().get(notif.get("type","system"), "Info")
        read = notif.get("read", False)

        icon_lbl = QLabel(f"{icon}  {type_label}")
        icon_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        icon_lbl.setStyleSheet(f"color: {f['accent']};")
        h_row.addWidget(icon_lbl)
        h_row.addStretch()

        time_lbl = QLabel(notif.get("timestamp",""))
        time_lbl.setStyleSheet("color: #888; font-size: 10px;")
        h_row.addWidget(time_lbl)

        if not read:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {f['accent']}; font-size: 8px;")
            h_row.addWidget(dot)

        lay.addLayout(h_row)

        # Titel
        title = QLabel(notif.get("title",""))
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        title.setWordWrap(True)
        lay.addWidget(title)

        # Text
        text = QLabel(notif.get("text",""))
        text.setObjectName("SettingsSubLabel")
        text.setWordWrap(True)
        lay.addWidget(text)

        # Stil je nach gelesen
        opacity = "1.0" if not read else "0.6"
        border_col = f["accent"] if not read else "#555"
        self.setStyleSheet(
            f"QWidget {{ border: 1px solid {border_col}; border-radius: 8px;"
            f" background: transparent; }}"
        )


class InfoPanel(QWidget):
    """Panel das alle Benachrichtigungen zeigt."""
    closed         = pyqtSignal()
    all_read       = pyqtSignal()

    def __init__(self, notifications: list, settings: dict, parent=None):
        super().__init__(parent)
        self._notifications = notifications
        self._settings      = settings
        self.setFixedWidth(320)
        self.setObjectName("SettingsPanel")
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(14, 12, 14, 12)

        title = QLabel("Benachrichtigungen")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setObjectName("PanelTitle")
        hl.addWidget(title)
        hl.addStretch()

        mark_btn = QPushButton("Alle gelesen")
        mark_btn.setObjectName("AccentBtn")
        mark_btn.setFixedHeight(26)
        mark_btn.clicked.connect(self._mark_all)
        hl.addWidget(mark_btn)

        lay.addWidget(header)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("HLine"); lay.addWidget(sep)

        # Scroll-Bereich
        self._scroll_content = QWidget()
        self._scroll_lay = QVBoxLayout(self._scroll_content)
        self._scroll_lay.setContentsMargins(12, 8, 12, 12)
        self._scroll_lay.setSpacing(8)
        self._scroll_lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(self._scroll_content)
        lay.addWidget(scroll)

        self._refresh_list()

    def _refresh_list(self):
        # Alle alten Karten entfernen
        while self._scroll_lay.count():
            w = self._scroll_lay.takeAt(0).widget()
            if w: w.deleteLater()

        faction = self._settings.get("faction", "caldari")
        current = nf.get_current(self._notifications)

        if not current:
            empty = QLabel("Keine Benachrichtigungen")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #888; padding: 20px;")
            self._scroll_lay.addWidget(empty)
            return

        # Ungelesene zuerst
        unread = [n for n in current if not n.get("read", False)]
        read   = [n for n in current if n.get("read", False)]

        if unread:
            lbl = QLabel(f"Neu  ({len(unread)})")
            lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            lbl.setObjectName("SettingsSubLabel")
            self._scroll_lay.addWidget(lbl)
            for n in unread:
                self._scroll_lay.addWidget(NotifCard(n, faction))

        if read:
            lbl2 = QLabel("Gelesen")
            lbl2.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
            lbl2.setObjectName("SettingsSubLabel")
            lbl2.setStyleSheet("margin-top: 8px;")
            self._scroll_lay.addWidget(lbl2)
            for n in read:
                self._scroll_lay.addWidget(NotifCard(n, faction))

    def _mark_all(self):
        self._notifications = nf.mark_all_read(self._notifications)
        self._refresh_list()
        self.all_read.emit()

    def update_notifications(self, notifications: list):
        self._notifications = notifications
        self._refresh_list()

    def set_faction(self, faction: str):
        self._settings["faction"] = faction
        self._refresh_list()