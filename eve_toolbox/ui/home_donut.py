"""
Home Screen Design 2 & 3 — Donut in PyQt6/QPainter.
"""
from core import logger as _logger
_log = _logger.get("home_donut")

import math
import time
from pathlib import Path
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF, QPoint, QMimeData, QTimer
from PyQt6.QtGui import (QPainter, QPainterPath, QColor, QPen, QBrush,
                          QFont, QPalette, QTransform, QPixmap, QDrag)

from core.config import (MODULES, FACTIONS, is_module_active, MODULE_SUBFUNCTIONS,
                          get_subfunction, get_module_name,
                          get_full_sub_slot_perm, get_ordered_subfunctions,
                          swap_subfunctions)
from core.i18n import t
from core import settings as cfg

ASSETS = (Path(__file__).resolve().parent.parent / "assets" / "icons")

ICON_MAP = {
    "package":   "📦", "chart-bar": "📊", "brain":     "🧠",
    "radar":     "📡", "plant":     "🌿", "hammer":    "🔨",
    "route":     "🗺", "cash":      "💰",
    # Außenring-Icons (Unterfunktionen) — ergänzt bei Bedarf
    "clipboard-list": "📋", "file-text": "📄", "settings": "⚙",
    "report-money":   "💹",
}


class DonutWidget(QWidget):
    module_clicked      = pyqtSignal(str)
    subfunction_clicked = pyqtSignal(str, str)  # (module_id, sub_id)

    # ── Außenring-Geometrie (Unterfunktionen pro Hauptmodul) ───────────
    # Slot-Breite bewusst auf 22.5° festgelegt (= halbe Hauptsegment-
    # Breite bei 8 Hauptmodulen) und Ring-Dicke auf 76% der Hauptring-
    # Dicke — beide Werte aus den Design-Vorschauen übernommen, die mit
    # dem Nutzer abgestimmt wurden (Punkt 0 = Hauptring-Maße als Basis).
    SUB_SLOT_WIDTH_DEG       = 22.5
    SUB_RING_THICKNESS_RATIO = 0.76
    SUB_RING_GAP_PX          = 6
    SUB_SLOT_GAP_DEG         = 2.0

    # ── Hover-Ausbreitungsanimation ─────────────────────────────────────
    # Drei Phasen, die jeweils einen Anteil der Gesamtzeit bekommen:
    #   1) Hauptsegment füllt sich radial (Logo-Seite → Außenkante)
    #   2) Füllung läuft weiter in Außenring-Slot 0
    #   3) Füllung läuft von Slot 0 gleichzeitig in beide Richtungen rum
    # Gesamtdauer ca. 2.5s (Nutzer wollte 2-4s) bis der Ring komplett
    # einmal rum ist. Anteile so gewählt, dass Phase 1 (Hauptsegment)
    # spürbar schneller ist als das komplette Rundlaufen in Phase 3.
    ANIM_DURATION_S     = 2.6
    ANIM_PHASE1_END     = 0.18   # Hauptsegment-Füllung fertig bei 18%
    ANIM_PHASE2_END     = 0.28   # Slot 0 gefüllt bei 28%
    # Phase 3 (0.28 .. 1.0): restliche Slots beidseitig von Slot 0 aus
    ANIM_TICK_MS        = 16     # ~60 FPS

    # Alpha-Werte der gedeckten Zwischenfarbe (während der Ausbreitung,
    # VOR dem finalen Vollfarbe-Glow). Bewusst deutlich transparenter als
    # die Vollfarbe (255), damit der spätere "Maus drauf"-Vollglanz sich
    # klar davon abhebt. ANIM_MIN_ALPHA ist ein Sofort-Sprung beim ersten
    # Erscheinen eines Elements (Hauptsegment oder Slot) — ohne diesen
    # Sprung ist der Übergang in den ersten paar Prozent Fortschritt so
    # nah an der Grundfarbe, dass er optisch kaum wahrnehmbar ist und es
    # wirkt, als poppe das Element erst spät plötzlich auf.
    ANIM_MIN_ALPHA      = 70
    ANIM_MID_ALPHA      = 95

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings    = settings
        self._hov        = -1
        self._pinned_ring = -1  # Hauptsegment-Index, dessen Außenring per
                                 # Klick fest angepinnt ist (-1 = keiner
                                 # gepinnt, normales Hover-Verhalten aktiv)
        self._last_hovered_sub = -1  # Sub-Slot-Index, der zuletzt von der
                                      # Maus getroffen wurde — nur zur
                                      # Erkennung von Positionswechseln
                                      # INNERHALB desselben Hauptsegments
                                      # (siehe mouseMoveEvent), damit dafür
                                      # ein Repaint ausgelöst wird.
        self._drag_seg   = -1
        self._click_toggle_candidate = -1  # Edit-Mode: Hauptsegment-Index,
                                            # falls der gerade laufende
                                            # Klick (noch kein Drag) auf
                                            # der bereits offenen Kategorie
                                            # begann — wird in
                                            # mouseReleaseEvent ausge-
                                            # wertet, um den Ring per
                                            # Toggle zu schließen, FALLS
                                            # daraus kein Drag wurde.
        self._edit_mode  = False
        self._faction    = settings.get("faction", "caldari")
        self._dev        = settings.get("dev_mode", False)
        self._show_empty_subslots = False  # später per Dev-Button umschaltbar
        self._logo_cache: dict = {}
        # Custom Drag State (Hauptring)
        self._dragging    = False
        self._drag_src    = -1
        self._drag_target = -1
        self._mouse_x     = 0.0
        self._mouse_y     = 0.0

        # Custom Drag State (Außenring / Unterfunktionen) — analog zum
        # Hauptring-Drag, aber bezogen auf Sub-Slot-Indizes innerhalb des
        # aktuell sichtbaren Rings (self._pinned_ring).
        self._sub_dragging    = False
        self._sub_drag_src    = -1   # Slot-INDEX (nicht ID) — auch leere
                                      # Slots sind gültige Drag-Quellen
        self._sub_drag_target = -1   # Slot-INDEX
        self._sub_drag_start_ring = -1
        self._sub_drag_start_slot = -1
        self._sub_drag_start_pos  = None

        # ── Hover-Ausbreitungsanimation ─────────────────────────────
        # _anim_ring: Hauptsegment-Index, für den GERADE eine Animation
        # läuft oder zuletzt gelaufen ist (-1 = keine). Startet/läuft
        # neu, sobald display_slot (Hover oder gepinnt) auf ein ANDERES
        # Hauptsegment wechselt. Verschwindet sofort (kein Rückwärts-
        # Lauf), sobald der Ring komplett geschlossen wird (kein Hover,
        # kein Pin mehr).
        self._anim_ring       = -1
        self._anim_start_time = 0.0
        self._anim_full_glow_start = None  # separater Zeitstempel für den
                                            # Übergang zur Vollfarbe, erst
                                            # NACH komplettem Ringdurchlauf
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(self.ANIM_TICK_MS)
        self._anim_timer.timeout.connect(self.update)

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

    def _full_sub_slot_perm(self, module_id: str) -> list:
        """Dünner Wrapper um die zentrale, layoutübergreifend geteilte
        Funktion get_full_sub_slot_perm() in core/config.py — siehe dort
        für die vollständige Erklärung. Bleibt als Methode erhalten,
        damit bestehende Aufrufstellen innerhalb dieser Klasse (sowie
        HomeDonut.swap_subfunctions über self._donut) unverändert
        funktionieren."""
        return get_full_sub_slot_perm(self.settings, module_id,
                                        self._sub_slot_count())

    def _ordered_subfunctions(self, module_id: str) -> list:
        """Dünner Wrapper um die zentrale, layoutübergreifend geteilte
        Funktion get_ordered_subfunctions() in core/config.py — siehe
        dort für die vollständige Erklärung."""
        return get_ordered_subfunctions(self.settings, module_id,
                                          self._sub_slot_count())

    def _dims(self):
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        available = min(w, h) / 2 - 8
        # r_out muss so gewählt werden, dass der GESAMTE Donut inklusive
        # Außenring (reicht bis r_out + SUB_RING_GAP_PX + Außenring-Dicke)
        # noch in die verfügbare Fläche passt — sonst ragt der Außenring
        # über den Rand hinaus. Alle anderen Maße (r_in, Außenring-Dicke,
        # Slot-Breiten in Grad, ...) sind reine Verhältnisse von r_out und
        # skalieren dadurch automatisch mit, ohne dass sich am Aussehen
        # oder an den Proportionen etwas ändert — nur die Gesamtgröße.
        main_inner_ratio = 0.52
        total_to_main_ratio = 1 + (1 - main_inner_ratio) * self.SUB_RING_THICKNESS_RATIO
        r_out = (available - self.SUB_RING_GAP_PX) / total_to_main_ratio
        r_in  = r_out * main_inner_ratio
        return cx, cy, r_out, r_in

    def _arc_path(self, cx, cy, ro, r_in, a_start, a_end):
        """Baut einen Ring-Segment-Pfad zwischen zwei Winkeln (Grad, 0°
        oben, im Uhrzeigersinn steigend). Allgemeinere Fassung von
        _seg_path — arbeitet direkt mit Start-/Endwinkel statt Index/
        Anzahl, damit sie sowohl für den Hauptring als auch für die
        Außenring-Slots verwendet werden kann."""
        steps = 32
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

    def _arc_center(self, cx, cy, ro, r_in, a_start, a_end):
        a = math.radians((a_start + a_end) / 2)
        lr = (ro + r_in) / 2
        return cx + lr * math.sin(a), cy - lr * math.cos(a)

    def _seg_path(self, cx, cy, ro, r_in, i, n, gap):
        slice_deg = 360.0 / n
        a_start = i * slice_deg + gap / 2
        a_end   = (i + 1) * slice_deg - gap / 2
        return self._arc_path(cx, cy, ro, r_in, a_start, a_end)

    def _seg_center(self, cx, cy, ro, r_in, i, n, gap):
        slice_deg = 360.0 / n
        a_start = i * slice_deg + gap / 2
        a_end   = (i + 1) * slice_deg - gap / 2
        return self._arc_center(cx, cy, ro, r_in, a_start, a_end)

    def _seg_mid_angle(self, i, n):
        """Mittlerer Winkel des i-ten Hauptsegments (ohne gap-Korrektur,
        die ist für die Mitte irrelevant — symmetrisch um den Slice)."""
        slice_deg = 360.0 / n
        return (i + 0.5) * slice_deg

    # ── Hover-Ausbreitungsanimation ─────────────────────────────────────
    def _update_anim_ring(self, target_ring: int):
        """Sorgt dafür, dass für `target_ring` (-1 = kein Ring sichtbar)
        eine Animation läuft bzw. gestoppt wird. Wechselt der sichtbare
        Ring auf ein ANDERES Hauptsegment, startet die Animation für
        dieses neu von vorne (kein Übergang/Crossfade — entspricht der
        Vorgabe, dass Verschwinden/Wechsel sofort passiert, nur das
        Erscheinen ist animiert)."""
        if target_ring < 0:
            if self._anim_ring != -1:
                self._anim_ring = -1
                self._anim_full_glow_start = None
                self._anim_timer.stop()
            return
        if target_ring != self._anim_ring:
            self._anim_ring = target_ring
            self._anim_start_time = time.monotonic()
            self._anim_full_glow_start = None
            if not self._anim_timer.isActive():
                self._anim_timer.start()

    def _anim_progress(self) -> float:
        """Gesamtfortschritt (0.0–1.0) der aktuell laufenden Animation,
        zeitbasiert (nicht frame-counter-basiert, damit das Tempo von
        der Framerate unabhängig gleich bleibt). 1.0 = fertig (Ring
        einmal komplett durchlaufen, bleibt dann stehen — der Timer
        läuft trotzdem weiter, da danach noch der Vollfarbe-Glow-Übergang
        animiert wird, siehe _anim_main_full_glow)."""
        if self._anim_ring < 0:
            return 0.0
        elapsed = time.monotonic() - self._anim_start_time
        progress = elapsed / self.ANIM_DURATION_S
        if progress >= 1.0:
            return 1.0
        return progress

    def _anim_main_fill(self, progress: float) -> float:
        """Füllstand (0.0–1.0) der INITIALEN Hauptsegment-Füllbewegung
        (Phase 1, schnell) — bestimmt nur, wie schnell die gedeckte
        Zwischenfarbe erreicht wird, NICHT ob/wann die kräftigere
        Vollfarbe erscheint (siehe _anim_main_full_glow dafür)."""
        if progress >= self.ANIM_PHASE1_END:
            return 1.0
        return progress / self.ANIM_PHASE1_END

    def _anim_main_full_glow(self, progress: float) -> float:
        """0.0–1.0: wie weit ist der Übergang von der gedeckten Zwischen-
        farbe des Hauptsegments zur kräftigen Vollfarbe. Soll erst
        einsetzen, wenn die GESAMTE Ringausbreitung fertig ist (sonst
        wirkt es, als wäre alles sofort fertig, noch während sich der
        Ring erst aufbaut) — daher direkt an progress >= 1.0 gekoppelt,
        mit einer kurzen eigenen Einblendzeit danach."""
        if progress < 1.0:
            return 0.0
        # progress bleibt bei 1.0 stehen (siehe _anim_progress), daher
        # separat über eine zweite Zeitbasis nachführen.
        if self._anim_full_glow_start is None:
            self._anim_full_glow_start = time.monotonic()
        elapsed = time.monotonic() - self._anim_full_glow_start
        glow_duration = 0.3
        if elapsed >= glow_duration:
            self._anim_timer.stop()  # alles fertig — keine weiteren Repaints nötig
            return 1.0
        return elapsed / glow_duration

    def _anim_slot_fill(self, progress: float, slot_index: int, n_slots: int) -> float:
        """Füllstand (0.0–1.0) eines bestimmten Außenring-Slots. Slot 0
        füllt sich in Phase 2, alle anderen breiten sich in Phase 3
        gleichzeitig von Slot 0 aus in beide Richtungen aus (kürzester
        Abstand zu Slot 0 im Kreis, z.B. Slot 1 und Slot n-1 zur
        gleichen Zeit)."""
        if progress <= self.ANIM_PHASE1_END:
            return 0.0
        if slot_index == 0:
            if progress >= self.ANIM_PHASE2_END:
                return 1.0
            span = self.ANIM_PHASE2_END - self.ANIM_PHASE1_END
            return (progress - self.ANIM_PHASE1_END) / span
        if progress <= self.ANIM_PHASE2_END:
            return 0.0
        # Kürzester Abstand von slot_index zu Slot 0 im Kreis (1..n//2)
        dist = min(slot_index, n_slots - slot_index)
        max_dist = n_slots // 2
        phase3_span = 1.0 - self.ANIM_PHASE2_END
        # Jeder Abstand bekommt ein gleich großes Zeitfenster, linear
        # von Slot 0 aus nach außen — bei max_dist Schritten verteilt
        # sich phase3_span gleichmäßig darüber.
        slot_start = self.ANIM_PHASE2_END + phase3_span * (dist - 1) / max_dist
        slot_end   = self.ANIM_PHASE2_END + phase3_span * dist / max_dist
        if progress >= slot_end:
            return 1.0
        if progress <= slot_start:
            return 0.0
        return (progress - slot_start) / (slot_end - slot_start)

    # ── Außenring (Unterfunktionen pro Hauptmodul) ─────────────────────
    def _sub_ring_dims(self, r_out, r_in):
        """Innen-/Außenradius des Außenrings, abgeleitet von der Haupt-
        ring-Geometrie (siehe SUB_RING_THICKNESS_RATIO/SUB_RING_GAP_PX)."""
        main_thickness = r_out - r_in
        sub_thickness   = main_thickness * self.SUB_RING_THICKNESS_RATIO
        r_in2  = r_out + self.SUB_RING_GAP_PX
        r_out2 = r_in2 + sub_thickness
        return r_in2, r_out2

    def _sub_slot_count(self) -> int:
        return round(360.0 / self.SUB_SLOT_WIDTH_DEG)

    def _sub_slot_angles(self, main_mid_angle, slot_index):
        """Start-/Endwinkel von Slot `slot_index` im Außenring einer
        Hauptkategorie, deren Mitte bei `main_mid_angle` liegt. Slot 0
        liegt dabei IMMER exakt mittig auf der Hauptkategorie, danach
        im Uhrzeigersinn durchnummeriert (1, 2, 3, ...)."""
        w = self.SUB_SLOT_WIDTH_DEG
        slot_mid = main_mid_angle + slot_index * w
        a_start = slot_mid - w / 2 + self.SUB_SLOT_GAP_DEG / 2
        a_end   = slot_mid + w / 2 - self.SUB_SLOT_GAP_DEG / 2
        return a_start, a_end

    def _sub_slot_visible_paths(self, cx, cy, r_out2, r_in2, main_mid, j,
                                  n_sub_slots, slot_t):
        """Liefert die SICHTBARE Teilfläche(n) von Slot `j` als Liste von
        QPainterPath, passend zur "Wasser läuft durch"-Ausbreitung:
        - Slot 0 füllt sich RADIAL (innen→außen), exakt wie das Haupt-
          segment selbst — eine direkte Fortsetzung des radialen Flusses,
          bevor er in den Slots seitlich weiterläuft.
        - Slots 1..n/2-1 (im Uhrzeigersinn von Slot 0 weg) füllen sich
          von ihrer Slot-0-zugewandten (linken) Kante zur rechten.
        - Slots n/2+1..n-1 (gegen den Uhrzeigersinn von Slot 0 weg)
          füllen sich gespiegelt: von ihrer Slot-0-zugewandten (rechten)
          Kante zur linken — sonst sähe es so aus, als käme das Wasser
          von der falschen Seite.
        - Slot n/2 (genau gegenüber von Slot 0) ist der letzte, der
          erreicht wird — gleichzeitig von BEIDEN Nachbarn (links von
          Slot n/2-1, rechts von Slot n/2+1), wächst also von beiden
          Außenkanten zur Mitte. Sobald beide Hälften sich treffen
          (slot_t >= 1.0), verschmelzen sie zu einer durchgehenden
          Fläche ohne Trennlinie in der Mitte.
        Liefert eine leere Liste, wenn slot_t <= 0 (noch nicht erreicht)."""
        if slot_t <= 0.0:
            return []
        a_start, a_end = self._sub_slot_angles(main_mid, j)
        max_dist = n_sub_slots // 2

        if j == 0:
            fill_r = r_in2 + (r_out2 - r_in2) * slot_t
            return [self._arc_path(cx, cy, fill_r, r_in2, a_start, a_end)]

        if j == max_dist:
            half = (a_end - a_start) / 2
            left_end   = a_start + half * slot_t
            right_start = a_end - half * slot_t
            if slot_t >= 1.0:
                # Hälften berühren/überlappen sich — als EINE durchgehende
                # Fläche zeichnen, damit keine Naht in der Mitte entsteht.
                return [self._arc_path(cx, cy, r_out2, r_in2, a_start, a_end)]
            return [
                self._arc_path(cx, cy, r_out2, r_in2, a_start, left_end),
                self._arc_path(cx, cy, r_out2, r_in2, right_start, a_end),
            ]

        if j < max_dist:
            visible_end = a_start + (a_end - a_start) * slot_t
            return [self._arc_path(cx, cy, r_out2, r_in2, a_start, visible_end)]

        # j > max_dist: von der rechten (Slot-0-fernen) Kante aus
        # gespiegelt füllen, also von a_end aus Richtung a_start wachsen.
        visible_start = a_end - (a_end - a_start) * slot_t
        return [self._arc_path(cx, cy, r_out2, r_in2, visible_start, a_end)]

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

    def _sub_slot_index_at(self, mx, my, main_idx):
        """Wie _sub_seg_at, aber liefert den SLOT-INDEX (0..n-1)
        unabhängig davon, ob der Slot belegt ist oder leer — gebraucht
        im Bearbeitungsmodus, wo auch leere Slots als Drag-Start/-Ziel
        dienen müssen, damit man eine Unterfunktion auf eine freie
        Position verschieben kann (und umgekehrt). Liefert -1, wenn
        außerhalb des Außenring-Bandes oder zwischen zwei Slots
        (Slot-Gap) geklickt wurde."""
        mods = self._ordered_modules()
        if not (0 <= main_idx < len(mods)):
            return -1
        cx, cy, r_out, r_in = self._dims()
        r_in2, r_out2 = self._sub_ring_dims(r_out, r_in)
        dx, dy = mx - cx, my - cy
        dist = math.sqrt(dx*dx + dy*dy)
        if dist < r_in2 or dist > r_out2:
            return -1
        angle = (90 - math.degrees(math.atan2(-dy, dx))) % 360
        n = len(mods)
        main_mid = self._seg_mid_angle(main_idx, n)
        n_sub_slots = self._sub_slot_count()
        w = self.SUB_SLOT_WIDTH_DEG
        for j in range(n_sub_slots):
            slot_mid = (main_mid + j * w) % 360
            diff = (angle - slot_mid + 180) % 360 - 180
            if abs(diff) <= w / 2 - self.SUB_SLOT_GAP_DEG / 2:
                return j
        return -1

    def _sub_seg_at(self, mx, my, main_idx):
        """Prüft, ob (mx, my) innerhalb eines BELEGTEN UND VOLLSTÄNDIG
        ERSCHIENENEN Unterfunktions-Slots im Außenring von Hauptkategorie
        `main_idx` liegt. Liefert die Unterfunktions-ID oder None — sowohl
        bei leeren/unbelegten Slots als auch bei Slots, deren Hover-
        Ausbreitungsanimation diese Position noch nicht (komplett)
        erreicht hat. Das verhindert Klicks auf etwas, das (noch) nicht
        oder nur teilweise sichtbar ist — wichtig z.B. bei schnellen
        Mausbewegungen oder Klicks während die Animation noch läuft."""
        mods = self._ordered_modules()
        if not (0 <= main_idx < len(mods)):
            return None
        subs = self._ordered_subfunctions(mods[main_idx]["id"])
        j = self._sub_slot_index_at(mx, my, main_idx)
        if j < 0 or subs[j] is None:
            return None
        n_sub_slots = self._sub_slot_count()
        slot_t = self._anim_slot_fill(self._anim_progress(), j, n_sub_slots)
        if slot_t < 1.0:
            return None
        return subs[j]["id"]

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

        # display_slot: welches Hauptsegment hat aktuell einen (Hover-
        # oder angepinnten) Außenring sichtbar — wird hier schon vorab
        # bestimmt, weil die Hover-Ausbreitungsanimation des Hauptsegments
        # selbst (Phase 1) davon abhängt. Gesperrte Module bekommen nie
        # einen Ring/eine Animation.
        display_slot = self._pinned_ring if self._pinned_ring >= 0 else self._hov
        if 0 <= display_slot < n:
            dm = mods[display_slot]
            if not is_module_active(dm, dev_mode=self._dev,
                    test_mode=self.settings.get("test_mode", False)):
                display_slot = -1
        self._update_anim_ring(display_slot)
        # Im Bearbeitungsmodus gibt es KEINE Ausbreitungsanimation — der
        # komplette Ring (Hauptsegment + alle Slots) soll sofort fertig
        # da sein, damit man ohne Wartezeit Subkategorien verschieben
        # kann. Der Timer/State läuft im Hintergrund trotzdem normal
        # weiter (_update_anim_ring oben bleibt unverändert), damit beim
        # Verlassen des Edit-Modes nahtlos der tatsächliche Fortschritt
        # wieder greift, statt dass die Animation neu von 0 starten muss.
        anim_progress = 1.0 if self._edit_mode else self._anim_progress()

        for i, mod in enumerate(mods):
            ready     = is_module_active(mod, dev_mode=self._dev,
                            test_mode=self.settings.get("test_mode",False))
            hov       = self._hov == i and ready  # kein Hover bei gesperrten
            drag_over = self._drag_seg == i
            is_anim_ring = (i == display_slot)
            main_fill_t  = self._anim_main_fill(anim_progress) if is_anim_ring else 0.0
            # Vollfarbe braucht BEIDES: kompletten Ringdurchlauf (Glow,
            # zeitbasiert) UND dass die Maus aktuell direkt auf diesem
            # Hauptsegment steht — steht sie stattdessen im Außenring
            # (auf einem Slot), bleibt das Hauptsegment in der gedeckten
            # Zwischenfarbe stehen, behält aber seine Wachstumsgröße bei
            # (siehe ro unten), solange der Ring offen ist.
            main_glow_t  = (self._anim_main_full_glow(anim_progress)
                             if is_anim_ring and hov else 0.0)
            # Größe: voll gewachsen, solange die Maus direkt drauf ist
            # ODER der zugehörige Ring offen ist (Hover/Pin) — das ist
            # der dezente "dieser Ring ist aktiv"-Indikator, der bestehen
            # bleibt, auch wenn die Maus gerade im Außenring auf einem
            # Slot steht statt auf dem Hauptsegment selbst.
            grown     = (hov or is_anim_ring) and not self._edit_mode
            ro        = r_out + (7 if grown else 0)
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
                if dark:
                    base_fill = QColor("#2a2a2a")
                else:
                    # Hell: weißer Grund + Fraktionsfarbe 12% Deckkraft
                    base_fill = QColor(accent.red(), accent.green(), accent.blue(), 30)
                if main_fill_t > 0.0:
                    # Hover-Ausbreitungsanimation, zwei Stufen:
                    # 1) gedeckte Zwischenfarbe (ANIM_MID_ALPHA) — bewusst
                    #    transparent, damit sie sich von der späteren
                    #    Vollfarbe klar abhebt. Springt beim allerersten
                    #    Erscheinen direkt auf einen sichtbaren Mindest-
                    #    wert (ANIM_MIN_ALPHA), statt bei 0 zu starten —
                    #    sonst ist der Übergang in den ersten Prozenten
                    #    kaum wahrnehmbar und es wirkt, als poppe er erst
                    #    spät plötzlich auf.
                    # 2) main_glow_t blendet danach (erst NACHDEM der
                    #    Ring komplett einmal durchlaufen ist) weiter zur
                    #    kräftigen Vollfarbe (accent, alpha 255).
                    mid_alpha = int(self.ANIM_MIN_ALPHA + (self.ANIM_MID_ALPHA - self.ANIM_MIN_ALPHA) * main_fill_t)
                    a = int(mid_alpha + (255 - mid_alpha) * main_glow_t)
                    fill = QColor(accent.red(), accent.green(), accent.blue(), a)
                else:
                    fill = base_fill
                bpen = QPen(accent, 2.0 if main_glow_t >= 1.0 else 1.2)
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
                icon_col = accent
            elif not ready:
                icon_col = QColor(150, 150, 150, 100)
            elif main_glow_t >= 1.0:
                icon_col = QColor("#ffffff")
            else:
                icon_col = accent

            # Icon
            p.setPen(QPen(icon_col))
            p.setFont(QFont("Segoe UI Emoji", 19))
            p.drawText(QRectF(lx-30, ly-16, 60, 32),
                       Qt.AlignmentFlag.AlignCenter,
                       ICON_MAP.get(mod["icon"], "●"))

            # Edit: 6-Punkte Handle
            if self._edit_mode:
                p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 180)))
                p.setFont(QFont("Segoe UI", 11))
                p.drawText(QRectF(lx-8, ly - r_in*0.18, 16, 14),
                           Qt.AlignmentFlag.AlignCenter, "⠿")

            # Slot-Buchstabe (A-H) — feste Positions-Kennung, unabhängig
            # vom Modul, das gerade dort sitzt. Nur im Bearbeitungsmodus
            # sichtbar, damit man weiß, welchen Außenring ein Klick öffnet.
            if self._edit_mode:
                slot_letter = chr(ord('A') + i) if i < 26 else str(i)
                p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 200)))
                p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                p.drawText(QRectF(lx-14, ly - r_in*0.36, 28, 16),
                           Qt.AlignmentFlag.AlignCenter, f"Slot {slot_letter}")

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

        # Außenring (Unterfunktionen pro Hauptmodul) — ein eigener, fest
        # ausgerichteter Ring pro Hauptkategorie, aber es ist NIE mehr als
        # einer gleichzeitig sichtbar. Hover zeigt den Ring temporär; ein
        # Klick auf die Hauptkategorie pinnt ihn fest (siehe _pinned_ring),
        # bis Rechtsklick / Sub-Klick / Klick auf andere Hauptkategorie
        # ihn wieder schließt. Klick auf eine Hauptkategorie selbst
        # navigiert NICHT mehr — nur Klicks auf Unterfunktionen im
        # Außenring navigieren. Slot 0 liegt immer exakt mittig auf der
        # zugehörigen Hauptkategorie, danach im Uhrzeigersinn durchnum-
        # meriert. Unbelegte Slots zeigen "(Leer)" statt eines Namens.
        # (display_slot wurde bereits vor dem Hauptsegment-Loop oben
        # berechnet, da die Füllanimation des Hauptsegments selbst
        # davon abhängt.)

        if 0 <= display_slot < n:
            r_in2, r_out2 = self._sub_ring_dims(r_out, r_in)
            n_sub_slots   = self._sub_slot_count()
            i   = display_slot
            mod = mods[i]
            subs = self._ordered_subfunctions(mod["id"])
            main_mid = self._seg_mid_angle(i, n)

            # Welcher Slot wird aktuell von der Maus getroffen (für den
            # "voll leuchten + wachsen"-Effekt) — nutzt die zuletzt
            # bekannte Mausposition (_mouse_x/_mouse_y werden bei jedem
            # mouseMoveEvent aktualisiert, auch außerhalb von Drag-
            # Vorgängen). Im Edit-Mode kein Slot-Hover-Glanz, da dort
            # der Cursor zum Draggen gebraucht wird und volle Konsistenz
            # mit "ein Slot leuchtet" optisch verwirren würde.
            hovered_sub_j = (self._sub_slot_index_at(self._mouse_x, self._mouse_y, i)
                             if not self._edit_mode else -1)
            # Wachstum proportional zur Außenring-Dicke übertragen, statt
            # einen neuen Wert zu erfinden — gleiches Verhältnis wie beim
            # Hauptring (7px bei dessen Dicke r_out - r_in).
            sub_grow_px = 7 * ((r_out2 - r_in2) / (r_out - r_in))

            max_dist = n_sub_slots // 2
            for j in range(n_sub_slots):
                slot_t = self._anim_slot_fill(anim_progress, j, n_sub_slots)

                belegt = subs[j] is not None
                if not belegt:
                    if self._edit_mode and slot_t > 0.0:
                        # Im Bearbeitungsmodus bleiben unbelegte Slots als
                        # gestrichelter Platzhalter sichtbar — sonst sähe
                        # man nicht, wohin eine Subkategorie verschoben
                        # werden kann. Außerhalb des Edit-Modes (normaler
                        # Betrieb) bleiben sie komplett unsichtbar (siehe
                        # else/continue unten).
                        a_start, a_end = self._sub_slot_angles(main_mid, j)
                        sub_path = self._arc_path(cx, cy, r_out2, r_in2, a_start, a_end)
                        p.setBrush(QBrush(QColor(120, 120, 120, 14)))
                        pen = QPen(QColor(150, 150, 150, 90), 0.8, Qt.PenStyle.DashLine)
                        pen.setDashPattern([3, 3])
                        p.setPen(pen)
                        p.drawPath(sub_path)
                        slx, sly = self._arc_center(cx, cy, r_out2, r_in2, a_start, a_end)
                        p.setPen(QPen(QColor(150, 150, 150, 140)))
                        p.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
                        p.drawText(QRectF(slx-30, sly-13, 60, 16),
                                   Qt.AlignmentFlag.AlignCenter, "(Leer)")
                        p.setFont(QFont("Segoe UI", 6))
                        p.drawText(QRectF(slx-20, sly+3, 40, 12),
                                   Qt.AlignmentFlag.AlignCenter, f"#{j}")
                    # Unbelegte Slots werden außerhalb des Edit-Modes
                    # komplett unsichtbar gezeichnet — kein Rahmen, keine
                    # Füllung, kein Text. Die Ausbreitungsanimation
                    # (slot_t) läuft für sie GENAUSO weiter wie für
                    # belegte Slots (jeder Index wird unabhängig
                    # berechnet, es gibt keine Kettenabhängigkeit zu
                    # Nachbarn) — so bleibt das Timing der Ausbreitung
                    # exakt gleich, egal ob ein Slot belegt ist oder
                    # nicht, auch wenn hier (außerhalb Edit-Mode) nichts
                    # davon gezeichnet wird.
                    continue

                # Solange die Ausbreitung diesen Slot noch nicht erreicht
                # hat, wird er behandelt, als wäre er (noch) leer — Name
                # poppt erst synchron mit der Farbe auf.
                sub_name = subs[j]["name"] if slot_t > 0.0 else None

                if slot_t <= 0.0:
                    # Noch nicht von der Animation erreicht — komplett
                    # unsichtbar (kein Rahmen, keine Füllung, kein Text),
                    # damit der Eindruck eines sich aufbauenden Rings
                    # entsteht statt eines bereits fertigen Rings, der
                    # nur noch eingefärbt wird.
                    continue

                # "Maus direkt drauf"-Glanz — alle Slots in diesem Block
                # sind belegt (unbelegte wurden oben bereits überspru-
                # ngen), daher reicht hier der reine Hover-Vergleich.
                slot_hov = (j == hovered_sub_j)
                slot_r_out2 = r_out2 + (sub_grow_px if slot_hov else 0.0)

                visible_paths = self._sub_slot_visible_paths(
                    cx, cy, slot_r_out2, r_in2, main_mid, j, n_sub_slots, slot_t)
                if not visible_paths:
                    continue

                # Alle Slots, die hier ankommen, sind belegt UND
                # sichtbar (unbelegte/noch-nicht-erschienene wurden oben
                # bereits per continue übersprungen) — daher kein
                # zusätzlicher belegt/unbelegt-Zweig mehr nötig.
                if slot_hov:
                    # Maus direkt auf diesem Slot — voll aufleuchten,
                    # analog zum Hauptsegment-Vollglanz.
                    sub_fill = accent
                    sub_pen  = QPen(accent, 1.6)
                else:
                    # Sofort-Sprung auf ANIM_MIN_ALPHA-Äquivalent beim
                    # ersten Erscheinen, dann weiter Richtung ANIM_MID_ALPHA
                    # — sonst ist der Unterschied zur Grundfarbe in den
                    # ersten Prozenten von slot_t kaum wahrnehmbar (siehe
                    # gleiches Prinzip beim Hauptsegment oben).
                    eff_t = self.ANIM_MIN_ALPHA / self.ANIM_MID_ALPHA + \
                            (1 - self.ANIM_MIN_ALPHA / self.ANIM_MID_ALPHA) * slot_t
                    if dark:
                        # Von "#2a2a2a" Richtung gedeckter Fraktionsfarbe
                        # einblenden — reine Alpha-Überlagerung wäre auf
                        # dunklem Grund kaum sichtbar, daher Kanal-Lerp,
                        # ebenfalls mit Sofort-Sprung-Anteil (eff_t statt
                        # slot_t direkt).
                        base_c = QColor("#2a2a2a")
                        target_c = QColor(
                            int(base_c.red()   + (accent.red()   - base_c.red())   * (self.ANIM_MID_ALPHA / 255)),
                            int(base_c.green() + (accent.green() - base_c.green()) * (self.ANIM_MID_ALPHA / 255)),
                            int(base_c.blue()  + (accent.blue()  - base_c.blue())  * (self.ANIM_MID_ALPHA / 255)),
                        )
                        r = int(base_c.red()   + (target_c.red()   - base_c.red())   * eff_t)
                        g = int(base_c.green() + (target_c.green() - base_c.green()) * eff_t)
                        b = int(base_c.blue()  + (target_c.blue()  - base_c.blue())  * eff_t)
                        sub_fill = QColor(r, g, b)
                    else:
                        a = int(30 + (self.ANIM_MID_ALPHA - 30) * eff_t)
                        sub_fill = QColor(accent.red(), accent.green(), accent.blue(), a)
                    sub_pen  = QPen(accent, 1.0)

                # Nur die sichtbare(n) Teilfläche(n) füllen UND umranden —
                # die "Wasserlinie" (wachsende Kante) bekommt dadurch
                # automatisch ebenfalls einen Rahmen mit, das ist
                # gewünscht (sieht aus wie eine fortlaufend wachsende
                # Box). Bei Slot max_dist mit zwei Teilflächen werden
                # beide gezeichnet; sobald sie sich berühren, liefert
                # _sub_slot_visible_paths nur noch EINEN durchgehenden
                # Pfad zurück, wodurch automatisch keine Naht in der
                # Mitte mehr entsteht.
                p.setBrush(QBrush(sub_fill))
                p.setPen(sub_pen)
                for vp in visible_paths:
                    p.drawPath(vp)

                # Text wird auf die sichtbare Fläche geklippt — bei zwei
                # Teilflächen (Slot max_dist, noch nicht verschmolzen)
                # werden beide vereinigt, damit der Text in BEIDEN
                # Hälften anteilig sichtbar sein kann.
                clip_path = visible_paths[0]
                for vp in visible_paths[1:]:
                    clip_path = clip_path.united(vp)
                p.save()
                p.setClipPath(clip_path)

                a_start, a_end = self._sub_slot_angles(main_mid, j)
                slx, sly = self._arc_center(cx, cy, slot_r_out2, r_in2, a_start, a_end)
                if slot_hov:
                    p.setPen(QPen(QColor("#ffffff")))
                else:
                    p.setPen(QPen(accent))
                p.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
                p.drawText(QRectF(slx-30, sly-13, 60, 16),
                           Qt.AlignmentFlag.AlignCenter, sub_name)

                # Slot-Nummer (0, 1, 2, ...) — Slot 0 ist immer die Mitte
                # des zugehörigen Hauptsegments, danach im Uhrzeigersinn.
                # Nur im Bearbeitungsmodus sichtbar (Orientierungshilfe
                # beim Verschieben von Subkategorien) — im Normalbetrieb
                # nicht relevant für den Nutzer.
                if self._edit_mode:
                    p.setPen(QPen(QColor(150, 150, 150, 160)))
                    p.setFont(QFont("Segoe UI", 6))
                    p.drawText(QRectF(slx-20, sly+3, 40, 12),
                               Qt.AlignmentFlag.AlignCenter, f"#{j}")
                p.restore()

            # Schwebender Sub-Slot beim Drag — exakt analog zum Ghost-
            # Segment des Hauptrings, nur mit Außenring-Geometrie
            # (feste Slot-Breite statt 360°/n) und nur innerhalb des
            # Rings, der gerade gedraggt wird (self._sub_drag_start_ring).
            if (self._sub_dragging and self._sub_drag_src >= 0
                    and self._sub_drag_start_ring == i):
                dx = self._mouse_x - cx
                dy = self._mouse_y - cy
                mouse_angle = (90 - math.degrees(math.atan2(-dy, dx))) % 360
                # Winkel relativ zur Ringmitte, auf nächsten Sub-Slot
                # einrasten (gleiches Prinzip wie beim Hauptring).
                rel = (mouse_angle - main_mid) % 360
                target_j = round(rel / self.SUB_SLOT_WIDTH_DEG) % n_sub_slots
                if target_j != self._sub_drag_src:
                    self._sub_drag_target = target_j
                else:
                    self._sub_drag_target = -1

                ga_start, ga_end = self._sub_slot_angles(main_mid, target_j)
                ghost_path = self._arc_path(cx, cy, r_out2 + 8, r_in2, ga_start, ga_end)
                ghost_fill = QColor(accent.red(), accent.green(), accent.blue(), 130)
                p.setBrush(QBrush(ghost_fill))
                p.setPen(Qt.PenStyle.NoPen)
                p.drawPath(ghost_path)
                p.setBrush(Qt.BrushStyle.NoBrush)
                gpen = QPen(accent, 2.0, Qt.PenStyle.DashLine)
                gpen.setDashPattern([4, 3])
                p.setPen(gpen)
                p.drawPath(ghost_path)
                glx, gly = self._arc_center(cx, cy, r_out2 + 8, r_in2, ga_start, ga_end)
                src_sub = subs[self._sub_drag_src]
                p.setPen(QPen(QColor("#ffffff")))
                p.setFont(QFont("Segoe UI", 7, QFont.Weight.Medium))
                p.drawText(QRectF(glx-30, gly-13, 60, 16),
                           Qt.AlignmentFlag.AlignCenter,
                           src_sub["name"] if src_sub else "(Leer)")

                if self._sub_drag_target >= 0:
                    ta_start, ta_end = self._sub_slot_angles(main_mid, self._sub_drag_target)
                    tgt_path = self._arc_path(cx, cy, r_out2, r_in2, ta_start, ta_end)
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
            if self._hov >= 0:
                p.setOpacity(0.20)
            else:
                p.setOpacity(1.0)
            p.drawPixmap(int(cx - scaled.width()/2),
                         int(cy - scaled.height()/2), scaled)
            p.setOpacity(1.0)

        if self._hov >= 0:
            mods2 = self._ordered_modules()
            if self._hov < len(mods2):
                hm = mods2[self._hov]
                hr = is_module_active(hm,
                         dev_mode=self._dev,
                         test_mode=self.settings.get("test_mode", False))
                if hr:
                    # Maus direkt auf einem belegten Sub-Slot im Außenring
                    # dieses Hauptsegments? Dann zusätzlich den Sub-Namen
                    # kleiner darunter anzeigen — gleiches Prinzip wie
                    # beim Hauptnamen selbst, nur eine Ebene "kleiner".
                    sub_label = None
                    j = self._sub_slot_index_at(self._mouse_x, self._mouse_y, self._hov)
                    if j >= 0:
                        subs_here = self._ordered_subfunctions(hm["id"])
                        if j < len(subs_here) and subs_here[j] is not None:
                            n_sub_here = self._sub_slot_count()
                            slot_t_here = self._anim_slot_fill(anim_progress, j, n_sub_here)
                            if slot_t_here >= 1.0:
                                sub_label = subs_here[j]["name"]

                    # Hauptname sitzt IMMER etwas höher als die exakte
                    # Mitte (nicht erst, wenn ein Sub-Name dazukommt) —
                    # so bleibt die Position stabil und es gibt keinen
                    # Sprung nach oben, sobald die Maus auf einen Slot
                    # wandert. Der Sub-Name bekommt dadurch dauerhaft
                    # reservierten Platz darunter.
                    main_y_offset = -12
                    sub_gap = 12  # zusätzlicher Luft-Abstand zwischen
                                  # Haupt- und Sub-Name (über die reine
                                  # Zeilenhöhe hinaus)
                    main_name = get_module_name(hm["id"])

                    if dark:
                        p.setPen(QPen(QColor(0, 0, 0, 120)))
                        p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
                        p.drawText(QRectF(cx - r_in + 10, cy - 14 + main_y_offset, (r_in - 8)*2, 32),
                                   Qt.AlignmentFlag.AlignCenter, main_name)
                    p.setPen(QPen(accent))
                    p.setFont(QFont("Segoe UI", 18, QFont.Weight.Black))
                    p.drawText(QRectF(cx - r_in + 8, cy - 16 + main_y_offset, (r_in - 8)*2, 32),
                               Qt.AlignmentFlag.AlignCenter, main_name)

                    if sub_label:
                        sub_y = cy - 16 + main_y_offset + 30 + sub_gap
                        if dark:
                            p.setPen(QPen(QColor(0, 0, 0, 120)))
                            p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
                            p.drawText(QRectF(cx - r_in + 10, sub_y - 1, (r_in - 8)*2, 20),
                                       Qt.AlignmentFlag.AlignCenter, sub_label)
                        p.setPen(QPen(accent))
                        p.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
                        p.drawText(QRectF(cx - r_in + 8, sub_y, (r_in - 8)*2, 20),
                                   Qt.AlignmentFlag.AlignCenter, sub_label)
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

        if self._sub_dragging:
            self.update()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if (self._edit_mode and
                event.buttons() & Qt.MouseButton.LeftButton and
                self._sub_drag_start_pos is not None):
            if (event.position().toPoint() - self._sub_drag_start_pos).manhattanLength() > 8:
                # Custom Sub-Drag starten — analog zum Hauptring-Drag.
                self._sub_dragging    = True
                self._sub_drag_src    = self._sub_drag_start_slot
                self._sub_drag_target = -1
                self.update()
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

        # Solange ein Ring per Klick angepinnt ist, ignoriert Hover
        # komplett jede andere Hauptkategorie — der Ring bleibt fix,
        # der Cursor darf trotzdem frei über den Donut wandern (z.B. um
        # eine Unterfunktion auf der "anderen Seite" des Rings zu
        # erreichen, ohne dabei den Hauptring abzufahren).
        if self._pinned_ring >= 0:
            if self._edit_mode:
                self.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                cx, cy, r_out, r_in = self._dims()
                r_in2, r_out2 = self._sub_ring_dims(r_out, r_in)
                dist = math.hypot(event.position().x() - cx,
                                   event.position().y() - cy)
                in_pinned_band = r_in2 <= dist <= r_out2
                sub_id = (self._sub_seg_at(event.position().x(),
                                            event.position().y(),
                                            self._pinned_ring)
                          if in_pinned_band else None)
                self.setCursor(Qt.CursorShape.PointingHandCursor if sub_id
                               else Qt.CursorShape.ArrowCursor)
                # Gleiches Repaint-Problem wie im normalen Hover-Zweig:
                # self._hov ändert sich hier nie (der Ring ist ja schon
                # angepinnt), daher muss der Sub-Slot-Wechsel separat
                # erkannt und ein update() ausgelöst werden, sonst bleibt
                # der "Slot unter der Maus leuchtet voll"-Effekt einge-
                # froren, während man durch die Slots wandert.
                new_sub_hov = (self._sub_slot_index_at(
                                   event.position().x(), event.position().y(),
                                   self._pinned_ring)
                               if in_pinned_band else -1)
                if new_sub_hov != self._last_hovered_sub:
                    self._last_hovered_sub = new_sub_hov
                    self.update()
            return

        # Außenring bleibt sichtbar, solange die Maus sich entweder auf
        # einem Hauptsegment ODER innerhalb des aktuell gezeigten Außen-
        # ring-Bandes befindet (nicht nur exakt auf dem Hauptsegment) —
        # sonst verschwindet er, sobald man von Hauptring in Außenring
        # wechselt, weil dort kein Hauptsegment mehr getroffen wird.
        cx, cy, r_out, r_in = self._dims()
        r_in2, r_out2 = self._sub_ring_dims(r_out, r_in)
        dist = math.hypot(event.position().x() - cx, event.position().y() - cy)
        in_outer_band = r_in2 <= dist <= r_out2

        if seg >= 0:
            new_hov = seg
        elif in_outer_band and self._hov >= 0:
            new_hov = self._hov  # in den Außenring gewechselt — Anzeige beibehalten
        else:
            new_hov = -1

        # Welcher Sub-Slot wird aktuell getroffen — wird benutzt, um ein
        # Repaint anzufordern, wenn sich NUR die Position innerhalb des
        # Außenrings ändert (Hauptsegment bleibt gleich, self._hov ändert
        # sich also NICHT, paintEvent würde sonst nie neu aufgerufen und
        # der "Slot unter der Maus leuchtet voll"-Effekt aus Schritt 2
        # bliebe eingefroren, während man durch die Slots wandert).
        new_sub_hov = (self._sub_slot_index_at(event.position().x(),
                                                event.position().y(), new_hov)
                       if in_outer_band and new_hov >= 0 else -1)

        hov_changed = new_hov != self._hov
        sub_hov_changed = new_sub_hov != self._last_hovered_sub
        self._last_hovered_sub = new_sub_hov
        if hov_changed:
            self._hov = new_hov
        if hov_changed or sub_hov_changed:
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
        elif in_outer_band and self._hov >= 0:
            sub_id = self._sub_seg_at(event.position().x(),
                                       event.position().y(), self._hov)
            self.setCursor(Qt.CursorShape.PointingHandCursor if sub_id
                           else Qt.CursorShape.ArrowCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event):
        was_dragging     = self._dragging
        was_sub_dragging = self._sub_dragging

        if self._sub_dragging and event.button() == Qt.MouseButton.LeftButton:
            self._sub_dragging = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if (self._sub_drag_target >= 0 and self._sub_drag_src >= 0
                    and self._sub_drag_start_ring >= 0
                    and self._sub_drag_target != self._sub_drag_src):
                mods = self._ordered_modules()
                ring = self._sub_drag_start_ring
                if ring < len(mods):
                    module_id = mods[ring]["id"]
                    donut = self.parent()
                    while donut and not isinstance(donut, HomeDonut):
                        donut = donut.parent()
                    if donut:
                        donut.swap_subfunctions(
                            module_id, self._sub_drag_src, self._sub_drag_target)
            self._sub_drag_src    = -1
            self._sub_drag_target = -1
            self._sub_drag_start_ring = -1
            self._sub_drag_start_slot = -1
            self.update()
        self._sub_drag_start_pos = None

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
        self._drag_start_seg = -1
        self._drag_start_pos = None

        # Toggle: war der gerade abgeschlossene Klick ein REINER Klick
        # (kein Haupt- oder Sub-Drag) und begann er auf der bereits
        # offenen Hauptkategorie, schließt er deren Ring jetzt. Ein
        # Klick, aus dem tatsächlich ein Drag wurde, löst das Toggle
        # NICHT aus — sonst würde z.B. das Verschieben einer Kategorie
        # gleichzeitig ungewollt ihren eigenen Ring zuklappen.
        if (event.button() == Qt.MouseButton.LeftButton
                and not was_dragging and not was_sub_dragging
                and self._click_toggle_candidate >= 0
                and self._click_toggle_candidate == self._pinned_ring):
            self._pinned_ring = -1
            self._hov = -1
            self.update()
        self._click_toggle_candidate = -1

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            # Rechtsklick irgendwo schließt einen angepinnten Ring.
            self._click_toggle_candidate = -1
            if self._pinned_ring >= 0:
                self._pinned_ring = -1
                self._hov = -1
                self.update()
            return

        if event.button() != Qt.MouseButton.LeftButton:
            return

        mx, my = event.position().x(), event.position().y()
        visible_ring = self._pinned_ring if self._pinned_ring >= 0 else self._hov

        if self._edit_mode:
            # Im Bearbeitungsmodus zeigt ein Klick auf eine Hauptkategorie
            # genau wie im Normalmodus deren Außenring an (nur ohne
            # Hover-Vorschau, da die Maus zum Draggen gebraucht wird).
            # Liegt der Klick auf EINEM SLOT (belegt oder leer) des
            # bereits sichtbaren Rings, wird stattdessen ein Sub-Drag
            # vorbereitet — leere Slots sind als Start/Ziel ebenfalls
            # gültig, damit Unterfunktionen auch auf freie Positionen
            # verschoben werden können (und umgekehrt).
            if visible_ring >= 0:
                mods = self._ordered_modules()
                visible_mod = (mods[visible_ring]
                               if visible_ring < len(mods) else None)
                if visible_mod:
                    cx, cy, r_out, r_in = self._dims()
                    r_in2, r_out2 = self._sub_ring_dims(r_out, r_in)
                    dist = math.hypot(mx - cx, my - cy)
                    if r_in2 <= dist <= r_out2:
                        slot_idx = self._sub_slot_index_at(mx, my, visible_ring)
                        if slot_idx >= 0:
                            self._sub_drag_start_ring = visible_ring
                            self._sub_drag_start_slot = slot_idx
                            self._sub_drag_start_pos  = event.position().toPoint()
                        # Kein Hauptkategorie-Klick — alter Toggle-
                        # Kandidat aus einem vorherigen Klick darf hier
                        # nicht "überleben" und später fälschlich ein
                        # Toggle auslösen.
                        self._click_toggle_candidate = -1
                        # Klick im Außenring-Band trifft nie ein Haupt-
                        # segment — hier early-return, damit unten nicht
                        # versehentlich ein anderes Hauptsegment erkannt
                        # (und der Ring dadurch ungewollt gewechselt) wird.
                        return

            seg = self._seg_at(mx, my)
            if seg < 0:
                # Linksklick irgendwohin (kein Hauptsegment, kein Slot
                # im sichtbaren Ring getroffen) schließt einen offenen
                # Ring — gleiches Verhalten wie Rechtsklick.
                self._click_toggle_candidate = -1
                if self._pinned_ring >= 0:
                    self._pinned_ring = -1
                    self._hov = -1
                    self.update()
                return
            mods = self._ordered_modules()
            if seg >= len(mods):
                return
            # Merken, ob bereits GENAU dieses Hauptsegment offen war —
            # wird in mouseReleaseEvent ausgewertet: war es ein REINER
            # Klick (kein Drag), schließt er den Ring (Toggle). Wurde
            # daraus ein Drag, gilt das Toggle nicht (siehe dort).
            self._click_toggle_candidate = (seg if seg == self._pinned_ring
                                             else -1)
            self._drag_start_seg = seg
            self._drag_start_pos = event.position().toPoint()
            # Gleiche Pin-Logik wie im Normalmodus — 1:1, nur ohne Hover.
            self._pinned_ring = seg
            self._hov         = seg
            self.update()
            return

        # ── Normalmodus ─────────────────────────────────────────────
        # Klick auf eine Unterfunktion hat Vorrang — unabhängig davon,
        # ob der Ring gerade nur per Hover sichtbar ist oder bereits
        # angepinnt wurde (gleiche "welcher Ring ist sichtbar"-Logik wie
        # im paintEvent: gepinnt schlägt Hover, sonst gilt Hover).
        # Klick außerhalb dieses Rings (z.B. auf eine andere Haupt-
        # kategorie) fällt unten in die normale Behandlung durch.
        if visible_ring >= 0:
            mods = self._ordered_modules()
            visible_mod = (mods[visible_ring]
                           if visible_ring < len(mods) else None)
            if visible_mod:
                sub_id = self._sub_seg_at(mx, my, visible_ring)
                if sub_id is not None:
                    self.subfunction_clicked.emit(visible_mod["id"], sub_id)
                    self._pinned_ring = -1
                    self._hov = -1
                    self.update()
                    return

        seg = self._seg_at(mx, my)
        if seg < 0:
            # Linksklick irgendwohin (kein Hauptsegment, kein Slot im
            # sichtbaren Ring getroffen) schließt einen offenen Ring —
            # gleiches Verhalten wie Rechtsklick.
            if self._pinned_ring >= 0:
                self._pinned_ring = -1
                self._hov = -1
                self.update()
            return
        mods = self._ordered_modules()
        if seg >= len(mods):
            return
        mod = mods[seg]
        if seg == self._pinned_ring:
            # Erneuter Klick auf die bereits offene Hauptkategorie
            # schließt ihren Ring (Toggle), statt ihn einfach erneut
            # zu pinnen (was optisch keinen Unterschied gemacht hätte).
            self._pinned_ring = -1
            self._hov = -1
            self.update()
            return
        if is_module_active(mod, dev_mode=self._dev,
                test_mode=self.settings.get("test_mode", False)):
            # Klick auf eine Hauptkategorie navigiert NICHT mehr direkt —
            # er pinnt nur noch deren Außenring fest (Wechsel, falls
            # zuvor schon ein anderer Ring gepinnt war). Die eigentliche
            # Navigation passiert ausschließlich über Klicks auf
            # Unterfunktionen im Außenring (siehe oben).
            self._pinned_ring = seg
            self._hov         = seg
            self.update()

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


class CornerPanel(QWidget):
    """Eckform für eine Statistik-Anzeige (Accounts, Industrie Jobs, ...).

    Vollständig eigenständig, keine Abhängigkeit zu home_grid.StatCard.
    Liegt als durchsichtiges Vollflächen-Overlay genau über dem Donut und
    malt NUR in seiner eigenen Bildschirm-Ecke etwas — der Rest bleibt
    transparent.

    Einfaches abgerundetes Rechteck statt einer an den Außenring ange-
    passten Kurvenform — die Kurvenform hatte einen unauflösbaren
    Zielkonflikt zwischen kurzem Stummel und Ringabstand (mathematisch
    nachgewiesen: bei einem zur Ecke versetzten Rundungs-Mittelpunkt
    bedeutet ein größerer Radius IMMER mehr Reichweite zum Ring hin,
    egal ob Kreis oder Ellipse). Beim Rechteck ist nur die EINE Ecke
    relevant, die dem Donut am nächsten liegt — ein einziger Abstands-
    Check statt Kurven-Abtastung, dadurch deutlich robuster.
    """

    GAP_TO_RING   = 50   # Mindestabstand der donut-nahen Rechteck-Ecke
                         # zum Außenring (einfacher Punkt-Check).
    CORNER_RADIUS = 14   # Radius der abgerundeten Rechteck-Ecken (rein
                         # optisch, unabhängig vom Donut).
    SIZE_FRACTION = 0.62 # Wie viel des verfügbaren Platzes (bis zum
                         # Außenring minus GAP_TO_RING) tatsächlich genutzt
                         # wird — < 1.0 lässt zusätzlich Luft zwischen den
                         # vier Rechtecken selbst.

    def __init__(self, donut: "DonutWidget", corner: str,
                 label: str, value: str, parent=None):
        super().__init__(parent)
        self._donut  = donut
        self._corner = corner  # "tl" | "tr" | "bl" | "br"
        self._label  = label
        self._value  = value
        self._faction = donut._faction
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_value(self, v: str):
        self._value = v
        self.update()

    def set_faction(self, faction: str):
        self._faction = faction
        self.update()

    def _signs(self):
        sign_x = 1 if self._corner in ("tl", "bl") else -1
        sign_y = 1 if self._corner in ("tl", "tr") else -1
        return sign_x, sign_y

    def _geometry(self):
        """Liefert (ox, oy, sign_x, sign_y, w, h) — Eckpunkt und Größe
        des Rechtecks in eigenen (lokalen) Koordinaten. Die Größe wird so
        gewählt, dass die donut-nahe Ecke mindestens GAP_TO_RING Abstand
        zum Außenring-Radius hat — ein einziger Punkt-Check reicht,
        da bei einem Rechteck immer genau diese eine Ecke am nächsten
        zum Mittelpunkt liegt."""
        d_cx, d_cy, r_out, r_in = self._donut._dims()
        r_in2, r_out2 = self._donut._sub_ring_dims(r_out, r_in)
        cx, cy = d_cx, d_cy

        sign_x, sign_y = self._signs()
        ox = 0 if sign_x > 0 else self.width()
        oy = 0 if sign_y > 0 else self.height()

        # Verfügbarer Platz pro Achse bis kurz vor den Außenring.
        avail_w = abs(ox - cx) - self.GAP_TO_RING
        avail_h = abs(oy - cy) - self.GAP_TO_RING
        if avail_w <= 0 or avail_h <= 0:
            return ox, oy, sign_x, sign_y, 0, 0

        w = avail_w * self.SIZE_FRACTION
        h = avail_h * self.SIZE_FRACTION

        # Sicherstellen, dass die nahe Ecke (w,h) wirklich GAP_TO_RING
        # vom Außenring entfernt bleibt — einfache, robuste Iteration
        # statt Algebra: so lange schrittweise verkleinern, bis der
        # Punkt-Check passt (maximal 30 Schritte, terminiert garantiert).
        target = r_out2 + self.GAP_TO_RING
        for _ in range(30):
            near_x = ox + sign_x*w
            near_y = oy + sign_y*h
            if math.hypot(near_x-cx, near_y-cy) >= target:
                break
            w *= 0.92
            h *= 0.92

        return ox, oy, sign_x, sign_y, w, h

    def paintEvent(self, event):
        ox, oy, sign_x, sign_y, w, h = self._geometry()
        if w <= 0 or h <= 0:
            return  # Fenster aktuell zu klein für diese Geometrie

        f = FACTIONS.get(self._faction, FACTIONS["caldari"])
        accent = QColor(f["accent"])
        dark_fill = QColor("#242424")

        rect_x = ox if sign_x > 0 else ox - w
        rect_y = oy if sign_y > 0 else oy - h
        rect = QRectF(rect_x, rect_y, w, h)

        path = QPainterPath()
        path.addRoundedRect(rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(dark_fill))
        p.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 90), 1.5))
        p.drawPath(path)

        # Akzentstreifen am äußeren (donut-fernen) Rand — wie früher bei
        # den rechteckigen Karten: eine schmale, farbige Linie INNERHALB
        # der Form, nicht an der gekrümmten/inneren Seite.
        stripe_w = 3
        if sign_x > 0:
            stripe = QRectF(rect_x, rect_y, stripe_w, h)
        else:
            stripe = QRectF(rect_x+w-stripe_w, rect_y, stripe_w, h)
        p.fillRect(stripe, QBrush(accent))

        # Beschriftung
        text_x = rect_x + 16
        text_y = rect_y + 16
        p.setPen(QPen(QColor(f["border"])))
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(text_x, text_y, w-32, 18),
                   Qt.AlignmentFlag.AlignLeft, self._label)
        p.setPen(QPen(accent))
        p.setFont(QFont("Segoe UI", 18, QFont.Weight.DemiBold))
        p.drawText(QRectF(text_x, text_y+18, w-32, 28),
                   Qt.AlignmentFlag.AlignLeft, self._value)
        p.end()



class _DonutStage(QWidget):
    """Hält Donut und die vier Eckformen exakt übereinander (volle Größe
    für alle), statt sie wie in einem normalen Layout nebeneinander
    anzuordnen. Nötig, damit die Eckformen auf die echte, aktuelle
    Donut-Geometrie zugreifen können. Der Donut bleibt dabei unverändert
    in voller Größe — etwaiger Platzbedarf wird ausschließlich innerhalb
    der Eckform selbst gelöst (siehe CornerPanel), nicht am Donut."""

    def __init__(self, donut: QWidget, corner_panels: list, parent=None):
        super().__init__(parent)
        self._donut = donut
        self._corner_panels = corner_panels
        donut.setParent(self)
        for cp in corner_panels:
            cp.setParent(self)
            cp.raise_()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._donut.setGeometry(0, 0, self.width(), self.height())
        for cp in self._corner_panels:
            cp.setGeometry(0, 0, self.width(), self.height())


class HomeDonut(QWidget):
    module_opened       = pyqtSignal(str)
    subfunction_opened  = pyqtSignal(str, str)  # (module_id, sub_id)

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        self._edit_banner = QLabel("✏  Bearbeitungsmodus — Segmente per Drag & Drop verschieben")
        self._edit_banner.hide()
        lay.addWidget(self._edit_banner)

        # Donut + vier Eckformen liegen exakt übereinander (siehe
        # _DonutStage), nicht nebeneinander wie bei einem normalen
        # Layout — die Eckformen greifen direkt auf die echte Donut-
        # Geometrie (Mittelpunkt, Außenring-Radius) zu.
        self._donut = DonutWidget(self.settings)
        self._donut.module_clicked.connect(self.module_opened)
        self._donut.subfunction_clicked.connect(self.subfunction_opened)

        self._corner_panels = []
        for corner, key, val in [
            ("tl", "home.accounts",      "2"),
            ("tr", "home.pi_colonies",   "—"),
            ("bl", "home.industry_jobs", "—"),
            ("br", "home.intel_alerts",  "0"),
        ]:
            cp = CornerPanel(self._donut, corner, t(key), val)
            self._corner_panels.append(cp)

        self._stage = _DonutStage(self._donut, self._corner_panels)
        lay.addWidget(self._stage, stretch=1)

    def retranslate(self):
        for cp, key in zip(self._corner_panels, [
            "home.accounts", "home.pi_colonies",
            "home.industry_jobs", "home.intel_alerts",
        ]):
            cp._label = t(key)
            cp.update()
        self._donut.update()

    def set_faction(self, faction: str):
        self.settings["faction"] = faction
        for cp in getattr(self, "_corner_panels", []):
            cp.set_faction(faction)
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

    def swap_subfunctions(self, module_id: str, src_slot: int, dst_slot: int):
        """Dünner Wrapper um die zentrale, layoutübergreifend geteilte
        Funktion swap_subfunctions() in core/config.py — ergänzt
        Speichern + Repaint, die layoutspezifisch bleiben."""
        if swap_subfunctions(self.settings, module_id, src_slot, dst_slot,
                              self._donut._sub_slot_count()):
            cfg.save(self.settings)
            self._donut.update()