"""
Fehler-Dialog für core.crash_handler.

Bewusst KEIN QMessageBox (Windows-Standarddialog wirkt fremd neben dem
Rest der App). Design an DevModeNoticeDialog angelehnt: eigenständig,
rahmenlos, Hintergrund fest dunkel — funktioniert unabhängig davon, ob
das App-Stylesheet bereits korrekt gesetzt ist (ein unbehandelter Fehler
kann theoretisch auftreten, BEVOR das Stylesheet steht).

Button und Rahmen nutzen die aktuelle Fraktionsfarbe (core.config.
get_current_faction_colors(), mit sicherem Amarr-Fallback) — passend zur
übrigen App. Die zwei tatsächlich sicherheitskritischen Dialoge
(SecurityWarningDialog, der Pflicht-Rollback-Fall in UpdatePopup) bleiben
bewusst fest Rot, als Ausnahme — dieser hier ist "etwas ist schiefgelaufen,
aber das Programm läuft normal weiter", kein Sicherheitsvorfall.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen


class ErrorNoticeDialog(QDialog):
    """Erfordert einen expliziten Klick auf OK — kein Auto-Close, da der
    Nutzer bewusst zur Kenntnis nehmen soll, dass eine Aktion fehlschlug,
    auch wenn das Programm selbst normal weiterläuft."""

    def __init__(self, exc_type, exc_value, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(420, 230)
        self._border_color = "#EF9F27"  # sicherer Standard, _build() überschreibt ihn sofort
        self._center()
        self._build(exc_type, exc_value)

    def _center(self):
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

    def _build(self, exc_type, exc_value):
        from core.config import get_current_faction_colors
        accent, border = get_current_faction_colors()
        self._border_color = border

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 20)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("⚠  Unerwarteter Fehler")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(title)

        body = QLabel(
            "Diese eine Aktion ist fehlgeschlagen. Das Programm läuft "
            "normal weiter — Details wurden ins Log geschrieben."
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        lay.addWidget(body)

        detail = QLabel(f"{exc_type.__name__}: {exc_value}")
        detail.setWordWrap(True)
        detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        detail.setStyleSheet("color: #e0805a; font-size: 10px; background: transparent;")
        lay.addWidget(detail)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedHeight(36)
        ok_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ok_btn.setStyleSheet(
            f"background: {accent}; color: white; border-radius: 8px; border: none; padding: 0 24px;")
        ok_btn.clicked.connect(self.accept)
        lay.addWidget(ok_btn, alignment=Qt.AlignmentFlag.AlignCenter)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(path, QColor("#0d0d1a"))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(self._border_color), 1.5))  # Fraktionsfarbe statt fest Rot
        p.drawPath(path)
        p.end()