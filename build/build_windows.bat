@echo off
chcp 65001 >nul
title EVE Toolbox - Windows Build
color 0F
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo.
echo  +================================================+
echo  ^|    EVE Toolbox - Windows Build                ^|
echo  ^|    by phantombite                             ^|
echo  +================================================+
echo.

:: ── Voraussetzungen pruefen ──────────────────────────────────
echo  +------------------------------------------------+
echo  ^|  Vorab-Check                                  ^|
echo  +------------------------------------------------+

set PRECHECK_OK=1

python --version >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Python nicht gefunden!
    set PRECHECK_OK=0
) else (
    for /f "tokens=*" %%v in ('python --version 2^>^&1') do echo  [  OK ] %%v gefunden
)

python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO ] PyInstaller fehlt - wird installiert...
    python -m pip install pyinstaller --quiet
    python -m PyInstaller --version >nul 2>&1
    if errorlevel 1 (
        echo  [FEHLER] PyInstaller konnte nicht installiert werden!
        set PRECHECK_OK=0
    ) else (
        echo  [  OK ] PyInstaller installiert
    )
) else (
    for /f "tokens=*" %%v in ('python -m PyInstaller --version 2^>^&1') do echo  [  OK ] PyInstaller %%v gefunden
)

if not exist "EVE_Toolbox.spec" (
    echo  [FEHLER] EVE_Toolbox.spec nicht gefunden!
    echo          Bitte sicherstellen dass build_windows.bat im build\ Ordner liegt.
    set PRECHECK_OK=0
) else (
    echo  [  OK ] EVE_Toolbox.spec gefunden
)

if not exist "..\eve_toolbox\main.py" (
    echo  [FEHLER] eve_toolbox\main.py nicht gefunden!
    set PRECHECK_OK=0
) else (
    echo  [  OK ] eve_toolbox\ gefunden
)

echo.
if "!PRECHECK_OK!"=="0" (
    echo  +================================================+
    echo  ^|  VORAB-CHECK FEHLGESCHLAGEN                   ^|
    echo  +================================================+
    echo.
    pause
    exit /b 1
)
echo  [  OK ] Vorab-Check bestanden
echo.

:: ── Build starten ────────────────────────────────────────────
echo  +------------------------------------------------+
echo  ^|  Build                                        ^|
echo  +------------------------------------------------+
echo.
echo  [...] Starte PyInstaller...
echo.

python -m PyInstaller EVE_Toolbox.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo  +================================================+
    echo  ^|  BUILD FEHLGESCHLAGEN                         ^|
    echo  +================================================+
    echo.
    pause
    exit /b 1
)

:: ── Ergebnis pruefen ─────────────────────────────────────────
echo.
echo  +------------------------------------------------+
echo  ^|  Ergebnis                                     ^|
echo  +------------------------------------------------+

if exist "dist\EVE_Toolbox\EVE_Toolbox.exe" (
    echo  [  OK ] EVE_Toolbox.exe erstellt
    for %%f in ("dist\EVE_Toolbox\EVE_Toolbox.exe") do echo  [  OK ] Groesse: %%~zf bytes
) else (
    echo  [FEHLER] EVE_Toolbox.exe nicht gefunden!
    pause
    exit /b 1
)

:: ── Ausgabe-Ordner anzeigen ──────────────────────────────────
echo.
echo  +================================================+
echo  ^|  BUILD ERFOLGREICH                            ^|
echo  +================================================+
echo.
echo  Ausgabe: build\dist\EVE_Toolbox\
echo.
echo  Inhalt fuer GitHub Release ZIP:
echo  Den Ordner dist\EVE_Toolbox\ als eve_toolbox.zip verpacken.
echo.
echo  Struktur der ZIP muss sein:
echo    eve_toolbox\
echo      EVE_Toolbox.exe
echo      _internal\
echo        ...
echo.

:ask_open
set OPEN_CHOICE=
set /p OPEN_CHOICE="  Ausgabe-Ordner jetzt oeffnen? (y/n) > "
if /i "!OPEN_CHOICE!"=="y" ( explorer "dist\EVE_Toolbox" & goto :ask_exit )
if /i "!OPEN_CHOICE!"=="n" goto :ask_exit
echo  Bitte y oder n eingeben.
goto :ask_open

:ask_exit
set EXIT_CHOICE=
set /p EXIT_CHOICE="  Beenden? (x) > "
if /i "!EXIT_CHOICE!"=="x" exit
echo  Bitte x eingeben.
goto :ask_exit