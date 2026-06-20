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

if not exist "eve_toolbox\core\release_crypto.py" (
    echo  [FEHLER] eve_toolbox\core\release_crypto.py nicht gefunden!
    set PRECHECK_OK=0
) else (
    echo  [  OK ] release_crypto.py gefunden
)

if not exist "eve_toolbox\core\_embed_pubkey.py" (
    echo  [FEHLER] eve_toolbox\core\_embed_pubkey.py nicht gefunden!
    set PRECHECK_OK=0
) else (
    echo  [  OK ] _embed_pubkey.py gefunden
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
if exist "dev_privkey.pem" ( echo  [  OK ] dev_privkey.pem   vorhanden  ^(Release Key^) ) else ( echo  [FEHLT] dev_privkey.pem   nicht vorhanden ^(Release Key^) )
if exist "dev_pubkey.pem"  ( echo  [  OK ] dev_pubkey.pem    vorhanden  ^(Release Key^) ) else ( echo  [FEHLT] dev_pubkey.pem    nicht vorhanden ^(Release Key^) )
if exist "checksums.json"  ( echo  [  OK ] checksums.json    vorhanden ) else ( echo  [FEHLT] checksums.json    nicht vorhanden )
if exist "checksums.json.sig" ( echo  [  OK ] checksums.json.sig vorhanden ) else ( echo  [FEHLT] checksums.json.sig nicht vorhanden )
if exist "release_cert.json" ( echo  [  OK ] release_cert.json vorhanden ^(Root autorisiert Release^) ) else ( echo  [FEHLT] release_cert.json nicht vorhanden — Root Key muss Release Key autorisieren! )
if exist "stable_version.json" ( echo  [  OK ] stable_version.json vorhanden ^(wird von release.bat/downgrade.bat gesetzt^) ) else ( echo  [INFO ] stable_version.json noch nicht vorhanden ^(entsteht bei release.bat^) )
if exist "dev_mode.flag"   ( echo  [  OK ] dev_mode.flag     vorhanden ) else ( echo  [FEHLT] dev_mode.flag     nicht vorhanden )
if exist "ROOT_KEY_SICHERN\root_privkey.pem" ( echo  [WARN ] Root Key liegt noch LOKAL in ROOT_KEY_SICHERN\ — auf Stick sichern und loeschen! ) else ( echo  [  OK ] Kein Root Key lokal gefunden ^(gut - sollte offline liegen^) )

:: ════════════════════════════════════════════════
::  Moduswahl — wiederholt bis gueltige Eingabe
:: ════════════════════════════════════════════════
echo.
echo  +------------------------------------------------+
echo  ^|  Was moechtest du tun?                        ^|
echo  ^|                                               ^|
echo  ^|  [1] Ersteinrichtung / Release Key neu        ^|
echo  ^|      Release-Keypair + Checksums + Token neu  ^|
echo  ^|      Braucht danach den Root Key zum           ^|
echo  ^|      Autorisieren ^(Stick einstecken^)          ^|
echo  ^|                                               ^|
echo  ^|  [2] Update veroeffentlichen                  ^|
echo  ^|      Nur Checksums neu generieren             ^|
echo  ^|      Release Key und Token bleiben            ^|
echo  ^|                                               ^|
echo  ^|  [3] Root Key erzeugen ^(NUR beim allerersten   ^|
echo  ^|      Einrichten oder wenn Root Key verloren^)  ^|
echo  ^|                                               ^|
echo  ^|  [4] Abbrechen                                ^|
echo  +------------------------------------------------+

:ask_mode
echo.
set MODE=
set /p MODE="  Auswahl (1/2/3/4) > "
if "!MODE!"=="1" goto :mode_full
if "!MODE!"=="2" goto :mode_update
if "!MODE!"=="3" goto :mode_root
if "!MODE!"=="4" ( set ABORTED=1 & goto :report )
echo  Bitte 1, 2, 3 oder 4 eingeben.
goto :ask_mode

:: ════════════════════════════════════════════════
::  MODUS 3 — Root Key erzeugen (separater Workflow)
::  Erzeugt einen eigenen Ordner mit NUR dem Root Key
::  drin, oeffnet ihn am Ende automatisch, damit sofort
::  klar ist: diese eine Datei auf den Stick, dann
::  lokal loeschen.
:: ════════════════════════════════════════════════
:mode_root
echo.
echo  +------------------------------------------------+
echo  ^|  Root Key erzeugen                            ^|
echo  +------------------------------------------------+
echo.
echo  Der Root Key ist der wichtigste Schluessel im     
echo  ganzen System. Er wird so gut wie nie benutzt -    
echo  nur wenn ein Release Key gewechselt werden muss.  
echo.
echo  Workflow:                                          
echo   1. Jetzt wird er einmalig erzeugt                 
echo   2. Ein Ordner ROOT_KEY_SICHERN\ oeffnet sich       
echo   3. Du ziehst die Datei root_privkey.pem auf        
echo      einen USB-Stick ^(am besten 2 Sticks^)           
echo   4. Danach bestaetigst du hier - die lokale Kopie   
echo      wird automatisch geloescht                      
echo.

if exist "ROOT_KEY_SICHERN\root_privkey.pem" (
    echo  +------------------------------------------------+
    echo  ^|  ACHTUNG: Root Key existiert bereits!         ^|
    echo  ^|  Neu erstellen macht ALLE bisherigen           ^|
    echo  ^|  release_cert.json Dateien ungueltig.          ^|
    echo  ^|  Nur fortfahren wenn der alte Root Key          ^|
    echo  ^|  wirklich verloren ist.                        ^|
    echo  +------------------------------------------------+
    set C=
    set /p C="  Trotzdem neu erstellen? (y/n) > "
    if /i not "!C!"=="y" ( set ABORTED=1 & goto :report )
)

if not exist "ROOT_KEY_SICHERN" mkdir "ROOT_KEY_SICHERN"
echo  [...] Erzeuge Root-Schluesselpaar...
> _root_tmp.py echo import sys
>> _root_tmp.py echo sys.path.insert(0, r"%CD%\eve_toolbox")
>> _root_tmp.py echo from core.release_crypto import generate_keypair
>> _root_tmp.py echo from pathlib import Path
>> _root_tmp.py echo generate_keypair(Path('ROOT_KEY_SICHERN/root_privkey.pem'), Path('ROOT_KEY_SICHERN/root_pubkey.pem'))
python _root_tmp.py
if errorlevel 1 ( echo  [FEHLER] Root Key fehlgeschlagen! & set ERRORS=1 & goto :report )
del _root_tmp.py >nul 2>&1
echo  [  OK ] Root Key erzeugt in ROOT_KEY_SICHERN\

echo  [...] Trage Root Public Key automatisch in release_crypto.py ein...
python eve_toolbox\core\_embed_pubkey.py "eve_toolbox\core\release_crypto.py" "ROOT_KEY_SICHERN\root_pubkey.pem"
if errorlevel 1 (
    echo  [FEHLER] Root Public Key konnte nicht eingetragen werden!
    set ERRORS=1
) else (
    echo  [  OK ] Root Public Key in release_crypto.py eingetragen
)
echo.

echo  +------------------------------------------------+
echo  ^|  JETZT: Ordner oeffnet sich gleich            ^|
echo  ^|  Ziehe root_privkey.pem auf deinen Stick      ^|
echo  +------------------------------------------------+
set C=
set /p C="  Ordner jetzt oeffnen? (y/n) > "
if /i "!C!"=="y" explorer "ROOT_KEY_SICHERN"
echo.

:ask_root_secured
set C=
set /p C="  Root Key auf Stick(s) gesichert? Lokale Kopie loeschen? (y/n) > "
if /i "!C!"=="y" (
    del "ROOT_KEY_SICHERN\root_privkey.pem" >nul 2>&1
    echo  [  OK ] Lokale Kopie von root_privkey.pem geloescht
    echo          ^(root_pubkey.pem bleibt - das ist kein Geheimnis^)
    goto :ask_root_done
)
if /i "!C!"=="n" (
    echo  [WARN ] Root Key bleibt LOKAL liegen - das ist unsicher!
    echo          Bitte so schnell wie moeglich sichern und diesen
    echo          Schritt erneut ausfuehren um die lokale Kopie zu loeschen.
    goto :ask_root_done
)
goto :ask_root_secured

:ask_root_done
echo.
echo  Root Key Einrichtung abgeschlossen.
echo  Naechster Schritt: Modus 1 ausfuehren um den Release
echo  Key zu erzeugen und vom Root Key autorisieren zu lassen.
echo.
goto :report

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
echo  [...] Erstelle Ed25519 Schluessel...
> _key_tmp.py echo import sys
>> _key_tmp.py echo sys.path.insert(0, r"%CD%\eve_toolbox")
>> _key_tmp.py echo from core.release_crypto import generate_keypair
>> _key_tmp.py echo from pathlib import Path
>> _key_tmp.py echo generate_keypair(Path('dev_privkey.pem'), Path('dev_pubkey.pem'))
python _key_tmp.py
if errorlevel 1 (
    echo  [FEHLER] Schluessel fehlgeschlagen!
    set KEY_STATUS=FEHLER
    set ERRORS=1
    goto :report
) else (
    if "!KEY_STATUS!"=="ueberschrieben" ( echo  [ UPD] Schluessel ueberschrieben ) else ( echo  [  OK ] Schluessel erstellt )
)
del _key_tmp.py >nul 2>&1
echo.

:: ════════════════════════════════════════════════
::  Release Key vom Root Key autorisieren lassen
::  (release_cert.json) — braucht den Root Key kurz
::  vom Stick. MUSS vor den Checksums passieren, da
::  sich sonst der Hash von release_crypto.py oder
::  anderen Dateien nochmal aendern wuerde.
:: ════════════════════════════════════════════════
echo  +------------------------------------------------+
echo  ^|  Release Key muss vom Root Key autorisiert    ^|
echo  ^|  werden ^(release_cert.json^)                   ^|
echo  +------------------------------------------------+
echo.
echo  Stecke jetzt den Stick mit root_privkey.pem ein.
echo.

:ask_root_path
set ROOT_PATH=
set /p ROOT_PATH="  Pfad zu root_privkey.pem (z.B. D:\root_privkey.pem) > "
if "!ROOT_PATH!"=="" ( echo  Bitte Pfad eingeben. & goto :ask_root_path )
if not exist "!ROOT_PATH!" ( echo  [FEHLER] Datei nicht gefunden: !ROOT_PATH! & goto :ask_root_path )

echo  [...] Erstelle release_cert.json...
> _cert_tmp.py echo import sys
>> _cert_tmp.py echo sys.path.insert(0, r"%CD%\eve_toolbox")
>> _cert_tmp.py echo from core.release_crypto import create_release_cert
>> _cert_tmp.py echo from pathlib import Path
>> _cert_tmp.py echo create_release_cert(Path('dev_pubkey.pem'), Path(r"!ROOT_PATH!"), Path('release_cert.json'))
python _cert_tmp.py
if errorlevel 1 (
    echo  [FEHLER] release_cert.json konnte nicht erstellt werden!
    echo           Pruefe ob !ROOT_PATH! wirklich der Root Key ist.
    set ERRORS=1
    goto :report
) else (
    echo  [  OK ] release_cert.json erstellt - Release Key autorisiert
)
del _cert_tmp.py >nul 2>&1
echo.
echo  Du kannst den Stick jetzt wieder abziehen.
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

:: ════════════════════════════════════════════════
::  Checksums signieren (in BEIDEN Modi, bei jedem
::  Release muss checksums.json.sig neu erzeugt werden)
:: ════════════════════════════════════════════════
set SIG_STATUS=erstellt
if exist "checksums.json.sig" set SIG_STATUS=ueberschrieben

if not exist "dev_privkey.pem" (
    echo  [WARN] Kein Schluessel - Signierung uebersprungen
    set SIG_STATUS=uebersprungen
    goto :after_sig
)

if not exist "release_cert.json" (
    echo  [FEHLER] release_cert.json fehlt!
    echo           Der Release Key wurde noch nicht vom Root Key
    echo           autorisiert. Modus 1 ausfuehren ^(braucht den
    echo           Root Key vom Stick^), bevor signiert werden kann.
    set ERRORS=1
    goto :report
)

echo  [...] Signiere checksums.json...
> _sig_tmp.py echo import sys
>> _sig_tmp.py echo sys.path.insert(0, r"%CSDIR%\eve_toolbox")
>> _sig_tmp.py echo from core.release_crypto import sign_data
>> _sig_tmp.py echo from pathlib import Path
>> _sig_tmp.py echo data = Path('checksums.json').read_bytes()
>> _sig_tmp.py echo sig = sign_data(data, Path('dev_privkey.pem'))
>> _sig_tmp.py echo Path('checksums.json.sig').write_text(sig, encoding='utf-8')
>> _sig_tmp.py echo print('  checksums.json.sig erstellt')
python _sig_tmp.py
if errorlevel 1 (
    echo  [FEHLER] Signierung fehlgeschlagen!
    set SIG_STATUS=FEHLER
    set ERRORS=1
) else (
    if "!SIG_STATUS!"=="ueberschrieben" ( echo  [ UPD] checksums.json.sig ueberschrieben ) else ( echo  [  OK ] checksums.json.sig erstellt )
)
del _sig_tmp.py >nul 2>&1
:after_sig
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
> _tok_tmp.py echo import sys
>> _tok_tmp.py echo sys.path.insert(0, r"%CD%\eve_toolbox")
>> _tok_tmp.py echo from core.release_crypto import sign_data, DEV_TOKEN_MESSAGE
>> _tok_tmp.py echo from pathlib import Path
>> _tok_tmp.py echo sig = sign_data(DEV_TOKEN_MESSAGE, Path('dev_privkey.pem'))
>> _tok_tmp.py echo Path('dev_mode.flag').write_text(sig, encoding='utf-8')
python _tok_tmp.py
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
echo  [...] Pruefe Release-Schluessel...
if not exist "dev_privkey.pem" ( echo  [FEHLT] dev_privkey.pem fehlt & set VERIFY_ERRORS=1 & goto :check_cert )
if not exist "dev_pubkey.pem"  ( echo  [FEHLT] dev_pubkey.pem fehlt  & set VERIFY_ERRORS=1 & goto :check_cert )
(
echo import sys
echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
echo from core.release_crypto import sign_data
echo from cryptography.hazmat.primitives import serialization
echo from pathlib import Path
echo sig = sign_data^(b'test', Path^('dev_privkey.pem'^)^)
echo pub=serialization.load_pem_public_key^(Path^('dev_pubkey.pem'^).read_bytes^(^)^)
echo import base64
echo pub.verify^(base64.b64decode^(sig^), b'test'^)
) > _v1.py
python _v1.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] Release-Schluessel passen nicht zusammen! & set VERIFY_ERRORS=1 ) else ( echo  [  OK ] Release-Schluessel verifiziert )
del _v1.py >nul 2>&1

:: -- Release-Zertifikat (Root autorisiert Release Key) --
:check_cert
echo  [...] Pruefe release_cert.json gegen Root Key im Code...
if not exist "release_cert.json" ( echo  [FEHLT] release_cert.json fehlt & set VERIFY_ERRORS=1 & goto :check_cs )
(
echo import sys
echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
echo from core.release_crypto import load_release_cert
echo from pathlib import Path
echo key = load_release_cert^(Path^('release_cert.json'^)^)
echo import sys as s
echo s.exit^(0 if key else 1^)
) > _v_cert.py
python _v_cert.py >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] release_cert.json ungueltig gegen Root Key im Code!
    echo           Pruefe core\release_crypto.py - ist der ROOT Public Key dort eingetragen?
    set VERIFY_ERRORS=1
) else (
    echo  [  OK ] release_cert.json verifiziert - Release Key vom Root autorisiert
)
del _v_cert.py >nul 2>&1

:: -- Checksums --
:check_cs
echo  [...] Pruefe checksums.json...
if not exist "checksums.json" ( echo  [FEHLT] checksums.json fehlt & set VERIFY_ERRORS=1 & goto :check_sig )
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

:: -- Signatur gegen Release Key (autorisiert durch Zertifikat) --
:: WICHTIG: das prueft zweistufig - erst release_cert.json gegen den
:: Root Key im Code, dann die eigentliche Signatur gegen den im
:: Zertifikat genannten Release Key. Schlaegt das fehl, ist entweder
:: der Root Key noch nicht im Code eingetragen, oder das Zertifikat
:: passt nicht zum aktuellen Release Key.
:check_sig
echo  [...] Pruefe checksums.json Signatur gegen autorisierten Release Key...
if not exist "checksums.json.sig" ( echo  [FEHLT] checksums.json.sig fehlt & set VERIFY_ERRORS=1 & goto :check_tok )
(
echo import sys
echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
echo from core.release_crypto import verify_release_signature
echo from pathlib import Path
echo data = Path^('checksums.json'^).read_bytes^(^)
echo sig = Path^('checksums.json.sig'^).read_text^(^).strip^(^)
echo ok = verify_release_signature^(data, sig, cert_path=Path^('release_cert.json'^)^)
echo import sys as s
echo s.exit^(0 if ok else 1^)
) > _v_sig.py
python _v_sig.py >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Signatur passt NICHT zum autorisierten Release Key!
    set VERIFY_ERRORS=1
) else (
    echo  [  OK ] Signatur gegen autorisierten Release Key verifiziert
)
del _v_sig.py >nul 2>&1

:: -- Dev-Token --
:check_tok
echo  [...] Pruefe Dev-Token...
if not exist "dev_mode.flag" ( echo  [FEHLT] dev_mode.flag fehlt & set VERIFY_ERRORS=1 & goto :report )
(
echo import sys
echo sys.path.insert^(0, r"%CD%\eve_toolbox"^)
echo from core.release_crypto import verify_dev_token
echo from pathlib import Path
echo token = Path^('dev_mode.flag'^).read_text^(^).strip^(^)
echo ok = verify_dev_token^(token, Path^('release_cert.json'^)^)
echo import sys as s
echo s.exit^(0 if ok else 1^)
) > _v3.py
python _v3.py >nul 2>&1
if errorlevel 1 (
    echo  [FEHLER] Dev-Token ungueltig gegen TRUSTED_PUBLIC_KEYS_PEM!
    set VERIFY_ERRORS=1
) else (
    echo  [  OK ] Dev-Token verifiziert
)
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
    echo  ^|   ALLES OK - BEREIT ZUM PUSHEN                ^|
    echo  ^|                                               ^|
    echo  +================================================+
    echo.
    echo  [OK] dev_privkey.pem    - Schluessel gueltig
    echo  [OK] dev_pubkey.pem     - Schluessel gueltig
    echo  [OK] checksums.json     - Dateien gehasht
    echo  [OK] checksums.json.sig - Signatur gueltig gegen Code-Trusted-Keys
    echo  [OK] dev_mode.flag      - Token gueltig
    echo  [OK] release_crypto.py  - Public Key automatisch eingetragen
    echo.
    echo  Alles erfolgreich - du kannst jetzt pushen.
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
echo  [ GIT ] checksums.json.sig
echo  [ GIT ] core\release_crypto.py  ^(falls Public Key neu eingetragen^)
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