@echo off
chcp 65001 >nul
title EVE Toolbox - Release Builder
color 0F
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo.
echo  +================================================+
echo  ^|    EVE Toolbox - Release Builder              ^|
echo  ^|    by phantombite                             ^|
echo  +================================================+
echo.

set ERRORS=0
set NEW_VERSION=

:: ════════════════════════════════════════════════
::  SCHRITT 1: Sicherheitsdateien pruefen
:: ════════════════════════════════════════════════
echo  +------------------------------------------------+
echo  ^|  Schritt 1/5 - Sicherheitsdateien             ^|
echo  +------------------------------------------------+
echo.

set SEC_OK=1

if not exist "checksums.json" (
    echo  [FEHLT] checksums.json nicht gefunden!
    echo         security_generator.bat ausfuehren.
    set SEC_OK=0
) else (
    python -c "import json; d=json.load(open('checksums.json')); exit(0 if len(d)>0 else 1)" >nul 2>&1
    if errorlevel 1 (
        echo  [FEHLER] checksums.json ist leer!
        set SEC_OK=0
    ) else (
        python -c "import json; d=json.load(open('checksums.json')); print(f'  [  OK ] checksums.json gueltig ^({len(d)} Dateien^)')"
    )
)

if not exist "dev_pubkey.pem" (
    echo  [FEHLT] dev_pubkey.pem nicht gefunden!
    set SEC_OK=0
) else (
    echo  [  OK ] dev_pubkey.pem vorhanden
)

python -c "from cryptography.hazmat.primitives import hashes" >nul 2>&1
if errorlevel 1 (
    echo  [INFO ] cryptography fehlt - wird installiert...
    python -m pip install cryptography --quiet
)

if exist "dev_mode.flag" if exist "dev_pubkey.pem" (
    python -c "from cryptography.hazmat.primitives import hashes,serialization; from cryptography.hazmat.primitives.asymmetric import padding; import base64; from pathlib import Path; pub=serialization.load_pem_public_key(Path('dev_pubkey.pem').read_bytes()); pub.verify(base64.b64decode(Path('dev_mode.flag').read_text().strip()),b'EVEToolbox-DevMode',padding.PKCS1v15(),hashes.SHA256())" >nul 2>&1
    if errorlevel 1 ( echo  [FEHLER] Dev-Token ungueltig! & set SEC_OK=0 ) else ( echo  [  OK ] Dev-Token gueltig )
)

echo.
if "!SEC_OK!"=="0" (
    echo  +================================================+
    echo  ^|  FEHLER: Sicherheitsdateien nicht in Ordnung  ^|
    echo  ^|  Bitte security_generator.bat ausfuehren      ^|
    echo  +================================================+
    goto :ask_exit
)
echo  [  OK ] Alle Sicherheitsdateien OK
echo.

:ask_1
set C=
set /p C="  Weiter mit Versionsnummer? (y/n) > "
if /i "!C!"=="y" goto :step2
if /i "!C!"=="n" goto :ask_exit
echo  Bitte y oder n eingeben.
goto :ask_1

:: ════════════════════════════════════════════════
::  SCHRITT 2: Versionsnummer
:: ════════════════════════════════════════════════
:step2
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 2/5 - Versionsnummer                 ^|
echo  +------------------------------------------------+
echo.

for /f "tokens=*" %%v in ('python -c "import json; print(json.load(open('version.json'))['version'])" 2^>nul') do set CURRENT_VERSION=%%v
echo  Aktuelle Version: !CURRENT_VERSION!
echo.

:ask_version
echo  Aktuelle Version beibehalten? (y/n)
set KEEP_VERSION=
set /p KEEP_VERSION="  > "
if /i "!KEEP_VERSION!"=="y" (
    set NEW_VERSION=!CURRENT_VERSION!
    echo  [  OK ] Version bleibt !CURRENT_VERSION!
    goto :do_version
)
if /i not "!KEEP_VERSION!"=="n" (
    echo  Bitte y oder n eingeben.
    goto :ask_version
)

:ask_new_version
set NEW_VERSION=
set /p NEW_VERSION="  Neue Versionsnummer (z.B. 0.5.0) > "
if "!NEW_VERSION!"=="" ( echo  Bitte Versionsnummer eingeben. & goto :ask_new_version )

python -c "import re,sys,json; v='!NEW_VERSION!'; cur=json.load(open('version.json'))['version']; ok=bool(re.match(r'^[0-9]+[.][0-9]+[.][0-9]+$',v)) and tuple(int(x) for x in v.split('.'))>=tuple(int(x) for x in cur.split('.')); sys.exit(0 if ok else 1)" >nul 2>&1
if errorlevel 1 ( echo  Muss mindestens !CURRENT_VERSION! sein und Format x.y.z & goto :ask_new_version )

echo.
echo  Aktuelle Version : !CURRENT_VERSION!
echo  Neue Version     : !NEW_VERSION!
echo.

:ask_version_ok
set C=
set /p C="  So setzen? (y/n) > "
if /i "!C!"=="y" goto :do_version
if /i "!C!"=="n" goto :ask_new_version
echo  Bitte y oder n eingeben.
goto :ask_version_ok

:do_version
> _ver_tmp.py echo import json
>> _ver_tmp.py echo from pathlib import Path
>> _ver_tmp.py echo d = json.loads(Path('version.json').read_text(encoding='utf-8'))
>> _ver_tmp.py echo d['version'] = '!NEW_VERSION!'
>> _ver_tmp.py echo d['download_zip'] = f"https://github.com/Phantombite/eve-toolbox/releases/download/v!NEW_VERSION!/eve_toolbox.zip"
>> _ver_tmp.py echo Path('version.json').write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding='utf-8')
python _ver_tmp.py
del _ver_tmp.py >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] version.json konnte nicht aktualisiert werden!
    set ERRORS=1
    goto :report
)
echo  [  OK ] version.json auf v!NEW_VERSION! gesetzt
echo.

:ask_2
set C=
set /p C="  Weiter mit EXE bauen? (y/n) > "
if /i "!C!"=="y" goto :step3
if /i "!C!"=="n" goto :ask_exit
echo  Bitte y oder n eingeben.
goto :ask_2

:: ════════════════════════════════════════════════
::  SCHRITT 3: EXE bauen
:: ════════════════════════════════════════════════
:step3
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 3/5 - EXE bauen                      ^|
echo  +------------------------------------------------+
echo.

:: PyInstaller pruefen
python -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO ] Installiere PyInstaller...
    python -m pip install pyinstaller --quiet
)

:: Struktur pruefen
if not exist "build\EVE_Toolbox.spec" (
    echo  [FEHLER] build\EVE_Toolbox.spec nicht gefunden!
    set ERRORS=1
    goto :report
)

echo  [...] Starte PyInstaller...
echo.
cd /d "%~dp0build"
python -m PyInstaller EVE_Toolbox.spec --clean --noconfirm
set BUILD_ERR=!errorlevel!
cd /d "%~dp0"

if "!BUILD_ERR!"=="1" (
    echo.
    echo  [FEHLER] Build fehlgeschlagen!
    set ERRORS=1
    goto :report
)

:: Ergebnis pruefen
if not exist "build\dist\EVE_Toolbox\EVE_Toolbox.exe" (
    echo  [FEHLER] EVE_Toolbox.exe nicht gefunden nach Build!
    set ERRORS=1
    goto :report
)
echo.
echo  [  OK ] EVE_Toolbox.exe erstellt
echo.

:: Struktur pruefen
set STRUCT_OK=1
if not exist "build\dist\EVE_Toolbox\_internal" ( echo  [FEHLT] _internal\ fehlt! & set STRUCT_OK=0 ) else ( echo  [  OK ] _internal\ vorhanden )
if not exist "build\dist\EVE_Toolbox\_internal\assets" ( echo  [WARN ] _internal\assets\ fehlt - Icons fehlen! ) else ( echo  [  OK ] _internal\assets\ vorhanden )
if not exist "build\dist\EVE_Toolbox\_internal\i18n" ( echo  [WARN ] _internal\i18n\ fehlt - Sprachdateien fehlen! ) else ( echo  [  OK ] _internal\i18n\ vorhanden )
echo.

:ask_3
set C=
set /p C="  Weiter mit ZIP und EXE kopieren? (y/n) > "
if /i "!C!"=="y" goto :step4
if /i "!C!"=="n" goto :ask_exit
echo  Bitte y oder n eingeben.
goto :ask_3

:: ════════════════════════════════════════════════
::  SCHRITT 4: ZIP erstellen + EXE kopieren
:: ════════════════════════════════════════════════
:step4
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 4/5 - ZIP erstellen + EXE kopieren   ^|
echo  +------------------------------------------------+
echo.

:: ZIP erstellen - nur Quellcode, nicht den PyInstaller Output
if exist "eve_toolbox.zip" del "eve_toolbox.zip" >nul 2>&1
echo  [...] Erstelle eve_toolbox.zip...

set "ROOT=%CD%"
set "DIST=%CD%\build\dist\EVE_Toolbox"
> _zip_tmp.py echo import zipfile
>> _zip_tmp.py echo from pathlib import Path
>> _zip_tmp.py echo root  = Path(r'!ROOT!')
>> _zip_tmp.py echo dist  = Path(r'!DIST!')
>> _zip_tmp.py echo out   = Path('eve_toolbox.zip')
>> _zip_tmp.py echo SKIP_DIRS = {'__pycache__', 'tokens', '.git'}
>> _zip_tmp.py echo SKIP_EXT  = {'.pyc', '.pyo', '.log', '.zip'}
>> _zip_tmp.py echo count = 0
>> _zip_tmp.py echo with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
>> _zip_tmp.py echo     # 1. eve_toolbox Quellcode
>> _zip_tmp.py echo     src = root / 'eve_toolbox'
>> _zip_tmp.py echo     for f in src.rglob('*'):
>> _zip_tmp.py echo         if not f.is_file(): continue
>> _zip_tmp.py echo         if any(s in f.parts for s in SKIP_DIRS): continue
>> _zip_tmp.py echo         if f.suffix.lower() in SKIP_EXT: continue
>> _zip_tmp.py echo         z.write(f, Path('eve_toolbox') / f.relative_to(src))
>> _zip_tmp.py echo         count += 1
>> _zip_tmp.py echo     # 2. EXE und _internal vom Build
>> _zip_tmp.py echo     for f in dist.rglob('*'):
>> _zip_tmp.py echo         if not f.is_file(): continue
>> _zip_tmp.py echo         z.write(f, f.relative_to(dist))
>> _zip_tmp.py echo         count += 1
>> _zip_tmp.py echo     # 3. Einzelne Dateien aus Root
>> _zip_tmp.py echo     for fname in ('version.json', 'checksums.json', 'dev_pubkey.pem'):
>> _zip_tmp.py echo         fp = root / fname
>> _zip_tmp.py echo         if fp.exists():
>> _zip_tmp.py echo             z.write(fp, fname)
>> _zip_tmp.py echo             count += 1
>> _zip_tmp.py echo print(f'{count} Dateien gepackt')
python _zip_tmp.py
del _zip_tmp.py >nul 2>&1

if errorlevel 1 ( echo  [FEHLER] ZIP fehlgeschlagen! & set ERRORS=1 & goto :report )
if not exist "eve_toolbox.zip" ( echo  [FEHLER] ZIP nicht erstellt! & set ERRORS=1 & goto :report )
for %%f in ("eve_toolbox.zip") do echo  [  OK ] eve_toolbox.zip erstellt ^(%%~zf bytes^)

:: Alten Release-Ordner loeschen und neu kopieren
echo.
echo  [...] Kopiere Release-Dateien ins Hauptverzeichnis...
if exist "EVE_Toolbox.exe" del "EVE_Toolbox.exe" >nul 2>&1
if exist "_internal" rmdir /s /q "_internal" >nul 2>&1
xcopy "build\dist\EVE_Toolbox\*" "." /E /Y /Q >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Kopieren fehlgeschlagen!
    set ERRORS=1
) else (
    echo  [  OK ] EVE_Toolbox.exe aktualisiert
    echo  [  OK ] _internal\ aktualisiert
)
echo.

:ask_4
set C=
set /p C="  Weiter mit Checksums aktualisieren? (y/n) > "
if /i "!C!"=="y" goto :step5
if /i "!C!"=="n" goto :report
echo  Bitte y oder n eingeben.
goto :ask_4

:: ════════════════════════════════════════════════
::  SCHRITT 5: Checksums neu generieren
:: ════════════════════════════════════════════════
:step5
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 5/5 - Checksums aktualisieren        ^|
echo  +------------------------------------------------+
echo.

set "CSDIR=%CD%"
> _cs_tmp.py echo import sys
>> _cs_tmp.py echo sys.path.insert(0, r'!CSDIR!\eve_toolbox')
>> _cs_tmp.py echo from core.integrity import generate_checksums
>> _cs_tmp.py echo from pathlib import Path
>> _cs_tmp.py echo r = generate_checksums(Path(r'!CSDIR!\checksums.json'))
>> _cs_tmp.py echo print(f'{len(r)} Dateien gehasht')
python _cs_tmp.py
del _cs_tmp.py >nul 2>&1

if errorlevel 1 ( echo  [FEHLER] Checksums fehlgeschlagen! & set ERRORS=1 ) else ( echo  [  OK ] checksums.json aktualisiert )
echo.

:: ════════════════════════════════════════════════
::  ABSCHLUSSBERICHT
:: ════════════════════════════════════════════════
:report
echo.
if "!ERRORS!"=="0" ( color 0A ) else ( color 0C )

echo  +================================================+
if "!ERRORS!"=="0" (
    echo  ^|  RELEASE v!NEW_VERSION! FERTIG                      ^|
) else (
    echo  ^|  RELEASE MIT FEHLERN - oben nachsehen         ^|
)
echo  +================================================+
echo.
echo  +------------------------------------------------+
echo  ^|  Jetzt in GitHub Desktop:                     ^|
echo  +------------------------------------------------+
echo  Committen und pushen:
echo  [ GIT ] version.json
echo  [ GIT ] checksums.json
echo  [ GIT ] dev_pubkey.pem  ^(falls neu erstellt^)
echo.
echo  +------------------------------------------------+
echo  ^|  Dann auf github.com - neues Release:         ^|
echo  +------------------------------------------------+
echo  [ GIT ] Tag: v!NEW_VERSION!
echo  [ GIT ] ZIP hochladen: eve_toolbox.zip
echo.
echo  +------------------------------------------------+
echo  ^|  NIEMALS pushen:                              ^|
echo  +------------------------------------------------+
echo  [ X ] dev_privkey.pem
echo  [ X ] dev_mode.flag
echo.

:ask_exit
set EXIT_CHOICE=
set /p EXIT_CHOICE="  Beenden? (x) > "
if /i "!EXIT_CHOICE!"=="x" exit
echo  Bitte x eingeben.
goto :ask_exit