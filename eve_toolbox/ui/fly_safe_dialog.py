"""
Fly-Safe-Abschlussfenster — erscheint beim Beenden der App, analog zum
Update-Popup-Design. Informiert kurz, was mit den Userdaten passiert ist:
entweder verschlüsselt gespeichert, oder vollständig gelöscht.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt, QRectF, QTimer
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen

from core.i18n import t


class FlySafeDialog(QDialog):
    """Kurzes, sich selbst schließendes Abschlussfenster. Blockiert das
    Beenden nicht — reine Information, kein Bestätigungs-Klick nötig."""

    def __init__(self, deleted: bool, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(360, 160)
        self._center()
        self._build(deleted)
        QTimer.singleShot(1800, self.accept)

    def _center(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2)

    def _build(self, deleted: bool):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 24)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if deleted:
            title_text = "🗑  " + t("security.exit_deleted_title")
            body_text  = t("security.exit_deleted_text")
        else:
            title_text = "🔒  " + t("security.exit_encrypted_title")
            body_text  = t("security.exit_encrypted_text")

        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(title)

        body = QLabel(body_text)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        lay.addWidget(body)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(path, QColor("#0d0d1a"))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(100, 50, 180, 120), 1.5))
        p.drawPath(path)
        p.end()