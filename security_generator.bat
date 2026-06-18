@echo off
chcp 65001 >nul
title EVE Toolbox - Security Generator
color 0F
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo.
echo  +================================================+
echo  ^|    EVE Toolbox - Security Generator           ^|
echo  ^|    by phantombite                             ^|
echo  +================================================+
echo.

set ERRORS=0
set VERIFY_ERRORS=0
set ABORTED=0
set KEY_STATUS=keine
set CS_STATUS=keine
set TOK_STATUS=keine
set "WORKDIR=%CD:\=/%"

:: ════════════════════════════════════════════════
::  VORAB-CHECK
:: ════════════════════════════════════════════════
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

if not exist "eve_toolbox\" (
    echo  [FEHLER] Ordner 'eve_toolbox' nicht gefunden!
    echo          Bitte sicherstellen dass diese bat im
    echo          Hauptverzeichnis von EVE Toolbox liegt.
    set PRECHECK_OK=0
) else (
    echo  [  OK ] eve_toolbox\ gefunden
)

if not exist "eve_toolbox\core\integrity.py" (
    echo  [FEHLER] eve_toolbox\core\integrity.py nicht gefunden!
    set PRECHECK_OK=0
) else (
    echo  [  OK ] integrity.py gefunden
)

python -c "from cryptography.hazmat.primitives import hashes" >nul 2>&1
if errorlevel 1 (
    echo  [INFO ] cryptography fehlt - wird installiert...
    python -m pip install cryptography --quiet
    python -c "from cryptography.hazmat.primitives import hashes" >nul 2>&1
    if errorlevel 1 (
        echo  [FEHLER] cryptography konnte nicht installiert werden!
        set PRECHECK_OK=0
    ) else (
        echo  [  OK ] cryptography installiert
    )
) else (
    echo  [  OK ] cryptography vorhanden
)

echo.
if "!PRECHECK_OK!"=="0" (
    echo  +================================================+
    echo  ^|  VORAB-CHECK FEHLGESCHLAGEN                   ^|
    echo  ^|  Bitte Fehler oben beheben und neu starten    ^|
    echo  +================================================+
    echo.
    cmd /k
)
echo  [  OK ] Vorab-Check bestanden
echo.

:: ════════════════════════════════════════════════
::  Aktueller Status
:: ════════════════════════════════════════════════
echo  +------------------------------------------------+
echo  ^|  Aktueller Status                             ^|
echo  +------------------------------------------------+
if exist "dev_privkey.pem" ( echo  [  OK ] dev_privkey.pem   vorhanden ) else ( echo  [FEHLT] dev_privkey.pem   nicht vorhanden )
if exist "dev_pubkey.pem"  ( echo  [  OK ] dev_pubkey.pem    vorhanden ) else ( echo  [FEHLT] dev_pubkey.pem    nicht vorhanden )
if exist "checksums.json"  ( echo  [  OK ] checksums.json    vorhanden ) else ( echo  [FEHLT] checksums.json    nicht vorhanden )
if exist "dev_mode.flag"   ( echo  [  OK ] dev_mode.flag     vorhanden ) else ( echo  [FEHLT] dev_mode.flag     nicht vorhanden )

:: ════════════════════════════════════════════════
::  Moduswahl — wiederholt bis gueltige Eingabe
:: ════════════════════════════════════════════════
echo.
echo  +------------------------------------------------+
echo  ^|  Was moechtest du tun?                        ^|
echo  ^|                                               ^|
echo  ^|  [1] Ersteinrichtung / Schluessel neu         ^|
echo  ^|      Keypair + Checksums + Token neu          ^|
echo  ^|      Nur einmalig oder bei verlorenem Key     ^|
echo  ^|                                               ^|
echo  ^|  [2] Update veroeffentlichen                  ^|
echo  ^|      Nur Checksums neu generieren             ^|
echo  ^|      Schluessel und Token bleiben             ^|
echo  ^|                                               ^|
echo  ^|  [3] Abbrechen                                ^|
echo  +------------------------------------------------+

:ask_mode
echo.
set MODE=
set /p MODE="  Auswahl (1/2/3) > "
if "!MODE!"=="1" goto :mode_full
if "!MODE!"=="2" goto :mode_update
if "!MODE!"=="3" ( set ABORTED=1 & goto :report )
echo  Bitte 1, 2 oder 3 eingeben.
goto :ask_mode

:: ════════════════════════════════════════════════
::  MODUS 1 — Alles neu
:: ════════════════════════════════════════════════
:mode_full
echo.
if exist "dev_privkey.pem" (
    echo  +------------------------------------------------+
    echo  ^|  ACHTUNG                                      ^|
    echo  ^|                                               ^|
    echo  ^|  Schluessel existiert bereits!                ^|
    echo  ^|  Neu erstellen bedeutet:                      ^|
    echo  ^|  - Alle bestehenden Nutzer muessen            ^|
    echo  ^|    komplett neu updaten                       ^|
    echo  ^|  - Alte Installationen sehen Fehler           ^|
    echo  ^|    bis sie geupdated haben                    ^|
    echo  ^|  - Nur sinnvoll wenn Schluessel verloren      ^|
    echo  +------------------------------------------------+
    echo.
    :ask_key_confirm
    set KEY_CONFIRM=
    set /p KEY_CONFIRM="  Wirklich neu erstellen? (y/n) > "
    if /i "!KEY_CONFIRM!"=="y" goto :do_keypair
    if /i "!KEY_CONFIRM!"=="n" ( set ABORTED=1 & goto :report )
    echo  Bitte y oder n eingeben.
    goto :ask_key_confirm
)

:do_keypair
echo.
set KEY_STATUS=erstellt
if exist "dev_privkey.pem" set KEY_STATUS=ueberschrieben
echo  [...] Erstelle RSA-4096 Schluessel...
python -c ^
"from cryptography.hazmat.primitives.asymmetric import rsa; from cryptography.hazmat.primitives import serialization; from pathlib import Path; k=rsa.generate_private_key(65537,4096); Path('dev_privkey.pem').write_bytes(k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())); Path('dev_pubkey.pem').write_bytes(k.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo))"
if errorlevel 1 (
    echo  [FEHLER] Schluessel fehlgeschlagen!
    set KEY_STATUS=FEHLER
    set ERRORS=1
) else (
    if "!KEY_STATUS!"=="ueberschrieben" ( echo  [ UPD] Schluessel ueberschrieben ) else ( echo  [  OK ] Schluessel erstellt )
)
echo.
goto :do_checksums

:: ════════════════════════════════════════════════
::  MODUS 2 — Nur Checksums
:: ════════════════════════════════════════════════
:mode_update
echo.
set KEY_STATUS=unveraendert
set TOK_STATUS=unveraendert

:: ════════════════════════════════════════════════
::  Checksums
:: ════════════════════════════════════════════════
:do_checksums
set CS_STATUS=erstellt
if exist "checksums.json" set CS_STATUS=ueberschrieben

echo  [...] Generiere Checksummen...
set "CSDIR=%CD%"
> _cs_tmp.py echo import sys
>> _cs_tmp.py echo sys.path.insert(0, r"%CSDIR%\eve_toolbox")
>> _cs_tmp.py echo from core.integrity import generate_checksums
>> _cs_tmp.py echo from pathlib import Path
>> _cs_tmp.py echo r = generate_checksums(Path(r"%CSDIR%\checksums.json"))
>> _cs_tmp.py echo print(f"  {len(r)} Dateien gehasht")
python _cs_tmp.py
if errorlevel 1 (
    echo  [FEHLER] Checksummen fehlgeschlagen!
    set CS_STATUS=FEHLER
    set ERRORS=1
) else (
    if "!CS_STATUS!"=="ueberschrieben" ( echo  [ UPD] checksums.json ueberschrieben ) else ( echo  [  OK ] checksums.json erstellt )
)
del _cs_tmp.py >nul 2>&1
echo.

if "!MODE!"=="2" goto :finalcheck

:: ════════════════════════════════════════════════
::  Dev-Token (nur Modus 1)
:: ════════════════════════════════════════════════
set TOK_STATUS=erstellt
if exist "dev_mode.flag" set TOK_STATUS=ueberschrieben

if not exist "dev_privkey.pem" (
    echo  [WARN] Kein Schluessel - Dev-Token uebersprungen
    set TOK_STATUS=uebersprungen
    goto :finalcheck
)

echo  [...] Erstelle Dev-Token...
python -c ^
"from cryptography.hazmat.primitives import hashes,serialization; from cryptography.hazmat.primitives.asymmetric import padding; import base64; from pathlib import Path; k=serialization.load_pem_private_key(Path('dev_privkey.pem').read_bytes(),password=None); m=b'EVEToolbox-DevMode'; t=base64.b64encode(k.sign(m,padding.PKCS1v15(),hashes.SHA256())).decode(); Path('dev_mode.flag').write_text(t,encoding='utf-8'); serialization.load_pem_public_key(Path('dev_pubkey.pem').read_bytes()).verify(base64.b64decode(t),m,padding.PKCS1v15(),hashes.SHA256())"
if errorlevel 1 (
    echo  [FEHLER] Dev-Token fehlgeschlagen!
    set TOK_STATUS=FEHLER
    set ERRORS=1
) else (
    if "!TOK_STATUS!"=="ueberschrieben" ( echo  [ UPD] dev_mode.flag ueberschrieben ) else ( echo  [  OK ] dev_mode.flag erstellt )
)
echo.

:: ════════════════════════════════════════════════
::  Frage ob Verifikation gewuenscht
:: ════════════════════════════════════════════════
echo.
echo  +================================================+
echo  ^|  ERSTELLUNG ABGESCHLOSSEN                     ^|
echo  +================================================+
echo.
if "!ERRORS!"=="0" (
    echo  ^>^> Schluessel  : !KEY_STATUS!
    echo  ^>^> Checksummen : !CS_STATUS!
    echo  ^>^> Dev-Token   : !TOK_STATUS!
    echo.
    echo  Alle Dateien wurden erfolgreich erstellt.
) else (
    echo  ^>^> Schluessel  : !KEY_STATUS!
    echo  ^>^> Checksummen : !CS_STATUS!
    echo  ^>^> Dev-Token   : !TOK_STATUS!
    echo.
    echo  ACHTUNG: Es gab Fehler - bitte oben nachsehen!
)
echo.

:ask_verify
echo.
set VERIFY_CHOICE=
set /p VERIFY_CHOICE="  Dateien jetzt pruefen? (y/n) > "
if /i "!VERIFY_CHOICE!"=="y" goto :finalcheck
if /i "!VERIFY_CHOICE!"=="n" goto :report
echo  Bitte y oder n eingeben.
goto :ask_verify

:: ════════════════════════════════════════════════
::  Finale Verifikation
:: ════════════════════════════════════════════════
:finalcheck
echo  +------------------------------------------------+
echo  ^|  Verifikation                                 ^|
echo  +------------------------------------------------+

:: -- Schluessel --
echo  [...] Pruefe Schluessel...
if not exist "dev_privkey.pem" ( echo  [FEHLT] dev_privkey.pem fehlt & set VERIFY_ERRORS=1 & goto :check_cs )
if not exist "dev_pubkey.pem"  ( echo  [FEHLT] dev_pubkey.pem fehlt  & set VERIFY_ERRORS=1 & goto :check_cs )
(
echo from cryptography.hazmat.primitives import hashes,serialization
echo from cryptography.hazmat.primitives.asymmetric import padding
echo from pathlib import Path
echo priv=serialization.load_pem_private_key^(Path^('dev_privkey.pem'^).read_bytes^(^),password=None^)
echo pub=serialization.load_pem_public_key^(Path^('dev_pubkey.pem'^).read_bytes^(^)^)
echo pub.verify^(priv.sign^(b'test',padding.PKCS1v15^(^),hashes.SHA256^(^)^),b'test',padding.PKCS1v15^(^),hashes.SHA256^(^)^)
) > _v1.py
python _v1.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] Schluessel passen nicht zusammen! & set VERIFY_ERRORS=1 ) else ( echo  [  OK ] Schluessel verifiziert )
del _v1.py >nul 2>&1

:: -- Checksums --
:check_cs
echo  [...] Pruefe checksums.json...
if not exist "checksums.json" ( echo  [FEHLT] checksums.json fehlt & set VERIFY_ERRORS=1 & goto :check_tok )
(
echo import json
echo from pathlib import Path
echo d=json.loads^(Path^('checksums.json'^).read_text^(^)^)
echo if len^(d^)==0: raise Exception^('leer'^)
echo print^(f'  {len^(d^)} Dateien gehasht'^)
) > _v2.py
python _v2.py
if errorlevel 1 ( echo  [FEHLER] checksums.json ist leer! & set VERIFY_ERRORS=1 ) else ( echo  [  OK ] checksums.json verifiziert )
del _v2.py >nul 2>&1

:: -- Dev-Token --
:check_tok
echo  [...] Pruefe Dev-Token...
if not exist "dev_mode.flag" ( echo  [FEHLT] dev_mode.flag fehlt & set VERIFY_ERRORS=1 & goto :report )
if not exist "dev_pubkey.pem" ( echo  [FEHLT] dev_pubkey.pem fehlt & set VERIFY_ERRORS=1 & goto :report )
(
echo from cryptography.hazmat.primitives import hashes,serialization
echo from cryptography.hazmat.primitives.asymmetric import padding
echo import base64
echo from pathlib import Path
echo pub=serialization.load_pem_public_key^(Path^('dev_pubkey.pem'^).read_bytes^(^)^)
echo pub.verify^(base64.b64decode^(Path^('dev_mode.flag'^).read_text^(^).strip^(^)^),b'EVEToolbox-DevMode',padding.PKCS1v15^(^),hashes.SHA256^(^)^)
) > _v3.py
python _v3.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] Dev-Token ungueltig! & set VERIFY_ERRORS=1 ) else ( echo  [  OK ] Dev-Token verifiziert )
del _v3.py >nul 2>&1

:: ════════════════════════════════════════════════
::  Abschlussbericht
:: ════════════════════════════════════════════════
:report
echo.

if "!ABORTED!"=="1" (
    echo  +================================================+
    echo  ^|  ERGEBNIS:   ABGEBROCHEN                      ^|
    echo  +================================================+
    echo.
    echo  Vorgang abgebrochen - nichts veraendert.
    goto :ask_exit
)

if "!VERIFY_ERRORS!"=="0" if "!ERRORS!"=="0" (
    color 0A
    echo  +================================================+
    echo  ^|                                               ^|
    echo  ^|   [OK] ALLES ERFOLGREICH VERIFIZIERT          ^|
    echo  ^|                                               ^|
    echo  +================================================+
    echo.
    echo  [OK] dev_privkey.pem  - Schluessel gueltig
    echo  [OK] dev_pubkey.pem   - Schluessel gueltig
    echo  [OK] checksums.json   - Dateien gehasht
    echo  [OK] dev_mode.flag    - Token gueltig
    echo.
    goto :push_info
) else (
    color 0C
    echo  +================================================+
    echo  ^|                                               ^|
    echo  ^|   [FEHLER] FEHLER GEFUNDEN                    ^|
    echo  ^|                                               ^|
    echo  +================================================+
    goto :ask_exit
)

:push_info
echo  +------------------------------------------------+
echo  ^|  Auf GitHub pushen:                           ^|
echo  ^|  ^(in GitHub Desktop committen und pushen^)     ^|
echo  +------------------------------------------------+
echo  [ GIT ] dev_pubkey.pem
echo  [ GIT ] checksums.json
echo.
echo  +------------------------------------------------+
echo  ^|  NIEMALS pushen oder verlieren:               ^|
echo  +------------------------------------------------+
echo  [ X ] dev_privkey.pem
echo  [ X ] dev_mode.flag
goto :ask_exit
echo.
:ask_exit
set EXIT_CHOICE=
set /p EXIT_CHOICE="  Beenden? (x) > "
if /i "!EXIT_CHOICE!"=="x" exit
echo  Bitte x eingeben zum Beenden.
goto :ask_exit