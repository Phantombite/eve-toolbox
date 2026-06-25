"""
Topbar — Logo, Tabs, Charakter, Einstellungen.
"""
from core import logger as _logger
_log = _logger.get("topbar")

from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QPushButton,
                              QFrame, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QTimer
from PyQt6.QtGui import QCursor, QIcon, QPixmap, QColor, QPainter, QPen, QBrush, QFont, QPainterPath
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "icons"

from core.config import APP_NAME, FACTIONS, MODULES
from core.i18n import t
from ui.settings_panel import SettingsPanel
from ui.account_popup import AccountPopup
from ui.unlock_popup import UnlockPopup
from core import crypto_vault as _vault


class HomeTabButton(QWidget):
    """Home-Tab mit Fraktionslogo oben und 'Home' Text darunter."""
    clicked = __import__('PyQt6.QtCore', fromlist=['pyqtSignal']).pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import QVBoxLayout
        self._checked = True
        self._pixmap  = None
        self._hov     = False
        self._accent  = "#185FA5"
        self._blink   = False
        self._blink_on= False
        self.setFixedWidth(54)
        self.setFixedHeight(40)
        self.setCursor(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.CursorShape.PointingHandCursor)

    def setChecked(self, v: bool):
        self._checked = v
        self.update()

    def set_blink(self, v: bool):
        self._blink    = v
        self._blink_on = False
        if v:
            if not hasattr(self, '_blink_timer'):
                from PyQt6.QtCore import QTimer
                self._blink_timer = QTimer()
                self._blink_timer.timeout.connect(self._do_blink)
            self._blink_timer.start(600)
        else:
            if hasattr(self, '_blink_timer'):
                self._blink_timer.stop()
            self._blink_on = False
            self.update()

    def _do_blink(self):
        self._blink_on = not self._blink_on
        self.update()

    def isChecked(self): return self._checked

    def setPixmap(self, pm):
        self._pixmap = pm
        self.update()

    def mousePressEvent(self, event):
        if event.button() == __import__('PyQt6.QtCore', fromlist=['Qt']).Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def setHovered(self, v: bool):
        self._hov = v
        self.update()

    def enterEvent(self, event):
        self._hov = True
        self.update()

    def leaveEvent(self, event):
        self._hov = False
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor, QPen, QFont
        from PyQt6.QtCore import Qt, QRect, QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Hintergrund wenn aktiv
        if self._checked:
            dark = self.palette().color(
                __import__('PyQt6.QtGui', fromlist=['QPalette']).QPalette.ColorRole.Window
            ).lightness() < 128
            p.fillRect(0, 0, w, h, QColor("#ffffff" if not dark else "#1a1a1a"))

        hov = getattr(self, "_hov", False)

        if hov:
            # Hover: t("nav.home") Text zentriert
            p.setFont(QFont("Segoe UI", 10, QFont.Weight.Medium))
            acc = QColor(getattr(self, "_accent", "#185FA5"))
            p.setPen(QPen(acc))
            p.drawText(QRect(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, t("nav.home"))
        else:
            # Normal: Logo groß zentriert
            if self._pixmap and not self._pixmap.isNull():
                pm = self._pixmap.scaled(28, 28,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap((w - pm.width())//2, (h - pm.height())//2, pm)

        # Blink-Punkt für ungelesene Nachrichten
        if getattr(self, "_blink_on", False):
            acc = QColor(getattr(self, "_accent", "#185FA5"))
            p.setBrush(QBrush(acc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(w-8, 4, 7, 7)

        # Aktiver Unterstrich
        if self._checked:
            acc = QColor(getattr(self, "_accent", "#185FA5"))
            p.fillRect(0, h-2, w, 2, acc)

        p.end()


class GearButton(QWidget):
    """Zahnrad-Button — immun gegen globale QPushButton Stylesheets."""
    clicked = __import__('PyQt6.QtCore', fromlist=['pyqtSignal']).pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hov       = False
        self._checked   = False   # True = zugehöriges Fenster ist offen
        self._blink_on  = False
        self._has_unread= False
        self._accent    = "#185FA5"
        self.setFixedSize(30, 30)

    def set_active(self, v: bool):
        self._checked = v
        self.update()
        self.setCursor(__import__('PyQt6.QtCore', fromlist=['Qt']).Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def mousePressEvent(self, event):
        # Togglet self._checked NICHT mehr selbst — set_active() wird von
        # jedem verbundenen Handler (z.B. _toggle_settings/_toggle_bell_popup)
        # ohnehin sofort danach mit dem tatsächlichen Zustand aufgerufen.
        # Der vorherige Eigen-Toggle hier war redundant und ein Risiko für
        # künftige Handler, die set_active() vergessen könnten.
        if event.button() == __import__('PyQt6.QtCore', fromlist=['Qt']).Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def enterEvent(self, event):
        self._hov = True
        self.update()

    def leaveEvent(self, event):
        self._hov = False
        self.update()

    def paintEvent(self, event):
        from PyQt6.QtCore import Qt, QRectF
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        acc  = QColor(getattr(self, "_accent", "#185FA5"))
        is_bell = getattr(self, "_symbol", "⚙") == "🔔"
        blink_on = getattr(self, "_blink_on", False)

        # Rahmen: immer bei Hover/aktiv, bei Glocke auch beim Blinken
        show_border = self._hov or self._checked or (is_bell and blink_on)
        if show_border:
            path = QPainterPath()
            path.addRoundedRect(QRectF(1, 1, w-2, h-2), 6, 6)
            fill = QColor(acc.red(), acc.green(), acc.blue(), 40 if blink_on else 20)
            p.fillPath(path, QBrush(fill))
            p.setBrush(Qt.BrushStyle.NoBrush)
            pen_w = 2.0 if blink_on else 1.5
            p.setPen(QPen(acc, pen_w))
            p.drawPath(path)

        # Symbol
        symbol = getattr(self, "_symbol", "⚙")
        p.setFont(QFont("Segoe UI Emoji", 15))
        p.setPen(QPen(acc))
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, symbol)

        # Roter Punkt bei Glocke wenn ungelesen
        if is_bell and getattr(self, "_has_unread", False):
            p.setBrush(QBrush(QColor("#ff3333")))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(w-9, 3, 8, 8)

        p.end()

    def set_accent(self, color: str):
        self._accent = color
        self.update()


class Topbar(QWidget):
    home_clicked     = pyqtSignal()
    faction_changed  = pyqtSignal(str)
    dev_mode_changed = pyqtSignal(bool)
    layout_changed   = pyqtSignal(str)
    theme_changed    = pyqtSignal(str)
    edit_mode_changed  = pyqtSignal(bool)
    open_settings      = pyqtSignal()
    open_bell_popup    = pyqtSignal()
    open_account_settings = pyqtSignal()
    account_changed    = pyqtSignal(dict)
    account_clicked    = pyqtSignal()

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._tabs: dict[str, tuple] = {}
        self.setObjectName("Topbar")
        self.setFixedHeight(40)
        self._build()
        # Initialen Repaint nach erstem Show erzwingen
        QTimer.singleShot(100, self._force_repaint)

    def _force_repaint(self):
        self.update()
        self.repaint()
        # Logo explizit neu zeichnen
        for child in self.findChildren(__import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel):
            child.update()
            child.repaint()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 12, 0)
        lay.setSpacing(0)

        # Puls + Logo
        pulse = QLabel("●")
        pulse.setStyleSheet("color: #1D9E75; font-size: 8px; padding-right: 6px;")
        lay.addWidget(pulse)

        logo = QLabel(APP_NAME)
        logo.setObjectName("TopbarLogo")
        logo.setMinimumWidth(180)
        lay.addWidget(logo)
        lay.addWidget(self._vline())

        # Home Tab — Fraktionslogo oben, t("nav.home") darunter
        self._home_btn = HomeTabButton(self)
        self._home_btn.clicked.connect(self.home_clicked)
        lay.addWidget(self._home_btn)
        self._update_home_logo(self.settings.get("faction", "caldari"))

        # Dynamische Tabs
        self._tabs_widget = QWidget()
        self._tabs_lay = QHBoxLayout(self._tabs_widget)
        self._tabs_lay.setContentsMargins(0, 0, 0, 0)
        self._tabs_lay.setSpacing(0)
        lay.addWidget(self._tabs_widget)

        lay.addStretch()

        # Charakter — Avatar + Name + Omega Badge
        self._char_widget = QWidget()
        self._char_widget.setObjectName("CharBtn")
        self._char_widget.setCursor(Qt.CursorShape.PointingHandCursor)
        self._faction_for_char = self.settings.get("faction", "caldari")
        char_lay = QHBoxLayout(self._char_widget)
        char_lay.setContentsMargins(8, 4, 8, 4)
        char_lay.setSpacing(6)

        # Avatar Kreis
        self._avatar = QLabel("?")
        self._avatar.setFixedSize(24, 24)
        self._avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._update_avatar_style(self.settings.get("faction", "caldari"))
        char_lay.addWidget(self._avatar)

        # Name — als Instanzvariable speichern damit wir nach Login aktualisieren können
        active_name = self._current_display_name()
        self._name_lbl = QLabel(active_name)
        self._name_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        char_lay.addWidget(self._name_lbl)

        # Omega Badge
        omega = QLabel("Ω")
        omega.setFixedSize(18, 18)
        omega.setAlignment(Qt.AlignmentFlag.AlignCenter)
        omega.setStyleSheet(
            "background: #FAC775; color: #633806; border-radius: 9px;"
            "font-size: 10px; font-weight: 700;"
        )
        char_lay.addWidget(omega)

        # Pfeil
        arrow = QLabel("▾")
        arrow.setStyleSheet("font-size: 10px; color: #888;")
        char_lay.addWidget(arrow)

        # Account Popup erstellen (nur sichtbar wenn Vault entsperrt ist)
        self._account_popup = AccountPopup(self.settings)
        self._account_popup.account_changed.connect(self._on_account_changed)
        self._account_popup.open_settings.connect(self.open_account_settings)
        self._account_popup.hide()

        # Entschlüsselungs-Popup (sichtbar solange Vault gesperrt ist)
        self._unlock_popup = UnlockPopup(self.settings)
        self._unlock_popup.unlocked.connect(self._on_vault_unlocked)
        self._unlock_popup.open_security.connect(self.open_account_settings)
        self._unlock_popup.hide()

        self._char_widget.mousePressEvent = lambda e: self._show_account_popup()
        lay.addWidget(self._char_widget)
        # Initial Stil setzen
        # Kasten initial unsichtbar — erscheint nur beim Hover
        self._char_widget.setStyleSheet("QWidget#CharBtn { border: none; border-radius: 6px; }")
        self._char_faction = self.settings.get("faction", "caldari")

        def _char_enter(e):
            f2 = FACTIONS.get(self._char_faction, FACTIONS["caldari"])
            self._char_widget.setStyleSheet(
                f"QWidget#CharBtn {{"
                f" border: 1.5px solid {f2['accent']};"
                f" border-radius: 6px;"
                f" background: rgba({int(QColor(f2['accent']).red())},"
                f"{int(QColor(f2['accent']).green())},"
                f"{int(QColor(f2['accent']).blue())},20);"
                f"}}"
            )
        def _char_leave(e):
            self._char_widget.setStyleSheet("QWidget#CharBtn { border: none; border-radius: 6px; }")

        self._char_widget.enterEvent = _char_enter
        self._char_widget.leaveEvent = _char_leave

        lay.addWidget(self._vline())

        # Info-Button (Glocke)
        self._bell_btn = GearButton(self)
        self._bell_btn._symbol = "🔔"
        self._bell_btn.clicked.connect(self.open_bell_popup)
        lay.addWidget(self._bell_btn)

        # Einstellungen-Button
        self._settings_btn = GearButton(self)
        self._settings_btn.clicked.connect(self._toggle_settings)
        lay.addWidget(self._settings_btn)

    def showEvent(self, event):
        """Panel erst erstellen wenn Fenster sichtbar ist."""
        super().showEvent(event)
        if not hasattr(self, "_panel"):
            # Panel als Kind des Hauptfensters erstellen
            win = self.window()
            self._panel = SettingsPanel(self.settings, win)
            self._panel.setWindowFlags(
                Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint
            )
            self._panel.hide()
            self._panel.faction_changed.connect(self.faction_changed)
            self._panel.dev_mode_changed.connect(self.dev_mode_changed)
            self._panel.layout_changed.connect(self.layout_changed)
            self._panel.theme_changed.connect(self.theme_changed)
            self._panel.edit_mode_changed.connect(self.edit_mode_changed)
            self._panel.open_settings.connect(self.open_settings)

            # Rahmen entfernen wenn Panel geschlossen
            orig_hide = self._panel.hideEvent
            def _on_panel_hide(e):
                orig_hide(e)
                self._settings_btn.set_active(False)
            self._panel.hideEvent = _on_panel_hide

    # ── Einstellungen ─────────────────────────────────────────
    def _toggle_settings(self):
        if not hasattr(self, "_panel"):
            return
        if self._panel.isVisible():
            self._panel.hide()
            self._settings_btn.set_active(False)
        else:
            # Global-Position des Buttons berechnen
            btn_global = self._settings_btn.mapToGlobal(
                QPoint(self._settings_btn.width(), self._settings_btn.height())
            )
            # Panel links vom Button-Ende positionieren
            x = btn_global.x() - self._panel.width()
            y = btn_global.y()
            self._panel.move(x, y)
            self._panel.show()
            self._panel.raise_()
            self._panel.activateWindow()
            self._settings_btn.set_active(True)

    # ── Tabs ──────────────────────────────────────────────────
    def add_notifications_tab(self):
        """Meldungen-Tab hinzufügen."""
        mod_id = "__notifications__"
        if mod_id in self._tabs:
            return
        btn = QPushButton(t("notifications.title"))
        btn.setObjectName("Tab")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._tab_clicked(mod_id))
        close = QPushButton("✕")
        close.setObjectName("TabClose")
        close.setFixedSize(16, 16)
        close.clicked.connect(lambda: self._close_tab(mod_id))
        wrap = QWidget()
        wl   = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        wl.addWidget(btn)
        wl.addWidget(close)
        self._tabs[mod_id] = (wrap, btn)
        self._tabs_lay.addWidget(wrap)

    def add_settings_tab(self):
        """Einstellungen-Tab hinzufügen — spezieller Tab mit ⚙ Icon."""
        mod_id = "__settings__"
        if mod_id in self._tabs:
            return

        btn = QPushButton(t("nav.settings"))
        btn.setObjectName("Tab")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._tab_clicked(mod_id))

        close = QPushButton("✕")
        close.setObjectName("TabClose")
        close.setFixedSize(16, 16)
        close.clicked.connect(lambda: self._close_tab(mod_id))

        wrap = QWidget()
        wl   = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        wl.addWidget(btn)
        wl.addWidget(close)

        self._tabs[mod_id] = (wrap, btn)
        self._tabs_lay.addWidget(wrap)

    def add_tab(self, mod_id: str):
        if mod_id in self._tabs:
            return
        mod  = next((m for m in MODULES if m["id"] == mod_id), None)
        name = mod["name"] if mod else mod_id

        btn = QPushButton(name)
        btn.setObjectName("Tab")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self._tab_clicked(mod_id))

        close = QPushButton("✕")
        close.setObjectName("TabClose")
        close.setFixedSize(16, 16)
        close.clicked.connect(lambda: self._close_tab(mod_id))

        wrap = QWidget()
        wl   = QHBoxLayout(wrap)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(2)
        wl.addWidget(btn)
        wl.addWidget(close)

        self._tabs[mod_id] = (wrap, btn)
        self._tabs_lay.addWidget(wrap)

    def set_active_tab(self, mod_id: str):
        self._home_btn.setChecked(mod_id == "home")
        self._home_btn.update()
        for tid, (_, btn) in self._tabs.items():
            btn.setChecked(tid == mod_id)

    def _tab_clicked(self, mod_id: str):
        win = self.window()
        if hasattr(win, "_open_tabs") and mod_id in win._open_tabs:
            win.stack.setCurrentIndex(win._open_tabs[mod_id])
            if hasattr(win, "_update_detach_button"):
                win._update_detach_button(mod_id)
        self.set_active_tab(mod_id)

    def _close_tab(self, mod_id: str):
        """Entfernt nur den Tab-Button. Stack-Verwaltung macht MainWindow."""
        if mod_id in self._tabs:
            wrap, _ = self._tabs.pop(mod_id)
            wrap.setParent(None)
            wrap.deleteLater()
        # Wenn vom X-Button aufgerufen → MainWindow informieren
        win = self.window()
        if hasattr(win, "close_tab") and mod_id in getattr(win, "_open_tabs", {}):
            win.close_tab(mod_id)

    def remove_tab(self, mod_id: str):
        """Nur Tab-Button entfernen ohne MainWindow zu informieren."""
        if mod_id in self._tabs:
            wrap, _ = self._tabs.pop(mod_id)
            wrap.setParent(None)
            wrap.deleteLater()

    def set_blink(self, v: bool):
        """Blinken des Home-Symbols ein/ausschalten."""
        self._home_btn.set_blink(v)

    def set_settings_active(self, v: bool):
        """Rahmen Zahnrad: sichtbar wenn Panel oder Einstellungsseite offen."""
        self._settings_btn.set_active(v)

    def set_bell_active(self, v: bool):
        """Rahmen Glocke: sichtbar wenn Popup oder Meldungsseite offen."""
        self._bell_btn.set_active(v)

    def set_unread(self, has_unread: bool):
        """Roten Punkt und Blinken der Glocke steuern."""
        self._bell_btn._has_unread = has_unread
        self._bell_btn._blink_on   = False
        if has_unread:
            if not hasattr(self._bell_btn, '_blink_timer'):
                from PyQt6.QtCore import QTimer
                self._bell_btn._blink_timer = QTimer()
                self._bell_btn._blink_timer.timeout.connect(
                    lambda: self._do_bell_blink())
            self._bell_btn._blink_timer.start(700)
        else:
            if hasattr(self._bell_btn, '_blink_timer'):
                self._bell_btn._blink_timer.stop()
        self._bell_btn.update()

    def _do_bell_blink(self):
        self._bell_btn._blink_on = not self._bell_btn._blink_on
        self._bell_btn.update()

    def update_active_account(self, account: dict):
        """Aktualisiert den angezeigten Account in der Topbar."""
        self._avatar.setText(account.get("initials","??"))
        f = FACTIONS.get(self.settings.get("faction","caldari"), FACTIONS["caldari"])
        self._avatar.setStyleSheet(
            f"background: {f['accent']}; color: white; border-radius: 12px;"
            "font-size: 9px; font-weight: 700;"
        )
        # Name updaten
        for child in self._char_widget.findChildren(
            __import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel):
            if child.text() not in [account.get("initials",""), "Ω", "α", "▾"]:
                child.setText(account.get("name",""))
                break
        # Omega Badge
        omega = self._char_widget.findChildren(
            __import__('PyQt6.QtWidgets', fromlist=['QLabel']).QLabel)
        for lbl in omega:
            if lbl.text() in ["Ω", "α"]:
                lbl.setText("Ω" if account.get("omega") else "α")
                break

    def set_faction(self, faction: str):
        self._update_home_logo(faction)
        self._update_avatar_style(faction)
        self._update_btn_accents(faction)
        if hasattr(self, "_account_popup"):
            self._account_popup.update_faction(faction)
        if hasattr(self, "_unlock_popup"):
            self._unlock_popup.update_faction(faction)
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        if hasattr(self, "_settings_btn"):
            self._settings_btn.set_accent(f["accent"])

    def _update_avatar_style(self, faction: str):
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        self._avatar.setStyleSheet(
            f"background: {f['accent']}; color: white; border-radius: 12px;"
            "font-size: 9px; font-weight: 700;"
        )
        self._char_faction = faction

    def _update_btn_accents(self, faction: str):
        from core.config import FACTIONS
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        self._bell_btn._accent = f["accent"]
        self._settings_btn._accent = f["accent"]
        self._bell_btn.update()
        self._settings_btn.update()

    def _update_home_logo(self, faction: str):
        f = FACTIONS.get(faction, FACTIONS["caldari"])
        self._home_btn._accent = f["accent"]
        path = ASSETS / f"{faction}.png"
        if path.exists():
            self._home_btn.setPixmap(QPixmap(str(path)))
        else:
            self._home_btn.setPixmap(None)
        self._home_btn.update()

    # ── Account Popup ─────────────────────────────────────────
    def _current_display_name(self) -> str:
        """Name für die Topbar-Anzeige — abhängig vom Vault-Lock-Status.
        Solange gesperrt, wird absichtlich KEIN Charaktername gezeigt
        (auch nicht der zuletzt aktive) — das wäre genau die Information,
        die die Verschlüsselung der kompletten Charakterdatei schützen soll."""
        if not _vault.is_unlocked():
            return "🔒 " + t("security.locked_title")
        try:
            from core import esi as esi_mod
            tokens = esi_mod.load_tokens()
            return tokens[0].get("name", "Kein Login") if tokens else "Kein Login"
        except Exception:
            return "Kein Login"

    def _on_vault_unlocked(self):
        """Wird ausgelöst, wenn das UnlockPopup erfolgreich entsperrt hat.
        Aktualisiert die Topbar-Anzeige und öffnet direkt das gewohnte
        Account-Popup — kein zweiter Klick nötig."""
        _log.info("Topbar: Vault entsperrt — wechsle zu Account-Popup")
        self._name_lbl.setText(self._current_display_name())
        self._account_popup.reload()
        from PyQt6.QtCore import QPoint
        gp = self._char_widget.mapToGlobal(
            QPoint(self._char_widget.width(), self._char_widget.height()))
        self._account_popup.move(gp.x() - self._account_popup.width(), gp.y())
        self._account_popup.show()
        self._account_popup.raise_()

    def lock_now(self):
        """Sperrt den Vault sofort (z.B. Auto-Lock-Timer, manueller Button
        in den Sicherheits-Einstellungen) und aktualisiert die Anzeige."""
        _vault.lock_session()
        self._name_lbl.setText(self._current_display_name())
        self._account_popup.hide()
        _log.info("Topbar: Vault gesperrt")

    def _show_account_popup(self):
        _log.debug("Charakter-Widget geklickt")
        if not _vault.is_unlocked():
            # Gesperrt → Entschlüsselungs-Popup statt Account-Popup zeigen
            if not hasattr(self, "_unlock_popup"):
                return
            if self._unlock_popup.isVisible():
                self._unlock_popup.hide()
                return
            from PyQt6.QtCore import QPoint
            gp = self._char_widget.mapToGlobal(
                QPoint(self._char_widget.width(), self._char_widget.height()))
            self._unlock_popup.move(gp.x() - self._unlock_popup.width(), gp.y())
            self._unlock_popup.show()
            self._unlock_popup.raise_()
            return

        if not hasattr(self, "_account_popup"):
            return
        if self._account_popup.isVisible():
            self._account_popup.hide()
            return
        # Accounts neu laden bevor Popup gezeigt wird
        self._account_popup.reload()
        from PyQt6.QtCore import QPoint
        gp = self._char_widget.mapToGlobal(
            QPoint(self._char_widget.width(), self._char_widget.height()))
        self._account_popup.move(gp.x() - self._account_popup.width(), gp.y())
        self._account_popup.show()
        self._account_popup.raise_()

    def _on_login_success(self, char_info: dict):
        """Wird nach erfolgreichem ESI Login aufgerufen — Topbar sofort aktualisieren."""
        name     = str(char_info.get("name", ""))
        initials = "".join(w[0] for w in name.split()[:2]).upper() if name else "?"
        self._avatar.setText(initials)
        self._name_lbl.setText(name)

    def _on_account_changed(self, account: dict):
        _log.debug(f"Topbar: Account geändert zu {account.get('name', '??')}")
        """Aktiven Account im Topbar-Widget aktualisieren."""
        name = str(account.get("name", "Kein Login"))
        if name and name != "Kein Login":
            initials = "".join(w[0] for w in name.split()[:2]).upper()
        else:
            initials = "?"
            name = "Kein Login"
        self._avatar.setText(initials)
        self._name_lbl.setText(name)
        self.account_changed.emit(account)

    def _vline(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setObjectName("VLine")
        return line