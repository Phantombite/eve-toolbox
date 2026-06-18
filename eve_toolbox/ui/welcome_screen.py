"""
Willkommens-Bildschirm — wird nur beim ersten Start angezeigt.
"""
from core import logger as _logger
_log = _logger.get("welcome_screen")

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QWidget, QComboBox, QButtonGroup)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import (QPainter, QColor, QFont, QLinearGradient,
                          QPainterPath, QPen, QPixmap)
from pathlib import Path

from core.config import FACTIONS, APP_VERSION
from core.i18n import t, set_language

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "icons"


class FactionCard(QWidget):
    """Klickbare Fraktionskarte."""
    clicked = pyqtSignal(str)

    def __init__(self, faction_key: str, faction: dict, parent=None):
        super().__init__(parent)
        self._key     = faction_key
        self._faction = faction
        self._selected = False
        self._hov      = False
        self.setFixedSize(100, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, v: bool):
        self._selected = v
        self.update()

    def enterEvent(self, e): self._hov = True;  self.update()
    def leaveEvent(self, e): self._hov = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h  = self.width(), self.height()
        acc   = QColor(self._faction["accent"])

        # Hintergrund
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, w-4, h-4), 10, 10)

        if self._selected:
            p.fillPath(path, QColor(acc.red(), acc.green(), acc.blue(), 60))
            p.setPen(QPen(acc, 2.5))
        elif self._hov:
            p.fillPath(path, QColor(acc.red(), acc.green(), acc.blue(), 30))
            p.setPen(QPen(acc, 1.5))
        else:
            p.fillPath(path, QColor(30, 25, 45))
            p.setPen(QPen(QColor(80, 70, 100), 1))
        p.drawPath(path)

        # Logo
        logo_path = ASSETS / f"{self._key}.png"
        if logo_path.exists():
            pm = QPixmap(str(logo_path)).scaled(
                50, 50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((w - pm.width())//2, 12, pm)

        # Name
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(QPen(acc if self._selected else QColor("#cccccc")))
        p.drawText(QRectF(0, h-22, w, 20),
                   Qt.AlignmentFlag.AlignCenter,
                   self._faction["name"])
        p.end()


class OptionBtn(QPushButton):
    """Toggle-Button für Theme/Layout-Auswahl."""
    def __init__(self, label: str, parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(36)
        self._update_style()
        self.toggled.connect(lambda _: self._update_style())

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(
                "background: #7B2FBE; color: white; border-radius: 8px;"
                "font-weight: 700; font-size: 13px; border: none;")
        else:
            self.setStyleSheet(
                "background: rgba(255,255,255,0.08); color: #aaaaaa;"
                "border-radius: 8px; font-size: 13px; border: none;")


class WelcomeScreen(QDialog):
    """Willkommens-Dialog beim ersten Start."""
    setup_complete = pyqtSignal(dict)  # Gibt gewählte Settings zurück

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings     = dict(settings)
        self._sel_faction = "caldari"
        self._sel_theme   = "dark"
        self._sel_lang    = "en"

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(560, 640)
        self._center()
        self._build()

    def _center(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2)

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(160)
        header.setStyleSheet("background: transparent;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(40, 30, 40, 20)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("EVE Toolbox")
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Black))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        hl.addWidget(title)

        sub = QLabel(f"v{APP_VERSION}  ·  by phantombite")
        sub.setFont(QFont("Segoe UI", 11))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color: rgba(180,140,255,0.8); background: transparent;")
        hl.addWidget(sub)

        main.addWidget(header)

        # ── Inhalt ────────────────────────────────────────────
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 10, 40, 10)
        cl.setSpacing(20)

        # Sprache — Dropdown (skaliert für viele Sprachen)
        cl.addWidget(self._section_label("Language / Sprache"))
        from PyQt6.QtWidgets import QComboBox
        self._lang_cb = QComboBox()
        self._lang_cb.setFixedHeight(36)
        self._lang_cb.setStyleSheet(
            "QComboBox { background: rgba(255,255,255,0.08); color: white;"
            "border-radius: 8px; padding: 0 12px; font-size: 13px; border: none; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            "QComboBox QAbstractItemView { background: #1a1a2e; color: white;"
            "border: 1px solid rgba(123,47,190,0.5); selection-background-color: #7B2FBE; }")
        self._lang_items = [
            {"code": "en", "name": "English 🇬🇧"},
            {"code": "de", "name": "Deutsch 🇩🇪"},
        ]
        for lang in self._lang_items:
            self._lang_cb.addItem(lang["name"], lang["code"])
        self._lang_cb.setCurrentIndex(0)  # English default
        self._lang_cb.currentIndexChanged.connect(
            lambda i: self._set_lang(self._lang_items[i]["code"]))
        cl.addWidget(self._lang_cb)

        # Theme
        self._theme_label = QLabel("Theme")
        self._theme_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._theme_label.setStyleSheet("color: #cccccc; background: transparent;")
        cl.addWidget(self._theme_label)

        theme_row = QHBoxLayout()
        theme_grp = QButtonGroup(self)
        self._btn_dark  = OptionBtn("🌙  Dark")
        self._btn_light = OptionBtn("☀  Light")
        self._btn_dark.setChecked(True)
        theme_grp.addButton(self._btn_dark)
        theme_grp.addButton(self._btn_light)
        theme_grp.setExclusive(True)
        self._btn_dark.toggled.connect(lambda v: v and self._set("theme","dark"))
        self._btn_light.toggled.connect(lambda v: v and self._set("theme","light"))
        theme_row.addWidget(self._btn_dark)
        theme_row.addWidget(self._btn_light)
        cl.addLayout(theme_row)

        # Fraktion
        self._faction_label = QLabel("Faction Design")
        self._faction_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._faction_label.setStyleSheet("color: #cccccc; background: transparent;")
        cl.addWidget(self._faction_label)

        faction_row = QHBoxLayout()
        faction_row.setSpacing(12)
        self._faction_cards = {}
        for key, f in sorted(FACTIONS.items(), key=lambda x: x[1]["name"]):
            card = FactionCard(key, f)
            card.clicked.connect(self._set_faction)
            faction_row.addWidget(card)
            self._faction_cards[key] = card
        self._faction_cards["caldari"].set_selected(True)
        cl.addLayout(faction_row)

        main.addWidget(content)
        main.addStretch()

        # ── Footer ────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(40, 10, 40, 30)
        fl.setSpacing(8)

        self._start_btn = QPushButton("🚀  Let's go!")
        self._start_btn.setFixedHeight(48)
        self._start_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._start_btn.setStyleSheet(
            "background: #7B2FBE; color: white; border-radius: 10px; border: none;")
        self._start_btn.clicked.connect(self._finish)
        fl.addWidget(self._start_btn)

        note = QLabel("EVE Online® is a registered trademark of CCP hf.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setStyleSheet("color: rgba(255,255,255,0.25); font-size: 9px; background: transparent;")
        fl.addWidget(note)

        main.addWidget(footer)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        lbl.setStyleSheet("color: #cccccc; background: transparent;")
        return lbl

    def _set_lang(self, lang: str):
        self._sel_lang = lang
        set_language(lang)
        # Labels aktualisieren
        self._theme_label.setText(t("settings.theme"))
        self._faction_label.setText(t("settings.faction_design"))
        self._start_btn.setText("🚀  " + ("Los geht's!" if lang == "de" else "Let's go!"))

    def _set(self, key: str, val):
        self.settings[key] = val

    def _set_faction(self, key: str):
        for k, card in self._faction_cards.items():
            card.set_selected(k == key)
        self._sel_faction = key

    def _finish(self):
        self.settings["language"]   = self._sel_lang
        self.settings["faction"]    = self._sel_faction
        self.settings["first_run"]  = False
        self.setup_complete.emit(self.settings)
        self.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Hintergrund
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(path, QColor("#0d0d1a"))

        # Lila Gradient oben
        grad = QLinearGradient(0, 0, w, 160)
        grad.setColorAt(0.0, QColor(80,  20, 140, 200))
        grad.setColorAt(1.0, QColor(13,  13,  26,   0))
        top = QPainterPath()
        top.addRoundedRect(QRectF(0, 0, w, 160), 16, 16)
        p.fillPath(top, grad)

        # Rahmen
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(100, 50, 180, 120), 1.5))
        p.drawPath(path)
        p.end()