"""
Schnell-Einstellungen — öffnet sich unter dem Zahnrad.
Nur Layout bearbeiten + Link zu allen Einstellungen.
"""
from core import logger as _logger
_log = _logger.get("settings_panel")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QFrame, QPushButton)
from PyQt6.QtCore import pyqtSignal
from core.i18n import t


class SettingsPanel(QWidget):
    faction_changed   = pyqtSignal(str)
    dev_mode_changed  = pyqtSignal(bool)
    layout_changed    = pyqtSignal(str)
    theme_changed     = pyqtSignal(str)
    edit_mode_changed = pyqtSignal(bool)
    open_settings     = pyqtSignal()

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setObjectName("SettingsPanel")
        self.setFixedWidth(260)
        # Layout EINMAL erzeugen, nie wieder neu — QWidget.setLayout()
        # (was QVBoxLayout(self) intern aufruft) lehnt ein zweites Layout
        # auf demselben Widget ab. _build() leert/befüllt dieses eine
        # Layout bei jedem Aufruf, statt ein neues zu erzeugen (das war
        # vorher der Bug: nach retranslate() blieb das Panel leer, weil
        # Qt das zweite QVBoxLayout(self) nur mit einer Warnung verwarf).
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(14, 14, 14, 14)
        self._outer_layout.setSpacing(10)
        self._build()
        self.adjustSize()

    def _clear_layout_item(self, item):
        """Entfernt ein Layout-Item rekursiv — sowohl direkte Widgets
        als auch verschachtelte Sub-Layouts (z.B. edit_row/info unten),
        deren enthaltene Widgets sonst beim Leeren übersehen würden."""
        w = item.widget()
        if w:
            w.deleteLater()
            return
        sub_layout = item.layout()
        if sub_layout:
            while sub_layout.count():
                self._clear_layout_item(sub_layout.takeAt(0))

    def _build(self):
        # Bestehenden Inhalt entfernen, falls _build() ein weiteres Mal
        # läuft (z.B. über retranslate() nach Sprachwechsel) — danach
        # wird dasselbe self._outer_layout wiederverwendet und neu befüllt.
        while self._outer_layout.count():
            self._clear_layout_item(self._outer_layout.takeAt(0))

        lay = self._outer_layout

        title = QLabel(t("settings.quick_title"))
        title.setObjectName("PanelTitle")
        title.setStyleSheet("background: transparent;")
        lay.addWidget(title)
        lay.addWidget(self._hline())

        # Bearbeitungsmodus
        edit_row = QHBoxLayout()
        info = QVBoxLayout(); info.setSpacing(1)
        lbl1 = QLabel(t("settings.edit_layout"))
        lbl1.setStyleSheet("background: transparent; font-weight: 600;")
        lbl2 = QLabel(t("settings.edit_layout_desc"))
        lbl2.setStyleSheet("background: transparent; font-size: 11px; color: #888;")
        info.addWidget(lbl1); info.addWidget(lbl2)
        edit_row.addLayout(info)
        edit_row.addStretch()

        self._edit_btn = QPushButton("OFF")
        self._edit_btn.setObjectName("ToggleBtn")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setChecked(not self.settings.get("edit_locked", True))
        self._edit_btn.setText("ON" if self._edit_btn.isChecked() else "OFF")
        self._edit_btn.setFixedSize(52, 24)
        self._edit_btn.clicked.connect(self._on_edit)
        edit_row.addWidget(self._edit_btn)
        lay.addLayout(edit_row)

        lay.addStretch()
        lay.addWidget(self._hline())

        all_btn = QPushButton(t("settings.all_settings"))
        all_btn.setObjectName("AccentBtn")
        all_btn.clicked.connect(self.open_settings)
        lay.addWidget(all_btn)

    def _on_edit(self):
        enabled = self._edit_btn.isChecked()
        self._edit_btn.setText("ON" if enabled else "OFF")
        self.edit_mode_changed.emit(enabled)

    def retranslate(self):
        """Wird bei Sprachwechsel aufgerufen — baut Panel neu (verwendet
        weiterhin dasselbe self._outer_layout, siehe _build())."""
        self._build()
        self.adjustSize()

    def _hline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("HLine")
        return line