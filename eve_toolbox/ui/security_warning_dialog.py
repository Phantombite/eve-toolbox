"""
Sicherheits-Warnungsdialog — erscheint bei kritischen, sicherheitsrelevanten
Zuständen, die der Nutzer bewusst sehen und bestätigen muss, statt sie nur
im Log oder kurz im Splash-Screen vorbeiblinken zu lassen:
    - checksums.json Signatur ungültig (manipuliert oder falscher Schlüssel)
    - Update-ZIP Signatur ungültig
Bewusst kein Auto-Close (anders als der Dev-Mode-Hinweis) — ein
Signaturfehler ist potenziell sicherheitsrelevant und sollte nicht
versehentlich übersehen werden.
"""
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QFont, QPainterPath, QPen


class SecurityWarningDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(420, 220)
        self._center()
        self._build(title, message)

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

    def _build(self, title: str, message: str):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 24, 30, 20)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel(f"⚠️  {title}")
        title_lbl.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
        title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_lbl.setStyleSheet("color: white; background: transparent;")
        lay.addWidget(title_lbl)

        body = QLabel(message)
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body.setStyleSheet("color: #cccccc; font-size: 12px; background: transparent;")
        lay.addWidget(body)

        ok_btn = QPushButton("Verstanden")
        ok_btn.setFixedHeight(36)
        ok_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        ok_btn.setStyleSheet(
            "background: #c0392b; color: white; border-radius: 8px; border: none; padding: 0 24px;")
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
        p.setPen(QPen(QColor(192, 57, 43, 180), 2))  # kräftiges Rot — Warnfarbe
        p.drawPath(path)
        p.end()