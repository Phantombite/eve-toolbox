"""
Home Screen Design 2 & 3 — Donut in PyQt6/QPainter.
"""
from core import logger as _logger
_log = _logger.get("home_donut")

import math
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint, QMimeData
from PyQt6.QtGui import (QPainter, QPainterPath, QColor, QPen, QBrush,
                          QFont, QPalette, QTransform, QPixmap, QDrag)

from core.config import MODULES, FACTIONS, is_module_active
from core.i18n import t
from core import settings as cfg

ASSETS = (Path(__file__).resolve().parent.parent / "assets" / "icons")

ICON_MAP = {
    "package":   "📦", "chart-bar": "📊", "brain":     "🧠",
    "radar":     "📡", "plant":     "🌿", "hammer":    "🔨",
    "route":     "🗺", "cash":      "💰",
}


class DonutWidget(QWidget):
    module_clicked = pyqtSignal(str)

    def __init__(self, settings: dict, mode: str = "text", parent=None):
        super().__init__(parent)
        self.settings    = settings
        self.mode        = mode
        self._hov        = -1
        self._drag_seg   = -1
        self._edit_mode  = False
        self._faction    = settings.get("faction", "caldari")
        self._dev        = settings.get("dev_mode", False)
        self._logo_cache: dict = {}
        # Custom Drag State
        self._dragging    = False
        self._drag_src    = -1
        self._drag_target = -1
        self._mouse_x     = 0.0
        self._mouse_y     = 0.0

        self.setMouseTracking(True)
        self.setAcceptDrops(False)  # Kein QDrag mehr
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(400, 400)

    # ── Hilfsmethoden ─────────────────────────────────────────
    def _get_logo(self, faction: str):
        if faction not in self._logo_cache:
            path = ASSETS / f"{faction}.png"
            self._logo_cache[faction] = QPixmap(str(path)) if path.exists() else None
        return self._logo_cache[faction]

    def _ordered_modules(self):
        from ui.home_grid import get_ordered_modules
        return get_ordered_modules(self.settings)

    def _dims(self):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        r_out = min(w, h) / 2 - 8
        r_in  = r_out * 0.52
        return cx, cy, r_out, r_in

    def _seg_path(self, cx, cy, ro, r_in, i, n, gap):
        slice_deg = 360.0 / n
        a_start = i * slice_deg + gap / 2
        a_end   = (i + 1) * slice_deg - gap / 2
        steps   = 32
        pts_o, pts_i = [], []
        for s in range(steps + 1):
            a = math.radians(a_start + (a_end - a_start) * s / steps)
            pts_o.append(QPointF(cx + ro   * math.sin(a), cy - ro   * math.cos(a)))
            pts_i.append(QPointF(cx + r_in * math.sin(a), cy - r_in * math.cos(a)))
        path = QPainterPath()
        path.moveTo(pts_o[0])
        for pt in pts_o[1:]: path.lineTo(pt)
        for pt in reversed(pts_i): path.lineTo(pt)
        path.closeSubpath()
        return path

    def _seg_center(self, cx, cy, ro, r_in, i, n, gap):
        slice_deg = 360.0 / n
        a = math.radians((i + 0.5) * slice_deg)
        lr = (ro + r_in) / 2
        return cx + lr * math.sin(a), cy - lr * math.cos(a)

    def _seg_at(self, mx, my):
        cx, cy, r_out, r_in = self._dims()
        dx, dy = mx - cx, my - cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < r_in or dist > r_out + 10:
            return -1
        angle = (90 - math.degrees(math.atan2(-dy, dx))) % 360
        n = len(self._ordered_modules())
        slice_deg = 360.0 / n
        idx = int(angle / slice_deg)
        within = angle % slice_deg
        if within < 0.75 or within > slice_deg - 0.75:
            return -1
        return min(idx, n - 1)

    # ── Zeichnen ──────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy, r_out, r_in = self._dims()
        gap  = 1.5
        mods = self._ordered_modules()
        n    = len(mods)
        f    = FACTIONS.get(self._faction, FACTIONS["caldari"])
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        accent = QColor(f["accent"])

        for i, mod in enumerate(mods):
            ready     = is_module_active(mod, dev_mode=self._dev,
                            test_mode=self.settings.get("test_mode",False))
            hov       = self._hov == i and ready  # kein Hover bei gesperrten
            drag_over = self._drag_seg == i
            ro        = r_out + (7 if hov and not self._edit_mode else 0)
            path      = self._seg_path(cx, cy, ro, r_in, i, n, gap)

            # Farben bestimmen
            if self._edit_mode:
                fill   = QColor(accent.red(), accent.green(), accent.blue(),
                                110 if drag_over else 40)
                bpen   = QPen(accent, 2.5 if drag_over else 2.0,
                              Qt.PenStyle.SolidLine if drag_over
                              else Qt.PenStyle.DashLine)
                if not drag_over:
                    bpen.setDashPattern([4, 3])
            elif ready:
                if hov:
                    fill = accent
                    bpen = QPen(accent, 2.0)
                else:
                    if dark:
                        fill = QColor("#2a2a2a")
                    else:
                        # Hell: weißer Grund + Fraktionsfarbe 12% Deckkraft
                        fill = QColor(accent.red(), accent.green(), accent.blue(), 30)
                    bpen = QPen(accent, 1.2)
            else:
                fill = QColor(120, 120, 120, 18)
                bpen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 60), 0.8)

            p.setBrush(QBrush(fill))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(bpen)
            p.drawPath(path)

            lx, ly = self._seg_center(cx, cy, ro, r_in, i, n, gap)

            # Icon-Farbe
            if self._edit_mode:
                icon_col = text_col = accent
            elif not ready:
                icon_col = text_col = QColor(150, 150, 150, 100)
            elif hov:
                icon_col = text_col = QColor("#ffffff")
            else:
                icon_col = text_col = accent

            # Icon
            p.setPen(QPen(icon_col))
            p.setFont(QFont("Segoe UI Emoji", 17 if self.mode == "text" else 19))
            icon_y = ly - (10 if self.mode == "text" else 0)
            p.drawText(QRectF(lx-30, icon_y-16, 60, 32),
                       Qt.AlignmentFlag.AlignCenter,
                       ICON_MAP.get(mod["icon"], "●"))

            # Edit: 6-Punkte Handle
            if self._edit_mode:
                p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 180)))
                p.setFont(QFont("Segoe UI", 11))
                p.drawText(QRectF(lx-8, ly - r_in*0.18, 16, 14),
                           Qt.AlignmentFlag.AlignCenter, "⠿")

            # Name (Design 2)
            if self.mode == "text":
                p.setPen(QPen(text_col))
                p.setFont(QFont("Segoe UI", 9, QFont.Weight.Medium))
                name = mod["name"]
                if "(" in name:
                    parts = name.split(" (")
                    p.drawText(QRectF(lx-34, ly+4, 68, 14),
                               Qt.AlignmentFlag.AlignCenter, parts[0])
                    p.drawText(QRectF(lx-34, ly+17, 68, 14),
                               Qt.AlignmentFlag.AlignCenter, "("+parts[1])
                else:
                    p.drawText(QRectF(lx-34, ly+4, 68, 14),
                               Qt.AlignmentFlag.AlignCenter, name)
                if not ready and not self._edit_mode:
                    p.setFont(QFont("Segoe UI Emoji", 9))
                    p.setPen(QPen(QColor(150, 150, 150, 140)))
                    p.drawText(QRectF(lx-16, ly+20, 32, 16),
                               Qt.AlignmentFlag.AlignCenter, "🔒")

        # Schwebendes Segment beim Drag
        if self._dragging and self._drag_src >= 0:
            # Winkel der Maus relativ zur Donut-Mitte
            dx = self._mouse_x - cx
            dy = self._mouse_y - cy
            mouse_angle = (90 - math.degrees(math.atan2(-dy, dx))) % 360
            # Auf nächstes Segment einrasten
            target = int(mouse_angle / (360.0 / n)) % n
            if target != self._drag_src:
                self._drag_target = target
            else:
                self._drag_target = -1

            # Schwebendes Segment an Maus-Winkel zeichnen
            ghost_path = self._seg_path(cx, cy, r_out + 12, r_in, target, n, gap)
            src_mod = mods[self._drag_src]
            ghost_fill = QColor(accent.red(), accent.green(), accent.blue(), 130)
            p.setBrush(QBrush(ghost_fill))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(ghost_path)
            p.setBrush(Qt.BrushStyle.NoBrush)
            gpen = QPen(accent, 2.5, Qt.PenStyle.DashLine)
            gpen.setDashPattern([4, 3])
            p.setPen(gpen)
            p.drawPath(ghost_path)
            # Icon im schwebenden Segment
            glx, gly = self._seg_center(cx, cy, r_out + 12, r_in, target, n, gap)
            p.setPen(QPen(QColor("#ffffff")))
            p.setFont(QFont("Segoe UI Emoji", 17))
            p.drawText(QRectF(glx-30, gly-16, 60, 32),
                       Qt.AlignmentFlag.AlignCenter,
                       ICON_MAP.get(src_mod["icon"], "●"))

            # Ziel-Segment hervorheben
            if self._drag_target >= 0:
                tgt_path = self._seg_path(cx, cy, r_out, r_in,
                                          self._drag_target, n, gap)
                tgt_fill = QColor(accent.red(), accent.green(), accent.blue(), 60)
                p.setBrush(QBrush(tgt_fill))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(tgt_path)

        # Mittelloch
        bg = self.palette().color(QPalette.ColorRole.Window)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(accent, 1.5))
        p.drawEllipse(QPointF(cx, cy), r_in - 1, r_in - 1)

        # Mitte-Inhalt
        p.setOpacity(1.0)
        # Logo immer zeichnen
        logo = self._get_logo(self._faction)
        if logo and not logo.isNull():
            logo_size = int(r_in * 1.35)
            scaled = logo.scaled(logo_size, logo_size,
                                 Qt.AspectRatioMode.KeepAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            # Hover: Logo 70% transparent damit Name lesbar
            if self.mode == "icon" and self._hov >= 0:
                p.setOpacity(0.20)
            else:
                p.setOpacity(1.0)
            p.drawPixmap(int(cx - scaled.width()/2),
                         int(cy - scaled.height()/2), scaled)
            p.setOpacity(1.0)

        if self.mode == "icon" and self._hov >= 0:
            mods2 = self._ordered_modules()
            if self._hov < len(mods2):
                hm = mods2[self._hov]
                hr = is_module_active(hm,
                         dev_mode=self._dev,
                         test_mode=self.settings.get("test_mode", False))
                if hr:
                    # Aktiv: Name anzeigen
                    if dark:
                        p.setPen(QPen(QColor(0, 0, 0, 120)))
                        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
                        p.drawText(QRectF(cx - r_in + 10, cy - 14, (r_in - 8)*2, 32),
                                   Qt.AlignmentFlag.AlignCenter, hm["name"])
                    p.setPen(QPen(accent))
                    p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
                    p.drawText(QRectF(cx - r_in + 8, cy - 16, (r_in - 8)*2, 32),
                               Qt.AlignmentFlag.AlignCenter, hm["name"])
                else:
                    # Gesperrt: t("home.not_available")
                    if dark:
                        p.setPen(QPen(QColor(0, 0, 0, 100)))
                        p.setFont(QFont("Segoe UI", 14, QFont.Weight.Black))
                        p.drawText(QRectF(cx - r_in + 10, cy - 12, (r_in - 8)*2, 28),
                                   Qt.AlignmentFlag.AlignCenter, t("home.not_available"))
                    p.setPen(QPen(QColor("#888888")))
                    p.setFont(QFont("Segoe UI", 14, QFont.Weight.Black))
                    p.drawText(QRectF(cx - r_in + 8, cy - 14, (r_in - 8)*2, 28),
                               Qt.AlignmentFlag.AlignCenter, t("home.not_available"))


        p.end()

    # ── Maus & Drag ───────────────────────────────────────────
    def mouseMoveEvent(self, event):
        self._mouse_x = event.position().x()
        self._mouse_y = event.position().y()

        if self._dragging:
            self.update()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if (self._edit_mode and
                event.buttons() & Qt.MouseButton.LeftButton and
                hasattr(self, '_drag_start_pos') and
                self._drag_start_pos is not None):
            if (event.position().toPoint() - self._drag_start_pos).manhattanLength() > 8:
                # Custom Drag starten
                self._dragging   = True
                self._drag_src   = getattr(self, '_drag_start_seg', -1)
                self._drag_target= -1
                self._hov        = -1
                self.update()
            return

        seg = self._seg_at(event.position().x(), event.position().y())
        if seg != self._hov:
            self._hov = seg
            self.update()
        if self._edit_mode:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif seg >= 0:
            mods = self._ordered_modules()
            ready = seg < len(mods) and is_module_active(
                mods[seg],
                dev_mode  = self._dev,
                test_mode = self.settings.get("test_mode", False),
            )
            self.setCursor(Qt.CursorShape.PointingHandCursor if ready
                           else Qt.CursorShape.ForbiddenCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self._drag_target >= 0 and self._drag_src >= 0:
                mods = self._ordered_modules()
                if self._drag_src < len(mods) and self._drag_target < len(mods):
                    src_id = mods[self._drag_src]["id"]
                    dst_id = mods[self._drag_target]["id"]
                    if src_id != dst_id:
                        donut = self.parent()
                        while donut and not isinstance(donut, HomeDonut):
                            donut = donut.parent()
                        if donut:
                            donut.swap_modules(src_id, dst_id)
            self._drag_src    = -1
            self._drag_target = -1
            self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            seg = self._seg_at(event.position().x(), event.position().y())
            if seg < 0: return
            mods = self._ordered_modules()
            if seg >= len(mods): return
            mod = mods[seg]
            if self._edit_mode:
                self._drag_start_seg = seg
                self._drag_start_pos = event.position().toPoint()
            elif is_module_active(mod, dev_mode=self._dev,
                    test_mode=self.settings.get("test_mode",False)):
                self.module_clicked.emit(mod["id"])


    def leaveEvent(self, event):
        self._hov = -1
        self.update()



    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        self.setCursor(Qt.CursorShape.OpenHandCursor if enabled
                       else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_faction(self, faction: str):
        self._faction = faction
        self.update()

    def set_dev_mode(self, enabled: bool):
        self._dev = enabled
        self.update()

    def set_test_mode(self, enabled: bool):
        self.settings["test_mode"] = enabled
        self.update()


class HomeDonut(QWidget):
    module_opened = pyqtSignal(str)

    def __init__(self, settings: dict, mode: str = "text", parent=None):
        super().__init__(parent)
        self.settings = settings
        self.mode     = mode
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_cards = []
        for label, val in [
            (t("home.accounts"),     "2"),
            (t("home.industry_jobs"),"—"),
            (t("home.intel_alerts"), "0"),
            (t("home.pi_colonies"),  "—"),
        ]:
            from ui.home_grid import StatCard
            sc = StatCard(label, val, self.settings.get("faction","caldari"))
            stats_row.addWidget(sc)
            self._stat_cards.append(sc)
        lay.addLayout(stats_row)

        self._edit_banner = QLabel("✏  Bearbeitungsmodus — Segmente per Drag & Drop verschieben")
        self._edit_banner.hide()
        lay.addWidget(self._edit_banner)

        self._donut = DonutWidget(self.settings, self.mode, self)
        self._donut.module_clicked.connect(self.module_opened)
        lay.addWidget(self._donut, stretch=1)

    def retranslate(self):
        for i, key in enumerate([
            "home.accounts", "home.industry_jobs",
            "home.intel_alerts", "home.pi_colonies"
        ]):
            if i < len(self._stat_cards):
                self._stat_cards[i]._label = t(key)
                self._stat_cards[i].update()
        self._donut.update()

    def set_faction(self, faction: str):
        self.settings["faction"] = faction
        for sc in getattr(self, "_stat_cards", []):
            sc.set_faction(faction)
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        self._edit_banner.setStyleSheet(
            f"background: rgba({QColor(f['accent']).red()},"
            f"{QColor(f['accent']).green()},"
            f"{QColor(f['accent']).blue()},30); "
            f"border: 1px solid {f['accent']}; border-radius: 6px; "
            f"padding: 5px 10px; font-size: 11px; color: {f['accent']};"
        )
        self._donut.set_faction(faction)

    def set_dev_mode(self, enabled: bool):
        self.settings["dev_mode"] = enabled
        self._donut.set_dev_mode(enabled)

    def set_test_mode(self, enabled: bool):
        self.settings["test_mode"] = enabled
        self._donut.set_test_mode(enabled)

    def set_edit_mode(self, enabled: bool):
        self._edit_banner.setVisible(enabled)
        self._donut.set_edit_mode(enabled)

    def swap_modules(self, src_id: str, dst_id: str):
        from ui.home_grid import get_ordered_modules
        order = [m["id"] for m in get_ordered_modules(self.settings)]
        if src_id not in order or dst_id not in order:
            return
        si, di = order.index(src_id), order.index(dst_id)
        order[si], order[di] = order[di], order[si]
        self.settings["module_order"] = order
        cfg.save(self.settings)
        self._donut.update()