"""
Splash Screen — wird beim Start angezeigt während Updates geprüft/installiert werden.
"""
from core import logger as _logger
_log = _logger.get("splash_screen")

from core.i18n import t as _t
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal
from PyQt6.QtGui import (QPainter, QColor, QFont, QPen, QBrush,
                          QPainterPath, QLinearGradient)


class SplashScreen(QWidget):
    finished = pyqtSignal()  # Wird emittiert wenn Splash fertig ist

    def __init__(self, settings: dict):
        super().__init__(None)
        self.settings    = settings
        self._progress   = 0      # 0-100
        self._status     = _t("splash.loading")
        self._phase      = "init" # init | checking | installing | done

        # Fenster-Flags: kein Rahmen, immer vorne
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.SplashScreen
        )
        # WA_TranslucentBackground weggelassen — verursacht Vollbild auf Windows
        self.setFixedSize(520, 300)

        # Zentrieren — resize nach show() nochmal erzwingen
        from PyQt6.QtWidgets import QApplication
        self.resize(520, 300)
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - 520) // 2,
            (screen.height() - 300) // 2
        )

        self.setStyleSheet("background: #0d0d14;")
        # Animations-Timer
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)  # ~60fps
        self._anim_pos = 0.0  # für spätere Animationen

    # ── Öffentliche API ───────────────────────────────────────

    def set_status(self, text: str, progress: int = None):
        self._status = text
        if progress is not None:
            self._progress = max(0, min(100, progress))
        self.update()

    def set_phase(self, phase: str):
        self._phase = phase
        self.update()

    def finish(self):
        self._progress = 100
        self._status   = "Bereit!"
        self.update()
        QTimer.singleShot(600, self._close)

    def _close(self):
        self._anim_timer.stop()
        self.hide()
        self.finished.emit()

    # ── Animation ─────────────────────────────────────────────

    def _tick(self):
        self._anim_pos = (self._anim_pos + 0.8) % 360
        self.update()

    # ── Zeichnen ──────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # ── Hintergrund ───────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)

        # Dunkler Hintergrund
        p.fillPath(path, QColor("#0d0d14"))

        # Lila Gradient oben
        grad = QLinearGradient(0, 0, w, 0)
        grad.setColorAt(0.0, QColor(80, 20, 120, 180))
        grad.setColorAt(0.5, QColor(120, 40, 180, 120))
        grad.setColorAt(1.0, QColor(40, 10, 80,  180))
        top_path = QPainterPath()
        top_path.addRoundedRect(QRectF(0, 0, w, 140), 16, 16)
        p.fillPath(top_path, grad)

        # Rahmen
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(120, 60, 200, 160), 1.5))
        p.drawPath(path)

        # ── Platzhalter-Bild (Lila Box) ───────────────────────
        img_rect = QRectF(30, 20, 140, 100)
        img_path = QPainterPath()
        img_path.addRoundedRect(img_rect, 8, 8)
        img_grad = QLinearGradient(30, 20, 170, 120)
        img_grad.setColorAt(0.0, QColor(100, 30, 160))
        img_grad.setColorAt(1.0, QColor(60,  10, 100))
        p.fillPath(img_path, img_grad)
        p.setPen(QPen(QColor(150, 80, 220), 1.0))
        p.drawPath(img_path)
        # Placeholder Text
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QPen(QColor(180, 130, 230, 150)))
        p.drawText(img_rect, Qt.AlignmentFlag.AlignCenter, "[ Bild ]")

        # ── Titel ─────────────────────────────────────────────
        p.setFont(QFont("Segoe UI", 22, QFont.Weight.Black))
        p.setPen(QPen(QColor("#ffffff")))
        p.drawText(QRectF(190, 25, w - 220, 40),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   "EVE Toolbox")

        # Version
        from core.config import APP_VERSION
        p.setFont(QFont("Segoe UI", 11))
        p.setPen(QPen(QColor(150, 100, 220)))
        p.drawText(QRectF(190, 65, w - 220, 24),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   f"Version {APP_VERSION}  ·  by phantombite")

        # Phase-Badge
        phase_colors = {
            "init":       ("#555",    "#aaa",    _t("splash.phase_init")),
            "integrity":  ("#2a1a4a", "#aa66ff", _t("splash.phase_integrity")),
            "checking":   ("#1a3a6a", "#4a9aff", _t("splash.phase_checking")),
            "installing": ("#3a2a00", "#ffaa00", _t("splash.phase_installing")),
            "done":       ("#0a3a0a", "#44cc44", _t("splash.phase_done")),
        }
        bg, fg, label = phase_colors.get(self._phase, phase_colors["init"])
        badge_rect = QRectF(190, 95, 130, 22)
        badge_path = QPainterPath()
        badge_path.addRoundedRect(badge_rect, 11, 11)
        p.fillPath(badge_path, QColor(bg))
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(QPen(QColor(fg)))
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, label)

        # ── Trennlinie ────────────────────────────────────────
        p.setPen(QPen(QColor(80, 40, 120, 100), 1))
        p.drawLine(20, 145, w - 20, 145)

        # ── Status-Text ───────────────────────────────────────
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QPen(QColor("#cccccc")))
        p.drawText(QRectF(30, 152, w - 60, 24),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._status)

        # ── Ladebalken ────────────────────────────────────────
        bar_x    = 30
        bar_y    = 185
        bar_w    = w - 60
        bar_h    = 28
        bar_rect = QRectF(bar_x, bar_y, bar_w, bar_h)

        # Hintergrund
        bar_bg = QPainterPath()
        bar_bg.addRoundedRect(bar_rect, bar_h/2, bar_h/2)
        p.fillPath(bar_bg, QColor(30, 20, 50))
        p.setPen(QPen(QColor(80, 40, 120, 150), 1))
        p.drawPath(bar_bg)

        # Füllstand
        fill_w = bar_w * self._progress / 100
        if fill_w > bar_h:
            fill_rect = QRectF(bar_x, bar_y, fill_w, bar_h)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, bar_h/2, bar_h/2)

            fill_grad = QLinearGradient(bar_x, 0, bar_x + fill_w, 0)
            fill_grad.setColorAt(0.0, QColor(20,  160, 60))
            fill_grad.setColorAt(0.6, QColor(40,  200, 80))
            fill_grad.setColorAt(1.0, QColor(100, 230, 120))
            p.fillPath(fill_path, fill_grad)

            # Glanz
            gloss = QPainterPath()
            gloss.addRoundedRect(
                QRectF(bar_x + 2, bar_y + 2, fill_w - 4, bar_h/2 - 2),
                (bar_h/2 - 2), (bar_h/2 - 2))
            p.fillPath(gloss, QColor(255, 255, 255, 25))

        # Text im Balken
        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        text_color = QColor("#ffffff") if self._progress > 40 else QColor("#aaaaaa")
        p.setPen(QPen(text_color))
        p.drawText(bar_rect, Qt.AlignmentFlag.AlignCenter, "EVE Toolbox")

        # Prozent rechts
        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QPen(QColor("#888888")))
        p.drawText(QRectF(bar_x, bar_y + bar_h + 4, bar_w, 16),
                   Qt.AlignmentFlag.AlignRight,
                   f"{self._progress}%")

        # ── Credit ────────────────────────────────────────────
        p.setFont(QFont("Segoe UI", 8))
        p.setPen(QPen(QColor(80, 60, 100)))
        p.drawText(QRectF(0, h - 22, w, 16),
                   Qt.AlignmentFlag.AlignCenter,
                   "EVE Online® ist ein eingetragenes Warenzeichen von CCP hf.")

        p.end()