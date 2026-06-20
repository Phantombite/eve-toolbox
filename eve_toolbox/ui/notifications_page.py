"""
Benachrichtigungs-Seite — Sidebar links, Meldungen rechts.
Aufbau wie die Einstellungsseite.
"""
from core import logger as _logger
_log = _logger.get("notifications_page")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QScrollArea, QFrame, QSizePolicy,
                              QStackedWidget)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath

from core import notifications as nf
from core.i18n import t
from core.config import FACTIONS


# ── Hilfswidgets ──────────────────────────────────────────────────────────────

class SidebarItem(QWidget):
    clicked = pyqtSignal()

    def __init__(self, icon: str, label: str, parent=None):
        super().__init__(parent)
        self.icon    = icon
        self.label   = label
        self._active = False
        self._hov    = False
        self._accent = "#185FA5"
        self._count  = 0
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_active(self, v: bool): self._active = v; self.update()
    def set_accent(self, c: str):  self._accent = c; self.update()
    def set_count(self, n: int):   self._count  = n; self.update()
    def enterEvent(self, e): self._hov = True;  self.update()
    def leaveEvent(self, e): self._hov = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h  = self.width(), self.height()
        acc   = QColor(self._accent)
        dark  = self.palette().color(self.palette().ColorRole.Window).lightness() < 128

        if self._active:
            p.fillRect(0, 0, w, h, QColor(acc.red(), acc.green(), acc.blue(), 30))
            p.fillRect(0, 0, 3, h, acc)
        elif self._hov:
            p.fillRect(0, 0, w, h, QColor(acc.red(), acc.green(), acc.blue(), 15))

        p.setFont(QFont("Segoe UI Emoji", 13))
        p.setPen(QPen(acc if self._active else QColor("#888")))
        p.drawText(QRectF(12, 0, 28, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter,
                   self.icon)

        p.setFont(QFont("Segoe UI", 11,
                        QFont.Weight.DemiBold if self._active else QFont.Weight.Normal))
        p.setPen(QPen(acc if self._active else
                      (QColor("#e8e8e8") if dark else QColor("#333"))))
        p.drawText(QRectF(46, 0, w - 80, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.label)

        # Zähler Badge
        if self._count > 0:
            badge_text = str(self._count)
            badge_w = max(20, len(badge_text) * 8 + 8)
            bx = w - badge_w - 8
            by = (h - 18) // 2
            p.setBrush(QBrush(acc if self._active else QColor("#ff3333")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(bx, by, badge_w, 18), 9, 9)
            p.setPen(QPen(QColor("#ffffff")))
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            p.drawText(QRectF(bx, by, badge_w, 18),
                       Qt.AlignmentFlag.AlignCenter, badge_text)
        p.end()


class NotifCard(QWidget):
    """Einzelne Meldungskarte."""
    mark_read = pyqtSignal(str)

    def __init__(self, notif: dict, faction: str, show_read_btn: bool = True, parent=None):
        super().__init__(parent)
        self.notif = notif
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        read = notif.get("read", False)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(6)

        # Header
        h_row = QHBoxLayout()
        icon  = nf.TYPE_ICONS.get(notif.get("type","system"), "ℹ")
        tname = nf.get_type_labels().get(notif.get("type","system"), "Info")

        type_lbl = QLabel(f"{icon}  {tname}")
        type_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        type_lbl.setStyleSheet(f"color: {f['accent']};")
        h_row.addWidget(type_lbl)
        h_row.addStretch()

        time_lbl = QLabel(notif.get("timestamp",""))
        time_lbl.setStyleSheet("color: #888; font-size: 10px;")
        h_row.addWidget(time_lbl)

        # Ungelesen-Punkt
        if not read:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {f['accent']}; font-size: 9px; padding-left: 4px;")
            h_row.addWidget(dot)
        lay.addLayout(h_row)

        # Titel
        title = QLabel(notif.get("title",""))
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        title.setWordWrap(True)
        if read:
            title.setStyleSheet("color: #888;")
        lay.addWidget(title)

        # Text
        text = QLabel(notif.get("text",""))
        text.setWordWrap(True)
        text.setStyleSheet("font-size: 11px; color: #999;" if read else "font-size: 11px;")
        lay.addWidget(text)

        # Gültig bis
        valid = notif.get("valid_until","")
        if valid and valid != "2099-12-31":
            valid_lbl = QLabel(f"Gültig bis: {valid}")
            valid_lbl.setStyleSheet("font-size: 10px; color: #666;")
            lay.addWidget(valid_lbl)

        # Als gelesen markieren Button
        if show_read_btn and not read:
            btn_row = QHBoxLayout()
            btn_row.addStretch()
            read_btn = QPushButton(t("notifications.mark_read"))
            read_btn.setObjectName("AccentBtn")
            read_btn.setFixedHeight(26)
            read_btn.clicked.connect(lambda: self.mark_read.emit(notif["id"]))
            btn_row.addWidget(read_btn)
            lay.addLayout(btn_row)

        # Rahmen
        border = f["accent"] if not read else "#444"
        self.setStyleSheet(
            f"QWidget {{ border: 1px solid {border}; border-radius: 8px; }}"
        )
        if read:
            self.setStyleSheet(
                "QWidget { border: 1px solid #333; border-radius: 8px; }"
            )


def hline():
    l = QFrame(); l.setFrameShape(QFrame.Shape.HLine); l.setObjectName("HLine")
    return l


class SimulatorPage(QWidget):
    """Test-Modus: Nachrichten simulieren."""
    notification_added   = pyqtSignal(dict)
    notifications_cleared= pyqtSignal()

    EXAMPLES = [
        (nf.TYPE_UPDATE,  "Update verfügbar",       "EVE Toolbox 0.2.0 ist verfügbar. Neue Module freigeschaltet."),
        (nf.TYPE_WARNING, "Verbindung unterbrochen", "ESI-Verbindung zu Darkwing wurde getrennt. Bitte erneut einloggen."),
        (nf.TYPE_NEWS,    "EVE News",                "Neues Patch-Update: Industrieänderungen und Balancing-Fixes."),
        (nf.TYPE_SYSTEM,  "Systemhinweis",           "Wartungsarbeiten geplant für Sonntag 08:00-10:00 UTC."),
        (nf.TYPE_UPDATE,  "Module freigeschaltet",   "Das Modul 'Skills' ist jetzt verfügbar."),
    ]

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings        = settings
        self._sim_notifs     = []   # Nur im RAM, nicht gespeichert
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(16)

        # Warnung
        warn = QLabel(t("notifications.sim_warning"))
        warn.setStyleSheet(
            "background: rgba(153,60,29,0.2); border: 1px solid #993C1D;"
            "border-radius: 8px; padding: 8px 14px; font-size: 12px; color: #D85A30;"
        )
        lay.addWidget(warn)

        # Beispiel-Nachrichten
        title = QLabel(t("notifications.sim_title"))
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        lay.addWidget(title)

        for ntype, ntitle, ntext in self.EXAMPLES:
            row = QHBoxLayout()
            icon = nf.TYPE_ICONS.get(ntype, "ℹ")
            lbl  = QLabel(f"{icon}  {ntitle}")
            lbl.setFont(QFont("Segoe UI", 11))
            lbl.setSizePolicy(
                __import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Policy.Expanding,
                __import__('PyQt6.QtWidgets', fromlist=['QSizePolicy']).QSizePolicy.Policy.Fixed,
            )
            row.addWidget(lbl)

            btn = QPushButton(t("notifications.send"))
            btn.setObjectName("AccentBtn")
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _, t=ntype, ti=ntitle, tx=ntext:
                                self._send(t, ti, tx))
            row.addWidget(btn)
            lay.addLayout(row)

        lay.addWidget(hline())

        # Gesendete simulierte Nachrichten
        self._sent_label = QLabel("Gesendete Test-Nachrichten: 0")
        self._sent_label.setObjectName("SettingsSubLabel")
        lay.addWidget(self._sent_label)

        clear_btn = QPushButton(t("notifications.sim_clear"))
        clear_btn.setObjectName("AccentBtn")
        clear_btn.setStyleSheet("background: #993C1D;")
        clear_btn.clicked.connect(self._clear)
        lay.addWidget(clear_btn)
        lay.addStretch()

    def _send(self, ntype: str, title: str, text: str):
        import uuid
        from datetime import datetime
        notif = {
            "id":          f"sim_{uuid.uuid4().hex[:8]}",
            "type":        ntype,
            "title":       f"[TEST] {title}",
            "text":        text,
            "valid_until": "2099-12-31",
            "read":        False,
            "timestamp":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            "simulated":   True,
        }
        self._sim_notifs.append(notif)
        self._sent_label.setText(f"Gesendete Test-Nachrichten: {len(self._sim_notifs)}")
        self.notification_added.emit(notif)

    def _clear(self):
        self._sim_notifs.clear()
        self._sent_label.setText("Gesendete Test-Nachrichten: 0")
        self.notifications_cleared.emit()

    def clear_all(self):
        """Wird aufgerufen wenn Test-Modus deaktiviert wird."""
        self._clear()


def scrolled_list(widgets: list, empty_text: str = "Keine Meldungen") -> QScrollArea:
    inner = QWidget()
    lay = QVBoxLayout(inner)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(10)
    lay.setAlignment(Qt.AlignmentFlag.AlignTop)

    if not widgets:
        lbl = QLabel(empty_text)
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #888; padding: 40px; font-size: 13px;")
        lay.addWidget(lbl)
    else:
        for w in widgets:
            lay.addWidget(w)

    lay.addStretch()
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setWidget(inner)
    return scroll


# ── Haupt-Seite ───────────────────────────────────────────────────────────────

class NotificationsPage(QWidget):
    close_requested          = pyqtSignal()
    unread_changed           = pyqtSignal(bool)
    all_notifications_changed= pyqtSignal(list)  # echt + sim  # hat es noch ungelesene?

    @property
    def CATEGORIES(self):
        return [
            ("🔔", t("notifications.current"),  None,            True),
            ("ℹ",  t("notifications.info"),     nf.TYPE_SYSTEM,  False),
            ("⚠",  t("notifications.important"),nf.TYPE_WARNING, False),
            ("🔄", t("notifications.updates"),  nf.TYPE_UPDATE,  False),
            ("📰", t("notifications.news"),     nf.TYPE_NEWS,    False),
            ("📋", t("notifications.all"),      None,            False),
            ("🧪", t("notifications.simulator"),"__sim__",       False),
        ]

    def __init__(self, notifications: list, settings: dict, parent=None):
        super().__init__(parent)
        self._notifications = notifications
        self._settings      = settings
        self._accent        = FACTIONS.get(
            settings.get("faction","caldari"), FACTIONS["caldari"])["accent"]
        self._sim_page      = SimulatorPage(settings)
        self._sim_page.notification_added.connect(self._on_sim_notif)
        self._sim_page.notifications_cleared.connect(self._on_sim_clear)
        self._sim_notifs: list = []
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ───────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("SettingsSidebar")
        sidebar.setFixedWidth(200)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        # Header
        hdr = QWidget(); hdr.setFixedHeight(56)
        hl  = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        _title   = QLabel(t("notifications.title"))
        _title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        hl.addWidget(_title)
        sb.addWidget(hdr)
        sb.addWidget(hline())

        self._sidebar_items: list[SidebarItem] = []
        for icon, label, ntype, unread_only in self.CATEGORIES:
            item = SidebarItem(icon, label)
            item.set_accent(self._accent)
            item.clicked.connect(lambda l=label: self._switch(l))
            sb.addWidget(item)
            self._sidebar_items.append(item)
            # Simulator nur im Test-Modus sichtbar
            if ntype == "__sim__":
                item.setVisible(self._settings.get("test_mode", False))

        sb.addStretch()
        sb.addWidget(hline())

        # Alle gelesen + Zurück
        btn_wrap = QWidget()
        bwl = QVBoxLayout(btn_wrap)
        bwl.setContentsMargins(12, 8, 12, 12)
        bwl.setSpacing(6)

        all_read_btn = QPushButton(t("notifications.mark_all_read"))
        all_read_btn.setObjectName("AccentBtn")
        all_read_btn.setFixedHeight(32)
        all_read_btn.clicked.connect(self._mark_all_read)
        bwl.addWidget(all_read_btn)

        close_btn = QPushButton(t("settings.back"))
        close_btn.setObjectName("AccentBtn")
        close_btn.setFixedHeight(32)
        close_btn.clicked.connect(self.close_requested)
        bwl.addWidget(close_btn)
        sb.addWidget(btn_wrap)

        root.addWidget(sidebar)

        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setObjectName("VLine")
        root.addWidget(vline)

        # ── Inhalts-Stack ─────────────────────────────────────
        self._stack = QStackedWidget()
        self._pages: dict[str, QScrollArea] = {}
        root.addWidget(self._stack, stretch=1)

        self._refresh_all()
        self._switch("Aktuell")

    def _make_cards(self, notifications: list, show_read_btn: bool) -> list:
        faction = self._settings.get("faction","caldari")
        cards   = []
        for notif in notifications:
            card = NotifCard(notif, faction, show_read_btn)
            card.mark_read.connect(self._on_mark_read)
            cards.append(card)
        return cards

    def _refresh_all(self):
        """Nur Stack neu bauen — Sidebar-Items bleiben bestehen."""
        # Alle Stack-Widgets entfernen außer sim_page (die bleibt im RAM)
        to_remove = []
        for i in range(self._stack.count()):
            w = self._stack.widget(i)
            if w is not self._sim_page:
                to_remove.append(w)
        for w in to_remove:
            self._stack.removeWidget(w)
            w.deleteLater()
        # sim_page aus Stack nehmen falls drin
        if self._stack.indexOf(self._sim_page) >= 0:
            self._stack.removeWidget(self._sim_page)
        self._pages.clear()

        all_plus_sim = self._notifications + self._sim_notifs

        for i, (icon, label, ntype, unread_only) in enumerate(self.CATEGORIES):
            if ntype == "__sim__":
                self._pages[label] = self._sim_page
                self._stack.addWidget(self._sim_page)
                if i < len(self._sidebar_items):
                    self._sidebar_items[i].set_count(len(self._sim_notifs))
                continue

            if label == "Aktuell":
                filtered = nf.get_unread(all_plus_sim)
                empty    = t("notifications.no_new") + " 🎉"
            elif label == "Alle":
                filtered = list(all_plus_sim)
                empty    = t("notifications.no_notifications")
            else:
                filtered = [n for n in all_plus_sim if n.get("type") == ntype]
                empty    = f"Keine {label}-Meldungen"

            cards  = self._make_cards(filtered, True)
            scroll = scrolled_list(cards, empty)
            self._pages[label] = scroll
            self._stack.addWidget(scroll)

            if i < len(self._sidebar_items):
                unread_count = sum(1 for n in filtered if not n.get("read", False))
                self._sidebar_items[i].set_count(unread_count)

    def _switch(self, label: str):
        for i, (_, lbl, _, _) in enumerate(self.CATEGORIES):
            self._sidebar_items[i].set_active(lbl == label)
        page = self._pages.get(label)
        if page:
            self._stack.setCurrentWidget(page)

    def _on_mark_read(self, notif_id: str):
        self._notifications = nf.mark_read(self._notifications, notif_id)
        self._refresh_after_change()

    def _mark_all_read(self):
        self._notifications = nf.mark_all_read(self._notifications)
        self._refresh_after_change()

    def _refresh_after_change(self):
        # Aktuelle Kategorie merken
        current = next(
            (lbl for i,(_, lbl, _, _) in enumerate(self.CATEGORIES)
             if self._sidebar_items[i]._active), "Aktuell")
        self._refresh_all()
        self._switch(current)
        has_unread = bool(nf.get_unread(self._notifications))
        self.unread_changed.emit(has_unread)

    def _on_sim_notif(self, notif: dict):
        self._sim_notifs.append(notif)
        current = next(
            (lbl for i,(_, lbl, _, _) in enumerate(self.CATEGORIES)
             if self._sidebar_items[i]._active), "Aktuell")
        self._refresh_all()
        self._switch(current)
        self.unread_changed.emit(True)
        # Alle Nachrichten (echt + sim) nach außen melden
        self.all_notifications_changed.emit(
            self._notifications + self._sim_notifs)

    def _on_sim_clear(self):
        self._sim_notifs.clear()
        current = next(
            (lbl for i,(_, lbl, _, _) in enumerate(self.CATEGORIES)
             if self._sidebar_items[i]._active), "Aktuell")
        self._refresh_all()
        self._switch(current)
        has_unread = bool(nf.get_unread(self._notifications))
        self.unread_changed.emit(has_unread)
        self.all_notifications_changed.emit(self._notifications)

    def set_test_mode(self, enabled: bool):
        """Simulator-Tab ein/ausblenden + bei Deaktivierung alles löschen."""
        # Simulator Item finden
        for i, (_, lbl, ntype, _) in enumerate(self.CATEGORIES):
            if ntype == "__sim__":
                self._sidebar_items[i].setVisible(enabled)
                break
        if not enabled and self._sim_notifs:
            self._sim_page.clear_all()
            # _on_sim_clear wird via Signal aufgerufen

    def retranslate(self):
        """Rebuild bei Sprachwechsel."""
        current = next(
            (lbl for i,(_, lbl, _, _) in enumerate(self.CATEGORIES)
             if i < len(self._sidebar_items) and self._sidebar_items[i]._active),
            self.CATEGORIES[0][1])
        self._refresh_all()
        self._switch(current)

    def update_notifications(self, notifications: list):
        self._notifications = notifications
        self._refresh_all()

    def set_faction(self, faction: str):
        self._accent = FACTIONS.get(faction, FACTIONS["caldari"])["accent"]
        self._settings["faction"] = faction
        for item in self._sidebar_items:
            item.set_accent(self._accent)
        self._refresh_all()