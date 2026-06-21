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

if not exist "checksums.json.sig" (
    echo  [FEHLT] checksums.json.sig nicht gefunden!
    echo         security_generator.bat ausfuehren ^(signiert bei jedem Lauf neu^).
    set SEC_OK=0
) else (
    echo  [  OK ] checksums.json.sig vorhanden
)

if not exist "release_cert.json" (
    echo  [FEHLT] release_cert.json nicht gefunden!
    echo         security_generator.bat Modus 1 ausfuehren ^(braucht Root Key vom Stick^).
    set SEC_OK=0
) else (
    echo  [  OK ] release_cert.json vorhanden
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

:: Zertifikat gegen Root Key im Code pruefen — NICHT direkt gegen
:: dev_pubkey.pem. Schlaegt das fehl, wurde der ROOT Public Key
:: vermutlich noch nicht in release_crypto.py eingetragen, oder das
:: Zertifikat passt nicht zum aktuellen Release Key.
if exist "release_cert.json" (
    > _sec_v0.py echo import sys
    >> _sec_v0.py echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
    >> _sec_v0.py echo from core.release_crypto import load_release_cert
    >> _sec_v0.py echo from pathlib import Path
    >> _sec_v0.py echo key = load_release_cert^(Path^('release_cert.json'^)^)
    >> _sec_v0.py echo sys.exit^(0 if key else 1^)
    python _sec_v0.py >nul 2>&1
    if errorlevel 1 ( echo  [FEHLER] release_cert.json ungueltig gegen Root Key im Code! & set SEC_OK=0 ) else ( echo  [  OK ] release_cert.json gueltig - Release Key autorisiert )
    del _sec_v0.py >nul 2>&1
)

:: Checksums-Signatur gegen den im Zertifikat autorisierten Release Key
if exist "checksums.json" if exist "checksums.json.sig" if exist "release_cert.json" (
    > _sec_v1.py echo import sys
    >> _sec_v1.py echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
    >> _sec_v1.py echo from core.release_crypto import verify_release_signature
    >> _sec_v1.py echo from pathlib import Path
    >> _sec_v1.py echo data = Path^('checksums.json'^).read_bytes^(^)
    >> _sec_v1.py echo sig = Path^('checksums.json.sig'^).read_text^(^).strip^(^)
    >> _sec_v1.py echo sys.exit^(0 if verify_release_signature^(data, sig, cert_path=Path^('release_cert.json'^)^) else 1^)
    python _sec_v1.py >nul 2>&1
    if errorlevel 1 ( echo  [FEHLER] checksums.json Signatur ungueltig gegen autorisierten Release Key! & set SEC_OK=0 ) else ( echo  [  OK ] checksums.json Signatur gueltig )
    del _sec_v1.py >nul 2>&1
)

if exist "dev_mode.flag" if exist "release_cert.json" (
    > _sec_v2.py echo import sys
    >> _sec_v2.py echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
    >> _sec_v2.py echo from core.release_crypto import verify_dev_token
    >> _sec_v2.py echo from pathlib import Path
    >> _sec_v2.py echo token = Path^('dev_mode.flag'^).read_text^(^).strip^(^)
    >> _sec_v2.py echo sys.exit^(0 if verify_dev_token^(token, Path^('release_cert.json'^)^) else 1^)
    python _sec_v2.py >nul 2>&1
    if errorlevel 1 ( echo  [FEHLER] Dev-Token ungueltig! & set SEC_OK=0 ) else ( echo  [  OK ] Dev-Token gueltig )
    del _sec_v2.py >nul 2>&1
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
>> _ver_tmp.py echo text = json.dumps(d, indent=2, ensure_ascii=False)
>> _ver_tmp.py echo Path('version.json').write_bytes(text.encode('utf-8'))
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
set /p C="  Weiter mit Checksums generieren? (y/n) > "
if /i "!C!"=="y" goto :step4
if /i "!C!"=="n" goto :ask_exit
echo  Bitte y oder n eingeben.
goto :ask_3

:: ════════════════════════════════════════════════
::  SCHRITT 4: Checksums generieren + signieren
::  MUSS vor dem ZIP-Bau passieren — sonst signiert
::  man Pruefsummen eines Standes, der nicht mehr
::  dem ausgelieferten ZIP entspricht. Nach diesem
::  Schritt duerfen KEINE Dateien mehr veraendert
::  werden, bevor die ZIP gebaut ist.
:: ════════════════════════════════════════════════
:step4
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 4/5 - Checksums generieren + signieren ^|
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

if errorlevel 1 ( echo  [FEHLER] Checksums fehlgeschlagen! & set ERRORS=1 & goto :report ) else ( echo  [  OK ] checksums.json aktualisiert )
echo.

if not exist "dev_privkey.pem" (
    echo  [FEHLER] dev_privkey.pem fehlt - kann nicht signieren!
    echo           security_generator.bat ausfuehren.
    set ERRORS=1
    goto :report
)
if not exist "release_cert.json" (
    echo  [FEHLER] release_cert.json fehlt - Release Key noch nicht autorisiert!
    echo           security_generator.bat Modus 1 ausfuehren ^(braucht Root Key vom Stick^).
    set ERRORS=1
    goto :report
)
echo  [...] Signiere checksums.json...
> _sig_tmp.py echo import sys
>> _sig_tmp.py echo sys.path.insert(0, r'!CSDIR!\eve_toolbox')
>> _sig_tmp.py echo from core.release_crypto import sign_data
>> _sig_tmp.py echo from pathlib import Path
>> _sig_tmp.py echo data = Path(r'!CSDIR!\checksums.json').read_bytes()
>> _sig_tmp.py echo sig = sign_data(data, Path(r'!CSDIR!\dev_privkey.pem'))
>> _sig_tmp.py echo Path(r'!CSDIR!\checksums.json.sig').write_text(sig, encoding='utf-8')
>> _sig_tmp.py echo print('checksums.json.sig aktualisiert')
python _sig_tmp.py
del _sig_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] Signierung fehlgeschlagen! & set ERRORS=1 & goto :report ) else ( echo  [  OK ] checksums.json.sig aktualisiert )
echo.

:: ── stable_version.json setzen + signieren ─────────────────
:: release.bat setzt IMMER die aktuell veroeffentlichte Version als
:: stable — ein gezielter Rollback auf eine AELTERE Version laeuft
:: ausschliesslich ueber downgrade.bat, niemals hier automatisch.
echo  [...] Setze stable_version.json auf v!NEW_VERSION!...
> _stable_tmp.py echo import json
>> _stable_tmp.py echo from pathlib import Path
>> _stable_tmp.py echo data = {"version": "!NEW_VERSION!", "mandatory": False}
>> _stable_tmp.py echo text = json.dumps(data, indent=2)
>> _stable_tmp.py echo Path(r'!CSDIR!\stable_version.json').write_bytes(text.encode('utf-8'))
>> _stable_tmp.py echo print('stable_version.json gesetzt')
python _stable_tmp.py
del _stable_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] stable_version.json fehlgeschlagen! & set ERRORS=1 & goto :report )

> _stable_sig_tmp.py echo import sys
>> _stable_sig_tmp.py echo sys.path.insert(0, r'!CSDIR!\eve_toolbox')
>> _stable_sig_tmp.py echo from core.release_crypto import sign_data
>> _stable_sig_tmp.py echo from pathlib import Path
>> _stable_sig_tmp.py echo data = Path(r'!CSDIR!\stable_version.json').read_bytes()
>> _stable_sig_tmp.py echo sig = sign_data(data, Path(r'!CSDIR!\dev_privkey.pem'))
>> _stable_sig_tmp.py echo Path(r'!CSDIR!\stable_version.json.sig').write_text(sig, encoding='utf-8')
>> _stable_sig_tmp.py echo print('stable_version.json.sig erstellt')
python _stable_sig_tmp.py
del _stable_sig_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] stable_version.json Signierung fehlgeschlagen! & set ERRORS=1 & goto :report ) else ( echo  [  OK ] stable_version.json signiert )
echo.
echo  +------------------------------------------------+
echo  ^|  AB JETZT: keine Dateien mehr veraendern!     ^|
echo  ^|  Checksums sind signiert - der naechste       ^|
echo  ^|  Schritt baut die ZIP exakt aus diesem Stand. ^|
echo  +------------------------------------------------+
echo.

:ask_4
set C=
set /p C="  Weiter mit ZIP bauen + signieren? (y/n) > "
if /i "!C!"=="y" goto :step5
if /i "!C!"=="n" goto :report
echo  Bitte y oder n eingeben.
goto :ask_4

:: ════════════════════════════════════════════════
::  SCHRITT 5: ZIP erstellen + EXE kopieren + ZIP signieren
::  Reihenfolge: Dateien fertig -> Checksums signiert
::  (Schritt 4) -> JETZT ZIP bauen -> ZIP signieren.
::  Nach der ZIP-Signierung darf NICHTS mehr in die
::  ZIP eingefuegt oder entfernt werden.
:: ════════════════════════════════════════════════
:step5
echo.
echo  +------------------------------------------------+
echo  ^|  Schritt 5/5 - ZIP erstellen + signieren      ^|
echo  +------------------------------------------------+
echo.

:: ZIP erstellen - nur Quellcode, nicht den PyInstaller Output
if exist "eve_toolbox.zip" del "eve_toolbox.zip" >nul 2>&1
if exist "eve_toolbox.zip.sig" del "eve_toolbox.zip.sig" >nul 2>&1
echo  [...] Erstelle eve_toolbox.zip...

set "ROOT=%CD%"
set "DIST=%CD%\build\dist\EVE_Toolbox"
> _zip_tmp.py echo import zipfile
>> _zip_tmp.py echo from pathlib import Path
>> _zip_tmp.py echo root  = Path(r'!ROOT!')
>> _zip_tmp.py echo dist  = Path(r'!DIST!')
>> _zip_tmp.py echo out   = Path('eve_toolbox.zip')
>> _zip_tmp.py echo SKIP_DIRS = {'__pycache__', 'tokens', '.git'}
>> _zip_tmp.py echo SKIP_EXT  = {'.pyc', '.pyo', '.log', '.zip', '.bak'}
>> _zip_tmp.py echo SKIP_NAMES = {'_embed_pubkey.py'}
>> _zip_tmp.py echo count = 0
>> _zip_tmp.py echo with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
>> _zip_tmp.py echo     # 1. eve_toolbox Quellcode (Checksums sind bereits signiert,
>> _zip_tmp.py echo     # diese Dateien duerfen sich ab jetzt nicht mehr aendern)
>> _zip_tmp.py echo     src = root / 'eve_toolbox'
>> _zip_tmp.py echo     for f in src.rglob('*'):
>> _zip_tmp.py echo         if not f.is_file(): continue
>> _zip_tmp.py echo         if any(s in f.parts for s in SKIP_DIRS): continue
>> _zip_tmp.py echo         if f.suffix.lower() in SKIP_EXT: continue
>> _zip_tmp.py echo         if f.name in SKIP_NAMES: continue
>> _zip_tmp.py echo         z.write(f, Path('eve_toolbox') / f.relative_to(src))
>> _zip_tmp.py echo         count += 1
>> _zip_tmp.py echo     # 2. EXE und _internal vom Build
>> _zip_tmp.py echo     for f in dist.rglob('*'):
>> _zip_tmp.py echo         if not f.is_file(): continue
>> _zip_tmp.py echo         z.write(f, f.relative_to(dist))
>> _zip_tmp.py echo         count += 1
>> _zip_tmp.py echo     # 3. Einzelne Dateien aus Root — bereits signierte Checksums
>> _zip_tmp.py echo     for fname in ('version.json', 'checksums.json', 'checksums.json.sig', 'release_cert.json', 'stable_version.json', 'stable_version.json.sig', 'dev_pubkey.pem'):
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
echo.

:: ── ZIP selbst signieren ────────────────────────────
:: Zusaetzlich zur checksums.json-Signatur wird jetzt
:: auch die fertige ZIP-Datei als Ganzes signiert. Das
:: schuetzt den Erstinstall-Fall (neuer Nutzer laedt nur
:: die ZIP von GitHub Releases, ohne vorher checksums.json
:: geprueft zu haben).
echo  [...] Signiere eve_toolbox.zip...
> _zipsig_tmp.py echo import sys
>> _zipsig_tmp.py echo sys.path.insert(0, r'!CSDIR!\eve_toolbox')
>> _zipsig_tmp.py echo from core.release_crypto import sign_data
>> _zipsig_tmp.py echo from pathlib import Path
>> _zipsig_tmp.py echo data = Path(r'!CSDIR!\eve_toolbox.zip').read_bytes()
>> _zipsig_tmp.py echo sig = sign_data(data, Path(r'!CSDIR!\dev_privkey.pem'))
>> _zipsig_tmp.py echo Path(r'!CSDIR!\eve_toolbox.zip.sig').write_text(sig, encoding='utf-8')
>> _zipsig_tmp.py echo print('eve_toolbox.zip.sig erstellt')
python _zipsig_tmp.py
del _zipsig_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] ZIP-Signierung fehlgeschlagen! & set ERRORS=1 & goto :report ) else ( echo  [  OK ] eve_toolbox.zip.sig erstellt )
echo.
echo  +------------------------------------------------+
echo  ^|  AB JETZT: ZIP nicht mehr veraendern!          ^|
echo  ^|  Keine Datei mehr einfuegen oder entfernen -   ^|
echo  ^|  die Signatur gilt fuer genau diesen ZIP-Inhalt.^|
echo  +------------------------------------------------+
echo.

:: Alten Release-Ordner loeschen und neu kopieren
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
echo  [ GIT ] checksums.json.sig
echo  [ GIT ] release_cert.json
echo  [ GIT ] stable_version.json
echo  [ GIT ] stable_version.json.sig
echo  [ GIT ] dev_pubkey.pem  ^(falls neu erstellt^)
echo  [ GIT ] core\release_crypto.py  ^(falls Root Key neu eingetragen^)
echo.
echo  +------------------------------------------------+
echo  ^|  Dann auf github.com - neues Release:         ^|
echo  +------------------------------------------------+
echo  [ GIT ] Tag: v!NEW_VERSION!
echo  [ GIT ] ZIP hochladen: eve_toolbox.zip
echo  [ GIT ] Signatur hochladen: eve_toolbox.zip.sig
echo  [ GIT ] Zertifikat hochladen: release_cert.json
echo.
echo  +------------------------------------------------+
echo  ^|  NIEMALS pushen oder hochladen:               ^|
echo  +------------------------------------------------+
echo  [ X ] dev_privkey.pem
echo  [ X ] dev_mode.flag
echo  [ X ] ROOT_KEY_SICHERN\ ^(falls noch vorhanden^)
echo.

:ask_exit
set EXIT_CHOICE=
set /p EXIT_CHOICE="  Beenden? (x) > "
if /i "!EXIT_CHOICE!"=="x" exit
echo  Bitte x eingeben.
goto :ask_exit