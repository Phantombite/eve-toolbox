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
echo ------------------------------------------------
echo  Vollstaendiger Start mit Integritaets-/Update-Check?
echo  [j] = Ja  -  normaler Start, prueft gegen GitHub
echo  [n] = Nein - Entwickler-Start, ueberspringt Checks
echo ------------------------------------------------
set CHECK_CHOICE=
set /p CHECK_CHOICE="Auswahl (j/n) > "

if /i "!CHECK_CHOICE!"=="n" (
    set EVE_SKIP_CHECKS=1
    echo [DEV] Integritaets-/Update-Check wird uebersprungen
) else (
    set EVE_SKIP_CHECKS=
    echo [OK] Vollstaendiger Start mit Checks
)

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