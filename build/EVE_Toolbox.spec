# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec-Datei für EVE Toolbox
# Erstellt eine portable Ordner-EXE — kein Installer nötig
# Ausführen mit: build_windows.bat

from pathlib import Path

# Pfade
BUILD_DIR = Path(SPECPATH)           # build/
ROOT      = BUILD_DIR.parent         # EVE_Toolbox/
EVE_DIR   = ROOT / "eve_toolbox"     # EVE_Toolbox/eve_toolbox/

a = Analysis(
    [str(EVE_DIR / "main.py")],
    pathex=[str(EVE_DIR)],
    binaries=[],
    datas=[
        # Assets (Icons, Bilder)
        (str(EVE_DIR / "assets"), "assets"),
        # Sprachdateien
        (str(EVE_DIR / "i18n"), "i18n"),
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "PyQt6.QtNetwork",
        "PyQt6.QtSvg",
        "core.config",
        "core.settings",
        "core.notifications",
        "core.updater",
        "core.integrity",
        "core.crypto_vault",
        "core.release_crypto",
        "core.esi",
        "core.esi_config",
        "core.esi_client",
        "core.esi_cache",
        "core.crash_handler",
        "core.memory_monitor",
        "core.i18n",
        "core.logger",
        "ui.main_window",
        "ui.topbar",
        "ui.splash_screen",
        "ui.welcome_screen",
        "ui.settings_page",
        "ui.settings_panel",
        "ui.notifications_page",
        "ui.bell_popup",
        "ui.account_popup",
        "ui.home_grid",
        "ui.home_donut",
        "ui.info_panel",
        "ui.unlock_popup",
        "ui.update_popup",
        "ui.dev_mode_notice",
        "ui.fly_safe_dialog",
        "ui.security_warning_dialog",
        "ui.error_notice_dialog",
    ],
    hookspath=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "PIL",
        "cv2",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EVE_Toolbox",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(EVE_DIR / "assets" / "EVE Toolbox.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="EVE_Toolbox",
)
