@echo off
title EVE Toolbox
color 0F
setlocal enabledelayedexpansion

set PYTHON_CMD=

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

echo.
echo  +================================================+
echo  ^|    EVE Toolbox                                ^|
echo  +================================================+
echo.
echo  Python 3.10+ wurde nicht gefunden.
echo  EVE Toolbox benoetigt Python um zu starten.
echo.
set /p INSTALL="  Python jetzt installieren? (y/n) > "
if /i "!INSTALL!"=="y" goto :install
if /i "!INSTALL!"=="n" goto :abort
echo  Bitte y oder n eingeben.
goto :ask_install

:install
echo.
echo  Der offizielle Python Installer wird jetzt geoeffnet.
echo  Bitte "Add python.exe to PATH" anwaehlen!
echo  Nach der Installation EVE Toolbox neu starten.
echo.
start https://www.python.org/downloads/
pause
exit /b 0

:abort
echo.
echo  EVE Toolbox kann ohne Python nicht gestartet werden.
pause
exit /b 1

:found
"%PYTHON_CMD%" -c "import PyQt6" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  +------------------------------------------------+
    echo  ^|  Fehlende Abhaengigkeit                       ^|
    echo  +------------------------------------------------+
    echo  PyQt6 wird benoetigt und fehlt noch.
    echo.
    set /p PYQT="  PyQt6 jetzt installieren? (y/n) > "
    if /i "!PYQT!"=="y" (
        echo  ^[...^] Installiere PyQt6...
        "%PYTHON_CMD%" -m pip install PyQt6 --quiet
        if errorlevel 1 (
            echo  ^[FEHLER^] Installation fehlgeschlagen!
            pause
            exit /b 1
        )
        echo  ^[  OK ^] PyQt6 installiert
    ) else (
        echo  EVE Toolbox kann ohne PyQt6 nicht gestartet werden.
        pause
        exit /b 1
    )
)

cd /d "%~dp0eve_toolbox"
"%PYTHON_CMD%" -u main.py 2>&1