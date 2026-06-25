@echo off
title EVE Toolbox — DEBUG MODE
color 0A
setlocal enabledelayedexpansion

echo ============================================
echo  EVE Toolbox DEBUG MODE
echo  %date% %time%
echo ============================================
echo.

set PYTHON_CMD=
set MIN_VERSION=310

for %%p in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%p (
        %%p -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if !errorlevel! == 0 (
            set PYTHON_CMD=%%p
            goto :found
        )
    )
)

for %%i in (python.exe) do (
    if exist "%%~$PATH:i" (
        "%%~$PATH:i" -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if !errorlevel! == 0 (
            set PYTHON_CMD=%%~$PATH:i
            goto :found
        )
    )
)

echo [FEHLER] Python 3.10+ nicht gefunden!
pause
exit /b 1

:found
echo [OK] Python gefunden: %PYTHON_CMD%
echo.

:: PyQt6 pruefen
"%PYTHON_CMD%" -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo [INSTALL] Installiere PyQt6...
    "%PYTHON_CMD%" -m pip install PyQt6 --quiet
) else (
    echo [OK] PyQt6 vorhanden
)

echo.
:ask_devmode
echo ------------------------------------------------
echo  Im Entwicklermodus starten?
echo  [j] = Ja  -  Checks werden uebersprungen (sicher, fuer lokales Testen)
echo  [n] = Nein - Vollstaendiger Start mit Integritaets-/Update-Check
echo ------------------------------------------------
set CHECK_CHOICE=
set /p CHECK_CHOICE="Auswahl (j/n) > "

if /i "!CHECK_CHOICE!"=="j" (
    set EVE_SKIP_CHECKS=1
    echo [DEV] Entwicklermodus aktiv - Integritaets-/Update-Check wird uebersprungen
    goto :checks_resolved
)
if /i "!CHECK_CHOICE!"=="n" goto :ask_warning

echo.
echo [HINWEIS] Ungueltige Eingabe — bitte nur j oder n eingeben.
echo.
goto :ask_devmode


:ask_warning
echo.
echo ------------------------------------------------
echo  WARNUNG: Beim vollstaendigen Start werden automatisch
echo  alle lokalen Dateien ueberschrieben, die noch nicht
echo  auf GitHub veroeffentlicht sind!
echo  Willst du abbrechen?
echo  [j] = Ja, abbrechen   -  zurueck zur vorherigen Frage
echo  [n] = Nein, nicht abbrechen
echo ------------------------------------------------
set WARN_CHOICE=
set /p WARN_CHOICE="Auswahl (j/n) > "

if /i "!WARN_CHOICE!"=="j" goto :ask_devmode
if /i "!WARN_CHOICE!"=="n" goto :ask_sure

echo.
echo [HINWEIS] Ungueltige Eingabe — bitte nur j oder n eingeben.
echo.
goto :ask_warning


:ask_sure
echo.
echo ------------------------------------------------
echo  Bist du dir ABSOLUT SICHER, dass du OHNE
echo  Entwicklermodus starten willst?
echo  [j] = Ja, sicher   -  vollstaendiger Start mit Checks
echo  [n] = Nein, doch nicht  -  zurueck zur ersten Frage
echo ------------------------------------------------
set SURE_CHOICE=
set /p SURE_CHOICE="Auswahl (j/n) > "

if /i "!SURE_CHOICE!"=="j" (
    set EVE_SKIP_CHECKS=
    echo [OK] Vollstaendiger Start mit Checks bestaetigt
    goto :checks_resolved
)
if /i "!SURE_CHOICE!"=="n" goto :ask_devmode

echo.
echo [HINWEIS] Ungueltige Eingabe — bitte nur j oder n eingeben.
echo.
goto :ask_sure


:checks_resolved

:: Debug-Umgebungsvariable setzen
set EVE_TOOLBOX_DEBUG=1

echo.
echo [START] Starte EVE Toolbox mit vollem Logging...
echo ============================================
echo.

cd /d "%~dp0eve_toolbox"

:: Python mit unbuffered output (-u) damit alle prints sofort erscheinen
"%PYTHON_CMD%" -u main.py 2>&1

echo.
echo ============================================
echo [ENDE] EVE Toolbox beendet mit Code: %errorlevel%
echo ============================================
pause