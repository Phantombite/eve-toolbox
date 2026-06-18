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
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QTimer
    from ui.main_window import MainWindow, make_stylesheet
    from ui.splash_screen import SplashScreen
    from core import notifications as nf
    from core import updater
    from core import integrity
    from core.i18n import t

    app = QApplication(sys.argv)
    app.setApplicationName("EVE Toolbox")

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

    def _run_startup():
        log.debug("Startup-Sequenz gestartet")
        splash.set_status(t("splash.initializing"), 10)
        app.processEvents()

        # ── Integritätscheck ──────────────────────────────────
        splash.set_phase("integrity")
        splash.set_status(t("splash.integrity_start"), 10)
        app.processEvents()

        def _integrity_progress(pct: int, status: str):
            # Integrity läuft von 10-40% im Gesamtfortschritt
            mapped = 10 + int(pct * 0.30)
            splash.set_status(status, mapped)
            app.processEvents()

        log.info("Starte Integritätscheck...")
        int_result = integrity.run_check(progress_callback=_integrity_progress)

        if int_result.dev_mode:
            log.info("Dev-Modus: Integritätscheck übersprungen")
            splash.set_status(t("splash.integrity_token"), 40)
        elif int_result.offline:
            log.warning("Offline: Integritätscheck übersprungen")
            splash.set_status(t("splash.integrity_offline"), 40)
        elif int_result.files_failed:
            log.error(f"Integritätscheck: {len(int_result.files_failed)} Fehler")
            splash.set_status(t("splash.integrity_failed", n=len(int_result.files_failed)), 40)
        elif int_result.files_fixed:
            log.info(f"Integritätscheck: {int_result.files_fixed} Dateien repariert")
            splash.set_status(t("splash.integrity_fixed", n=int_result.files_fixed), 40)
        else:
            log.info("Integritätscheck: Alle Dateien OK")
            splash.set_status(t("splash.integrity_ok"), 40)

        app.processEvents()

        # ── Update-Check ──────────────────────────────────────
        check_updates = s.get("update_on_start", True)
        auto_install  = s.get("update_auto_install", True)

        if not check_updates:
            log.debug("Update-Check deaktiviert")
            splash.set_status(t("splash.starting"), 90)
            app.processEvents()
            splash.finish()
            return

        splash.set_phase("checking")
        splash.set_status(t("splash.checking_updates"), 45)
        app.processEvents()

        log.debug("Prüfe auf Updates...")
        info = updater.check_sync()

        if not info:
            log.debug("Kein Update verfügbar")
            splash.set_status(t("splash.no_update"), 80)
            app.processEvents()
            QTimer.singleShot(400, splash.finish)
            return

        log.info(f"Update verfügbar: v{info['version']}")
        splash.set_status(t("splash.update_found", version=info["version"]), 40)
        app.processEvents()

        if not auto_install:
            _add_update_notif(window, info, installed=False)
            splash.set_status(t("splash.no_auto_install"), 80)
            app.processEvents()
            QTimer.singleShot(600, splash.finish)
            return

        splash.set_phase("installing")
        splash.set_status(t("splash.creating_backup"), 60)
        app.processEvents()

        log.info("Erstelle Backup...")
        updater.create_backup()
        splash.set_status(t("splash.installing", version=info["version"]), 70)
        app.processEvents()

        log.info(f"Installiere Update v{info['version']}...")
        ok, msg = updater.download_and_install(
            info,
            progress_callback=lambda pct: (
                splash.set_status(t("splash.installing", version=info["version"]) + f" {pct}%",
                                  50 + pct // 5),
                app.processEvents()
            )
        )

        if ok:
            log.info(f"Update v{info['version']} erfolgreich installiert")
            splash.set_phase("done")
            splash.set_status(t("splash.installed", version=info["version"]), 100)
            _add_update_notif(window, info, installed=True)
        else:
            log.error(f"Update fehlgeschlagen: {msg}")
            splash.set_status(t("splash.failed", error=msg), 80)
            _add_update_notif(window, info, installed=False, failed=True)

        app.processEvents()
        QTimer.singleShot(1200, splash.finish)

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
                text       = info.get("notes","") + " — Automatische Installation deaktiviert.",
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