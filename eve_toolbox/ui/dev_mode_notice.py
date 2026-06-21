"""
Dev-Mode-Benachrichtigung — erscheint NUR, wenn EVE_SKIP_CHECKS gesetzt
UND der Dev-Token tatsächlich gültig war (siehe main.py _run_startup).
Reines Sicherheitsnetz für den Entwickler selbst: bestätigt, dass der
Integritätscheck wirklich übersprungen wurde, statt dass das nur im Log
nachlesbar ist. Im normalen Betrieb (kein Dev-Mode) erscheint dieses
Fenster nie.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen


class DevModeNoticeDialog(QDialog):
    """Erfordert einen expliziten Klick auf OK — kein Auto-Close, da
    es als bewusste Bestätigung gedacht ist ('ja, ich weiß, dass der
    Check übersprungen wurde'), nicht als flüchtiger Hinweis."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(380, 180)
        self._center()
        self._build()

    def _center(self):
        # Bevorzugt relativ zum Hauptfenster zentrieren, Fallback auf
        # den Bildschirm nur ohne Parent (siehe DevModeNoticeDialog
        # wird IMMER mit window als Parent aufgerufen, Fallback ist
        # hier nur Sicherheitsnetz).
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

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 20)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("🛠  Dev-Mode aktiv")
        title.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(title)

        body = QLabel(
            "Integritäts- und Update-Check wurden übersprungen "
            "(gültiger Dev-Token erkannt).\n\n"
            "Diese Meldung erscheint nur im Entwickler-Start."
        )
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        lay.addWidget(body)

        ok_btn = QPushButton("OK")
        ok_btn.setFixedHeight(36)
        ok_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ok_btn.setStyleSheet(
            "background: #7B2FBE; color: white; border-radius: 8px; border: none; padding: 0 24px;")
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
        p.setPen(QPen(QColor(180, 80, 30, 160), 1.5))  # warnfarben statt lila
        p.drawPath(path)
        p.end()