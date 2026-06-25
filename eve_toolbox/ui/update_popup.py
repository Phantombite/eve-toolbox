"""
Update-Popup (Block 3) — erscheint beim Start, wenn ein Update verfügbar
ist. Ersetzt die alte Vorab-Einstellung "Updates automatisch installieren
Ja/Nein": Die Entscheidung wird jedes Mal neu getroffen, nicht einmalig
vorab festgelegt.

Zwei Buttons, bewusst keine dritte Option:
    "Jetzt installieren"      → Download + Installation startet sofort
    "Beim nächsten Neustart"  → Schließt das Popup, lädt NICHTS herunter.
                                 Beim nächsten App-Start wird erneut gefragt.

Kein Pre-Download bei "später" (Teil B der Roadmap): Es gibt keinen
Hintergrund-Download, der auf den nächsten Start wartet — das vermeidet
ein Zeitfenster zwischen Download und Installation, in dem die Datei auf
der Platte liegt, aber noch nicht verwendet wurde.

Mandatory-Rollback (Stable-Version-System) nutzt dasselbe Popup, aber
ohne die "Beim nächsten Neustart"-Option — siehe `mandatory` Parameter.
"""
from core import logger as _logger
_log = _logger.get("update_popup")

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen
from core.i18n import t


class UpdatePopup(QDialog):
    """
    Zeigt Versionsvergleich (aktuell → neu) + Changelog-Notizen.
    Gibt über self.result_choice zurück, was der Nutzer gewählt hat:
        "install_now" | "later" | None (Fenster weggeklickt — wie "later")
    """

    def __init__(self, current_version: str, new_version: str, notes: str,
                 mandatory: bool = False, rollback: bool = False, parent=None):
        super().__init__(parent)
        self.result_choice = None
        self._mandatory = mandatory
        self._rollback = rollback
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(440, 320 if notes else 240)
        self._center()
        self._build(current_version, new_version, notes)

    def _center(self):
        # Läuft aktuell beim Start IMMER mit parent=None (Hauptfenster ist
        # zu diesem Zeitpunkt noch nicht sichtbar) — Bildschirm-Fallback
        # ist hier der Normalfall, nicht nur Sicherheitsnetz. Trotzdem
        # robust für künftige Aufrufe mit sichtbarem Parent gehalten.
        parent = self.parentWidget()
        if parent is not None:
            geo = parent.geometry()
            self.move(
                geo.x() + (geo.width()  - self.width())  // 2,
                geo.y() + (geo.height() - self.height()) // 2)
        else:
            from PyQt6.QtWidgets import QApplication
            screen = QApplication.primaryScreen().geometry()
            self.move(
                (screen.width()  - self.width())  // 2,
                (screen.height() - self.height()) // 2)

    def _build(self, current_version: str, new_version: str, notes: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 20)
        lay.setSpacing(12)

        if self._rollback:
            icon_title = t("update_popup.title_rollback_mandatory") if self._mandatory else t("update_popup.title_rollback")
        else:
            icon_title = t("update_popup.title_update")

        title = QLabel(icon_title)
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(title)

        # Versionsvergleich
        ver_row = QHBoxLayout()
        ver_row.setSpacing(16)
        ver_row.addStretch()

        cur_box = self._version_box(t("update_popup.current_label"), current_version, dim=True)
        ver_row.addWidget(cur_box)

        arrow = QLabel("→")
        arrow.setFont(QFont("Segoe UI", 16))
        arrow.setStyleSheet("color: #888; background: transparent;")
        ver_row.addWidget(arrow)

        new_label = t("update_popup.recommended_label") if self._rollback else t("update_popup.new_label")
        new_box = self._version_box(new_label, new_version, dim=False)
        ver_row.addWidget(new_box)

        ver_row.addStretch()
        lay.addLayout(ver_row)

        if notes:
            notes_lbl = QLabel(notes)
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet(
                "color: #cccccc; font-size: 11px; background: rgba(255,255,255,0.05); "
                "border-radius: 8px; padding: 10px;")
            lay.addWidget(notes_lbl)

        if self._rollback and self._mandatory:
            warn = QLabel(t("update_popup.mandatory_warning"))
            warn.setWordWrap(True)
            warn.setStyleSheet(
                "color: #f0b840; font-size: 10px; background: rgba(240,184,64,0.08); "
                "border: 1px solid rgba(240,184,64,0.3); border-radius: 6px; padding: 8px;")
            lay.addWidget(warn)

        lay.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        # Feste Breite würde bei längeren Übersetzungen (z.B. künftig
        # Französisch/Portugiesisch) den Dialog sprengen oder Text
        # abschneiden. Stattdessen: Mindestbreite (bleibt klickbar bei
        # kurzen Texten) + Elidierung falls der Text trotzdem nicht in
        # die verfügbare Dialogbreite passt (kein Layout-Bruch, voller
        # Text als Tooltip).
        available_btn_width = (self.width() - 60 - 10) // 2  # Ränder + Spacing abziehen, beide Buttons gleich breit

        if not self._mandatory:
            later_btn = QPushButton()
            later_btn.setFixedHeight(40)
            later_btn.setMinimumWidth(110)
            later_btn.setStyleSheet(
                "background: rgba(255,255,255,0.08); color: #ccc; "
                "border-radius: 8px; border: none;")
            self._set_elided_text(later_btn, t("update_popup.later_button"), available_btn_width)
            later_btn.clicked.connect(self._on_later)
            btn_row.addWidget(later_btn)

        if self._rollback:
            install_label = t("update_popup.rollback_now_button")
        else:
            install_label = t("update_popup.install_now_button")
        install_btn = QPushButton()
        install_btn.setFixedHeight(40)
        install_btn.setMinimumWidth(110)
        install_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        if self._mandatory:
            accent = "#c0392b"  # Pflicht-Rollback bleibt bewusst fest Rot
        else:
            from core.config import get_current_faction_colors
            accent, _border = get_current_faction_colors()
        install_btn.setStyleSheet(
            f"background: {accent}; color: white; border-radius: 8px; border: none;")
        self._set_elided_text(install_btn, install_label, available_btn_width)
        install_btn.clicked.connect(self._on_install_now)
        btn_row.addWidget(install_btn)

        lay.addLayout(btn_row)

    def _set_elided_text(self, button: QPushButton, full_text: str, available_width: int) -> None:
        """
        Kürzt den Button-Text mit '…' falls er nicht in available_width
        passt, und setzt den vollen Text als Tooltip — gleiches Pattern
        wie ui/settings_page.py FlexButton, hier lokal gehalten, da
        dieser Dialog bewusst keine Abhängigkeit zu settings_page.py
        haben soll.
        """
        metrics = button.fontMetrics()
        elided = metrics.elidedText(full_text, Qt.TextElideMode.ElideRight, available_width - 20)
        button.setText(elided)
        button.setToolTip(full_text if elided != full_text else "")

    def _version_box(self, label: str, version: str, dim: bool) -> QLabel:
        color = "#888" if dim else "#ffffff"
        box = QLabel(f"{label}\n{version}")
        box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent;")
        return box

    def _on_install_now(self):
        self.result_choice = "install_now"
        self.accept()

    def _on_later(self):
        self.result_choice = "later"
        self.accept()

    def closeEvent(self, event):
        if self._mandatory:
            # Erzwungener Rollback: Schließen ohne Installation nicht
            # erlaubt — Fenster ignoriert den Schließen-Versuch.
            event.ignore()
            return
        if self.result_choice is None:
            self.result_choice = "later"
        super().closeEvent(event)

    def keyPressEvent(self, event):
        # Escape darf bei mandatory=True das Fenster nicht schließen.
        if self._mandatory and event.key() == Qt.Key.Key_Escape:
            return
        super().keyPressEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(path, QColor("#0d0d1a"))
        p.setBrush(Qt.BrushStyle.NoBrush)
        if self._mandatory:
            border_color = QColor(192, 57, 43, 160)  # Pflicht-Rollback bleibt bewusst fest Rot
        else:
            from core.config import get_current_faction_colors
            _accent, border_hex = get_current_faction_colors()
            border_color = QColor(border_hex)
            border_color.setAlpha(160)
        p.setPen(QPen(border_color, 1.5))
        p.drawPath(path)
        p.end()