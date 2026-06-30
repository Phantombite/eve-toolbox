"""
Home Screen Design 1 — Grid mit Drag & Drop Reihenfolge.
"""
from core import logger as _logger
_log = _logger.get("home_grid")

import math
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                              QGridLayout, QLabel, QSizePolicy, QApplication)
from PyQt6.QtCore import (Qt, pyqtSignal, pyqtProperty, QRect, QRectF, QPoint,
                           QMimeData, QByteArray, QPropertyAnimation, QEasingCurve)
from PyQt6.QtGui import (QPainter, QColor, QPen, QBrush, QFont,
                          QPainterPath, QPalette, QDrag, QPixmap, QTransform)

from core.config import (MODULES, FACTIONS, DEFAULT_ORDER, is_module_active,
                          get_module_name, get_module_desc, get_subfunction,
                          get_ordered_subfunctions, get_full_sub_slot_perm,
                          swap_subfunctions, SUB_SLOT_COUNT, MODULE_SUBFUNCTIONS)
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
    clicked              = pyqtSignal(str)
    drag_started         = pyqtSignal(str)
    subfunction_clicked  = pyqtSignal(str, str)  # (module_id, sub_id)

    def __init__(self, mod: dict, settings: dict, parent=None):
        super().__init__(parent)
        self.mod        = mod
        self.settings   = settings
        self._hov       = False
        self._drag_over = False
        self._edit_mode = False
        # Flip-Zustand: 0.0 = Vorderseite, 1.0 = Rückseite (16 Sub-Slots).
        # _flip_progress wird per QPropertyAnimation animiert, _flipped
        # ist der LOGISCHE Soll-Zustand. Anders als beim Donut-Ring gibt
        # es im Grid KEIN persistentes Klick-Pinning der Hauptkarte:
        # im Normalmodus öffnet/schließt ausschließlich Hover (die
        # Vorderseite wird beim Flip komplett verdeckt, ein zweiter
        # Klick auf "dieselbe Stelle" würde ohnehin nur noch einen Sub-
        # Slot treffen — Klick-Toggle der Hauptkarte ist daher sinnlos).
        # Im Edit-Mode öffnet ein Klick (Hover wird ja zum Draggen
        # gebraucht) — siehe mousePressEvent. In beiden Fällen gilt:
        # höchstens EINE Karte gleichzeitig offen, koordiniert über
        # HomeGrid.request_open_card/close_all_cards.
        self._flip_progress = 0.0
        self._flipped       = False
        self._flip_anim = QPropertyAnimation(self, b"flipProgress")
        self._flip_anim.setDuration(280)
        self._flip_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Welcher Sub-Slot (0..SUB_SLOT_COUNT-1) wird aktuell von der
        # Maus getroffen, während die Rückseite sichtbar ist — analog
        # zu DonutWidget._sub_slot_index_at, aber rechteckig statt
        # winkelbasiert (siehe _sub_slot_at).
        self._hovered_sub = -1
        # Edit-Mode Sub-Drag-Vorbereitung (analog zu DonutWidget)
        self._sub_drag_start_slot = -1
        self._sub_drag_start_pos  = None
        self._sub_dragging   = False
        self._sub_drag_src   = -1   # Slot-INDEX, nicht ID (auch leere
                                     # Slots sind gültige Drag-Quellen)
        self._sub_drag_target = -1
        self._sub_drag_mouse_pos = QPoint(0, 0)

        self.setMouseTracking(True)
        self.setMinimumHeight(100)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._update_cursor()

    # ── Flip-Animation (Qt-Property für QPropertyAnimation) ──────────
    def _get_flip_progress(self):
        return self._flip_progress

    def _set_flip_progress(self, value):
        self._flip_progress = value
        self.update()

    flipProgress = pyqtProperty(float, _get_flip_progress, _set_flip_progress)

    def set_flipped(self, flipped: bool):
        """Startet die Dreh-Animation zum gewünschten Zustand, sofern
        nicht schon dort/dabei."""
        if self._flipped == flipped:
            return
        self._flipped = flipped
        self._flip_anim.stop()
        self._flip_anim.setStartValue(self._flip_progress)
        self._flip_anim.setEndValue(1.0 if flipped else 0.0)
        self._flip_anim.start()

    def _grid(self):
        """Findet den übergeordneten HomeGrid (für request_open_card/
        close_all_cards/start_card_drag)."""
        grid = self.parent()
        while grid and not isinstance(grid, HomeGrid):
            grid = grid.parent()
        return grid

    def is_open(self) -> bool:
        """True solange die Karte (an)geflippt ist oder gerade dorthin
        animiert — genutzt von HomeGrid, um zu entscheiden, ob diese
        Karte beim Öffnen einer anderen geschlossen werden muss."""
        return self._flipped or self._flip_progress > 0.0

    def force_close(self):
        """Schließt die Karte sofort (von außen, z.B. weil HomeGrid eine
        andere Karte geöffnet hat oder der Bearbeitungsmodus verlassen
        wurde) — bricht auch einen laufenden Sub-Drag sauber ab."""
        self._hov = False
        self._hovered_sub = -1
        self._sub_dragging = False
        self._sub_drag_src = -1
        self._sub_drag_target = -1
        self._sub_drag_start_slot = -1
        self._sub_drag_start_pos = None
        self.set_flipped(False)
        self.repaint()

    def _is_active(self):
        return is_module_active(
            self.mod,
            dev_mode  = self.settings.get("dev_mode", False),
            test_mode = self.settings.get("test_mode", False),
        )

    def _f(self):
        return FACTIONS.get(self.settings.get("faction", "caldari"), FACTIONS["caldari"])

    def _sub_slot_rects(self):
        """Liefert die 16 Rechtecke (lokale Widget-Koordinaten) des
        4×4-Sub-Slot-Rasters auf der Kartenrückseite, zeilenweise von
        oben-links nach unten-rechts (Slot 0 = oben-links, Slot 15 =
        unten-rechts) — das ist die layoutspezifische Geometrie-
        Entscheidung fürs Grid, analog zur winkelbasierten Geometrie
        beim Donut, aber bewusst anders (siehe Absprache: Layouts
        dürfen optisch unterschiedlich angeordnet sein, nur die
        zugrundeliegenden Daten/Indizes sind geteilt)."""
        w, h = self.width(), self.height()
        margin = 6
        gap = 3
        cols, rows = 4, 4
        cell_w = (w - 2*margin - (cols-1)*gap) / cols
        cell_h = (h - 2*margin - (rows-1)*gap) / rows
        rects = []
        for j in range(SUB_SLOT_COUNT):
            row, col = divmod(j, cols)
            x = margin + col * (cell_w + gap)
            y = margin + row * (cell_h + gap)
            rects.append(QRectF(x, y, cell_w, cell_h))
        return rects

    def _sub_slot_at(self, pos: QPoint) -> int:
        """Liefert den Sub-Slot-Index unter `pos` (lokale Koordinaten),
        unabhängig davon ob belegt oder leer — Pendant zu
        DonutWidget._sub_slot_index_at. Liefert -1 außerhalb aller
        Slots."""
        for j, rect in enumerate(self._sub_slot_rects()):
            if rect.contains(pos.x(), pos.y()):
                return j
        return -1

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
        w, h = self.width(), self.height()

        # Flip-Effekt: horizontale Skalierung simuliert eine 3D-Drehung
        # um die Y-Achse (QPainter kann keine echte 3D-Rotation, aber
        # ein Schrumpfen auf 0 in der Mitte + Seitenwechsel wirkt sehr
        # ähnlich und ist deutlich robuster/performanter). progress
        # 0.0 = Vorderseite voll sichtbar, 0.5 = Kante (Umschaltpunkt
        # Vorder-/Rückseite), 1.0 = Rückseite voll sichtbar.
        progress = self._flip_progress
        showing_back = progress >= 0.5
        # scale_x geht von 1.0 (progress=0) über 0.0 (progress=0.5)
        # zurück zu 1.0 (progress=1.0) — Betrag von cos(progress*π).
        scale_x = abs(math.cos(progress * math.pi))

        p.save()
        p.translate(w/2, h/2)
        p.scale(max(scale_x, 0.02), 1.0)  # nie exakt 0, sonst Division/Render-Glitches
        p.translate(-w/2, -h/2)

        if showing_back:
            self._paint_back(p, w, h)
        else:
            self._paint_front(p, w, h)

        p.restore()
        p.end()

    def _paint_front(self, p: QPainter, w: int, h: int):
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
                   get_module_name(self.mod["id"]))

        p.setPen(QPen(desc_color))
        p.setFont(QFont("Segoe UI", 9))
        p.drawText(QRect(14, 66, w-28, h-76),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop |
                   Qt.TextFlag.TextWordWrap, get_module_desc(self.mod["id"]))

        if not active and not self._edit_mode:
            p.setOpacity(0.45)
            p.setFont(QFont("Segoe UI Emoji", 11))
            p.setPen(QPen(QColor("#bbb")))
            p.drawText(QRect(w-28, 10, 18, 18),
                       Qt.AlignmentFlag.AlignCenter, "🔒")

    def _paint_back(self, p: QPainter, w: int, h: int):
        """Kartenrückseite — 4×4-Raster mit den Unterfunktionen dieses
        Hauptmoduls. Layoutspezifische Optik (rechteckige Mini-Kacheln
        statt der Donut-Wasserlauf-Animation), aber identische
        Datenquelle (get_ordered_subfunctions, geteilt mit dem Donut).
        Unbelegte Slots: im Edit-Mode gestrichelter Platzhalter, sonst
        komplett unsichtbar — analog zu DonutWidget."""
        f      = self._f()
        dark   = self.palette().color(QPalette.ColorRole.Window).lightness() < 128
        accent = QColor(f["accent"])

        # Karten-Rahmen der Rückseite (eigener, leicht hervorgehobener
        # Look, damit klar ist "das ist die Rückseite/ein Untermenü").
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w-1, h-1), 10, 10)
        bg = QColor("#2a2a2a") if dark else QColor("#ffffff")
        p.fillPath(path, QBrush(bg))
        p.setPen(QPen(accent, 1.4))
        p.drawPath(path)

        subs = get_ordered_subfunctions(self.settings, self.mod["id"], SUB_SLOT_COUNT)
        rects = self._sub_slot_rects()

        for j, rect in enumerate(rects):
            sub = subs[j]
            belegt = sub is not None
            if not belegt and not self._edit_mode:
                # Unbelegte Slots im Normalbetrieb komplett unsichtbar —
                # exakt wie beim Donut.
                continue

            is_hov = belegt and j == self._hovered_sub and not self._edit_mode

            slot_path = QPainterPath()
            slot_path.addRoundedRect(rect, 5, 5)

            if not belegt:
                # Edit-Mode Platzhalter
                p.setBrush(QBrush(QColor(120, 120, 120, 14)))
                pen = QPen(QColor(150, 150, 150, 90), 0.8, Qt.PenStyle.DashLine)
                pen.setDashPattern([3, 3])
                p.setPen(pen)
                p.drawPath(slot_path)
            else:
                if is_hov:
                    fill = accent
                    text_col = QColor("#ffffff")
                    pen = QPen(accent, 1.4)
                else:
                    fill = (QColor(accent.red(), accent.green(), accent.blue(), 90)
                            if dark else
                            QColor(accent.red(), accent.green(), accent.blue(), 40))
                    text_col = accent
                    pen = QPen(accent, 0.8)
                p.setBrush(QBrush(fill))
                p.setPen(pen)
                p.drawPath(slot_path)

                p.setClipPath(slot_path)
                p.setPen(QPen(text_col))
                p.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                           sub["name"])
                p.setClipping(False)

            if self._edit_mode:
                p.setPen(QPen(QColor(150, 150, 150, 160)))
                p.setFont(QFont("Segoe UI", 6))
                num_rect = QRectF(rect.x(), rect.bottom()-10, rect.width(), 10)
                p.drawText(num_rect, Qt.AlignmentFlag.AlignCenter, f"#{j}")

        # Schwebendes Sub-Slot-Element beim Drag — analog zum Donut-
        # Ghost: folgt der Maus, Zielslot wird separat hervorgehoben.
        if self._sub_dragging and self._sub_drag_src >= 0:
            mp = self._sub_drag_mouse_pos
            src_sub = subs[self._sub_drag_src] if self._sub_drag_src < len(subs) else None
            ghost_w, ghost_h = 60, 32
            ghost_rect = QRectF(mp.x() - ghost_w/2, mp.y() - ghost_h/2, ghost_w, ghost_h)
            ghost_path = QPainterPath()
            ghost_path.addRoundedRect(ghost_rect, 5, 5)
            ghost_fill = QColor(accent.red(), accent.green(), accent.blue(), 150)
            p.setBrush(QBrush(ghost_fill))
            gpen = QPen(accent, 1.6, Qt.PenStyle.DashLine)
            gpen.setDashPattern([4, 3])
            p.setPen(gpen)
            p.drawPath(ghost_path)
            p.setClipPath(ghost_path)
            p.setPen(QPen(QColor("#ffffff")))
            p.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
            p.drawText(ghost_rect, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       src_sub["name"] if src_sub else "")
            p.setClipping(False)

            if self._sub_drag_target >= 0:
                tgt_rect = rects[self._sub_drag_target]
                tgt_path = QPainterPath()
                tgt_path.addRoundedRect(tgt_rect, 5, 5)
                tgt_fill = QColor(accent.red(), accent.green(), accent.blue(), 70)
                p.setBrush(QBrush(tgt_fill))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(tgt_path)

    def enterEvent(self, event):
        super().enterEvent(event)
        # Hover öffnet NUR im Normalmodus (im Edit-Mode wird die Maus
        # zum Draggen gebraucht, Öffnen passiert dort ausschließlich
        # über Klick — siehe mousePressEvent).
        if self._is_active() and not self._edit_mode:
            self._hov = True
            grid = self._grid()
            if grid:
                grid.request_open_card(self.mod["id"])
            self.set_flipped(True)
            self.repaint()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self._hov = False
        self._hovered_sub = -1
        # Im Normalmodus schließt die Karte IMMER, sobald die Maus sie
        # verlässt (kein Klick-Pinning der Hauptkarte im Grid — siehe
        # Kommentar in __init__). Im Edit-Mode bleibt sie offen, bis
        # ein Klick-ins-Leere/Rechtsklick sie schließt (siehe
        # mousePressEvent) — das Verlassen per Maus alleine schließt
        # im Edit-Mode NICHT, sonst könnte man nie über die Slots der
        # Rückseite fahren, um sie zu ziehen.
        if not self._edit_mode:
            self.set_flipped(False)
            grid = self._grid()
            if grid:
                grid.notify_card_closed(self.mod["id"])
        self.repaint()

    def mouseMoveEvent(self, event):
        self._sub_drag_mouse_pos = event.position().toPoint()

        # Sub-Drag-Start: Schwellenwert (>8px Bewegung seit Klick auf
        # einem Sub-Slot im Edit-Mode) — analog zum Donut-Hauptring-Drag.
        if (self._edit_mode and event.buttons() & Qt.MouseButton.LeftButton
                and self._sub_drag_start_pos is not None and not self._sub_dragging):
            if (event.position().toPoint() - self._sub_drag_start_pos).manhattanLength() > 8:
                self._sub_dragging = True
                self._sub_drag_src = self._sub_drag_start_slot
                self._sub_drag_target = -1
            self.repaint()
            return

        if self._sub_dragging:
            target = self._sub_slot_at(event.position().toPoint())
            if target != self._sub_drag_src:
                self._sub_drag_target = target
            else:
                self._sub_drag_target = -1
            self.repaint()
            return

        # Sub-Slot-Hover auf der Rückseite (nur relevant sobald die
        # Drehung weit genug ist, dass die Rückseite überhaupt sichtbar
        # bzw. eine sinnvolle Trefferfläche hat).
        if self._flip_progress >= 0.5 and not self._edit_mode:
            new_sub = self._sub_slot_at(event.position().toPoint())
            subs = get_ordered_subfunctions(self.settings, self.mod["id"], SUB_SLOT_COUNT)
            if new_sub >= 0 and (new_sub >= len(subs) or subs[new_sub] is None):
                new_sub = -1  # unbelegte Slots reagieren nicht auf Hover
            if new_sub != self._hovered_sub:
                self._hovered_sub = new_sub
                self.setCursor(Qt.CursorShape.PointingHandCursor if new_sub >= 0
                               else Qt.CursorShape.ArrowCursor)
                self.repaint()
        elif self._hovered_sub != -1:
            self._hovered_sub = -1
            self.repaint()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # Rechtsklick schließt eine offene Karte — gilt in beiden
            # Modi (Linksklick-ins-Leere schließt zusätzlich, NUR im
            # Edit-Mode, siehe unten — im Normalmodus übernimmt das
            # ohnehin schon leaveEvent).
            if self._flip_progress > 0.0:
                grid = self._grid()
                if grid:
                    grid.close_all_cards()
                else:
                    self.force_close()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._edit_mode:
            # Liegt der Klick auf einem BELEGTEN Sub-Slot der bereits
            # sichtbaren Rückseite, wird ein Sub-Drag vorbereitet
            # (Verschieben der Unterfunktion) — leere Slots sind
            # ebenfalls gültige Start-/Zielpunkte für den Drag selbst,
            # aber ein Klick OHNE folgenden Drag auf irgendeine Stelle
            # der Rückseite soll die Karte schließen (da es im Grid,
            # anders als beim Donut, kaum "leeren Raum" außerhalb der
            # Slots gibt, in den man sonst klicken könnte).
            if self._flip_progress >= 0.5:
                slot_idx = self._sub_slot_at(event.position().toPoint())
                if slot_idx >= 0:
                    self._sub_drag_start_slot = slot_idx
                    self._sub_drag_start_pos  = event.position().toPoint()
                else:
                    # Klick komplett daneben (z.B. Rand) — sofort
                    # schließen, kein Drag möglich.
                    grid = self._grid()
                    if grid:
                        grid.close_all_cards()
                    else:
                        self.force_close()
                return
            # Klick auf die Vorderseite: war die Karte schon offen
            # (sollte im Edit-Mode eigentlich nicht vorkommen, da die
            # Vorderseite dann verdeckt ist) → ignorieren. Sonst öffnet
            # der Klick sie (einziger Weg im Edit-Mode, da Hover zum
            # Draggen gebraucht wird) und bereitet zugleich den Haupt-
            # Karten-Drag vor.
            grid = self._grid()
            if grid:
                grid.request_open_card(self.mod["id"])
                global_pos = self.mapToGlobal(event.position().toPoint())
                grid_pos   = grid.mapFromGlobal(global_pos)
                grid.start_card_drag(self.mod["id"], grid_pos)
            self.set_flipped(True)
            return

        # ── Normalmodus ──────────────────────────────────────────────
        # Hauptkarte selbst ist hier nie klickbar zum Öffnen/Schließen
        # (das macht ausschließlich Hover, siehe enterEvent/leaveEvent)
        # — ein Klick kann hier nur noch einen Sub-Slot treffen, sofern
        # die Rückseite durch Hover schon sichtbar ist.
        if self._flip_progress >= 0.5:
            slot_idx = self._sub_slot_at(event.position().toPoint())
            subs = get_ordered_subfunctions(self.settings, self.mod["id"], SUB_SLOT_COUNT)
            if 0 <= slot_idx < len(subs) and subs[slot_idx] is not None:
                self.subfunction_clicked.emit(self.mod["id"], subs[slot_idx]["id"])
                self._hovered_sub = -1
                self.set_flipped(False)
                grid = self._grid()
                if grid:
                    grid.notify_card_closed(self.mod["id"])

    def mouseReleaseEvent(self, event):
        if self._sub_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._sub_dragging = False
            if (self._sub_drag_target >= 0 and self._sub_drag_src >= 0
                    and self._sub_drag_target != self._sub_drag_src):
                if swap_subfunctions(self.settings, self.mod["id"],
                                      self._sub_drag_src, self._sub_drag_target,
                                      SUB_SLOT_COUNT):
                    cfg.save(self.settings)
            self._sub_drag_src = -1
            self._sub_drag_target = -1
            self.repaint()
        self._sub_drag_start_slot = -1
        self._sub_drag_start_pos = None

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
    module_opened       = pyqtSignal(str)
    subfunction_opened  = pyqtSignal(str, str)  # (module_id, sub_id)
    order_changed       = pyqtSignal(list)  # neue Reihenfolge als ID-Liste

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings   = settings
        self._cards:    list[ModuleCard] = []
        self._edit_mode  = False
        # Modul-ID der aktuell offenen (geflippten) Karte — es darf zu
        # jeder Zeit höchstens EINE Karte offen sein, sowohl im Normal-
        # als auch im Bearbeitungsmodus. Zentral hier verwaltet (statt
        # pro Karte), damit eine neu öffnende Karte garantiert alle
        # anderen schließt — analog zu DonutWidget._pinned_ring.
        self._open_card_id = None
        self._dragging    = False
        self._drag_src_id  = None
        self._drag_over_id = None
        self._drag_pixmap  = None
        self._mouse_pos    = QPoint(0, 0)
        self._drag_hotspot = QPoint(0, 0)
        self._build()

    def request_open_card(self, mod_id: str):
        """Öffnet die Karte mit `mod_id` und schließt dabei garantiert
        jede andere offene Karte — analog zu DonutWidget._pinned_ring,
        das ebenfalls nur einen Ring gleichzeitig erlaubt. Wird sowohl
        von Hover (Normalmodus) als auch von Klick (Edit-Mode) auf-
        gerufen (siehe ModuleCard)."""
        if self._open_card_id == mod_id:
            return
        self._open_card_id = mod_id
        for card in self._cards:
            if card.mod["id"] != mod_id and card.is_open():
                card.force_close()

    def close_all_cards(self):
        """Schließt jede offene Karte — aufgerufen bei Linksklick/
        Rechtsklick ins Leere und beim Verlassen des Bearbeitungsmodus
        (siehe set_edit_mode)."""
        self._open_card_id = None
        for card in self._cards:
            if card.is_open():
                card.force_close()

    def notify_card_closed(self, mod_id: str):
        """Eine Karte teilt mit, dass sie sich selbst geschlossen hat
        (Hover verlassen oder Sub-Klick navigiert+schließt) — räumt den
        zentralen 'offen'-Status auf, falls er noch auf diese Karte
        zeigte. Vermeidet direkten Zugriff auf _open_card_id von außen."""
        if self._open_card_id == mod_id:
            self._open_card_id = None

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
            card.subfunction_clicked.connect(self.subfunction_opened)
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
                                 get_module_name(card.mod["id"]))
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
        if not enabled:
            # Beim Verlassen des Bearbeitungsmodus müssen alle offenen
            # Karten schließen — im Normalmodus zählt ja nur Hover, und
            # die Maus steht in dem Moment i.d.R. nicht über der Karte
            # (z.B. wenn über einen Einstellungs-Schalter umgeschaltet
            # wurde). Explizit erzwungen statt nur auf den nächsten
            # Hover-Wechsel zu hoffen, damit es zuverlässig immer
            # funktioniert.
            self.close_all_cards()
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