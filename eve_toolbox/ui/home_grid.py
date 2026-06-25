"""
Home Screen Design 1 — Grid mit Drag & Drop Reihenfolge.
"""
from core import logger as _logger
_log = _logger.get("home_grid")

import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QGridLayout, QLabel, QSizePolicy, QApplication)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QRectF, QPoint, QMimeData, QByteArray
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPainterPath, QPalette, QDrag, QPixmap)

from core.config import MODULES, FACTIONS, DEFAULT_ORDER, is_module_active
from core.i18n import t
from core import settings as cfg

ICON_MAP = {
    "package":   "📦", "chart-bar": "📊", "brain":     "🧠",
    "radar":     "📡", "plant":     "🌿", "hammer":    "🔨",
    "route":     "🗺", "cash":      "💰",
}


def get_ordered_modules(settings: dict) -> list:
    """Gibt Module in gespeicherter Reihenfolge zurück."""
    order = settings.get("module_order", [])
    if not order:
        return list(MODULES)
    mod_map = {m["id"]: m for m in MODULES}
    ordered = [mod_map[mid] for mid in order if mid in mod_map]
    # Neue Module die noch nicht in order sind ans Ende
    known = set(order)
    for m in MODULES:
        if m["id"] not in known:
            ordered.append(m)
    return ordered


class ModuleCard(QWidget):
    clicked     = pyqtSignal(str)
    drag_started= pyqtSignal(str)

    def __init__(self, mod: dict, settings: dict, parent=None):
        super().__init__(parent)
        self.mod        = mod
        self.settings   = settings
        self._hov       = False
        self._drag_over = False
        self._edit_mode = False
        self.setMouseTracking(True)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._update_cursor()

    def _is_active(self):
        return is_module_active(
            self.mod,
            dev_mode  = self.settings.get("dev_mode", False),
            test_mode = self.settings.get("test_mode", False),
        )

    def _f(self):
        return FACTIONS.get(self.settings.get("faction", "caldari"), FACTIONS["caldari"])

    def _update_cursor(self):
        if self._edit_mode:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._is_active():
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        self._update_cursor()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h   = self.width(), self.height()
        f      = self._f()
        active = self._is_active()
        dark   = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        accent = QColor(f["accent"])
        light  = QColor(f["light"])

        # Hintergrund
        if self._drag_over:
            bg, border, border_w = light, accent, 2.5
        elif active and self._hov and not self._edit_mode:
            bg, border, border_w = accent, accent, 2.0
        elif active:
            bg = QColor("#ffffff") if not dark else QColor("#2a2a2a")
            border, border_w = accent, 1.2
        else:
            bg = QColor(245, 245, 245, 80) if not dark else QColor(40, 40, 40, 80)
            border = QColor(accent.red(), accent.green(), accent.blue(), 80)
            border_w = 1.0

        # Edit-Modus: transparente Akzentfarbe + gestrichelter Rahmen
        if self._edit_mode:
            bg = QColor(accent.red(), accent.green(), accent.blue(), 40)
            border = accent
            border_w = 1.5

        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w-1, h-1), 10, 10)
        p.fillPath(path, QBrush(bg))

        if self._edit_mode:
            pen = QPen(accent, border_w, Qt.PenStyle.DashLine)
        else:
            pen = QPen(border, border_w)
        p.setPen(pen)
        p.drawPath(path)

        if not active and not self._edit_mode:
            p.setOpacity(0.45)

        # Farben
        if not active:
            icon_color = name_color = QColor("#bbb")
            desc_color = QColor("#ccc")
        elif self._hov and not self._edit_mode:
            icon_color = accent
            name_color = QColor("#1a1a1a") if not dark else QColor("#e8e8e8")
            desc_color = QColor("#999") if not dark else QColor("#666")
        else:
            icon_color = accent
            name_color = QColor("#1a1a1a") if not dark else QColor("#e8e8e8")
            desc_color = QColor("#999") if not dark else QColor("#666")

        # Edit-Modus Indikator
        if self._edit_mode:
            p.setOpacity(1.0)
            p.setPen(QPen(accent))
            p.setFont(QFont("Segoe UI", 14))
            p.drawText(QRect(w-28, 8, 20, 20),
                       Qt.AlignmentFlag.AlignCenter, "⠿")

        # Icon
        p.setOpacity(1.0 if active else 0.45)
        p.setPen(QPen(icon_color))
        p.setFont(QFont("Segoe UI Emoji", 20))
        p.drawText(QRect(14, 12, w-28, 30),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   ICON_MAP.get(self.mod["icon"], "●"))

        p.setPen(QPen(name_color))
        p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        p.drawText(QRect(14, 46, w-28, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.mod["name"])

        p.setPen(QPen(desc_color))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRect(14, 66, w-28, h-76),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop |
                   Qt.TextFlag.TextWordWrap, self.mod["desc"])

        if not active and not self._edit_mode:
            p.setOpacity(0.45)
            p.setFont(QFont("Segoe UI Emoji", 11))
            p.setPen(QPen(QColor("#bbb")))
            p.drawText(QRect(w-28, 10, 18, 18),
                       Qt.AlignmentFlag.AlignCenter, "🔒")

        if active and self._hov and not self._edit_mode:
            p.setOpacity(1.0)
            p.setPen(QPen(QColor("#ffffff"), 1.5))
            p.setFont(QFont("Segoe UI", 11))
            p.drawText(QRect(w-24, 10, 14, 14),
                       Qt.AlignmentFlag.AlignCenter, "→")
        p.end()

    def enterEvent(self, event):
        super().enterEvent(event)
        if self._is_active() and not self._edit_mode:
            self._hov = True
            self.repaint()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hov = False
        self.repaint()

    def mouseMoveEvent(self, event):
        # Sicherheits-Fallback falls enterEvent nicht feuert
        if self._is_active() and not self._edit_mode and not self._hov:
            self._hov = True
            self.repaint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._edit_mode:
                grid = self.parent()
                while grid and not isinstance(grid, HomeGrid):
                    grid = grid.parent()
                if grid:
                    # Globale Position → HomeGrid-Koordinaten
                    global_pos = self.mapToGlobal(event.position().toPoint())
                    grid_pos   = grid.mapFromGlobal(global_pos)
                    grid.start_card_drag(self.mod["id"], grid_pos)
            elif self._is_active():
                self.clicked.emit(self.mod["id"])

    def set_faction(self, faction: str):
        self.settings["faction"] = faction
        self.update()

    def set_dev_mode(self, enabled: bool):
        self.settings["dev_mode"] = enabled
        self._update_cursor()
        self.update()


class StatCard(QWidget):
    def __init__(self, label: str, value: str = "—", faction: str = "caldari"):
        super().__init__()
        self._label   = label
        self._value   = value
        self._faction = faction
        self.setMinimumHeight(62)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_value(self, v: str):
        self._value = v
        self.update()

    def set_faction(self, faction: str):
        self._faction = faction
        self.update()

    def paintEvent(self, event):
        from core.config import FACTIONS
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        f = FACTIONS.get(getattr(self, "_faction", "caldari"), FACTIONS["caldari"])
        accent = QColor(f["accent"])
        if dark:
            bg = QColor("#242424")
        else:
            # Heller Modus: Fraktionsfarbe mit 12% Deckkraft
            bg = QColor(accent.red(), accent.green(), accent.blue(), 30)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 8, 8)
        # Weißer Basisgrund
        if not dark:
            p.fillPath(path, QBrush(QColor("#ffffff")))
        p.fillPath(path, QBrush(bg))
        # Akzent-Linie links
        p.fillRect(QRect(0, 0, 3, h), QBrush(accent))
        p.setFont(QFont("Segoe UI", 10))
        p.setPen(QPen(QColor(f["border"])))
        p.drawText(QRect(14, 9, w-18, 16), Qt.AlignmentFlag.AlignLeft, self._label)
        text_col = QColor("#1a1a1a") if not dark else QColor("#e8e8e8")
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        p.setPen(QPen(accent))
        p.drawText(QRect(14, 28, w-18, 26), Qt.AlignmentFlag.AlignLeft, self._value)
        p.end()


class DragOverlay(QWidget):
    """Transparentes Widget das immer oben ist und die Drag-Vorschau zeichnet."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._pixmap   = None
        self._pos      = QPoint(0, 0)
        self._hotspot  = QPoint(0, 0)
        self.hide()

    def show_drag(self, pixmap, pos, hotspot):
        self._pixmap  = pixmap
        self._pos     = pos
        self._hotspot = hotspot
        self.show()
        self.raise_()
        self.update()

    def move_drag(self, pos):
        self._pos = pos
        self.update()

    def hide_drag(self):
        self._pixmap = None
        self.hide()

    def paintEvent(self, event):
        if not self._pixmap:
            return
        p = QPainter(self)
        p.setOpacity(0.88)
        # Mitte der Pixmap liegt unter der Maus
        x = self._pos.x() - self._pixmap.width() // 2
        y = self._pos.y() - self._pixmap.height() // 2
        p.drawPixmap(x, y, self._pixmap)
        p.end()


class HomeGrid(QWidget):
    module_opened  = pyqtSignal(str)
    order_changed  = pyqtSignal(list)  # neue Reihenfolge als ID-Liste

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings   = settings
        self._cards:    list[ModuleCard] = []
        self._edit_mode  = False
        self._dragging    = False
        self._drag_src_id  = None
        self._drag_over_id = None
        self._drag_pixmap  = None
        self._mouse_pos    = QPoint(0, 0)
        self._drag_hotspot = QPoint(0, 0)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # Begrüßung
        self._welcome = QLabel("Willkommen, Pilot")
        self._welcome.setFont(QFont("Segoe UI", 17, QFont.Weight.DemiBold))
        self._sub = QLabel("Verbinde einen Account um zu starten.")
        self._sub.setFont(QFont("Segoe UI", 11))
        lay.addWidget(self._welcome)
        lay.addWidget(self._sub)

        # Stats
        stats_row = QHBoxLayout()
        stats_row.setSpacing(8)
        self._stat_cards = []
        for label, val in [
            (t("home.accounts"),     "2"),
            (t("home.industry_jobs"),"—"),
            (t("home.intel_alerts"), "0"),
            (t("home.pi_colonies"),  "—"),
        ]:
            sc = StatCard(label, val, self.settings.get("faction","caldari"))
            stats_row.addWidget(sc)
            self._stat_cards.append(sc)
        lay.addLayout(stats_row)

        # Edit-Banner
        self._edit_banner = QLabel("✏  Bearbeitungsmodus — Module per Drag & Drop verschieben")
        self._edit_banner.hide()
        lay.addWidget(self._edit_banner)
        self._update_banner_style()

        # Grid
        self._grid_layout = QGridLayout()
        self._grid_layout.setSpacing(8)
        self._grid_widget = QWidget()
        self._grid_widget.setLayout(self._grid_layout)
        lay.addWidget(self._grid_widget)
        lay.addStretch()

        self._rebuild_grid()

        # Overlay für Drag-Vorschau
        self._overlay = DragOverlay(self)
        self._overlay.resize(self.size())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_overlay'):
            self._overlay.resize(self.size())

    def _rebuild_grid(self):
        # Alte Karten entfernen
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.setParent(None)
        self._cards.clear()

        # Module in gespeicherter Reihenfolge
        ordered = get_ordered_modules(self.settings)
        for i, mod in enumerate(ordered):
            card = ModuleCard(mod, self.settings, self)
            card.clicked.connect(self.module_opened)
            card.set_edit_mode(self._edit_mode)
            card.setMinimumHeight(100)
            self._grid_layout.addWidget(card, i // 4, i % 4)
            self._cards.append(card)

    def swap_modules(self, src_id: str, dst_id: str):
        """Tauscht zwei Module und speichert neue Reihenfolge."""
        order = [c.mod["id"] for c in self._cards]
        if src_id not in order or dst_id not in order:
            return
        si, di = order.index(src_id), order.index(dst_id)
        order[si], order[di] = order[di], order[si]
        self.settings["module_order"] = order
        cfg.save(self.settings)
        self.order_changed.emit(order)
        self._rebuild_grid()
        # Edit-Modus nach Rebuild wiederherstellen
        for card in self._cards:
            card.set_edit_mode(self._edit_mode)

    def start_card_drag(self, mod_id: str, pos: QPoint):
        """Startet custom Drag — wie Donut aber eckig."""
        self._dragging     = True
        self._drag_src_id  = mod_id
        self._drag_over_id = None
        # pos kommt von der Karte (mapToParent) — in HomeGrid-Koordinaten
        self._mouse_pos    = pos
        # Quell-Karte finden und Pixmap rendern
        for card in self._cards:
            if card.mod["id"] == mod_id:
                self._src_card = card
                # Pixmap der Karte im Edit-Stil rendern
                pm = QPixmap(card.size())
                pm.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pm)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                w, h = card.width(), card.height()
                f = FACTIONS.get(self.settings.get("faction","caldari"), FACTIONS["caldari"])
                accent = QColor(f["accent"])
                path = QPainterPath()
                path.addRoundedRect(QRectF(0.5, 0.5, w-1, h-1), 10, 10)
                bg = QColor(accent.red(), accent.green(), accent.blue(), 40)
                painter.fillPath(path, QBrush(bg))
                pen = QPen(accent, 1.5, Qt.PenStyle.DashLine)
                pen.setDashPattern([4, 3])
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.setPen(pen)
                painter.drawPath(path)
                # Icon
                painter.setPen(QPen(accent))
                painter.setFont(QFont("Segoe UI Emoji", 20))
                painter.drawText(QRect(14, 12, w-28, 30),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 ICON_MAP.get(card.mod["icon"], "●"))
                painter.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
                painter.drawText(QRect(14, 46, w-28, 20),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                                 card.mod["name"])
                painter.end()
                self._drag_pixmap  = pm
                self._drag_hotspot = QPoint(pm.width()//2, pm.height()//2)
                break
        self.grabMouse()
        self.setMouseTracking(True)
        if hasattr(self, '_overlay'):
            # pos ist bereits in HomeGrid-Koordinaten
            # Hotspot = Mitte der Karte
            self._overlay.show_drag(self._drag_pixmap, pos, self._drag_hotspot)

    def _card_at_pos(self, pos: QPoint):
        """Karte unter globaler Mausposition finden."""
        global_pos = self.mapToGlobal(pos)
        for card in self._cards:
            card_global = card.mapToGlobal(QPoint(0, 0))
            rect = QRect(card_global, card.size())
            if rect.contains(global_pos):
                return card
        return None

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        # Globale Position → in Overlay-Koordinaten umrechnen (Overlay ist Kind von self)
        global_pos = self.mapToGlobal(event.position().toPoint())
        self._mouse_pos = self.mapFromGlobal(global_pos)
        if hasattr(self, '_overlay') and self._drag_pixmap:
            self._overlay.move_drag(self._mouse_pos)
        card = self._card_at_pos(self._mouse_pos)
        new_over = card.mod["id"] if card else None

        if new_over != self._drag_over_id:
            for c in self._cards:
                if c._drag_over:
                    c._drag_over = False
                    c.repaint()
            if card and card.mod["id"] != self._drag_src_id:
                card._drag_over = True
                card.repaint()
            self._drag_over_id = new_over

    def mouseReleaseEvent(self, event):
        if not self._dragging:
            return
        self.releaseMouse()
        self._dragging = False
        if self._drag_over_id and self._drag_over_id != self._drag_src_id:
            self.swap_modules(self._drag_src_id, self._drag_over_id)
        for c in self._cards:
            c._drag_over = False
            c.repaint()
        self._drag_src_id  = None
        self._drag_over_id = None
        if hasattr(self, '_overlay'):
            self._overlay.hide_drag()
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        dark = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        p.fillRect(self.rect(), QColor("#f5f5f5") if not dark else QColor("#1a1a1a"))
        p.end()

    def set_edit_mode(self, enabled: bool):
        self._edit_mode = enabled
        self._edit_banner.setVisible(enabled)
        for card in self._cards:
            card.set_edit_mode(enabled)

    def _update_banner_style(self):
        from core.config import FACTIONS
        from PyQt6.QtGui import QColor
        f = FACTIONS.get(self.settings.get("faction","caldari"), FACTIONS["caldari"])
        acc = QColor(f["accent"])
        self._edit_banner.setStyleSheet(
            f"background: rgba({acc.red()},{acc.green()},{acc.blue()},30); "
            f"border: 1px solid {f['accent']}; border-radius: 6px; "
            f"padding: 5px 10px; font-size: 11px; color: {f['accent']};"
        )

    def retranslate(self):
        """Baut Stat-Karten mit neuer Sprache neu."""
        for i, (key, val) in enumerate([
            ("home.accounts",     "2"),
            ("home.industry_jobs","—"),
            ("home.intel_alerts", "0"),
            ("home.pi_colonies",  "—"),
        ]):
            if i < len(self._stat_cards):
                self._stat_cards[i]._label = t(key)
                self._stat_cards[i].update()

    def set_faction(self, faction: str):
        self.settings["faction"] = faction
        self._update_banner_style()
        for sc in getattr(self, "_stat_cards", []):
            sc.set_faction(faction)
        for card in self._cards:
            card.set_faction(faction)

    def set_dev_mode(self, enabled: bool):
        self.settings["dev_mode"] = enabled
        for card in self._cards:
            card.update()

    def set_test_mode(self, enabled: bool):
        self.settings["test_mode"] = enabled
        for card in self._cards:
            card.update()