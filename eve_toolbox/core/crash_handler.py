"""
Globaler Exception-Hook — fängt unbehandelte Fehler ab (Haupt-Thread UND
Hintergrund-Threads), loggt sie vollständig mit Traceback und zeigt im
Haupt-Thread eine freundliche, nicht-technische Meldung statt dass die App
lautlos nichts tut oder unkontrolliert abstürzt.

Hintergrund: Beim Audit vom 24.06.2026 hat ein unbehandelter print()-Fehler
(sys.stdout ist None in der mit console=False kompilierten EXE) den
kompletten Login-Button lautlos lahmgelegt — kein Crash, keine Meldung,
einfach nichts passiert. Dieser Hook ist das Sicherheitsnetz dagegen für
JEDEN künftigen Fehler dieser Art in jedem kommenden Modul, nicht nur für
genau diesen einen, bereits behobenen Fall.

Empirisch verifiziert (nicht nur aus der Doku übernommen):
  - PyQt6 ruft sys.excepthook tatsächlich auf, wenn eine Exception
    innerhalb eines verbundenen Slots auftritt.
  - Die App läuft danach normal weiter, der Klick selbst schlägt fehl,
    aber das Programm bleibt benutzbar.
  - threading.excepthook fängt Fehler in Hintergrund-Threads (z.B.
    ESI-Aufrufe) gleichermaßen ab.
"""
import sys
import threading
import traceback

from core import logger as _logger
_log = _logger.get("crash_handler")

_app_ref = None  # Referenz auf QApplication, nur für den Dialog gebraucht


def install(app) -> None:
    """Installiert beide Hooks. Sollte direkt nach QApplication-Erstellung
    aufgerufen werden, bevor irgendein Slot/Signal feuern oder ein
    Hintergrund-Thread starten kann."""
    global _app_ref
    _app_ref = app
    sys.excepthook = _handle_main_thread_exception
    threading.excepthook = _handle_thread_exception
    _log.debug("Globaler Exception-Hook installiert (Haupt-Thread + Hintergrund-Threads)")


def _handle_main_thread_exception(exc_type, exc_value, exc_tb):
    if exc_type is KeyboardInterrupt:
        return
    full_trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    _log.error(f"UNBEHANDELTER FEHLER im Haupt-Thread:\n{full_trace}")
    # Sicher, da sys.excepthook per Definition nur im Haupt-Thread feuert —
    # an dieser Stelle dürfen Qt-Widgets erzeugt werden.
    try:
        _show_error_dialog(exc_type, exc_value)
    except Exception:
        _log.error("Fehler-Dialog konnte selbst nicht angezeigt werden.")


def _handle_thread_exception(args: threading.ExceptHookArgs):
    if args.exc_type is SystemExit:
        return
    full_trace = "".join(traceback.format_exception(
        args.exc_type, args.exc_value, args.exc_traceback))
    thread_name = args.thread.name if args.thread else "Unbekannt"
    _log.error(f"UNBEHANDELTER FEHLER in Hintergrund-Thread '{thread_name}':\n{full_trace}")
    # Bewusst KEIN Dialog hier — Qt-Widgets dürfen nicht aus einem
    # Hintergrund-Thread heraus erzeugt/manipuliert werden. Der Eintrag
    # im Log ist für Hintergrund-Fehler ausreichend; falls eine sichtbare
    # Reaktion nötig ist, soll der jeweilige Aufrufer das selbst über ein
    # Qt-Signal in den Haupt-Thread melden (siehe z.B. core.esi.login()).


def _show_error_dialog(exc_type, exc_value):
    from ui.error_notice_dialog import ErrorNoticeDialog
    dialog = ErrorNoticeDialog(exc_type, exc_value, parent=_app_ref.activeWindow() if _app_ref else None)
    dialog.exec()