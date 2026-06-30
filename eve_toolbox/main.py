"""
EVE Toolbox — Startpunkt.
"""
import sys
import os
os.environ["PYTHONUNBUFFERED"] = "1"


def clear_pycache():
    """Löscht alle __pycache__ Ordner beim Start — kein manuelles Löschen nötig."""
    import shutil
    from pathlib import Path
    app_dir = Path(__file__).resolve().parent
    for cache in app_dir.rglob("__pycache__"):
        try:
            shutil.rmtree(cache)
        except Exception:
            pass


def check_python():
    if sys.version_info < (3, 10):
        print(f"Python 3.10+ benötigt. Aktuell: {sys.version}")
        sys.exit(1)


check_python()
clear_pycache()

from core import settings as cfg
from core import logger
from core.config import APP_VERSION
log = logger.get("main")


def main():
    # Sprache ZUERST laden bevor irgendwelche UI-Module importiert werden
    s = cfg.load()

    log.info("=" * 50)
    log.info("EVE Toolbox gestartet")
    log.info(f"Python {sys.version.split()[0]} | Platform: {sys.platform}")
    log.info(f"Einstellungen: faction={s.get('faction')} theme={s.get('theme')} lang={s.get('language')}")
    log.info("=" * 50)

    # Jetzt UI-Module importieren — t() gibt bereits die richtige Sprache zurück
    from pathlib import Path
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QIcon
    from ui.main_window import MainWindow, make_stylesheet
    from ui.splash_screen import SplashScreen
    from core import notifications as nf
    from core import updater
    from core import integrity
    from core.i18n import t

    app = QApplication(sys.argv)
    app.setApplicationName("EVE Toolbox")

    # Globaler Exception-Hook — so früh wie möglich installieren, bevor
    # irgendein Slot/Signal feuern oder ein Hintergrund-Thread starten
    # kann. Sicherheitsnetz gegen unsichtbare Fehler in jedem kommenden
    # Modul (siehe core.crash_handler Docstring für den Hintergrund).
    from core import crash_handler
    crash_handler.install(app)

    # Anwendungsweites Icon — wirkt zusätzlich zu window.setWindowIcon()
    # in main_window.py auf manchen Windows-Konfigurationen robuster auf
    # die Taskleiste (z.B. bevor das Hauptfenster überhaupt erstellt ist,
    # während Splash-Screen/Welcome-Screen laufen).
    icon_path = Path(__file__).resolve().parent / "assets" / "EVE Toolbox.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    else:
        log.warning(f"App-Icon nicht gefunden: {icon_path}")

    dark = s.get("theme", "dark") == "dark"
    app.setStyleSheet(make_stylesheet(s.get("faction", "caldari"), dark))

    # ── Willkommens-Bildschirm (vor allem anderen) ───────────
    if s.get("first_run", True):
        from ui.welcome_screen import WelcomeScreen
        welcome = WelcomeScreen(s)
        def _on_setup(new_settings: dict):
            s.update(new_settings)
            from core import settings as cfg_inner
            from core import i18n as i18n_inner
            cfg_inner.save(s)
            i18n_inner.set_language(s.get("language", "en"))
            dark2 = s.get("theme", "dark") == "dark"
            app.setStyleSheet(make_stylesheet(s.get("faction", "caldari"), dark2))
            log.info("Willkommens-Setup abgeschlossen")
        welcome.setup_complete.connect(_on_setup)
        welcome.exec()

    # ── Master-Passwort: KEIN erzwungener Schritt beim Start ───
    # Bewusst kein PasswordSetupScreen hier: das Programm soll ohne
    # Passwort starten und öffentliche Funktionen (z.B. normaler Markt
    # ohne Login) sofort funktionieren. Das Master-Passwort wird erst
    # gebraucht, wenn zum ersten Mal eine account-gebundene Funktion
    # aufgerufen wird — dann übernimmt core.crypto_vault.unlock_session()
    # automatisch die Erstanlage, falls noch kein Vault existiert
    # (siehe ui/unlock_popup.py). Kein separater Onboarding-Dialog nötig.

    # ── Splash Screen ─────────────────────────────────────────
    splash = SplashScreen(s)
    splash.show()
    app.processEvents()

    log.debug("Erstelle MainWindow")
    window = MainWindow(app)
    log.debug("MainWindow erstellt")

    def _start_main():
        window.show()
        w = s.get("window_width", 1200)
        h = s.get("window_height", 750)
        window.resize(w, h)
        splash.close()
        log.info(f"Hauptfenster geöffnet ({w}x{h})")

        from core import memory_monitor
        memory_monitor.start()

        if getattr(_run_startup, "dev_mode_triggered", False):
            from ui.dev_mode_notice import DevModeNoticeDialog
            notice = DevModeNoticeDialog(window)
            notice.exec()

        security_warning = getattr(_run_startup, "security_warning", None)
        if security_warning:
            from ui.security_warning_dialog import SecurityWarningDialog
            warn_title, warn_msg = security_warning
            warn_dlg = SecurityWarningDialog(warn_title, warn_msg, window)
            warn_dlg.exec()

    def _run_startup():
        log.debug("Startup-Sequenz gestartet")
        splash.set_status(t("splash.initializing"), 5)
        app.processEvents()

        # ── Update der Spieldatenbank (items/universe/characters.sqlite) ──
        # Läuft IMMER, auch im Dev-Modus (EVE_SKIP_CHECKS) — bewusst VOR
        # der EVE_SKIP_CHECKS-Prüfung platziert, damit dieser frühe
        # return (siehe unten) den Aufruf nicht überspringen kann.
        # Begründung (Dragnax-Entscheidung): die SPIELDATEN (Item-Werte,
        # Blueprint-Materialmengen, Skill-Anforderungen) sollen beim
        # Entwickeln IMMER aktuell sein, im Gegensatz zum PROGRAMM-
        # Update/Integritätscheck (core.updater/core.integrity), der im
        # Dev-Modus bewusst übersprungen wird, um nicht bei jedem
        # lokalen Start gegen GitHub zu validieren. Spieldaten und
        # Programm-Code sind zwei unabhängige Update-Mechanismen
        # (siehe core/data/db_updater.py Modul-Docstring).
        from core.data import db_updater as _db_updater

        # Splash-Screen zeigt nur eine einfache, stabile Nachricht ("was
        # macht die App gerade") — die technischen Detail-Nachrichten von
        # db_updater (welche Datei wird geladen, welche Datenbank gebaut,
        # ...) sind für den Nutzer nicht relevant und landen bereits
        # vollständig im Log (siehe core/data/db_updater.py, jeder Schritt
        # ruft _log.info()). Der progress-Callback hier wird daher
        # bewusst NICHT an splash.set_status() durchgereicht.
        def _db_update_progress(message: str):
            app.processEvents()

        log.info("Prüfe Spieldatenbank-Update...")
        splash.set_status(t("splash.updating_database"), 6)
        app.processEvents()
        db_ok = _db_updater.check_and_update(progress=_db_update_progress)
        if not db_ok:
            log.warning(
                "Spieldatenbank (items.sqlite) konnte nicht aufgebaut werden "
                "(z.B. erster Start ohne Internetverbindung) — Module, die "
                "darauf aufbauen (Markt, Industrie, ...), sind vorübergehend "
                "nicht verfügbar. Alle anderen Programmteile funktionieren normal."
            )

        # ── Dev: Checks überspringen — NUR mit gültigem Dev-Token ──
        # EVE_SKIP_CHECKS wird von debug.bat gesetzt, damit lokale
        # Entwicklung nicht bei jedem Start gegen GitHub validiert wird.
        # Anders als zuvor reicht die Variable allein NICHT mehr aus:
        # sie wird nur akzeptiert, wenn zusätzlich ein gültiger,
        # signierter Dev-Token (dev_mode.flag) vorhanden ist — derselbe
        # Trusted-Keys-Mechanismus wie für Release-Signaturen. Eine
        # blanke Umgebungsvariable allein kann von jedem gesetzt werden;
        # ein gültiger Token kann nur von jemandem mit dem privaten
        # Schlüssel erzeugt werden (core.release_crypto.sign_data()).
        if os.environ.get("EVE_SKIP_CHECKS") == "1":
            if integrity.check_dev_token():
                log.warning("EVE_SKIP_CHECKS + gültiger Dev-Token — Integritäts-/Update-Check übersprungen (DEV)")
                splash.set_status("Dev-Modus: Checks übersprungen", 90)
                app.processEvents()
                _run_startup.dev_mode_triggered = True
                QTimer.singleShot(300, splash.finish)
                return
            else:
                log.error(
                    "EVE_SKIP_CHECKS gesetzt, aber KEIN gültiger Dev-Token gefunden — "
                    "Variable wird ignoriert, voller Check läuft trotzdem."
                )
                # Bewusst kein return hier — Ablauf fällt durch zum vollen Check.

        # ── Alte _old Dateien vom letzten Update löschen ──────
        updater.cleanup_old_files()

        # ── Schritt 1: Mini-Integritätscheck (nur kritische Dateien) ──
        # Stellt sicher dass updater.py, integrity.py und main.py
        # immer funktionsfähig sind bevor der Update-Check läuft.
        splash.set_phase("integrity")
        splash.set_status("Prüfe kritische Dateien...", 8)
        app.processEvents()

        def _mini_progress(pct: int, status: str):
            mapped = 8 + int(pct * 0.12)
            splash.set_status(status, mapped)
            app.processEvents()

        log.info("Starte Mini-Integritätscheck...")
        mini_result = integrity.mini_check(progress_callback=_mini_progress)

        if mini_result.signature_valid is False and not mini_result.offline:
            log.error("Mini-Check: Signatur von checksums.json UNGÜLTIG — Reparatur nicht möglich")
        elif mini_result.needs_repair:
            to_fix = mini_result.missing_files + mini_result.corrupted_files
            log.info(f"Mini-Check: {len(to_fix)} kritische Datei(en) werden repariert...")
            local_version = integrity.get_local_version()
            fixed, failed = updater.repair_files(to_fix, local_version, verified_signature=True, checksums=mini_result.checksums)
            if failed:
                log.error(f"Mini-Check: {len(failed)} Datei(en) konnten nicht repariert werden: {failed}")
            else:
                log.info(f"Mini-Check: {len(fixed)} kritische Datei(en) erfolgreich repariert")
        else:
            log.info("Mini-Check: OK")

        app.processEvents()

        # ── Schritt 2: Update-Check (Block 3: Popup statt Vorab-Toggle) ──
        # "update_auto_install" als Vorab-Einstellung gibt es nicht mehr —
        # die Entscheidung (jetzt / beim nächsten Start) wird jedes Mal
        # über das UpdatePopup neu getroffen, nicht einmalig festgelegt.
        check_updates = s.get("update_on_start", True)

        if not check_updates:
            log.debug("Update-Check deaktiviert")
        else:
            splash.set_phase("checking")
            splash.set_status(t("splash.checking_updates"), 22)
            app.processEvents()

            # ── Stable-Version-Check (Notfall-Rollback) ────────
            # Läuft VOR dem normalen Update-Check: ein erzwungener
            # Rollback hat Vorrang vor einem regulären Update-Angebot.
            # rollback_popup_shown verhindert, dass im selben Durchlauf
            # ZUSÄTZLICH noch ein normales Update-Popup erscheint — sonst
            # sieht der Nutzer zwei unabhängige Popups direkt
            # hintereinander, was verwirrend ist und nicht dem Sinn
            # des Stable-Version-Systems entspricht (genau ein
            # Trust-Entscheid pro Start, nicht zwei konkurrierende).
            log.debug("Prüfe Stable-Version...")
            stable_status = updater.check_stable_version()
            rollback_popup_shown = False

            if stable_status.rollback_needed:
                log.warning(
                    f"Rollback empfohlen/erforderlich: v{APP_VERSION} -> "
                    f"v{stable_status.stable_version} (mandatory={stable_status.mandatory})"
                )
                splash.hide()
                from ui.update_popup import UpdatePopup
                popup = UpdatePopup(
                    current_version=APP_VERSION,
                    new_version=stable_status.stable_version,
                    notes="",
                    mandatory=stable_status.mandatory,
                    rollback=True,
                    parent=None,
                )
                popup.exec()
                splash.show()
                rollback_popup_shown = True
                log.info(
                    f"Rollback-Popup: Nutzer-Entscheidung = {popup.result_choice!r} "
                    f"(mandatory={stable_status.mandatory})"
                )

                if popup.result_choice == "install_now" or stable_status.mandatory:
                    splash.set_phase("installing")
                    splash.set_status(t("splash.creating_backup"), 35)
                    app.processEvents()
                    updater.create_backup()

                    ok, msg = updater.download_and_install(
                        stable_status.rollback_info,
                        allow_downgrade=True,  # gewollter, signierter Rollback
                        progress_callback=lambda pct: (
                            splash.set_status(f"Rolle zurück... {pct}%", 40 + int(pct * 0.45)),
                            app.processEvents()
                        )
                    )
                    if not ok:
                        log.error(f"Rollback fehlgeschlagen: {msg}")
                        _run_startup.security_warning = ("Rollback fehlgeschlagen", msg)
                # "later" bei mandatory=False: einfach normal weiterstarten,
                # kein Download, nächster Start fragt erneut.

            log.debug("Prüfe auf Updates...")
            info = updater.check_sync() if not rollback_popup_shown else None
            if rollback_popup_shown:
                log.debug(
                    "Regulärer Update-Check übersprungen — Rollback-Popup "
                    "wurde in diesem Durchlauf bereits gezeigt, kein "
                    "zweites Popup im selben Start."
                )

            if info:
                log.info(f"Update verfügbar: v{info['version']}")
                splash.set_status(t("splash.update_found", version=info["version"]), 30)
                app.processEvents()

                splash.hide()
                from ui.update_popup import UpdatePopup
                popup = UpdatePopup(
                    current_version=APP_VERSION,
                    new_version=info["version"],
                    notes=info.get("notes", ""),
                    mandatory=False,
                    rollback=False,
                    parent=None,
                )
                popup.exec()
                splash.show()
                log.info(f"Update-Popup: Nutzer-Entscheidung = {popup.result_choice!r}")

                if popup.result_choice == "install_now":
                    splash.set_phase("installing")
                    splash.set_status(t("splash.creating_backup"), 35)
                    app.processEvents()

                    log.info("Erstelle Backup...")
                    updater.create_backup()

                    log.info(f"Installiere Update v{info['version']}...")
                    splash.set_status(t("splash.installing", version=info["version"]), 40)
                    app.processEvents()

                    # download_and_install → startet neu nach Erfolg (kehrt nicht zurück)
                    ok, msg = updater.download_and_install(
                        info,
                        progress_callback=lambda pct: (
                            splash.set_status(
                                t("splash.installing", version=info["version"]) + f" {pct}%",
                                40 + int(pct * 0.45)
                            ),
                            app.processEvents()
                        )
                    )

                    if not ok:
                        log.error(f"Update fehlgeschlagen: {msg}")
                        splash.set_status(t("splash.failed", error=msg), 80)
                        _add_update_notif(window, info, installed=False, failed=True)
                        app.processEvents()
                        if "Signatur" in msg or "UNGÜLTIG" in msg:
                            _run_startup.security_warning = (
                                "Update-Signatur ungültig",
                                "Die heruntergeladene Update-Datei hatte eine ungültige "
                                "Signatur und wurde verworfen — die Installation wurde "
                                "abgebrochen, bevor irgendetwas verändert wurde. "
                                "Die App läuft unverändert in der bisherigen Version weiter."
                            )
                else:
                    # "later" — bewusst KEIN Pre-Download (Teil B der
                    # Roadmap). Nächster Start fragt erneut, nichts liegt
                    # in der Zwischenzeit unnötig auf der Platte.
                    _add_update_notif(window, info, installed=False)
                    splash.set_status(t("splash.no_auto_install"), 80)
                    app.processEvents()
            else:
                log.debug("Kein Update verfügbar")
                splash.set_status(t("splash.no_update"), 22)
                app.processEvents()

        # ── Schritt 3: Voller Integritätscheck ────────────────
        splash.set_phase("integrity")
        splash.set_status(t("splash.integrity_start"), 25)
        app.processEvents()

        def _integrity_progress(pct: int, status: str):
            mapped = 25 + int(pct * 0.55)
            splash.set_status(status, mapped)
            app.processEvents()

        log.info("Starte Integritätscheck...")
        int_result = integrity.run_check(progress_callback=_integrity_progress)

        if int_result.dev_mode:
            log.info("Dev-Modus: Integritätscheck übersprungen")
            splash.set_status(t("splash.integrity_token"), 80)
        elif int_result.offline:
            log.warning("Offline: Integritätscheck übersprungen")
            splash.set_status(t("splash.integrity_offline"), 80)
        elif int_result.signature_valid is False:
            log.error("Integritätscheck: Signatur von checksums.json UNGÜLTIG — Prüfung verworfen")
            splash.set_status(t("splash.integrity_failed", n=0), 80)
            _run_startup.security_warning = (
                "Signaturprüfung fehlgeschlagen",
                "Die Signatur der Prüfsummen-Datei konnte nicht verifiziert werden. "
                "Aus Sicherheitsgründen wurde KEINE Integritätsprüfung und KEINE Reparatur "
                "durchgeführt. Das kann an einer fehlenden Internetverbindung liegen, "
                "oder die Datei wurde manipuliert. Die App funktioniert normal weiter, "
                "Updates sind aber vorübergehend nicht möglich."
            )
        elif int_result.needs_repair:
            to_fix = int_result.missing_files + int_result.corrupted_files
            log.info(f"Integritätscheck: {len(to_fix)} Datei(en) werden repariert...")
            local_version = integrity.get_local_version()

            def _repair_progress(pct: int, status: str):
                mapped = 80 + int(pct * 0.15)
                splash.set_status(status, mapped)
                app.processEvents()

            fixed, failed = updater.repair_files(to_fix, local_version, verified_signature=True, checksums=int_result.checksums, progress_callback=_repair_progress)

            if failed:
                log.error(f"Integritätscheck: {len(failed)} Fehler — {failed}")
                splash.set_status(t("splash.integrity_failed", n=len(failed)), 95)
            else:
                log.info(f"Integritätscheck: {len(fixed)} Dateien repariert")
                splash.set_status(t("splash.integrity_fixed", n=len(fixed)), 95)
        else:
            log.info("Integritätscheck: Alle Dateien OK")
            splash.set_status(t("splash.integrity_ok"), 80)

        app.processEvents()
        QTimer.singleShot(400, splash.finish)

    def _add_update_notif(win, info: dict, installed: bool, failed: bool = False):
        notifs = win._notifications
        if installed:
            notifs = nf.add_notification(
                notifs,
                notif_id   = f"update_avail_{info['version'].replace('.','_')}",
                ntype      = nf.TYPE_UPDATE,
                title      = f"Update v{info['version']} war verfügbar",
                text       = info.get("notes", ""),
                valid_until= "2099-12-31",
            )
            notifs = nf.mark_read(notifs, f"update_avail_{info['version'].replace('.','_')}")
            notifs = nf.add_notification(
                notifs,
                notif_id   = f"update_done_{info['version'].replace('.','_')}",
                ntype      = nf.TYPE_UPDATE,
                title      = f"Update v{info['version']} erfolgreich installiert",
                text       = "Bitte starte die App neu um die neue Version zu nutzen.",
                valid_until= "2099-12-31",
            )
        elif failed:
            notifs = nf.add_notification(
                notifs,
                notif_id   = f"update_fail_{info['version'].replace('.','_')}",
                ntype      = nf.TYPE_WARNING,
                title      = f"Update v{info['version']} fehlgeschlagen",
                text       = "Das Update konnte nicht installiert werden.",
                valid_until= "2099-12-31",
            )
        else:
            notifs = nf.add_notification(
                notifs,
                notif_id   = f"update_avail_{info['version'].replace('.','_')}",
                ntype      = nf.TYPE_UPDATE,
                title      = f"Update v{info['version']} verfügbar",
                text       = info.get("notes","") + " — Wird beim nächsten Neustart erneut angeboten.",
                valid_until= "2099-12-31",
            )
        win._notifications = notifs
        win._update_blink()

    splash.set_status(t("splash.loading"), 5)
    splash.finished.connect(_start_main)
    QTimer.singleShot(200, _run_startup)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()