"""
Hauptfenster der EVE Toolbox.
"""
from pathlib import Path
from core import logger as _logger
_log = _logger.get("main_window")

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                              QStackedWidget, QLabel, QApplication, QPushButton)
from PyQt6.QtCore import QPoint, QTimer
from PyQt6.QtGui import QPalette, QColor, QIcon
from PyQt6.QtCore import Qt
from core.config import APP_NAME, APP_VERSION, MODULES, FACTIONS
from core import settings as cfg
from ui.topbar import Topbar
from ui.home_grid import HomeGrid
from ui.home_donut import HomeDonut
from ui.settings_page import SettingsPage
from ui.notifications_page import NotificationsPage
from ui.bell_popup import BellPopup
from ui.account_popup import AccountPopup
from ui.fly_safe_dialog import FlySafeDialog
from core import notifications as nf
from core import updater
from core import integrity
from core import crypto_vault as _vault
from core.i18n import t
import os


def make_stylesheet(faction_key: str, dark: bool) -> str:
    """Generiert das komplette Stylesheet für die gewählte Fraktion und Theme."""
    from core.config import FACTIONS
    f = FACTIONS.get(faction_key, FACTIONS["caldari"])

    accent       = f["accent"]
    border       = f["border"]
    light        = f["light"]
    text_acc     = f["text_on_accent"]
    tab_active   = f["tab_active"]
    scrollbar    = f["scrollbar"]
    input_focus  = f["input_focus"]
    btn_hover    = f["button_hover"]

    if dark:
        bg          = "#1a1a1a"
        bg2         = "#242424"
        bg3         = "#2e2e2e"
        text        = "#e8e8e8"
        text2       = "#aaaaaa"
        text3       = "#666666"
        card_bg     = "#242424"
        card_border = "rgba(255,255,255,0.08)"
        sep         = "rgba(255,255,255,0.08)"
        tab_bg      = "#1a1a1a"
        input_bg    = "#2e2e2e"
        menu_bg     = "#2e2e2e"
        stat_bg     = "#242424"
    else:
        bg          = "#f5f5f5"
        bg2         = "#ebebeb"
        bg3         = "#e0e0e0"
        text        = "#1a1a1a"
        text2       = "#555555"
        text3       = "#999999"
        card_bg     = "#ffffff"
        card_border = "rgba(0,0,0,0.09)"
        sep         = "rgba(0,0,0,0.07)"
        tab_bg      = "#ffffff"
        input_bg    = "#f5f5f5"
        menu_bg     = "#ffffff"
        stat_bg     = "#ebebeb"  # wird in home_grid überschrieben

    return f"""
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 13px;
}}

/* ── Topbar ── */
#Topbar {{
    background: {bg2};
    border-bottom: 2px solid {accent};
}}
#TopbarLogo {{
    font-weight: 900;
    font-size: 20px;
    color: {accent};
    letter-spacing: 0.10em;
    padding-right: 12px;
}}

/* ── Tabs ── */
QPushButton#Tab {{
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 0 14px;
    font-size: 12px;
    color: {text2};
    height: 40px;
    border-radius: 0;
    min-width: 40px;
}}
QPushButton#Tab:checked {{
    background: {tab_bg};
    color: {text};
    font-weight: 600;
    border-bottom: 2px solid {accent};
}}
QPushButton#Tab:hover:!checked {{
    background: {light};
    color: {accent};
}}
QPushButton#TabClose {{
    background: transparent;
    border: none;
    color: {text3};
    font-size: 10px;
    padding: 0;
    min-width: 16px;
}}
QPushButton#TabClose:hover {{ color: {accent}; }}

/* ── Charakter Button ── */
QPushButton#CharBtn {{
    background: {card_bg};
    border: 1px solid {accent};
    border-radius: 6px;
    padding: 3px 10px;
    font-size: 12px;
    color: {text};
    margin: 6px 4px;
}}
QPushButton#CharBtn:hover {{
    background: {light};
    color: {accent};
}}

/* ── Icon Buttons (Zahnrad etc.) ── */
QPushButton#IconBtn {{
    background: transparent;
    border: 1px solid {accent};
    border-radius: 6px;
    font-size: 16px;
    color: {accent};
    margin: 6px 0;
    padding: 0;
    min-width: 28px;
    min-height: 28px;
    max-width: 28px;
    max-height: 28px;
}}
QPushButton#IconBtn:hover {{
    background: {light};
    color: {accent};
}}
QPushButton#IconBtn:checked {{
    background: {accent};
    color: {text_acc};
}}

/* ── Trennlinien ── */
QFrame#VLine {{
    border: none;
    border-left: 1px solid {accent};
    max-width: 1px;
    margin: 8px 6px;
    opacity: 0.3;
}}

/* ── Einstellungen Panel ── */
#SettingsPanel {{
    background: {card_bg};
    border: 1px solid {accent};
    border-radius: 10px;
}}
#PanelTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {accent};
}}
#SettingsLabel {{ font-size: 12px; color: {text}; }}
#SettingsSubLabel {{ font-size: 11px; color: {text3}; }}
QFrame#HLine {{
    border: none;
    border-top: 1px solid {sep};
}}

/* ── ComboBox ── */
QComboBox#SettingsCombo {{
    background: {input_bg};
    color: {text};
    border: 1px solid {accent};
    border-radius: 6px;
    padding: 3px 8px;
    font-size: 12px;
    min-width: 110px;
}}
QComboBox#SettingsCombo:focus {{
    border: 1.5px solid {input_focus};
}}
QComboBox#SettingsCombo::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{
    background: {card_bg};
    color: {text};
    border: 1px solid {accent};
    selection-background-color: {light};
    selection-color: {accent};
}}

/* ── Toggle Button ── */
QPushButton#ToggleBtn {{
    background: {bg3};
    border: none;
    border-radius: 9px;
    color: {text2};
    font-size: 11px;
    font-weight: 600;
    min-width: 44px;
    min-height: 20px;
    padding: 0 6px;
}}
QPushButton#ToggleBtn:checked {{
    background: {accent};
    color: {text_acc};
}}

/* ── Stat Karten ── */
#StatCard {{
    background: {stat_bg};
    border-radius: 8px;
    border: 1px solid {card_border};
}}
#StatLabel {{ font-size: 11px; color: {text3}; }}
#StatVal   {{ font-size: 18px; font-weight: 600; color: {text}; }}

/* ── Modul Karten ── */
#WelcomeTitle {{ font-size: 17px; font-weight: 600; color: {text}; }}
#WelcomeSub   {{ font-size: 12px; color: {text3}; }}

/* ── Scrollbars ── */
QScrollBar:vertical {{
    background: {bg2};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {scrollbar};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::handle:vertical:hover {{ background: {accent}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {bg2};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {scrollbar};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::handle:horizontal:hover {{ background: {accent}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── Input Felder ── */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background: {input_bg};
    color: {text};
    border: 1px solid {card_border};
    border-radius: 6px;
    padding: 4px 8px;
    selection-background-color: {accent};
    selection-color: {text_acc};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    border: 1.5px solid {input_focus};
}}

/* ── Buttons allgemein — nur explizit benannte ── */
QPushButton#AccentBtn {{
    background: {accent};
    color: {text_acc};
    border: none;
    border-radius: 6px;
    padding: 5px 14px;
    font-size: 12px;
    font-weight: 500;
}}
QPushButton#AccentBtn:hover {{ background: {btn_hover}; }}
QPushButton#AccentBtn:disabled {{ background: {bg3}; color: {text3}; }}

/* ── Menü ── */
QMenu {{
    background: {menu_bg};
    color: {text};
    border: 1px solid {accent};
    border-radius: 8px;
    padding: 4px;
    font-size: 12px;
}}
QMenu::item {{ padding: 6px 16px; border-radius: 4px; }}
QMenu::item:selected {{
    background: {light};
    color: {accent};
}}
QMenu::separator {{
    height: 1px;
    background: {sep};
    margin: 4px 0;
}}

/* ── Tabellen ── */
QTableWidget, QTableView {{
    background: {card_bg};
    color: {text};
    gridline-color: {sep};
    border: 1px solid {card_border};
    border-radius: 6px;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {light};
    color: {accent};
}}
QHeaderView::section {{
    background: {bg2};
    color: {text2};
    border: none;
    border-bottom: 2px solid {accent};
    padding: 4px 8px;
    font-weight: 600;
}}

/* ── Tooltip ── */
QToolTip {{
    background: {card_bg};
    color: {text};
    border: 1px solid {accent};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 11px;
}}

/* ── Progressbar ── */
QProgressBar {{
    background: {bg3};
    border-radius: 4px;
    height: 6px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {accent};
    border-radius: 4px;
}}
"""

def _make_dark_stylesheet():
    from core import settings as _cfg
    s = _cfg.load()
    return make_stylesheet(s.get("faction","caldari"), dark=True)

def _make_light_stylesheet():
    from core import settings as _cfg
    s = _cfg.load()
    return make_stylesheet(s.get("faction","caldari"), dark=False)


class DetachedTabWindow(QMainWindow):
    """
    Eigenständiges Fenster für einen entfixten Tab. Hält nur eine
    Referenz auf mod_id + das umgezogene Modul-Widget. Schließen
    dieses Fensters (z.B. über X) entspricht einem vollständigen
    Schließen des Tabs — kein automatisches Wieder-Andocken.

    Bekommt einen eigenen DetachButton (Andocken-Symbol), da der
    Button im Hauptfenster physisch im Hauptfenster-Stack bleibt und
    nicht mit hierher wandert.
    """

    def __init__(self, mod_id: str, title: str, widget: QWidget, parent=None):
        super().__init__(parent)
        self.mod_id = mod_id
        self.setWindowTitle(title)
        self.setCentralWidget(widget)
        self.resize(900, 650)

        self.attach_btn = DetachButton(self)
        self.attach_btn.set_state(mod_id, True)  # True = zeigt Andocken-Icon
        self.attach_btn.move(8, 8)
        self.attach_btn.raise_()
        self.attach_btn.show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        margin = 8
        x = self.width() - self.attach_btn.width() - margin
        self.attach_btn.move(max(0, x), margin)
        self.attach_btn.raise_()

    def closeEvent(self, event):
        # Widget VOR jeder weiteren Qt-internen Verarbeitung explizit
        # umparenten — verlässlicher als nur setCentralWidget(), da
        # setParent(None) sofort und unabhängig vom restlichen
        # closeEvent-Ablauf wirkt. Verhindert, dass Qt das Modul-Widget
        # mit dem Fenster mitzerstört.
        w = self.centralWidget()
        if w is not None:
            w.setParent(None)

        # Falls attach_tab() bereits das Umparenten + Andocken erledigt
        # hat (_attaching-Flag), nicht zusätzlich die "Tab komplett
        # schließen"-Logik auslösen — w ist dann schon im Hauptfenster.
        if not getattr(self, "_attaching", False):
            win = self.parent()
            if win is not None and hasattr(win, "_on_detached_window_closed"):
                win._on_detached_window_closed(self.mod_id, w)
        super().closeEvent(event)


class DetachButton(QPushButton):
    """
    Fester Button-Slot oben rechts über dem Stack. Zeigt je nach
    Zustand des aktuell aktiven Tabs entweder das Entfix- oder das
    Andocken-Symbol. Position bleibt immer reserviert (nur die
    Sichtbarkeit/das Icon wechselt), damit beim Umschalten zwischen
    Modulen nichts im Layout springt.
    """
    DETACH_ICON = "⧉"
    ATTACH_ICON = "⧈"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DetachButton")
        self.setFixedSize(28, 28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mod_id = None
        self._detached = False
        self.clicked.connect(self._on_click)
        self.set_state(None, False)

    def set_state(self, mod_id: str | None, detached: bool):
        """mod_id=None (z.B. Home) -> Button unsichtbar, Platz bleibt reserviert."""
        self._mod_id = mod_id
        self._detached = detached
        if mod_id is None:
            self.setVisible(False)
            return
        self.setVisible(True)
        self.setText(self.ATTACH_ICON if detached else self.DETACH_ICON)
        self.setToolTip(t("tabs.attach") if detached else t("tabs.detach"))

    def _on_click(self):
        if self._mod_id is None:
            return
        win = self.window()
        # Sitzt der Button in einem DetachedTabWindow, ist self.window()
        # genau dieses Fenster (hat kein detach_tab) — die eigentliche
        # MainWindow-Instanz hängt dann an dessen .parent().
        if not hasattr(win, "detach_tab") and hasattr(win, "parent"):
            parent_win = win.parent()
            if parent_win is not None and hasattr(parent_win, "detach_tab"):
                win = parent_win
        if not hasattr(win, "detach_tab"):
            return
        if self._detached:
            win.attach_tab(self._mod_id)
        else:
            win.detach_tab(self._mod_id)


class _ResizableStack(QStackedWidget):
    """QStackedWidget, das bei Größenänderung einen Callback auslöst —
    genutzt um den DetachButton-Overlay oben rechts neu zu positionieren."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on_resize_cb = None

    def set_resize_callback(self, cb):
        self._on_resize_cb = cb

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._on_resize_cb:
            self._on_resize_cb()


class MainWindow(QMainWindow):
    def __init__(self, app=None):
        super().__init__()
        self._app = app
        self.settings = cfg.load()
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        # __file__ = .../eve_toolbox/ui/main_window.py -> assets liegt
        # eine Ebene höher, direkt unter eve_toolbox/ (gleicher Ordner,
        # der bereits für assets/icons/ genutzt wird, siehe welcome_screen.py)
        icon_path = Path(__file__).resolve().parent.parent / "assets" / "EVE Toolbox.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            _log.warning(f"App-Icon nicht gefunden: {icon_path}")
        self.setMinimumSize(900, 650)
        self.resize(1200, 750)  # Standard — wird nach show() überschrieben
        self._open_tabs = {}
        self._detached_tabs = {}   # mod_id -> DetachedTabWindow (entfixte Tabs)
        self._build_ui()
        self._apply_faction()
        self._setup_autolock()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.topbar = Topbar(self.settings, self)
        self.topbar.home_clicked.connect(self._show_home)
        self.topbar.faction_changed.connect(self._on_faction)
        self.topbar.dev_mode_changed.connect(self._on_dev_mode)
        self.topbar.layout_changed.connect(self._on_layout)
        self.topbar.theme_changed.connect(self._on_theme)
        self.topbar.edit_mode_changed.connect(self._on_edit_mode)
        self.topbar.open_settings.connect(self._open_settings_page)
        self.topbar.open_account_settings.connect(self._open_account_settings)
        # Popup leitet Login-Anfrage zur Account-Verwaltung
        self.topbar._account_popup.request_login.connect(self._open_account_login)
        self.topbar.open_bell_popup.connect(self._toggle_bell_popup)
        layout.addWidget(self.topbar)

        self.stack = _ResizableStack()
        layout.addWidget(self.stack)

        # Entfix/Andock-Button — schwebt als Overlay oben rechts über
        # dem Stack, Position bleibt immer reserviert. Wird bei jedem
        # Tab-Wechsel über _update_detach_button() aktualisiert.
        self._detach_btn = DetachButton(self.stack)
        self.stack.set_resize_callback(self._position_detach_button)
        self._position_detach_button()

        self.home_grid    = HomeGrid(self.settings, self)
        self.home_donut_t = HomeDonut(self.settings, mode="text", parent=self)
        self.home_donut_i = HomeDonut(self.settings, mode="icon", parent=self)

        self._home_idx = {
            "grid":       self.stack.addWidget(self.home_grid),
            "donut_text": self.stack.addWidget(self.home_donut_t),
            "donut_icon": self.stack.addWidget(self.home_donut_i),
        }
        for home in [self.home_grid, self.home_donut_t, self.home_donut_i]:
            home.module_opened.connect(self._open_module)

        # Einstellungsseite (wird on-demand als Tab geöffnet)
        self.settings_page = SettingsPage(self.settings)
        self.settings_page.hide()  # Verstecken bis geöffnet
        self.settings_page.faction_changed.connect(self._on_faction)
        self.settings_page.theme_changed.connect(self._on_theme)
        self.settings_page.layout_changed.connect(self._on_layout)
        self.settings_page.dev_mode_changed.connect(self._on_dev_mode)
        self.settings_page.test_mode_changed.connect(self._on_test_mode)
        self.settings_page.edit_mode_changed.connect(self._on_edit_mode)
        self.settings_page.window_size_changed.connect(self._on_window_size)
        self.settings_page.close_requested.connect(
            self._close_settings_page)
        self.settings_page.language_changed.connect(self._on_language)
        # SettingsPage informiert main_window bei Account-Änderungen
        self.settings_page.accounts_changed.connect(self._on_accounts_changed)
        # Sicherheits-Page: Sperren, Auto-Lock-Zeit, Lösch-Notausgang
        self.settings_page.lock_requested.connect(self._on_lock_requested)
        self.settings_page.autolock_changed.connect(self._on_autolock_changed)
        self.settings_page.lock_on_minimize_changed.connect(self._on_lock_on_minimize_changed)
        self.settings_page.delete_once_changed.connect(self._on_delete_once_changed)
        self.settings_page.delete_always_changed.connect(self._on_delete_always_changed)
        # Popup-Referenz und Reload-Callback direkt an PageAccounts übergeben
        page = self.settings_page._pages.get("Accounts")
        if page:
            page._popup_ref = self.topbar._account_popup
            page._reload_callback = self._reload_accounts_page

        # Benachrichtigungen laden
        self._notifications    = nf.load()
        self._notifications_page = NotificationsPage(
            self._notifications, self.settings, self)
        self._notifications_page.setVisible(False)  # Verhindert floating widget
        self._notifications_page.close_requested.connect(
            self._close_notifications_page)
        self._notifications_page.unread_changed.connect(self.topbar.set_unread)
        self._notifications_page.all_notifications_changed.connect(
            self._on_all_notifs_changed)

        # Entwickler-Unterkategorie "Notifications" (Simulator) lebt in
        # den Einstellungen, schickt simulierte Nachrichten aber an die
        # echte NotificationsPage, damit sie sich wie echte Nachrichten
        # verhalten (Glocke, Badge-Zähler, etc.).
        dev_notif_page = self.settings_page._pages.get(
            SettingsPage.DEV_SUB_NOTIFICATIONS)
        if dev_notif_page:
            dev_notif_page.notification_added.connect(
                self._notifications_page._on_sim_notif)
            dev_notif_page.notifications_cleared.connect(
                self._notifications_page._on_sim_clear)
        # Accounts

        self._account_popup = AccountPopup(self.settings, self)
        self._account_popup.account_changed.connect(self._on_account_changed)
        self._account_popup.hide()

        self._bell_popup = BellPopup([], self.settings, self)
        self._bell_popup.open_notifications.connect(self._open_notifications_page)
        self._bell_popup.open_notification.connect(self._open_to_notification)
        self._bell_popup.marked_read.connect(self._on_notifs_updated)
        # Rahmen entfernen wenn Popup geschlossen (z.B. Klick außerhalb)
        orig_hide = self._bell_popup.hideEvent
        def _on_bell_hide(e):
            orig_hide(e)
            if not ("__notifications__" in self._open_tabs):
                self.topbar.set_bell_active(False)
        self._bell_popup.hideEvent = _on_bell_hide
        self._bell_popup.hide()
        # Notifications nach allem laden und updaten
        self._bell_popup.update_data(self._all_notifs())
        self._update_blink()

        # Update-Check im Hintergrund — überspringen, wenn der Dev-Mode-
        # Pfad bereits in main.py gegriffen hat (gleiche Bedingung wie
        # dort: EVE_SKIP_CHECKS + gültiger Dev-Token). Sonst würde dieser
        # unabhängige Hintergrund-Check trotzdem gegen GitHub laufen und
        # offline-Fehler ins Log schreiben, auch wenn der Dev-Mode aktiv ist.
        if os.environ.get("EVE_SKIP_CHECKS") == "1" and integrity.check_dev_token():
            _log.debug("Dev-Mode aktiv — Hintergrund-Update-Check übersprungen")
        else:
            updater.check_for_update(self._on_update_result)

        self._show_home()

    def _show_home(self):
        layout = self.settings.get("home_layout", "grid")
        self.stack.setCurrentIndex(self._home_idx.get(layout, 0))
        self.topbar.set_active_tab("home")
        self._update_detach_button(None)



    def _update_blink(self):
        unread = nf.get_unread(self._all_notifs())
        self.topbar.set_unread(bool(unread))

    def _close_notifications_page(self):
        self.close_tab("__notifications__")
        self.topbar.set_bell_active(False)

    def _on_update_result(self, info: dict | None):
        """Wird vom Update-Thread aufgerufen."""
        if not info:
            return
        from PyQt6.QtCore import QMetaObject, Qt
        # Muss im Main-Thread ausgeführt werden
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, lambda: self._show_update_notification(info))

    def _show_update_notification(self, info: dict):
        """Fügt Update-Benachrichtigung ins Glocken-System ein."""
        self._notifications = nf.add_notification(
            self._notifications,
            notif_id  = f"update_{info['version'].replace('.','_')}",
            ntype     = nf.TYPE_UPDATE,
            title     = f"Update verfügbar — v{info['version']}",
            text      = info.get("notes", "Neue Version verfügbar."),
            valid_until = "2099-12-31",
        )
        self._update_blink()
        self._bell_popup.update_data(self._all_notifs())
        if hasattr(self, "_notifications_page"):
            self._notifications_page.update_notifications(self._notifications)

    def _all_notifs(self) -> list:
        """Gibt echte + simulierte Nachrichten zurück."""
        sim = getattr(self._notifications_page, "_sim_notifs", [])
        return self._notifications + sim

    def _toggle_bell_popup(self):
        if self._bell_popup.isVisible():
            self._bell_popup.hide()
            self.topbar.set_bell_active(False)
            return
        self._bell_popup.update_data(self._all_notifs())
        btn = self.topbar._bell_btn
        gp  = btn.mapToGlobal(QPoint(btn.width(), btn.height()))
        self._bell_popup.move(gp.x() - self._bell_popup.width(), gp.y())
        self._bell_popup.show()
        self._bell_popup.raise_()
        self.topbar.set_bell_active(True)

    def _open_to_notification(self, notif_id: str):
        """Öffnet Notifications-Seite und springt zur Nachricht."""
        self._open_notifications_page()
        # Zur Aktuell-Kategorie — Nachricht ist dort sichtbar

    def _on_all_notifs_changed(self, all_notifs: list):
        """Wird aufgerufen wenn sim-Nachrichten hinzukommen/gelöscht werden."""
        self._bell_popup.update_data(all_notifs)
        self.topbar.set_unread(bool(nf.get_unread(all_notifs)))

    def _on_notifs_updated(self, notifications: list):
        self._notifications = notifications
        self._update_blink()
        if hasattr(self, "_notifications_page"):
            self._notifications_page.update_notifications(notifications)

    def _toggle_account_popup(self):
        if self._account_popup.isVisible():
            self._account_popup.hide()
            return
        self._account_popup.update_accounts(self._accounts)
        # Direkt unter dem Char-Widget positionieren
        cw  = self.topbar._char_widget
        gp  = cw.mapToGlobal(QPoint(0, cw.height()))
        self._account_popup.move(gp)
        self._account_popup.show()
        self._account_popup.raise_()

    def _on_account_changed(self, account: dict):
        self.topbar.update_active_account(account)
        self._account_popup.hide()

    def _on_add_account(self):
        self._account_popup.hide()
        # Öffnet später die Account-Einstellungsseite

    def _open_account_settings(self):
        self._open_settings_page()
        if hasattr(self, "settings_page"):
            self.settings_page._switch("Accounts")

    def _open_account_login(self):
        """Popup hat Login angefragt → Account-Verwaltung öffnen und Login starten."""
        self._open_settings_page()
        if hasattr(self, "settings_page"):
            self.settings_page._switch("Accounts")
            # Login in der Verwaltung direkt starten
            page = self.settings_page._pages.get("Accounts")
            if page and hasattr(page, "_on_add_account"):
                from PyQt6.QtCore import QTimer
                QTimer.singleShot(200, page._on_add_account)

    def _on_accounts_changed(self):
        """SettingsPage meldet Account-Änderung → Popup aktualisieren."""
        if hasattr(self, "topbar") and hasattr(self.topbar, "_account_popup"):
            self.topbar._account_popup.reload()

    def _reload_accounts_page(self):
        """Accounts-Seite direkt neu laden ohne Tab zu schließen."""
        if hasattr(self, "settings_page"):
            page = self.settings_page._pages.get("Accounts")
            if page:
                page._load_tokens()
                page._build()

    def _focus_if_detached(self, mod_id: str) -> bool:
        """
        Prüft ob mod_id aktuell als eigenes Fenster offen ist. Falls ja:
        Fenster nach vorne holen (Singleton-Verhalten — kein zweites
        Fenster/Tab für dasselbe Modul). Gibt True zurück wenn behandelt,
        damit die aufrufende _open_*-Methode danach early-return machen kann.
        """
        win = self._detached_tabs.get(mod_id)
        if win is None:
            return False
        win.raise_()
        win.activateWindow()
        return True

    def _close_settings_page(self):
        self.close_tab("__settings__")
        self.topbar.set_settings_active(False)

    def _open_notifications_page(self):
        """Öffnet die Meldungsseite als Tab."""
        mod_id = "__notifications__"
        self._notifications_page.update_notifications(self._notifications)
        if self._focus_if_detached(mod_id):
            return
        if mod_id in self._open_tabs:
            self.stack.setCurrentIndex(self._open_tabs[mod_id])
            self.topbar.set_active_tab(mod_id)
            self._update_detach_button(mod_id)
            return
        idx = self.stack.addWidget(self._notifications_page)
        self._open_tabs[mod_id] = idx
        self.stack.setCurrentIndex(idx)
        self.topbar.add_notifications_tab()
        self.topbar.set_active_tab(mod_id)
        self.topbar.set_bell_active(True)
        if hasattr(self.topbar, '_panel'):
            self.topbar._panel.hide()
        self._update_detach_button(mod_id)



    def _open_module(self, mod_id: str):
        if self._focus_if_detached(mod_id):
            return
        if mod_id in self._open_tabs:
            self.stack.setCurrentIndex(self._open_tabs[mod_id])
            self.topbar.set_active_tab(mod_id)
            self._update_detach_button(mod_id)
            return
        widget = self._make_placeholder(mod_id)
        idx = self.stack.addWidget(widget)
        self._open_tabs[mod_id] = idx
        self.stack.setCurrentIndex(idx)
        self.topbar.add_tab(mod_id)
        self.topbar.set_active_tab(mod_id)
        self._update_detach_button(mod_id)

    def close_tab(self, mod_id: str):
        if mod_id not in self._open_tabs:
            return
        idx = self._open_tabs.pop(mod_id)
        w = self.stack.widget(idx)
        if w is not None:
            self.stack.removeWidget(w)
            if mod_id not in ("__settings__", "__notifications__"):
                w.deleteLater()
            else:
                w.setVisible(False)
        # Button-Zustand zurücksetzen
        if mod_id == "__settings__":
            self.topbar.set_settings_active(False)
        elif mod_id == "__notifications__":
            self.topbar.set_bell_active(False)
        self.topbar.remove_tab(mod_id)
        self._show_home()

    def _tab_title(self, mod_id: str) -> str:
        if mod_id == "__settings__":
            return t("nav.settings")
        if mod_id == "__notifications__":
            return t("notifications.title")
        mod = next((m for m in MODULES if m["id"] == mod_id), None)
        return mod["name"] if mod else mod_id

    def _position_detach_button(self):
        """Hält den Entfix/Andock-Button oben rechts über dem Stack."""
        margin = 8
        x = self.stack.width() - self._detach_btn.width() - margin
        self._detach_btn.move(max(0, x), margin)
        self._detach_btn.raise_()

    def _update_detach_button(self, mod_id: str):
        """Aktualisiert Sichtbarkeit/Icon des Entfix-Buttons für mod_id.
        mod_id=None (Home) -> Button bleibt unsichtbar, Platz reserviert."""
        if mod_id is None or mod_id == "home":
            self._detach_btn.set_state(None, False)
        else:
            self._detach_btn.set_state(mod_id, mod_id in self._detached_tabs)
        self._position_detach_button()

    def detach_tab(self, mod_id: str):
        """Löst einen offenen Tab aus dem Hauptfenster und zeigt ihn in
        einem eigenständigen Fenster. Das Modul-Widget bleibt am Leben
        (im Gegensatz zu close_tab, das es ggf. zerstört)."""
        if mod_id not in self._open_tabs or mod_id in self._detached_tabs:
            return
        idx = self._open_tabs.pop(mod_id)
        w = self.stack.widget(idx)
        if w is None:
            return
        self.stack.removeWidget(w)
        w.setVisible(True)

        win = DetachedTabWindow(mod_id, self._tab_title(mod_id), w, parent=self)
        self._detached_tabs[mod_id] = win
        win.show()

        # Tab-Reiter verschwindet komplett aus der Topbar solange entfixt
        self.topbar.remove_tab(mod_id)
        if mod_id == "__settings__":
            self.topbar.set_settings_active(False)
        elif mod_id == "__notifications__":
            self.topbar.set_bell_active(False)
        self._show_home()

    def attach_tab(self, mod_id: str):
        """Holt ein entfixtes Modul zurück ins Hauptfenster als normalen Tab."""
        win = self._detached_tabs.pop(mod_id, None)
        if win is None:
            return
        w = win.centralWidget()
        if w is not None:
            w.setParent(None)  # sofort umparenten, bevor win.close() läuft
        win._attaching = True  # verhindert dass closeEvent _on_detached_window_closed nochmal aufruft
        win.close()

        idx = self.stack.addWidget(w)
        self._open_tabs[mod_id] = idx
        self.stack.setCurrentIndex(idx)

        if mod_id == "__settings__":
            self.topbar.add_settings_tab()
            self.topbar.set_settings_active(True)
        elif mod_id == "__notifications__":
            self.topbar.add_notifications_tab()
            self.topbar.set_bell_active(True)
        else:
            self.topbar.add_tab(mod_id)
        self.topbar.set_active_tab(mod_id)
        self._update_detach_button(mod_id)

    def _current_active_mod_id(self) -> str | None:
        """Ermittelt, welches Modul/Tab im Stack aktuell sichtbar ist —
        None wenn es Home ist. Wird gebraucht für Ereignisse, die NICHT
        selbst zu einem bestimmten Tab navigieren (z.B. Schließen eines
        entfixten Fensters über X), damit der Entfix-Button danach das
        TATSÄCHLICH sichtbare Tab widerspiegelt, statt blind von Home
        auszugehen."""
        current_idx = self.stack.currentIndex()
        if current_idx in self._home_idx.values():
            return None
        for mod_id, idx in self._open_tabs.items():
            if idx == current_idx:
                return mod_id
        return None

    def _on_detached_window_closed(self, mod_id: str, w: QWidget | None):
        """Wird von DetachedTabWindow.closeEvent aufgerufen — Schließen
        eines losgelösten Fensters (z.B. über X) entspricht einem
        vollständigen Schließen des Tabs (kein Wieder-Andocken)."""
        win = self._detached_tabs.pop(mod_id, None)
        if win is None:
            return  # bereits über attach_tab() entfernt
        if mod_id not in ("__settings__", "__notifications__"):
            if w is not None:
                w.deleteLater()
        else:
            if w is not None:
                w.setVisible(False)
        if mod_id == "__settings__":
            self.topbar.set_settings_active(False)
        elif mod_id == "__notifications__":
            self.topbar.set_bell_active(False)
        self._update_detach_button(self._current_active_mod_id())

    def _make_placeholder(self, mod_id: str) -> QWidget:
        mod  = next((m for m in MODULES if m["id"] == mod_id), None)
        name = mod["name"] if mod else mod_id
        status = mod.get("status", "geplant") if mod else "geplant"
        icons = {"assets":"📦","markt":"📊","skills":"🧠","intel":"📡",
                 "pi":"🌿","industrie":"🔨","routen":"🗺","wallet":"💰"}
        status_text = {
            "fertig":      "Dieses Modul ist fertig — wird bald freigeschaltet.",
            "entwicklung": "Dieses Modul ist in Entwicklung.",
            "geplant":     "Dieses Modul ist geplant und noch nicht begonnen.",
        }.get(status, "In Entwicklung.")
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl = QLabel(f"{icons.get(mod_id,'🚧')}  {name}\n\n{status_text}")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("font-size: 15px; color: #888;")
        lay.addWidget(lbl)
        return w

    def _on_faction(self, faction: str):
        _log.info(f"Fraktion geändert: {faction}")
        self.settings["faction"] = faction
        cfg.save(self.settings)
        self._apply_stylesheet()
        self._apply_faction()

    def _on_dev_mode(self, enabled: bool):
        _log.info(f"Entwicklermodus: {'aktiviert' if enabled else 'deaktiviert'}")
        self.settings["dev_mode"] = enabled
        if not enabled:
            self.settings["test_mode"] = False
        cfg.save(self.settings)
        self._refresh_homes()

    def _on_layout(self, layout: str):
        _log.debug(f"Home-Layout geändert: {layout}")
        self.settings["home_layout"] = layout
        cfg.save(self.settings)
        self._show_home()

    def _open_settings_page(self):
        _log.debug("Einstellungsseite geöffnet")
        mod_id = "__settings__"
        if self._focus_if_detached(mod_id):
            self.settings_page.sync()   # Auch wenn als Fenster offen
            return
        if hasattr(self.topbar, '_panel'):
            self.topbar._panel.hide()
        self.topbar.set_settings_active(True)
        # Als Tab öffnen wie ein Modul
        if mod_id in self._open_tabs:
            self.stack.setCurrentIndex(self._open_tabs[mod_id])
            self.topbar.set_active_tab(mod_id)
            self.settings_page.sync()   # Auch wenn Tab bereits offen ist
            self._update_detach_button(mod_id)
            return
        self.settings_page.sync()
        idx = self.stack.addWidget(self.settings_page)
        self._open_tabs[mod_id] = idx
        self.stack.setCurrentIndex(idx)
        self.topbar.add_settings_tab()
        self.topbar.set_active_tab(mod_id)
        self._update_detach_button(mod_id)

    def _on_test_mode(self, enabled: bool):
        _log.info(f"Testmodus: {'aktiviert' if enabled else 'deaktiviert'}")
        self.settings["test_mode"] = enabled
        cfg.save(self.settings)
        self._refresh_homes()
        if hasattr(self, "_notifications_page"):
            self._notifications_page.set_test_mode(enabled)
        if not enabled:
            dev_notif_page = self.settings_page._pages.get(
                SettingsPage.DEV_SUB_NOTIFICATIONS)
            if dev_notif_page:
                dev_notif_page._sim_page.clear_all()

    def _on_window_size(self, w: int, h: int):
        _log.debug(f"Fenstergröße geändert: {w}x{h}")
        self.settings["window_width"]  = w
        self.settings["window_height"] = h
        cfg.save(self.settings)
        self.resize(w, h)

    def _refresh_homes(self):
        """Alle Home-Screens nach Modus-Wechsel aktualisieren."""
        dev  = self.settings.get("dev_mode", False)
        test = self.settings.get("test_mode", False)
        for home in [self.home_grid, self.home_donut_t, self.home_donut_i]:
            home.set_dev_mode(dev)
            if hasattr(home, "set_test_mode"):
                home.set_test_mode(test)

    def _on_language(self, lang: str):
        self.settings["language"] = lang
        from core import settings as cfg
        from core import i18n
        cfg.save(self.settings)
        i18n.set_language(lang)
        self._retranslate_ui()

    def _retranslate_ui(self):
        """Aktualisiert alle UI-Texte nach Sprachwechsel."""
        from core.config import APP_NAME, APP_VERSION
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        # Topbar Panel
        if hasattr(self.topbar, "_panel") and self.topbar._panel:
            if hasattr(self.topbar._panel, "retranslate"):
                self.topbar._panel.retranslate()
        # Einstellungsseite neu aufbauen
        if hasattr(self, "settings_page"):
            if hasattr(self.settings_page, "retranslate"):
                self.settings_page.retranslate()
        # Notifications
        if hasattr(self, "_notifications_page"):
            if hasattr(self._notifications_page, "retranslate"):
                self._notifications_page.retranslate()
        # Home-Screens
        for home in [self.home_grid, self.home_donut_t, self.home_donut_i]:
            if hasattr(home, "retranslate"):
                home.retranslate()

    def _on_edit_mode(self, enabled: bool):
        self.settings["edit_locked"] = not enabled
        cfg.save(self.settings)
        for home in [self.home_grid, self.home_donut_t, self.home_donut_i]:
            home.set_edit_mode(enabled)

    def _apply_stylesheet(self):
        """Stylesheet neu generieren mit aktueller Fraktion + Theme."""
        app = self._app or QApplication.instance()
        if app:
            faction = self.settings.get("faction", "caldari")
            dark    = self.settings.get("theme", "light") == "dark"
            app.setStyleSheet(make_stylesheet(faction, dark))

    def _on_theme(self, theme: str):
        _log.info(f"Theme geändert: {theme}")
        self.settings["theme"] = theme
        cfg.save(self.settings)
        self._apply_stylesheet()

    def _apply_faction(self):
        faction = self.settings.get("faction", "caldari")
        for home in [self.home_grid, self.home_donut_t, self.home_donut_i]:
            home.set_faction(faction)
        self.topbar.set_faction(faction)
        if hasattr(self, "settings_page"):
            self.settings_page.set_faction(faction)
        if hasattr(self, "_notifications_page"):
            self._notifications_page.set_faction(faction)
        if hasattr(self, "_bell_popup"):
            self._bell_popup.set_faction(faction)
        if hasattr(self, "_account_popup"):
            self._account_popup.update_faction(faction)

    # ── Sicherheit: Auto-Lock ──────────────────────────────────
    def _setup_autolock(self):
        """
        Richtet den Inaktivitäts-Timer für das automatische Sperren ein.
        0 Minuten = "Niemals (erst beim Beenden)" → kein Timer aktiv.
        Jede Maus-/Tastatur-Aktivität im Hauptfenster setzt den Timer
        zurück (siehe eventFilter).
        """
        self._autolock_timer = QTimer(self)
        self._autolock_timer.setSingleShot(True)
        self._autolock_timer.timeout.connect(self._on_autolock_timeout)
        self._restart_autolock_timer()
        # Globaler Event-Filter auf der Application-Instanz, damit JEDE
        # Nutzerinteraktion irgendwo im Fenster den Timer zurücksetzt —
        # nicht nur Klicks auf das Hauptfenster selbst.
        app = self._app or QApplication.instance()
        if app:
            app.installEventFilter(self)

    def _restart_autolock_timer(self):
        minutes = self.settings.get("autolock_minutes", 15)
        self._autolock_timer.stop()
        if minutes and minutes > 0 and _vault.is_unlocked():
            self._autolock_timer.start(minutes * 60 * 1000)

    def eventFilter(self, obj, event):
        # Bei jeder Maus-/Tastatureingabe irgendwo in der App: Timer
        # zurücksetzen. Bewusst breit gefasst (MouseMove eingeschlossen),
        # da "Inaktivität" hier ehrlich gemeint ist — Mausbewegung allein
        # zählt als Aktivität.
        from PyQt6.QtCore import QEvent
        if event.type() in (
            QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove,
            QEvent.Type.KeyPress, QEvent.Type.Wheel,
        ):
            if _vault.is_unlocked():
                self._restart_autolock_timer()
        return super().eventFilter(obj, event)

    def _on_autolock_timeout(self):
        _log.info("Auto-Lock: Inaktivitätszeit erreicht — Vault wird gesperrt")
        if hasattr(self, "topbar"):
            self.topbar.lock_now()

    def _on_lock_requested(self):
        """'Jetzt sperren' Button in den Sicherheits-Einstellungen."""
        _log.info("Manuelle Sperrung angefordert ('Jetzt sperren')")
        if hasattr(self, "topbar"):
            self.topbar.lock_now()
        self._autolock_timer.stop()

    def _on_autolock_changed(self, minutes: int):
        _log.info(
            f"Auto-Lock-Zeit geändert: "
            + ("Niemals" if minutes == 0 else f"{minutes} Minuten")
        )
        self.settings["autolock_minutes"] = minutes
        cfg.save(self.settings)
        self._restart_autolock_timer()

    def _on_lock_on_minimize_changed(self, enabled: bool):
        _log.info(f"'Sperren beim Minimieren': {'aktiviert' if enabled else 'deaktiviert'}")
        self.settings["lock_on_minimize"] = enabled
        cfg.save(self.settings)

    def changeEvent(self, event):
        """
        Erkennt Minimieren — plattformunabhängig über Qt's eigenes
        WindowStateChangeEvent, keine Windows-spezifische API. Sperrt
        den Vault sofort, wenn die Option aktiv ist, unabhängig vom
        Auto-Lock-Timer (deckt den Fall ab, dass "Niemals sperren"
        gewählt ist, aber Minimieren trotzdem ein Sicherheitsrisiko
        darstellt — z.B. fremder Blick auf den Bildschirm).
        """
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized() and self.settings.get("lock_on_minimize", False):
                if _vault.is_unlocked():
                    _log.info("Fenster minimiert — Vault wird gesperrt (Einstellung aktiv)")
                    if hasattr(self, "topbar"):
                        self.topbar.lock_now()
        super().changeEvent(event)

    def _on_delete_once_changed(self, enabled: bool):
        _log.warning(f"'Einmalig löschen beim Beenden': {'AKTIVIERT' if enabled else 'deaktiviert'}")
        self.settings["delete_once_on_exit"] = enabled
        cfg.save(self.settings)

    def _on_delete_always_changed(self, enabled: bool):
        _log.warning(f"'Immer löschen beim Beenden': {'AKTIVIERT' if enabled else 'deaktiviert'}")
        self.settings["delete_always_on_exit"] = enabled
        cfg.save(self.settings)

    # ── Beenden: Verschlüsseln/Löschen + Fly-Safe-Meldung ──────
    def closeEvent(self, event):
        """
        Regelt den Zustand der Userdaten beim Beenden:
        - Normalfall: Vault ist bereits durchgehend verschlüsselt auf der
          Platte (siehe core.crypto_vault — niemals Klartext-Zwischenstand),
          hier wird nur noch die RAM-Sitzung aufgeräumt.
        - "Einmalig löschen": löscht den Vault jetzt, setzt das Häkchen
          danach selbst zurück (einmaliger Trigger).
        - "Immer löschen": löscht Vault UND App-Einstellungen bei JEDEM
          Beenden, dauerhaft aktiv bis der Nutzer es selbst abschaltet.
        Zeigt abschließend die Fly-Safe-Meldung.
        """
        delete_once   = self.settings.get("delete_once_on_exit", False)
        delete_always = self.settings.get("delete_always_on_exit", False)
        deleted = False

        try:
            if delete_always:
                _vault.delete_all_user_data(include_settings=True)
                deleted = True
                _log.warning("Beenden: 'Immer löschen' aktiv — alle Userdaten gelöscht")
            elif delete_once:
                # include_settings=True (nicht False wie ursprünglich):
                # Nutzer erwartet nach "Einmalig löschen" den exakten
                # Zustand vor dem allerersten Start (first_run greift
                # wieder, Welcome-Screen erscheint erneut) — nicht nur
                # einen leeren Vault bei sonst unverändertem App-Zustand.
                _vault.delete_all_user_data(include_settings=True)
                deleted = True
                _log.info("Beenden: einmaliger Lösch-Trigger ausgeführt (inkl. Settings/Welcome-Screen)")
                # WICHTIG: kein cfg.save(self.settings) hier — settings.json
                # wurde gerade gelöscht, ein Schreiben jetzt würde sie mit
                # dem RAM-Stand (first_run: False) sofort wieder anlegen
                # und den ganzen Zweck der Löschung unterlaufen. Die Datei
                # bleibt bewusst weg; beim nächsten Start lädt core.settings
                # automatisch die Defaults (first_run: True).
            else:
                # Normalfall: Sitzung im RAM aufräumen. Die Platte zeigt
                # bereits durchgehend nur die verschlüsselte Version,
                # hier passiert kein zusätzliches Schreiben mehr.
                _vault.lock_session()
        except Exception as e:
            _log.error(f"Fehler beim Beenden-Handling: {e}")

        try:
            dlg = FlySafeDialog(deleted=deleted, parent=self)
            dlg.exec()
        except Exception as e:
            _log.error(f"Fly-Safe-Dialog fehlgeschlagen: {e}")

        super().closeEvent(event)