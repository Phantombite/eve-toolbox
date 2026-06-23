"""
Willkommens-Bildschirm — wird nur beim ersten Start angezeigt.
"""
from core import logger as _logger
_log = _logger.get("welcome_screen")

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QWidget, QComboBox, QButtonGroup,
                              QStackedWidget, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import (QPainter, QColor, QFont, QLinearGradient,
                          QPainterPath, QPen, QPixmap)
from pathlib import Path

from core.config import FACTIONS, APP_VERSION
from core.i18n import t, set_language

ASSETS = Path(__file__).resolve().parent.parent / "assets" / "icons"


class FactionCard(QWidget):
    """Klickbare Fraktionskarte."""
    clicked = pyqtSignal(str)

    def __init__(self, faction_key: str, faction: dict, parent=None):
        super().__init__(parent)
        self._key     = faction_key
        self._faction = faction
        self._selected = False
        self._hov      = False
        self.setFixedSize(100, 100)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, v: bool):
        self._selected = v
        self.update()

    def enterEvent(self, e): self._hov = True;  self.update()
    def leaveEvent(self, e): self._hov = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._key)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h  = self.width(), self.height()
        acc   = QColor(self._faction["accent"])

        # Hintergrund
        path = QPainterPath()
        path.addRoundedRect(QRectF(2, 2, w-4, h-4), 10, 10)

        if self._selected:
            p.fillPath(path, QColor(acc.red(), acc.green(), acc.blue(), 60))
            p.setPen(QPen(acc, 2.5))
        elif self._hov:
            p.fillPath(path, QColor(acc.red(), acc.green(), acc.blue(), 30))
            p.setPen(QPen(acc, 1.5))
        else:
            p.fillPath(path, QColor(30, 25, 45))
            p.setPen(QPen(QColor(80, 70, 100), 1))
        p.drawPath(path)

        # Logo
        logo_path = ASSETS / f"{self._key}.png"
        if logo_path.exists():
            pm = QPixmap(str(logo_path)).scaled(
                50, 50,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            p.drawPixmap((w - pm.width())//2, 12, pm)

        # Name
        p.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        p.setPen(QPen(acc if self._selected else QColor("#cccccc")))
        p.drawText(QRectF(0, h-22, w, 20),
                   Qt.AlignmentFlag.AlignCenter,
                   self._faction["name"])
        p.end()


class OptionBtn(QPushButton):
    """Toggle-Button für Theme/Layout-Auswahl. Akzentfarbe folgt der
    aktuell gewählten Fraktion/Corporation — keine fest hartcodierte
    Farbe mehr, damit ein Design-Wechsel sofort sichtbar wird."""
    def __init__(self, label: str, accent: str = "#BA7517", parent=None):
        super().__init__(label, parent)
        self.setCheckable(True)
        self.setFixedHeight(36)
        self._accent = accent
        self._update_style()
        self.toggled.connect(lambda _: self._update_style())

    def set_accent(self, accent: str):
        self._accent = accent
        self._update_style()

    def _update_style(self):
        if self.isChecked():
            self.setStyleSheet(
                f"background: {self._accent}; color: white; border-radius: 8px;"
                "font-weight: 700; font-size: 13px; border: none;")
        else:
            self.setStyleSheet(
                "background: rgba(255,255,255,0.08); color: #aaaaaa;"
                "border-radius: 8px; font-size: 13px; border: none;")


class WelcomeScreen(QDialog):
    """Willkommens-Dialog beim ersten Start."""
    setup_complete = pyqtSignal(dict)  # Gibt gewählte Settings zurück

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings     = dict(settings)
        self._sel_faction = "amarr"
        self._sel_theme   = "dark"
        self._sel_lang    = "en"
        # Labels, die nur den "gedämpften Grau"-Stil tragen (Sektion-
        # Überschriften etc.) — zu zahlreich für einzelne Instanz-
        # attribute, daher zentral in einer Liste verwaltet und in
        # _apply_theme() gemeinsam aktualisiert.
        self._theme_dependent_labels = []
        # Wie oben, aber für Text, der die "main_text"-Helligkeit
        # braucht statt der gedämpften "muted_text"-Variante (z.B. der
        # Sicherheitsseiten-Titel, der nicht wie eine Sektion-
        # Überschrift wirken soll, sondern wie ein echter Seitentitel).
        self._theme_dependent_labels_strong = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Dialog)
        self.setModal(True)
        self.setFixedSize(560, 700)
        self._center()
        self._build()

    def _center(self):
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2)

    def _set_combo_style(self, combo, accent: str):
        """Setzt das Dropdown-Stylesheet mit einer konkreten Akzentfarbe
        UND passend zum aktuellen Theme — vorher war der Hintergrund
        fest auf Dark hartcodiert (#1a1a2e), unabhängig vom gewählten
        Theme, nur die Akzentfarbe selbst war schon umschaltbar."""
        is_dark = self._sel_theme == "dark"
        combo_bg   = "rgba(255,255,255,0.08)" if is_dark else "rgba(0,0,0,0.05)"
        combo_text = "white" if is_dark else "#1a1a1a"
        list_bg    = "#1a1a2e" if is_dark else "#ffffff"
        list_text  = "white" if is_dark else "#1a1a1a"
        combo.setStyleSheet(
            f"QComboBox {{ background: {combo_bg}; color: {combo_text};"
            "border-radius: 8px; padding: 0 12px; font-size: 13px; border: none; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
            f"QComboBox QAbstractItemView {{ background: {list_bg}; color: {list_text};"
            f"border: 1px solid {accent}; selection-background-color: {accent}; }}")

    def _set_start_btn_style(self, accent: str):
        self._start_btn.setStyleSheet(
            f"background: {accent}; color: white; border-radius: 10px; border: none;")
        if hasattr(self, "_setup_pw_btn"):
            self._setup_pw_btn.setStyleSheet(
                f"background: {accent}; color: white; border-radius: 8px;"
                "border: none; font-size: 13px; font-weight: 600;")

    def _build(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        # ── Header ────────────────────────────────────────────
        header = QWidget()
        header.setFixedHeight(220)
        header.setStyleSheet("background: transparent;")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(40, 20, 40, 10)
        hl.setSpacing(4)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo — __file__ = .../eve_toolbox/ui/welcome_screen.py,
        # assets liegt eine Ebene höher, direkt unter eve_toolbox/
        logo_path = Path(__file__).resolve().parent.parent / "assets" / "EVE Toolbox.png"
        if logo_path.exists():
            logo_lbl = QLabel()
            logo_pm = QPixmap(str(logo_path)).scaled(
                110, 110,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(logo_pm)
            logo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_lbl.setStyleSheet("background: transparent;")
            hl.addWidget(logo_lbl)

        self._title_lbl = QLabel("EVE Toolbox")
        self._title_lbl.setFont(QFont("Segoe UI", 28, QFont.Weight.Black))
        self._title_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self._title_lbl)

        self._sub_lbl = QLabel(f"v{APP_VERSION}  ·  by phantombite")
        self._sub_lbl.setFont(QFont("Segoe UI", 11))
        self._sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hl.addWidget(self._sub_lbl)

        main.addWidget(header)

        # ── Inhalt — zweistufiger Assistent (Setup / Sicherheit) ──
        # Beide Seiten liegen im selben Fenster (kein zweiter Dialog,
        # kein Fenster-Flackern) — "Weiter" wechselt von Seite 1 auf 2,
        # "Zurück" geht wieder zurück, Header/Footer-Rahmen bleiben fix.
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cl = QVBoxLayout(content)
        cl.setContentsMargins(40, 10, 40, 10)
        cl.setSpacing(20)

        # Sprache — Dropdown (skaliert für viele Sprachen)
        cl.addWidget(self._section_label("Language"))
        self._lang_cb = QComboBox()
        self._lang_cb.setFixedHeight(36)
        self._set_combo_style(self._lang_cb, "#BA7517")  # Default Amarr, wird bei Auswahl aktualisiert
        self._lang_items = [
            {"code": "en", "name": "English 🇬🇧"},
            {"code": "de", "name": "Deutsch 🇩🇪"},
        ]
        for lang in self._lang_items:
            self._lang_cb.addItem(lang["name"], lang["code"])
        self._lang_cb.setCurrentIndex(0)  # English default
        self._lang_cb.currentIndexChanged.connect(
            lambda i: self._set_lang(self._lang_items[i]["code"]))
        cl.addWidget(self._lang_cb)

        # Theme
        self._theme_label = QLabel(t("settings.theme"))
        self._theme_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._theme_dependent_labels.append(self._theme_label)
        cl.addWidget(self._theme_label)

        theme_row = QHBoxLayout()
        theme_grp = QButtonGroup(self)
        self._btn_dark  = OptionBtn("🌙  Dark")
        self._btn_light = OptionBtn("☀  Light")
        self._btn_dark.setChecked(True)
        theme_grp.addButton(self._btn_dark)
        theme_grp.addButton(self._btn_light)
        theme_grp.setExclusive(True)
        self._btn_dark.toggled.connect(lambda v: v and self._set("theme","dark"))
        self._btn_light.toggled.connect(lambda v: v and self._set("theme","light"))
        theme_row.addWidget(self._btn_dark)
        theme_row.addWidget(self._btn_light)
        cl.addLayout(theme_row)

        # Fraktion
        self._faction_label = QLabel(t("settings.faction_design"))
        self._faction_label.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._theme_dependent_labels.append(self._faction_label)
        cl.addWidget(self._faction_label)

        faction_row = QHBoxLayout()
        faction_row.setSpacing(12)
        self._faction_cards = {}
        for key, f in sorted(FACTIONS.items(), key=lambda x: x[1]["name"]):
            card = FactionCard(key, f)
            card.clicked.connect(self._set_faction)
            faction_row.addWidget(card)
            self._faction_cards[key] = card
        self._faction_cards["amarr"].set_selected(True)
        cl.addLayout(faction_row)
        cl.addStretch()

        self._stack.addWidget(content)            # Index 0: Setup
        self._stack.addWidget(self._build_security_page())  # Index 1: Sicherheit
        main.addWidget(self._stack)

        # ── Footer ────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet("background: transparent;")
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(40, 10, 40, 30)
        fl.setSpacing(8)

        self._start_btn = QPushButton(t("settings.welcome_next"))
        self._start_btn.setFixedHeight(48)
        self._start_btn.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._set_start_btn_style("#BA7517")  # Default Amarr, wird bei Auswahl aktualisiert
        self._start_btn.clicked.connect(self._go_to_security_page)
        fl.addWidget(self._start_btn)

        self._note_lbl = QLabel(t("settings.welcome_trademark"))
        self._note_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._note_lbl.setStyleSheet("font-size: 9px; background: transparent;")
        fl.addWidget(self._note_lbl)

        main.addWidget(footer)
        self._apply_theme()  # initialer Stand (Default: Dark)

    def _section_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        lbl.setStyleSheet("background: transparent;")
        self._theme_dependent_labels.append(lbl)
        return lbl

    def _set_lang(self, lang: str):
        self._sel_lang = lang
        set_language(lang)
        # Alle übersetzbaren Texte konsistent über t() aktualisieren —
        # vorher fehlte der Trademark-Hinweis hier komplett (blieb immer
        # Englisch), und der Start-Button hatte eine eigene if/else-
        # Sonderlogik statt über das normale i18n-System zu laufen.
        self._theme_label.setText(t("settings.theme"))
        self._faction_label.setText(t("settings.faction_design"))
        self._start_btn.setText(t("settings.welcome_next"))
        self._note_lbl.setText(t("settings.welcome_trademark"))

    def _set(self, key: str, val):
        self.settings[key] = val
        if key == "theme":
            # _sel_theme wird im paintEvent gelesen — ohne dieses Update
            # hätte der Theme-Wechsel weiterhin keinen sichtbaren Effekt
            # im Fenster selbst, nur die spätere settings.json wäre korrekt.
            self._sel_theme = val
            self._apply_theme()
            self.update()

    def _apply_theme(self):
        """Aktualisiert alle Theme-abhängigen Texte/Hinweise auf Dark
        oder Light — vorher komplett hartcodiert auf Dark, der
        Theme-Umschalter hatte trotz Auswahl keinen sichtbaren Effekt
        im Willkommens-Fenster selbst."""
        is_dark = self._sel_theme == "dark"
        main_text   = "#ffffff" if is_dark else "#1a1a1a"
        muted_text  = "#cccccc" if is_dark else "#555555"
        faint_text  = "rgba(255,255,255,0.25)" if is_dark else "rgba(0,0,0,0.35)"

        self._title_lbl.setStyleSheet(f"color: {main_text}; background: transparent;")
        self._note_lbl.setStyleSheet(f"color: {faint_text}; font-size: 9px; background: transparent;")
        for lbl in self._theme_dependent_labels:
            lbl.setStyleSheet(f"color: {muted_text}; background: transparent;")
        for lbl in self._theme_dependent_labels_strong:
            lbl.setStyleSheet(f"color: {main_text}; background: transparent;")
        if hasattr(self, "_back_btn"):
            # _back_btn existiert erst nach dem Aufbau der Sicherheitsseite
            back_text = "#cccccc" if is_dark else "#444444"
            back_bg = "rgba(255,255,255,0.08)" if is_dark else "rgba(0,0,0,0.06)"
            self._back_btn.setStyleSheet(
                f"background: {back_bg}; color: {back_text};"
                "border-radius: 8px; border: none; font-size: 13px;")
            skip_text = "#999999" if is_dark else "#777777"
            self._skip_btn.setStyleSheet(
                f"color: {skip_text}; background: transparent; border: none;"
                "font-size: 12px; text-decoration: underline;")

        # Dropdown-Hintergrund hängt zusätzlich zur Akzentfarbe vom
        # Theme ab — muss hier erneut gesetzt werden, sonst bliebe das
        # Sprach-Dropdown bis zum nächsten Fraktionswechsel im alten
        # (immer dunklen) Stil stehen.
        current_accent = FACTIONS.get(self._sel_faction, FACTIONS["amarr"])["accent"]
        self._set_combo_style(self._lang_cb, current_accent)

    def _set_faction(self, key: str):
        for k, card in self._faction_cards.items():
            card.set_selected(k == key)
        self._sel_faction = key

        # Live-Vorschau: alle UI-Elemente, die bisher fest lila waren,
        # übernehmen sofort die Akzentfarbe der gewählten Fraktion/
        # Corporation — der Nutzer sieht direkt, wie das Programm mit
        # diesem Design aussehen würde, statt das erst nach dem
        # eigentlichen Start zu erfahren.
        accent = FACTIONS.get(key, FACTIONS["amarr"])["accent"]
        self._sub_lbl.setStyleSheet(f"color: {accent}; background: transparent;")
        self._set_combo_style(self._lang_cb, accent)
        self._set_start_btn_style(accent)
        for btn in (self._btn_dark, self._btn_light):
            btn.set_accent(accent)
        self.update()  # Rahmenfarbe im paintEvent folgt ebenfalls der Fraktion

    def _go_to_security_page(self):
        """Wechselt von Seite 1 (Setup) zu Seite 2 (Sicherheit) — der
        Start-Button heißt auf Seite 1 "Weiter", erst auf Seite 2 gibt
        es den eigentlichen Abschluss-Button."""
        self._stack.setCurrentIndex(1)
        self._start_btn.hide()  # Seite 2 hat ihre eigenen Buttons im Footer

    def _go_back_to_setup_page(self):
        self._stack.setCurrentIndex(0)
        self._start_btn.show()

    def _build_security_page(self) -> QWidget:
        """Seite 2 des Assistenten — erklärt, wofür das Master-Passwort
        gedacht ist, lässt es optional gleich einrichten (zwei Felder),
        oder per "Später einrichten" überspringen. Überspringen ändert
        NICHTS an der bestehenden Lazy-Login-Architektur aus Block 1 —
        wer überspringt, sieht beim ersten Öffnen einer account-
        gebundenen Funktion einfach das normale Setup-UnlockPopup,
        genau wie bisher auch ohne dieses Onboarding."""
        page = QWidget()
        page.setStyleSheet("background: transparent;")
        pl = QVBoxLayout(page)
        pl.setContentsMargins(40, 10, 40, 10)
        pl.setSpacing(14)

        self._sec_title = QLabel(t("security.tab_title"))
        self._sec_title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self._theme_dependent_labels_strong.append(self._sec_title)
        pl.addWidget(self._sec_title)

        self._sec_explainer = QLabel(t("settings.welcome_security_explainer"))
        self._sec_explainer.setWordWrap(True)
        self._sec_explainer.setFont(QFont("Segoe UI", 11))
        self._theme_dependent_labels.append(self._sec_explainer)
        pl.addWidget(self._sec_explainer)

        self._pw_input = QLineEdit()
        self._pw_input.setPlaceholderText(t("security.new_password"))
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_input.setFixedHeight(38)
        pl.addWidget(self._pw_input)

        self._pw_repeat_input = QLineEdit()
        self._pw_repeat_input.setPlaceholderText(t("security.new_password_repeat"))
        self._pw_repeat_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_repeat_input.setFixedHeight(38)
        pl.addWidget(self._pw_repeat_input)

        self._sec_error_lbl = QLabel("")
        self._sec_error_lbl.setStyleSheet("color: #D85A30; font-size: 11px; background: transparent;")
        self._sec_error_lbl.setWordWrap(True)
        self._sec_error_lbl.hide()
        pl.addWidget(self._sec_error_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._back_btn = QPushButton(t("settings.welcome_back"))
        self._back_btn.setFixedHeight(44)
        self._back_btn.setStyleSheet(
            "background: rgba(255,255,255,0.08); color: #cccccc;"
            "border-radius: 8px; border: none; font-size: 13px;")
        self._back_btn.clicked.connect(self._go_back_to_setup_page)
        btn_row.addWidget(self._back_btn)

        self._setup_pw_btn = QPushButton(t("settings.welcome_setup_password"))
        self._setup_pw_btn.setFixedHeight(44)
        self._setup_pw_btn.clicked.connect(self._finish_with_password)
        btn_row.addWidget(self._setup_pw_btn)

        pl.addLayout(btn_row)

        self._skip_btn = QPushButton(t("settings.welcome_skip_password"))
        self._skip_btn.setFlat(True)
        self._skip_btn.setStyleSheet(
            "color: #999999; background: transparent; border: none;"
            "font-size: 12px; text-decoration: underline;")
        self._skip_btn.clicked.connect(self._finish)
        pl.addWidget(self._skip_btn)

        pl.addStretch()
        return page

    def _finish_with_password(self):
        """Richtet den Vault direkt hier mit dem eingegebenen Passwort
        ein, statt das später dem normalen UnlockPopup zu überlassen —
        wer die Mühe macht, hier ein Passwort einzugeben, soll nicht
        gleich danach noch einmal danach gefragt werden."""
        pw = self._pw_input.text()
        repeat = self._pw_repeat_input.text()

        if len(pw) < 8:
            self._sec_error_lbl.setText(t("security.password_too_short"))
            self._sec_error_lbl.show()
            return
        if pw != repeat:
            self._sec_error_lbl.setText(t("security.wrong_password"))
            self._sec_error_lbl.show()
            return

        from core import crypto_vault as _vault
        try:
            _vault.create_vault(pw)
        except Exception as e:
            _log.error(f"Vault-Erstellung im Onboarding fehlgeschlagen: {e}")
            self._sec_error_lbl.setText(str(e))
            self._sec_error_lbl.show()
            return

        self._finish()

    def _finish(self):
        self.settings["language"]   = self._sel_lang
        self.settings["faction"]    = self._sel_faction
        self.settings["first_run"]  = False
        self.setup_complete.emit(self.settings)
        self.accept()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Hintergrund — folgt der Theme-Auswahl (Dark/Light), die bisher
        # komplett wirkungslos war (Buttons speicherten den Wert nur in
        # self.settings, ohne jeden visuellen Effekt im Fenster selbst)
        is_dark = self._sel_theme == "dark"
        bg_color = QColor("#0d0d1a") if is_dark else QColor("#f5f5f5")

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 16, 16)
        p.fillPath(path, bg_color)

        # Rahmen — folgt der gewählten Fraktion/Corporation statt fest
        # lila (der alte lila Verlaufsbalken oben wurde entfernt, seit
        # es ein echtes Logo im Header gibt, brauchte es keinen
        # Platzhalter-Farbverlauf mehr)
        accent = QColor(FACTIONS.get(self._sel_faction, FACTIONS["amarr"])["accent"])
        border_color = QColor(accent.red(), accent.green(), accent.blue(), 140)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(border_color, 1.5))
        p.drawPath(path)
        p.end()