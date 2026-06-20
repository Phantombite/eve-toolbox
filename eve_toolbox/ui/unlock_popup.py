"""
Entschlüsselungs-Popup (UnlockPopup) — erscheint statt des Account-Popups,
solange der Vault gesperrt ist. Gleicher Anker-Punkt, gleiches Styling-
Schema (Fraktionsfarbe) wie AccountPopup, damit der Wechsel zwischen
beiden Zuständen sich nahtlos anfühlt.

Ablauf:
    1. Nutzer klickt auf das Charakter-Widget in der Topbar (Status "Gesperrt")
    2. UnlockPopup erscheint mit Passwortfeld
    3. Bei korrektem Passwort: vault.unlock_session() erfolgreich
       → Signal `unlocked` wird gesendet, Topbar zeigt danach das normale
         AccountPopup
    4. Bei falschem Passwort: Fehlermeldung im selben Popup, neuer Versuch
    5. "Zur Sicherheit" Link → öffnet Einstellungen direkt auf dem
       Sicherheits-Reiter (analog zu "Account-Verwaltung" im AccountPopup)
"""
from core import logger as _logger
_log = _logger.get("unlock_popup")

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QFrame, QLineEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from core import crypto_vault as _vault
from core.i18n import t


class UnlockPopup(QWidget):
    """Fraktions-gestyltes Passwort-Popup — ersetzt AccountPopup im
    gesperrten Zustand."""
    unlocked      = pyqtSignal()   # Vault erfolgreich entsperrt
    open_security = pyqtSignal()   # "Zur Sicherheit" → Einstellungen öffnen

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self._settings = settings
        self.setObjectName("SettingsPanel")
        self.setWindowFlags(
            Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setFixedWidth(260)
        self._outer_layout = QVBoxLayout(self)
        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(0)
        self._build()

    def _clear_layout(self):
        while self._outer_layout.count():
            item = self._outer_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _build(self):
        # Inhalt komplett neu aufbauen — Setup- vs. Unlock-Ansicht kann
        # sich zwischen zwei Anzeigen ändern (z.B. nach "Alle Daten
        # löschen" existiert plötzlich wieder kein Vault).
        self._clear_layout()
        lay = self._outer_layout

        is_setup = not _vault.vault_exists()

        # Header
        hdr = QWidget()
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 10, 14, 10)
        title_text = ("🔐  " + t("security.setup_title")) if is_setup else ("🔒  " + t("security.locked_title"))
        title = QLabel(title_text)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setObjectName("PanelTitle")
        title.setStyleSheet("background: transparent;")
        title.setWordWrap(True)
        hl.addWidget(title)
        lay.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("HLine")
        lay.addWidget(sep)

        # Inhalt
        body = QWidget()
        bl   = QVBoxLayout(body)
        bl.setContentsMargins(14, 14, 14, 14)
        bl.setSpacing(10)

        if is_setup:
            # Erstanlage: kein Vault vorhanden — dieses Popup ist beim
            # allerersten Aufruf einer account-gebundenen Funktion
            # gleichzeitig die Einrichtung des Master-Passworts.
            expl = QLabel(t("security.setup_explanation"))
            expl.setWordWrap(True)
            expl.setStyleSheet("font-size: 10px; color: #ccc; background: transparent;")
            bl.addWidget(expl)

            warn = QLabel(t("security.setup_warning"))
            warn.setWordWrap(True)
            warn.setStyleSheet(
                "font-size: 9px; color: #f0b840; background: rgba(240,184,64,0.08);"
                "border: 1px solid rgba(240,184,64,0.3); border-radius: 6px; padding: 8px;")
            bl.addWidget(warn)
        else:
            hint = QLabel(t("security.unlock_hint"))
            hint.setWordWrap(True)
            hint.setStyleSheet("font-size: 10px; color: #888; background: transparent;")
            bl.addWidget(hint)

        self._pw_input = QLineEdit()
        self._pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        placeholder = t("security.setup_password") if is_setup else t("security.password_placeholder")
        self._pw_input.setPlaceholderText(placeholder)
        self._pw_input.setFixedHeight(32)
        if not is_setup:
            self._pw_input.returnPressed.connect(self._try_unlock)
        bl.addWidget(self._pw_input)

        # Zweites Feld nur bei Erstanlage — Passwort muss bestätigt werden,
        # da es bei Verlust nicht wiederherstellbar ist.
        self._pw_repeat = None
        if is_setup:
            self._pw_repeat = QLineEdit()
            self._pw_repeat.setEchoMode(QLineEdit.EchoMode.Password)
            self._pw_repeat.setPlaceholderText(t("security.setup_password_repeat"))
            self._pw_repeat.setFixedHeight(32)
            self._pw_repeat.returnPressed.connect(self._try_unlock)
            bl.addWidget(self._pw_repeat)

        self._error_lbl = QLabel("")
        self._error_lbl.setWordWrap(True)
        self._error_lbl.setStyleSheet("font-size: 10px; color: #e05a5a; background: transparent;")
        self._error_lbl.hide()
        bl.addWidget(self._error_lbl)

        btn_text = t("security.setup_continue") if is_setup else t("security.unlock_button")
        btn_icon = "🔐  " if is_setup else "🔓  "
        self._unlock_btn = QPushButton(btn_icon + btn_text)
        self._unlock_btn.setObjectName("AccentBtn")
        self._unlock_btn.setFixedHeight(30)
        self._unlock_btn.clicked.connect(self._try_unlock)
        bl.addWidget(self._unlock_btn)

        lay.addWidget(body)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setObjectName("HLine")
        lay.addWidget(sep2)

        # Footer — Link zu Sicherheits-Einstellungen
        footer = QWidget()
        fl     = QVBoxLayout(footer)
        fl.setContentsMargins(12, 8, 12, 8)
        sec_btn = QPushButton("⚙  " + t("security.open_settings"))
        sec_btn.setObjectName("AccentBtn")
        sec_btn.setFixedHeight(28)
        sec_btn.clicked.connect(self._on_open_security)
        fl.addWidget(sec_btn)
        lay.addWidget(footer)

    def showEvent(self, event):
        super().showEvent(event)
        self._build()
        self._error_lbl.hide()
        self._pw_input.setFocus()

    def _try_unlock(self):
        password = self._pw_input.text()
        if not password:
            return

        is_setup = not _vault.vault_exists()
        if is_setup:
            repeat = self._pw_repeat.text() if self._pw_repeat else ""
            if len(password) < 8:
                self._error_lbl.setText(t("security.setup_too_short"))
                self._error_lbl.show()
                return
            if password != repeat:
                self._error_lbl.setText(t("security.setup_mismatch"))
                self._error_lbl.show()
                return

        try:
            _vault.unlock_session(password)
        except _vault.WrongPassword:
            self._error_lbl.setText(t("security.wrong_password"))
            self._error_lbl.show()
            self._pw_input.clear()
            self._pw_input.setFocus()
            _log.warning("Entschlüsselung fehlgeschlagen — falsches Passwort")
            return
        except _vault.VaultError as e:
            self._error_lbl.setText(str(e))
            self._error_lbl.show()
            _log.error(f"Vault-Fehler beim Entsperren: {e}")
            return

        _log.info("Vault erfolgreich entsperrt" if not is_setup else "Master-Passwort erstmalig eingerichtet")
        self.hide()
        self.unlocked.emit()

    def _on_open_security(self):
        self.hide()
        self.open_security.emit()

    def update_faction(self, faction: str):
        self._settings["faction"] = faction