"""
Einstellungsseite — Sidebar links, Inhalt rechts.
"""
from core import logger as _logger
_log = _logger.get("settings_page")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QScrollArea, QFrame, QComboBox, QPushButton,
                              QSizePolicy, QStackedWidget,
                              QMessageBox, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPainterPath

from core.config import FACTIONS, HOME_LAYOUTS, MODULES
from core.i18n import t, available_languages


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
        self.setFixedHeight(42)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def set_active(self, v: bool): self._active = v; self.update()
    def set_accent(self, c: str):  self._accent = c; self.update()
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
        p.drawText(QRectF(46, 0, w-50, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.label)
        p.end()


def hline():
    l = QFrame(); l.setFrameShape(QFrame.Shape.HLine); l.setObjectName("HLine")
    return l

def section(text: str) -> QLabel:
    l = QLabel(text)
    l.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    return l


class SettingRow(QWidget):
    def __init__(self, label: str, sublabel: str = "", parent=None):
        super().__init__(parent)
        self.setMinimumHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 8)
        lay.setSpacing(12)
        info = QVBoxLayout(); info.setSpacing(2)
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Medium))
        info.addWidget(lbl)
        if sublabel:
            sub = QLabel(sublabel); sub.setObjectName("SettingsSubLabel")
            sub.setWordWrap(True); info.addWidget(sub)
        lay.addLayout(info, stretch=1)
        self._lay = lay

    def add_control(self, w): self._lay.addWidget(w)


class ToggleBtn(QPushButton):
    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setObjectName("ToggleBtn")
        self.setCheckable(True); self.setChecked(checked)
        self.setText("ON" if checked else "OFF")
        self.setFixedSize(52, 24)
        self.clicked.connect(lambda: self.setText("ON" if self.isChecked() else "OFF"))


class SettingsCombo(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsCombo")
        self.setMinimumWidth(150)


def scrolled(inner: QWidget) -> QScrollArea:
    s = QScrollArea(); s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setWidget(inner); return s


# ── Seiten ────────────────────────────────────────────────────────────────────

class PageAllgemein(QWidget):
    language_changed    = pyqtSignal(str)
    window_size_changed = pyqtSignal(int, int)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings    = settings
        self._pending_lang = settings.get("language", "de")
        inner = QWidget()
        lay   = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(0)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        lay.addWidget(section(t("settings.general")))
        lay.addWidget(hline()); lay.addSpacing(12)

        # Sprache
        row_lang = SettingRow(t("settings.language"), t("settings.language_desc"))
        self._lang_cb = SettingsCombo()
        self._lang_items = [
            {"code": "de", "name": "Deutsch 🇩🇪"},
            {"code": "en", "name": "English 🇬🇧"},
        ]
        cur_lang = self.settings.get("language", "de")
        cur_idx  = 0
        for idx, lang in enumerate(self._lang_items):
            self._lang_cb.addItem(lang["name"], lang["code"])
            if lang["code"] == cur_lang:
                cur_idx = idx
        self._lang_cb.blockSignals(True)
        self._lang_cb.setCurrentIndex(cur_idx)
        self._lang_cb.blockSignals(False)
        row_lang.add_control(self._lang_cb)
        lay.addWidget(row_lang)

        # Neustart-Banner (versteckt bis Sprachwechsel)
        self._restart_banner = QWidget()
        self._restart_banner.setStyleSheet(
            "background: #BA7517; border-radius: 6px; margin: 2px 0;")
        _rbl = QHBoxLayout(self._restart_banner)
        _rbl.setContentsMargins(12, 8, 12, 8)
        _rwarn = QLabel("⚠  App-Neustart erforderlich für Sprachänderung.")
        _rwarn.setStyleSheet("color: white; background: transparent; font-weight: 600;")
        _rbl.addWidget(_rwarn); _rbl.addStretch()
        _rrbtn = QPushButton("↺  Jetzt neu starten")
        _rrbtn.setStyleSheet(
            "background: white; color: #BA7517; font-weight: 700;"
            "border-radius: 5px; padding: 4px 12px; border: none;")
        _rrbtn.clicked.connect(self._do_restart)
        _rbl.addWidget(_rrbtn)
        _rcbtn = QPushButton("✕")
        _rcbtn.setStyleSheet(
            "background: transparent; color: white; font-size: 16px; border: none;")
        _rcbtn.clicked.connect(self._cancel_lang)
        _rbl.addWidget(_rcbtn)
        self._restart_banner.setVisible(False)
        lay.addWidget(self._restart_banner)

        # Signal erst nach Banner verbinden
        self._lang_cb.currentIndexChanged.connect(self._on_lang_change)

        lay.addWidget(hline()); lay.addSpacing(4)

        # Fenstergröße
        row2 = SettingRow(t("settings.window_size"), t("settings.window_size_desc"))
        self._size_cb = SettingsCombo()
        self._window_sizes = [
            ("Klein       (1024 × 640)",   1024, 640),
            ("Mittel      (1280 × 800)",   1280, 800),
            ("Standard    (1200 × 750)",   1200, 750),
            ("Groß        (1440 × 900)",   1440, 900),
            ("HD          (1600 × 900)",   1600, 900),
            ("Full HD     (1920 × 1080)",  1920, 1080),
            ("2K          (2560 × 1440)",  2560, 1440),
        ]
        cur_w   = self.settings.get("window_width",  1200)
        cur_h   = self.settings.get("window_height", 750)
        size_idx = 2
        for idx, (label, w, h) in enumerate(self._window_sizes):
            self._size_cb.addItem(label)
            if w == cur_w and h == cur_h:
                size_idx = idx
        self._size_cb.setCurrentIndex(size_idx)
        self._size_cb.currentIndexChanged.connect(self._on_size)
        row2.add_control(self._size_cb)
        lay.addWidget(row2)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def _on_lang_change(self, idx: int):
        new_lang = self._lang_items[idx]["code"]
        cur_lang = self.settings.get("language", "de")
        if new_lang == cur_lang:
            self._restart_banner.setVisible(False)
            return
        self._pending_lang = new_lang
        self._restart_banner.setVisible(True)

    def _do_restart(self):
        from core import settings as cfg
        self.settings["language"] = self._pending_lang
        cfg.save(self.settings)
        import sys, subprocess
        try:
            subprocess.Popen([sys.executable] + sys.argv)
        except Exception:
            try:
                import os; os.startfile(sys.argv[0])
            except Exception:
                pass
        sys.exit(0)

    def _cancel_lang(self):
        self._restart_banner.setVisible(False)
        cur = self.settings.get("language", "de")
        for i, l in enumerate(self._lang_items):
            if l["code"] == cur:
                self._lang_cb.blockSignals(True)
                self._lang_cb.setCurrentIndex(i)
                self._lang_cb.blockSignals(False)
                break

    def _on_size(self, idx: int):
        _, w, h = self._window_sizes[idx]
        self.settings["window_width"]  = w
        self.settings["window_height"] = h
        self.window_size_changed.emit(w, h)

    def sync(self):
        cur = self.settings.get("language", "de")
        for i, l in enumerate(self._lang_items):
            if l["code"] == cur:
                self._lang_cb.blockSignals(True)
                self._lang_cb.setCurrentIndex(i)
                self._lang_cb.blockSignals(False)
                break
        cur_w = self.settings.get("window_width",  1200)
        cur_h = self.settings.get("window_height", 750)
        for idx, (_, w, h) in enumerate(self._window_sizes):
            if w == cur_w and h == cur_h:
                self._size_cb.setCurrentIndex(idx)
                return
        self._size_cb.setCurrentIndex(2)


class PageDarstellung(QWidget):
    faction_changed   = pyqtSignal(str)
    theme_changed     = pyqtSignal(str)
    layout_changed    = pyqtSignal(str)
    edit_mode_changed = pyqtSignal(bool)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(0); lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        lay.addWidget(section(t("settings.appearance")))
        lay.addWidget(hline()); lay.addSpacing(12)

        # Fraktion
        row = SettingRow(t("settings.faction_design"), t("settings.faction_design_desc"))
        self._faction_cb = SettingsCombo()
        for key, f in sorted(FACTIONS.items(), key=lambda x: x[1]["name"]):
            self._faction_cb.addItem(f["name"], key)
        cur = self.settings.get("faction","caldari")
        sorted_keys = [key for key, _ in sorted(FACTIONS.items(), key=lambda x: x[1]["name"])]
        self._faction_cb.setCurrentIndex(sorted_keys.index(cur) if cur in sorted_keys else 0)
        self._faction_cb.currentIndexChanged.connect(
            lambda i: self.faction_changed.emit(self._faction_cb.itemData(i)))
        row.add_control(self._faction_cb); lay.addWidget(row)
        lay.addWidget(hline()); lay.addSpacing(4)

        # Theme
        row2 = SettingRow(t("settings.theme"), t("settings.theme_desc"))
        self._theme_cb = SettingsCombo()
        self._theme_cb.addItem(t("settings.theme_light"), "light"); self._theme_cb.addItem(t("settings.theme_dark"), "dark")
        self._theme_cb.setCurrentIndex(0 if self.settings.get("theme","dark") == "light" else 1)
        self._theme_cb.currentIndexChanged.connect(
            lambda i: self.theme_changed.emit("light" if i == 0 else "dark"))
        row2.add_control(self._theme_cb); lay.addWidget(row2)
        lay.addWidget(hline()); lay.addSpacing(4)

        # Home Layout
        row3 = SettingRow(t("settings.home_layout"), t("settings.home_layout_desc"))
        self._layout_cb = SettingsCombo()
        for key, label in HOME_LAYOUTS.items():
            self._layout_cb.addItem(label, key)
        cur_l = self.settings.get("home_layout","grid")
        lkeys = list(HOME_LAYOUTS.keys())
        self._layout_cb.setCurrentIndex(lkeys.index(cur_l) if cur_l in lkeys else 0)
        self._layout_cb.currentIndexChanged.connect(
            lambda i: self.layout_changed.emit(list(HOME_LAYOUTS.keys())[i]))
        row3.add_control(self._layout_cb); lay.addWidget(row3)
        lay.addWidget(hline()); lay.addSpacing(4)

        # Bearbeitungsmodus
        row4 = SettingRow(t("settings.edit_layout"), t("settings.edit_layout_desc"))
        self._edit_btn = ToggleBtn(not self.settings.get("edit_locked", True))
        self._edit_btn.clicked.connect(
            lambda: self.edit_mode_changed.emit(self._edit_btn.isChecked()))
        row4.add_control(self._edit_btn); lay.addWidget(row4)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def sync(self):
        cur = self.settings.get("faction","caldari")
        sorted_keys = [key for key, _ in sorted(FACTIONS.items(), key=lambda x: x[1]["name"])]
        self._faction_cb.setCurrentIndex(sorted_keys.index(cur) if cur in sorted_keys else 0)
        self._theme_cb.setCurrentIndex(0 if self.settings.get("theme","dark") == "light" else 1)
        lkeys = list(HOME_LAYOUTS.keys())
        cur_l = self.settings.get("home_layout","grid")
        self._layout_cb.setCurrentIndex(lkeys.index(cur_l) if cur_l in lkeys else 0)
        self._edit_btn.setChecked(not self.settings.get("edit_locked", True))
        self._edit_btn.setText("ON" if self._edit_btn.isChecked() else "OFF")


class PageFunktionsInfo(QWidget):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(0); lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        lay.addWidget(section(t("settings.func_info")))

        info = QLabel(
            "Hier siehst du den Status aller Module.\n"
            "Fertig = produktionsbereit  ·  In Entwicklung = im Dev-Modus aktiv  ·  Geplant = noch nicht begonnen"
        )
        info.setObjectName("SettingsSubLabel")
        info.setWordWrap(True)
        lay.addWidget(info)
        lay.addWidget(hline()); lay.addSpacing(12)

        STATUS_ICONS = {
            "fertig":      ("✓",  "#3B6D11"),
            "entwicklung": ("⚙",  "#BA7517"),
            "geplant":     ("○",  "#888888"),
        }
        STATUS_LABELS = {
            "fertig":      "Fertig",
            "entwicklung": "In Entwicklung",
            "geplant":     "Geplant",
        }

        for mod in MODULES:
            status = mod.get("status", "geplant")
            icon, color = STATUS_ICONS.get(status, ("○", "#888"))
            label = STATUS_LABELS.get(status, "Geplant")

            row = SettingRow(mod["name"], mod["desc"])
            badge = QLabel(f"{icon}  {label}")
            badge.setStyleSheet(
                f"color: {color}; font-size: 11px; font-weight: 600;"
                f"min-width: 130px;"
            )
            row.add_control(badge)
            lay.addWidget(row)
            lay.addWidget(hline())

        lay.addStretch()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def sync(self): pass


class PageEntwickler(QWidget):
    dev_mode_changed  = pyqtSignal(bool)
    test_mode_changed = pyqtSignal(bool)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(0); lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        lay.addWidget(section(t("settings.developer")))
        lay.addWidget(hline()); lay.addSpacing(12)

        # Warnung
        warn = QLabel(
            "⚠  Diese Einstellungen sind für Entwickler und Tester.\n"
            "   Im Normalbetrieb sollten beide Modi deaktiviert sein."
        )
        warn.setStyleSheet(
            "background: #FAEEDA; border: 1px solid #EF9F27; border-radius: 8px;"
            "padding: 10px 14px; font-size: 12px; color: #633806;"
        )
        warn.setWordWrap(True)
        lay.addWidget(warn); lay.addSpacing(12)

        # Entwicklermodus
        row = SettingRow(t("settings.dev_mode"),
                         "Schaltet Module frei die als 'In Entwicklung' markiert sind")
        self._dev_btn = ToggleBtn(self.settings.get("dev_mode", False))
        self._dev_btn.clicked.connect(self._on_dev)
        row.add_control(self._dev_btn); lay.addWidget(row)
        lay.addWidget(hline()); lay.addSpacing(4)

        # Testmodus
        row2 = SettingRow(t("settings.test_mode"),
                          "Hebt ALLE Sperren auf — auch geplante Module.\n"
                          "Nur verfügbar wenn Entwicklermodus aktiv ist.")
        self._test_btn = ToggleBtn(self.settings.get("test_mode", False))
        self._test_btn.setEnabled(self.settings.get("dev_mode", False))
        self._test_btn.clicked.connect(
            lambda: self.test_mode_changed.emit(self._test_btn.isChecked()))
        row2.add_control(self._test_btn); lay.addWidget(row2)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def _on_dev(self):
        enabled = self._dev_btn.isChecked()
        self._test_btn.setEnabled(enabled)
        if not enabled:
            self._test_btn.setChecked(False)
            self._test_btn.setText("OFF")
            self.test_mode_changed.emit(False)
        self.dev_mode_changed.emit(enabled)

    def sync(self):
        dev = self.settings.get("dev_mode", False)
        self._dev_btn.setChecked(dev)
        self._dev_btn.setText("ON" if dev else "OFF")
        test = self.settings.get("test_mode", False)
        self._test_btn.setChecked(test)
        self._test_btn.setText("ON" if test else "OFF")
        self._test_btn.setEnabled(dev)


class PageZuruecksetzen(QWidget):
    reset_requested = pyqtSignal(str)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        inner = QWidget()
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(32, 24, 32, 24)
        lay.setSpacing(0); lay.setAlignment(Qt.AlignmentFlag.AlignTop)

        lay.addWidget(section(t("settings.reset")))
        lay.addWidget(hline()); lay.addSpacing(12)

        items = [
            ("Layout zurücksetzen",
             "Setzt die Reihenfolge der Module auf Standard zurück",
             "layout", False),
            ("Einstellungen zurücksetzen",
             "Setzt Fraktion, Theme, Sprache und alle Darstellungsoptionen zurück",
             "settings", False),
            ("Alles zurücksetzen",
             "Setzt alle Einstellungen und Layouts auf Werkseinstellungen zurück",
             "all", True),
        ]

        self._status = QLabel("")
        self._status.setObjectName("SettingsSubLabel")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for label, sub, what, danger in items:
            row = SettingRow(label, sub)
            btn = QPushButton("⚠  Zurücksetzen" if danger else t("settings.reset_btn"))
            btn.setObjectName("AccentBtn")
            btn.setFixedWidth(160)
            if danger:
                btn.setStyleSheet("background: #993C1D; color: white;")
            btn.clicked.connect(lambda checked, w=what: self._confirm(w))
            row.add_control(btn)
            lay.addWidget(row)
            lay.addWidget(hline()); lay.addSpacing(4)

        lay.addSpacing(16)
        lay.addWidget(self._status)
        lay.addStretch()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def _confirm(self, what: str):
        labels = {"layout":"das Layout","settings":"die Einstellungen","all":"ALLES"}
        msg = QMessageBox(self)
        msg.setWindowTitle("Zurücksetzen bestätigen")
        msg.setText(f"Möchtest du wirklich {labels[what]} zurücksetzen?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            self.reset_requested.emit(what)
            self._status.setText(f"✓  {labels[what].capitalize()} wurde zurückgesetzt.")

    def sync(self): pass


class PageAccounts(QWidget):
    accounts_changed = pyqtSignal()   # Feuert nach Login oder Löschen
    login_done       = pyqtSignal()   # Thread-sicheres Signal nach Login
    login_error      = pyqtSignal()   # Thread-sicheres Signal nach Fehler

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings         = settings
        self._del_mode        = False
        self._selected        = set()
        self._pending_delete  = set()
        self._tokens          = []
        self._add_btn_ref     = None
        self._popup_ref       = None
        self._reload_callback = None
        self._load_tokens()
        self._build_static()   # Statischer Rahmen — wird nie neu gebaut
        self.login_done.connect(self._on_login_done)
        self.login_error.connect(self._on_login_error)

    def _build_static(self):
        """Baut den statischen Rahmen einmalig auf."""
        f = FACTIONS.get(self.settings.get("faction","caldari"), FACTIONS["caldari"])

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 24, 32, 24)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Titel + Mehrfachlöschen Buttons
        title_row = QHBoxLayout()
        title_row.addWidget(section(t("settings.accounts")))
        title_row.addStretch()

        # Löschen-Button (nur sichtbar wenn Auswahl getroffen)
        self._multi_del_btn = QPushButton("✕  Löschen")
        self._multi_del_btn.setFixedHeight(28)
        self._multi_del_btn.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; padding: 0 10px;")
        self._multi_del_btn.clicked.connect(self._confirm_multi_delete)
        self._multi_del_btn.hide()
        title_row.addWidget(self._multi_del_btn)

        # Mehrere/Abbrechen Button
        self._multi_btn = QPushButton(t("settings.delete_multiple"))
        self._multi_btn.setFixedHeight(28)
        self._multi_btn.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; padding: 0 10px;")
        self._multi_btn.clicked.connect(self._toggle_del_mode)
        title_row.addWidget(self._multi_btn)

        title_widget = QWidget()
        title_widget.setLayout(title_row)
        outer.addWidget(title_widget)

        info = QLabel("Alle verbundenen EVE-Charaktere. Klicke 'Account hinzufügen' um dich einzuloggen.")
        info.setObjectName("SettingsSubLabel")
        info.setWordWrap(True)
        outer.addWidget(info)
        outer.addWidget(hline())
        outer.addSpacing(8)

        # Char-Liste — nur dieser Teil wird neu gebaut
        self._char_container = QWidget()
        self._char_lay = QVBoxLayout(self._char_container)
        self._char_lay.setContentsMargins(0, 0, 0, 0)
        self._char_lay.setSpacing(0)
        outer.addWidget(self._char_container)

        outer.addSpacing(8)

        # Buttons — statisch, werden nie neu gebaut
        btn_widget = QWidget()
        btn_row = QHBoxLayout(btn_widget)
        btn_row.setContentsMargins(0, 0, 0, 0)

        add_btn = QPushButton("＋  Account hinzufügen  (EVE SSO Login)")
        self._add_btn_ref = add_btn
        add_btn.setObjectName("AccentBtn")
        add_btn.clicked.connect(self._on_add_account)
        btn_row.addWidget(add_btn)



        outer.addWidget(btn_widget)
        outer.addStretch()

        # Initial befüllen
        self._build()

    def _load_tokens(self):
        """Lädt Token-Dateien und stellt sicher dass alle Felder Strings sind."""
        try:
            from core import esi as esi_mod
            raw = esi_mod.load_tokens()
        except Exception:
            raw = []
        self._tokens = []
        for t in raw:
            self._tokens.append({
                "id":        str(t.get("id", "")),
                "name":      str(t.get("name", "Unbekannt")),
                "corp_name": str(t.get("corp_name") or t.get("corp_id") or "Unbekannt"),
            })

    def _build(self):
        """Nur die Char-Liste neu aufbauen — Rahmen bleibt."""
        f = FACTIONS.get(self.settings.get("faction","caldari"), FACTIONS["caldari"])

        # Rendering einfrieren während Umbau
        self._char_container.setUpdatesEnabled(False)

        # Char-Container leeren
        while self._char_lay.count():
            item = self._char_lay.takeAt(0)
            w = item.widget()
            if w:
                w.hide()
                w.setParent(None)

        if not self._tokens:
            empty = QLabel("Noch kein Charakter eingeloggt.")
            empty.setStyleSheet("color: #888; font-size: 11px; padding: 8px 0;")
            self._char_lay.addWidget(empty)
            self._char_lay.addWidget(hline())
        else:
            for tok in self._tokens:
                cid  = tok["id"]
                name = tok["name"]
                corp = tok["corp_name"]

                row = SettingRow(name, f"Corp: {corp}")
                is_pending = cid in self._pending_delete

                if self._del_mode:
                    # Mehrfach-Auswahl Modus
                    selected = cid in self._selected
                    chk = QPushButton("☑" if selected else "☐")
                    chk.setFixedSize(28, 28)
                    chk.setStyleSheet(
                        "background: #993C1D; color: white; border-radius: 5px; font-size: 14px;"
                        if selected else
                        "background: #555; color: white; border-radius: 5px; font-size: 14px;")
                    chk.clicked.connect(lambda _, c=cid: self._toggle_select(c))
                    row.add_control(chk)
                elif is_pending:
                    # Einzel-Löschen Bestätigung
                    del_confirm = QPushButton("✕  Löschen")
                    del_confirm.setFixedHeight(26)
                    del_confirm.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; padding: 0 8px;")
                    del_confirm.clicked.connect(lambda _, c=cid: self._do_delete(c))
                    abort_btn = QPushButton("Abbrechen")
                    abort_btn.setFixedHeight(26)
                    abort_btn.setStyleSheet("background: #555; color: white; border-radius: 5px; padding: 0 8px;")
                    abort_btn.clicked.connect(lambda _, c=cid: self._cancel_delete(c))
                    row.add_control(del_confirm)
                    row.add_control(abort_btn)
                else:
                    # Normal — einzelner Löschen Button
                    del_btn = QPushButton("✕")
                    del_btn.setFixedSize(32, 28)
                    del_btn.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; font-weight: 700;")
                    del_btn.clicked.connect(lambda _, c=cid: self._request_delete(c))
                    row.add_control(del_btn)

                self._char_lay.addWidget(row)
                self._char_lay.addWidget(hline())

        # Rendering wieder freigeben — alles auf einmal zeichnen
        self._char_container.setUpdatesEnabled(True)
        self._char_container.show()

    def _on_login_error(self):
        """Login fehlgeschlagen — Button erst nach 2 Sek freigeben damit Server-Thread fertig ist."""
        print(f"[{__import__('time').strftime('%H:%M:%S')}][UI] login_error Signal empfangen", flush=True)
        if hasattr(self, "_countdown_timer") and self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        if self._popup_ref is not None:
            self._popup_ref.set_login_state(0)
        # 2 Sekunden warten damit der alte Server-Thread vollständig beendet ist
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, self._release_login_btn)

    def _release_login_btn(self):
        """Button freigeben."""
        self._add_btn_ref.setEnabled(True)
        self._add_btn_ref.setText("＋  Account hinzufügen  (EVE SSO Login)")

    def _on_login_done(self):
        """Wird im Main Thread aufgerufen wenn Login erfolgreich — thread-sicher."""
        print(f"[{__import__('time').strftime('%H:%M:%S')}][UI] login_done Signal empfangen", flush=True)
        # Countdown Timer stoppen
        if hasattr(self, "_countdown_timer") and self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        # Liste und Popup sofort aktualisieren
        if self._popup_ref is not None:
            self._popup_ref.reload()
        self._refresh_list()
        # 5 Sekunden Cooldown — verhindert CCP Rate-Limiting
        self._add_btn_ref.setText("⏳  5s")
        if self._popup_ref is not None:
            self._popup_ref.set_login_state(5)
        self._cooldown = 5
        from PyQt6.QtCore import QTimer
        self._cooldown_timer = QTimer()
        def _tick():
            self._cooldown -= 1
            if self._cooldown > 0:
                self._add_btn_ref.setText(f"⏳  {self._cooldown}s")
                if self._popup_ref is not None:
                    self._popup_ref.set_login_state(self._cooldown)
            else:
                self._cooldown_timer.stop()
                self._release_login_btn()
        self._cooldown_timer.timeout.connect(_tick)
        self._cooldown_timer.start(1000)

    def _refresh_list(self):
        """Aktualisiert nur die Char-Liste."""
        self._load_tokens()
        self._build()
        self._char_container.show()
        self._char_container.update()

    def _request_delete(self, char_id: str):
        """Zeigt inline Bestätigung an."""
        self._pending_delete.add(char_id)
        self._build()

    def _cancel_delete(self, char_id: str):
        self._pending_delete.discard(char_id)
        self._build()

    def _do_delete(self, char_id: str):
        """Löscht Token aus Datei und Liste."""
        _log.info(f"Charakter {char_id} wird gelöscht")
        from core import esi as esi_mod
        esi_mod.delete_token(char_id)
        self._pending_delete.discard(char_id)
        self._selected.discard(char_id)
        self._load_tokens()
        self._build()
        if self._popup_ref is not None:
            self._popup_ref.reload()

    def _set_active(self, char_id: str):
        pass  # Wird später implementiert



    def _toggle_del_mode(self):
        self._del_mode = not self._del_mode
        self._selected.clear()
        if self._del_mode:
            self._multi_btn.setText("Abbrechen")
            self._multi_btn.setStyleSheet("background: #555; color: white; border-radius: 5px; padding: 0 10px;")
            self._multi_del_btn.hide()
        else:
            self._multi_btn.setText(t("settings.delete_multiple"))
            self._multi_btn.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; padding: 0 10px;")
            self._multi_del_btn.hide()
        self._build()

    def _update_del_btn(self):
        """Löschen-Button zeigen wenn Auswahl vorhanden."""
        if self._del_mode and self._selected:
            self._multi_del_btn.setText(f"✕  {len(self._selected)} löschen")
            self._multi_del_btn.show()
        else:
            self._multi_del_btn.hide()

    def _toggle_select(self, char_id: str):
        if char_id in self._selected:
            self._selected.discard(char_id)
        else:
            self._selected.add(char_id)
        self._update_del_btn()
        self._build()

    def _confirm_multi_delete(self):
        """Direkt löschen — kein Popup, kein Dialog."""
        if not self._selected:
            return
        from core import esi as esi_mod
        for cid in self._selected:
            esi_mod.delete_token(cid)
        self._selected.clear()
        self._del_mode = False
        self._multi_btn.setText(t("settings.delete_multiple"))
        self._multi_btn.setStyleSheet("background: #993C1D; color: white; border-radius: 5px; padding: 0 10px;")
        self._multi_del_btn.hide()
        self._load_tokens()
        self._build()
        if self._popup_ref is not None:
            self._popup_ref.reload()

    def _on_add_account(self):
        """ESI Login starten."""
        from core import esi as esi_mod
        from PyQt6.QtCore import QTimer
        print(f"[{__import__('time').strftime('%H:%M:%S')}][UI] Login-Button geklickt", flush=True)
        # Vorherigen Timer stoppen falls noch einer läuft
        if hasattr(self, "_countdown_timer") and self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        self._add_btn_ref.setEnabled(False)
        self._add_btn_ref.setText("⏳  30s")
        if self._popup_ref is not None:
            self._popup_ref.set_login_state(30)

        self._countdown = 30
        self._countdown_timer = QTimer()
        def _tick():
            self._countdown -= 1
            if self._countdown > 0:
                # Nur Anzeige aktualisieren — Button NICHT freigeben
                self._add_btn_ref.setText(f"⏳  {self._countdown}s")
                if self._popup_ref is not None:
                    self._popup_ref.set_login_state(self._countdown)
            else:
                # Timeout nach 120s — dann doch freigeben
                self._countdown_timer.stop()
                self._release_login_btn()
        self._countdown_timer.timeout.connect(_tick)
        self._countdown_timer.start(1000)

        def _ok(char_info: dict):
            # Signal feuern — Qt überträgt es thread-sicher in den Main Thread
            self.login_done.emit()

        def _err(msg: str):
            # Fehler-Signal — Button erst nach kurzer Pause freigeben
            self.login_error.emit()

        import threading
        threading.Thread(
            target=esi_mod.login,
            kwargs={"on_success": _ok, "on_error": _err},
            daemon=True
        ).start()

    def sync(self):
        """Tokens neu laden und Liste neu aufbauen."""
        self._load_tokens()
        self._build()

    def _force_redraw(self):
        """Qt zwingen die Seite neu zu rendern — auch wenn sie sichtbar ist."""
        self._inner.update()
        self._inner.repaint()
        self._scroll_area.update()
        self._scroll_area.repaint()
        self.update()
        self.repaint()


class PageUpdates(QWidget):
    _update_checked = pyqtSignal(object)  # Thread-sicheres Signal für Update-Check Ergebnis

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings    = settings
        self._remote_ver = None
        self._update_checked.connect(self._on_update_checked)
        inner = QWidget()
        self._lay = QVBoxLayout(inner)
        self._lay.setContentsMargins(32, 24, 32, 24)
        self._lay.setSpacing(0)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._build()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scrolled(inner))

    def _build(self):
        from core.config import APP_VERSION
        from core import updater
        lay = self._lay
        while lay.count():
            w = lay.takeAt(0).widget()
            if w: w.deleteLater()

        lay.addWidget(section(t("settings.updates")))
        lay.addWidget(hline())
        lay.addSpacing(12)

        # ── Versionsinfo ──────────────────────────────────────
        row_cur = SettingRow(t("settings.installed_version"), "")
        ver_lbl = QLabel(APP_VERSION)
        ver_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        ver_lbl.setStyleSheet("background: transparent;")
        row_cur.add_control(ver_lbl)
        lay.addWidget(row_cur)
        lay.addWidget(hline())
        lay.addSpacing(4)

        row_new = SettingRow(t("settings.latest_version"), "")
        self._new_ver_lbl = QLabel("—")
        self._new_ver_lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._new_ver_lbl.setStyleSheet("background: transparent;")
        row_new.add_control(self._new_ver_lbl)

        self._check_btn = QPushButton(t("settings.check_update"))
        self._check_btn.setObjectName("AccentBtn")
        self._check_btn.setFixedWidth(130)
        self._check_btn.clicked.connect(self._do_check)
        row_new.add_control(self._check_btn)

        self._install_now_btn = QPushButton("Jetzt installieren")
        self._install_now_btn.setObjectName("AccentBtn")
        self._install_now_btn.setFixedWidth(150)
        self._install_now_btn.setVisible(False)
        self._install_now_btn.clicked.connect(self._do_install_now)
        row_new.add_control(self._install_now_btn)

        lay.addWidget(row_new)
        lay.addWidget(hline())
        lay.addSpacing(4)

        # Update-Notes
        self._notes_row = SettingRow("Was ist neu", "")
        self._notes_lbl = QLabel("—")
        self._notes_lbl.setObjectName("SettingsSubLabel")
        self._notes_lbl.setWordWrap(True)
        self._notes_row.add_control(self._notes_lbl)
        lay.addWidget(self._notes_row)
        lay.addWidget(hline())
        lay.addSpacing(12)

        # ── Einstellungen ─────────────────────────────────────
        lbl_s = QLabel(t("settings.title"))
        lbl_s.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        lbl_s.setStyleSheet("background: transparent;")
        lay.addWidget(lbl_s)
        lay.addWidget(hline())
        lay.addSpacing(8)

        row_auto = SettingRow(t("settings.check_on_start"),
                              "App sucht beim Start automatisch nach Updates")
        self._auto_btn = ToggleBtn(self.settings.get("update_on_start", True))
        self._auto_btn.clicked.connect(
            lambda: self._save("update_on_start", self._auto_btn.isChecked()))
        row_auto.add_control(self._auto_btn)
        lay.addWidget(row_auto)
        lay.addWidget(hline())
        lay.addSpacing(4)

        row_install = SettingRow(t("settings.auto_install"),
                                 "Gefundene Updates direkt installieren. Nur aktiv wenn 'Beim Start prüfen' an.")
        self._install_btn = ToggleBtn(self.settings.get("update_auto_install", False))
        self._install_btn.setEnabled(self.settings.get("update_on_start", True))
        self._install_btn.clicked.connect(
            lambda: self._save("update_auto_install", self._install_btn.isChecked()))
        row_install.add_control(self._install_btn)
        lay.addWidget(row_install)
        lay.addWidget(hline())
        lay.addSpacing(12)

        # ── Backup / Wiederherstellung ────────────────────────
        lbl_b = QLabel("Backup")
        lbl_b.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        lbl_b.setStyleSheet("background: transparent;")
        lay.addWidget(lbl_b)
        lay.addWidget(hline())
        lay.addSpacing(8)

        backup_ver = updater.get_backup_version()
        has_backup = updater.has_backup()
        backup_sub = f"Backup vorhanden: v{backup_ver}" if has_backup else "Kein Backup vorhanden"
        row_restore = SettingRow(t("settings.restore_title"), backup_sub)

        self._restore_btn = QPushButton(t("settings.restore"))
        self._restore_btn.setObjectName("AccentBtn")
        self._restore_btn.setFixedWidth(160)
        self._restore_btn.setEnabled(has_backup)
        self._restore_btn.clicked.connect(self._do_restore)
        row_restore.add_control(self._restore_btn)
        lay.addWidget(row_restore)
        lay.addStretch()

    def _save(self, key: str, val):
        self.settings[key] = val
        from core import settings as cfg
        cfg.save(self.settings)
        self._install_btn.setEnabled(self.settings.get("update_on_start", True))

    def _do_check(self):
        from core import updater
        self._check_btn.setText("Prüfe...")
        self._check_btn.setEnabled(False)
        self._install_now_btn.setVisible(False)

        def _done(info):
            # Wird aus Hintergrund-Thread aufgerufen — Signal sorgt für
            # sicheren Wechsel zurück in den Qt Main Thread.
            self._update_checked.emit(info)

        updater.check_for_update(_done)

    def _on_update_checked(self, info):
        self._check_btn.setText(t("settings.check_update"))
        self._check_btn.setEnabled(True)
        if info:
            self._remote_ver = info
            self._new_ver_lbl.setText(info["version"])
            self._new_ver_lbl.setStyleSheet(
                "color: #3B6D11; font-weight: 700; background: transparent;")
            self._notes_lbl.setText(info.get("notes", "—"))
            self._install_now_btn.setVisible(True)
        else:
            from core.config import APP_VERSION
            self._new_ver_lbl.setText(f"{APP_VERSION} (aktuell)")
            self._new_ver_lbl.setStyleSheet("background: transparent;")
            self._notes_lbl.setText("Du hast die neueste Version.")
            self._install_now_btn.setVisible(False)

    def _do_install_now(self):
        if not self._remote_ver:
            return
        from PyQt6.QtWidgets import QMessageBox
        from PyQt6.QtCore import QTimer

        version = self._remote_ver["version"]
        confirm = QMessageBox(self)
        confirm.setWindowTitle("Update installieren")
        confirm.setText(f"Update auf v{version} jetzt installieren?")
        confirm.setInformativeText(
            "Die App wird automatisch neu gestartet sobald die Installation abgeschlossen ist.")
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm.setDefaultButton(QMessageBox.StandardButton.No)
        if confirm.exec() != QMessageBox.StandardButton.Yes:
            return

        self._install_now_btn.setEnabled(False)
        self._install_now_btn.setText("Installiere...")
        self._check_btn.setEnabled(False)

        from core import updater
        updater.create_backup()

        def _progress(pct):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._install_now_btn.setText(f"{pct}%"))

        # download_and_install startet die App neu bei Erfolg (kehrt nicht zurück)
        ok, msg = updater.download_and_install(self._remote_ver, progress_callback=_progress)

        if not ok:
            self._install_now_btn.setEnabled(True)
            self._install_now_btn.setText("Jetzt installieren")
            self._check_btn.setEnabled(True)
            err = QMessageBox(self)
            err.setWindowTitle("Update fehlgeschlagen")
            err.setText(msg)
            err.exec()

    def _do_restore(self):
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox(self)
        msg.setWindowTitle("Version wiederherstellen")
        backup_ver = updater.get_backup_version()
        msg.setText(f"Auf Version {backup_ver} zurücksetzen?")
        msg.setInformativeText(
            "Die aktuelle Version wird ersetzt. Die App muss danach neu gestartet werden.")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        if msg.exec() == QMessageBox.StandardButton.Yes:
            ok, msg_text = updater.restore_backup()
            from PyQt6.QtWidgets import QMessageBox as MB
            info = MB(self)
            info.setWindowTitle("Wiederherstellung")
            info.setText(msg_text)
            info.exec()

    def sync(self):
        self._auto_btn.setChecked(self.settings.get("update_on_start", True))
        self._auto_btn.setText("ON" if self._auto_btn.isChecked() else "OFF")
        self._install_btn.setChecked(self.settings.get("update_auto_install", False))
        self._install_btn.setText("ON" if self._install_btn.isChecked() else "OFF")
        self._install_btn.setEnabled(self.settings.get("update_on_start", True))


# ── Haupt-Einstellungsseite ───────────────────────────────────────────────────

class SettingsPage(QWidget):
    faction_changed    = pyqtSignal(str)
    theme_changed      = pyqtSignal(str)
    layout_changed     = pyqtSignal(str)
    dev_mode_changed   = pyqtSignal(bool)
    test_mode_changed  = pyqtSignal(bool)
    edit_mode_changed  = pyqtSignal(bool)
    language_changed   = pyqtSignal(str)
    window_size_changed= pyqtSignal(int, int)
    close_requested    = pyqtSignal()
    accounts_changed   = pyqtSignal()

    CATEGORIES = [
        ("🌐", "Allgemein"),
        ("🔄", "Updates"),
        ("🎨", "Darstellung"),
        ("👤", "Accounts"),
        ("🧩", t("settings.func_info")),
        ("🛠", "Entwickler"),
        ("↺",  t("settings.reset_btn")),
    ]

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._accent  = FACTIONS.get(
            settings.get("faction","caldari"), FACTIONS["caldari"])["accent"]
        self._build()

    def _build(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        sidebar = QWidget()
        sidebar.setObjectName("SettingsSidebar")
        sidebar.setFixedWidth(210)
        sb = QVBoxLayout(sidebar)
        sb.setContentsMargins(0, 0, 0, 0)
        sb.setSpacing(0)

        sb_hdr = QWidget(); sb_hdr.setFixedHeight(56)
        sh = QHBoxLayout(sb_hdr); sh.setContentsMargins(16, 0, 16, 0)
        _hdr = QLabel(t("settings.title"))
        _hdr.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        sh.addWidget(_hdr)
        sb.addWidget(sb_hdr)
        sb.addWidget(hline())

        self._sidebar_items: list[SidebarItem] = []
        for icon, label in self.CATEGORIES:
            item = SidebarItem(icon, label)
            item.set_accent(self._accent)
            item.clicked.connect(lambda l=label: self._switch(l))
            sb.addWidget(item)
            self._sidebar_items.append(item)

        sb.addStretch()
        sb.addWidget(hline())

        close_btn = QPushButton(t("settings.back"))
        close_btn.setObjectName("AccentBtn")
        close_btn.setFixedHeight(36)
        close_btn.clicked.connect(self.close_requested)
        wrap = QWidget()
        wl = QVBoxLayout(wrap); wl.setContentsMargins(12, 8, 12, 12)
        wl.addWidget(close_btn)
        sb.addWidget(wrap)
        root.addWidget(sidebar)

        vline = QFrame()
        vline.setFrameShape(QFrame.Shape.VLine)
        vline.setObjectName("VLine")
        root.addWidget(vline)

        # Stack
        self._stack = QStackedWidget()
        self._pages = {
            "Allgemein":      PageAllgemein(self.settings),
            "Updates":        PageUpdates(self.settings),
            "Darstellung":    PageDarstellung(self.settings),
            "Accounts":       PageAccounts(self.settings),
            t("settings.func_info"): PageFunktionsInfo(self.settings),
            "Entwickler":     PageEntwickler(self.settings),
            t("settings.reset_btn"):   PageZuruecksetzen(self.settings),
        }
        self._pages["Allgemein"].language_changed.connect(self.language_changed)
        self._pages["Allgemein"].window_size_changed.connect(self.window_size_changed)
        self._pages["Darstellung"].faction_changed.connect(self.faction_changed)
        self._pages["Darstellung"].theme_changed.connect(self.theme_changed)
        self._pages["Darstellung"].layout_changed.connect(self.layout_changed)
        self._pages["Darstellung"].edit_mode_changed.connect(self.edit_mode_changed)
        self._pages["Entwickler"].dev_mode_changed.connect(self.dev_mode_changed)
        self._pages["Entwickler"].test_mode_changed.connect(self.test_mode_changed)
        # Accounts-Seite: Signal nicht mehr nötig — direkt über _popup_ref
        self._pages[t("settings.reset_btn")].reset_requested.connect(self._on_reset)

        for page in self._pages.values():
            self._stack.addWidget(page)

        root.addWidget(self._stack, stretch=1)
        self._switch("Allgemein")

    def _on_accounts_changed(self):
        """Accounts-Seite neu aufbauen, dann Popup informieren."""
        from PyQt6.QtCore import QTimer
        def _do():
            page = self._pages.get("Accounts")
            if page:
                page.sync()
            # Erst NACH sync() das Popup informieren
            self.accounts_changed.emit()
        QTimer.singleShot(200, _do)

    def _switch(self, label: str):
        for i, (_, lbl) in enumerate(self.CATEGORIES):
            self._sidebar_items[i].set_active(lbl == label)
        page = self._pages.get(label)
        if page:
            self._stack.setCurrentWidget(page)

    def _on_reset(self, what: str):
        from core import settings as cfg
        if what in ("layout", "all"):
            self.settings["module_order"] = []
        if what in ("settings", "all"):
            from core.settings import DEFAULTS
            self.settings.update({
                "faction":    DEFAULTS["faction"],
                "theme":      DEFAULTS["theme"],
                "language":   DEFAULTS["language"],
                "home_layout":DEFAULTS["home_layout"],
                "dev_mode":   False,
                "test_mode":  False,
                "edit_locked":True,
                "window_width": DEFAULTS["window_width"],
                "window_height":DEFAULTS["window_height"],
            })
            self.faction_changed.emit(DEFAULTS["faction"])
            self.theme_changed.emit(DEFAULTS["theme"])
            self.layout_changed.emit(DEFAULTS["home_layout"])
            self.dev_mode_changed.emit(False)
            self.test_mode_changed.emit(False)
        cfg.save(self.settings)
        self.sync()

    def sync(self):
        for page in self._pages.values():
            page.sync()

    def retranslate(self):
        """Rebuildet alle Seiten nach Sprachwechsel."""
        for page in self._pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()
        # Sidebar-Labels aktualisieren
        for i, (icon, label) in enumerate(self.CATEGORIES):
            if i < len(self._sidebar_items):
                self._sidebar_items[i].label = t(f"settings.{label.lower().replace('-','_').replace('ü','u').replace('ä','a').replace('ö','o')}") if False else label
        self.sync()

    def set_faction(self, faction: str):
        self._accent = FACTIONS.get(faction, FACTIONS["caldari"])["accent"]
        for item in self._sidebar_items:
            item.set_accent(self._accent)