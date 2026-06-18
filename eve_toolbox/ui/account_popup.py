"""
Account-Popup — erscheint unter dem Spieler-Widget in Fraktionsfarbe.
Zeigt Chars an, leitet Login zur Account-Verwaltung weiter.
"""
from core import logger as _logger
_log = _logger.get("account_popup")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath

from core.config import FACTIONS
from core import esi as esi_mod


class CharRow(QWidget):
    """Eine Charakter-Zeile im Popup."""
    set_active = pyqtSignal(str)

    def __init__(self, char: dict, faction: str, parent=None):
        super().__init__(parent)
        self._char = char
        self._hov  = False
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        self._accent = f["accent"]
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._build(char, f)

    def _build(self, char: dict, f: dict):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 4, 12, 4)
        lay.setSpacing(10)

        initials = "".join(w[0] for w in str(char["name"]).split()[:2]).upper()
        avatar = QLabel(initials)
        avatar.setFixedSize(28, 28)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background: {f['accent']}; color: white; border-radius: 14px;"
            "font-size: 10px; font-weight: 700;")
        lay.addWidget(avatar)

        info = QVBoxLayout()
        info.setSpacing(1)

        name_lbl = QLabel(str(char["name"]))
        name_lbl.setFont(QFont("Segoe UI", 11,
            QFont.Weight.DemiBold if char.get("active") else QFont.Weight.Normal))
        name_lbl.setStyleSheet("background: transparent;")
        info.addWidget(name_lbl)

        corp_text = str(char.get("corp") or "")
        corp_lbl = QLabel(corp_text)
        corp_lbl.setStyleSheet("font-size: 10px; color: #888; background: transparent;")
        info.addWidget(corp_lbl)
        lay.addLayout(info, stretch=1)

        if char.get("omega"):
            omega = QLabel("Ω")
            omega.setFixedSize(18, 18)
            omega.setAlignment(Qt.AlignmentFlag.AlignCenter)
            omega.setStyleSheet(
                "background: #FAC775; color: #633806; border-radius: 9px;"
                "font-size: 10px; font-weight: 700;")
            lay.addWidget(omega)

        if char.get("active"):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {f['accent']}; font-size: 10px; background: transparent;")
            lay.addWidget(dot)

    def enterEvent(self, e):
        self._hov = True
        self.update()

    def leaveEvent(self, e):
        self._hov = False
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.set_active.emit(str(self._char["id"]))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        acc = QColor(self._accent)
        if self._char.get("active"):
            p.fillRect(0, 0, self.width(), self.height(),
                       QColor(acc.red(), acc.green(), acc.blue(), 25))
            p.fillRect(0, 0, 3, self.height(), acc)
        elif self._hov:
            p.fillRect(0, 0, self.width(), self.height(),
                       QColor(acc.red(), acc.green(), acc.blue(), 15))
        p.end()


class AccountPopup(QWidget):
    """Fraktions-gestyltes Account-Dropdown — reines Anzeige/Auswahl Widget."""
    account_changed = pyqtSignal(dict)
    open_settings   = pyqtSignal()
    request_login   = pyqtSignal()

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self._settings  = settings
        self._active_id = None   # Merkt sich welcher Char aktiv ist
        self._accounts  = []
        self.setObjectName("SettingsPanel")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(260)
        self._build()
        self.reload()

    def _load_accounts(self) -> list:
        """Lädt alle Charaktere direkt aus Token-Dateien."""
        try:
            tokens = esi_mod.load_tokens()
        except Exception:
            return []
        chars = []
        for t in tokens:
            chars.append({
                "id":    str(t.get("id", "")),
                "name":  str(t.get("name", "Unbekannt")),
                "corp":  str(t.get("corp_name") or t.get("corp_id") or "Unbekannt"),
                "omega": True,
                "active": False,
            })
        return chars

    def reload(self):
        _log.debug("Popup: Accounts werden neu geladen")
        """Accounts neu laden — aktiven Char merken, nach Löschen zum ersten wechseln."""
        chars = self._load_accounts()
        prev_active_id = self._active_id

        if not chars:
            self._active_id = None
            self._accounts  = []
            # Topbar informieren dass kein Char mehr aktiv ist
            if prev_active_id is not None:
                self.account_changed.emit({"name": "Kein Login", "id": "", "corp": ""})
        else:
            ids = [c["id"] for c in chars]
            if self._active_id not in ids:
                self._active_id = chars[0]["id"]

            for c in chars:
                c["active"] = (c["id"] == self._active_id)

            self._accounts = chars

            # Topbar informieren wenn aktiver Char sich geändert hat
            if self._active_id != prev_active_id:
                active = next((c for c in chars if c["active"]), None)
                if active:
                    self.account_changed.emit(active)

        self._refresh()

    def set_login_state(self, countdown: int):
        """Timer-Stand vom Account-Verwaltungs-Login synchronisieren."""
        if countdown > 0:
            self._add_btn.setEnabled(False)
            self._add_btn.setText(f"⏳  {countdown}s")
        else:
            self._add_btn.setEnabled(True)
            self._add_btn.setText("＋  Account hinzufügen")

    def _on_add(self):
        """Login-Anfrage → Account-Verwaltung öffnen."""
        self.hide()
        self.request_login.emit()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        title = QLabel("Accounts")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setObjectName("PanelTitle")
        title.setStyleSheet("background: transparent;")
        hl.addWidget(title)
        lay.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("HLine")
        lay.addWidget(sep)

        # Char-Liste
        self._list_widget = QWidget()
        self._list_lay    = QVBoxLayout(self._list_widget)
        self._list_lay.setContentsMargins(0, 4, 0, 4)
        self._list_lay.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setWidget(self._list_widget)
        self._scroll.setMaximumHeight(6 * 48 + 8)
        lay.addWidget(self._scroll)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("HLine")
        lay.addWidget(sep2)

        # Footer
        footer = QWidget()
        fl     = QVBoxLayout(footer)
        fl.setContentsMargins(12, 8, 12, 8)
        fl.setSpacing(6)

        add_btn = QPushButton("＋  Account hinzufügen")
        add_btn.setObjectName("AccentBtn")
        add_btn.setFixedHeight(28)
        add_btn.clicked.connect(self._on_add)
        fl.addWidget(add_btn)
        self._add_btn = add_btn

        mgr_btn = QPushButton("⚙  Account-Verwaltung")
        mgr_btn.setObjectName("AccentBtn")
        mgr_btn.setFixedHeight(28)
        mgr_btn.clicked.connect(self._on_open_settings)
        fl.addWidget(mgr_btn)
        lay.addWidget(footer)

    def _refresh(self):
        """Nur die Char-Liste neu aufbauen."""
        while self._list_lay.count():
            w = self._list_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.setParent(None)

        faction = self._settings.get("faction", "caldari")

        if not self._accounts:
            empty = QLabel("  Noch kein Account eingeloggt.")
            empty.setStyleSheet("font-size: 10px; color: #888; padding: 8px;")
            self._list_lay.addWidget(empty)
        else:
            for char in self._accounts:
                row = CharRow(char, faction)
                row.set_active.connect(self._on_set_active)
                self._list_lay.addWidget(row)

        visible = min(len(self._accounts), 6) if self._accounts else 1
        self._scroll.setMaximumHeight(visible * 48 + 8)
        self._scroll.setMinimumHeight(visible * 48 + 8)

    def _on_set_active(self, char_id: str):
        _log.info(f"Aktiver Char gesetzt: {char_id}")
        self._active_id = char_id
        active_char = None
        for char in self._accounts:
            char["active"] = (char["id"] == char_id)
            if char["active"]:
                active_char = char
        if active_char:
            self.account_changed.emit(active_char)
        self._refresh()
        self.hide()

    def _on_open_settings(self):
        self.hide()
        self.open_settings.emit()

    def update_faction(self, faction: str):
        self._settings["faction"] = faction
        self._refresh()