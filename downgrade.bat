@echo off
chcp 65001 >nul
title EVE Toolbox - Notfall-Downgrade
color 0C
setlocal enabledelayedexpansion
cd /d "%~dp0"

cls
echo.
echo  +================================================+
echo  ^|    EVE Toolbox - Notfall-Downgrade            ^|
echo  ^|    by phantombite                             ^|
echo  +================================================+
echo.
echo  Dieses Skript setzt eine AELTERE Version als         
echo  "stable" — fuer den Fall, dass eine veroeffentlichte 
echo  Version ein Problem hat und du gerade keine Zeit     
echo  hast, einen richtigen Fix zu bauen.                   
echo.
echo  Alle Installationen, die stable_version.json beim     
echo  naechsten Start pruefen, werden auf die hier           
echo  angegebene Version zurueckgesetzt oder zumindest       
echo  informiert ^(siehe "mandatory" unten^).                
echo.
echo  WICHTIG: braucht den Release Key ^(dev_privkey.pem^),   
echo  NICHT den Root Key. Kein Stick noetig.                 
echo.

set ERRORS=0

if not exist "dev_privkey.pem" (
    echo  [FEHLER] dev_privkey.pem fehlt!
    set ERRORS=1
    goto :ask_exit
)
if not exist "release_cert.json" (
    echo  [FEHLER] release_cert.json fehlt!
    echo           security_generator.bat Modus 1 zuerst ausfuehren.
    set ERRORS=1
    goto :ask_exit
)

for /f "tokens=*" %%v in ('python -c "import json; print(json.load(open('version.json'))['version'])" 2^>nul') do set CURRENT_VERSION=%%v
echo  Aktuell veroeffentlichte Version: !CURRENT_VERSION!
if exist "stable_version.json" (
    for /f "tokens=*" %%v in ('python -c "import json; print(json.load(open('stable_version.json'))['version'])" 2^>nul') do set CURRENT_STABLE=%%v
    echo  Aktuell als stable markiert     : !CURRENT_STABLE!
)
echo.

:ask_version
set ROLLBACK_VERSION=
set /p ROLLBACK_VERSION="  Auf welche Version zuruecksetzen? (z.B. 1.4.0) > "
if "!ROLLBACK_VERSION!"=="" ( echo  Bitte Versionsnummer eingeben. & goto :ask_version )

python -c "import re,sys; v='!ROLLBACK_VERSION!'; sys.exit(0 if re.match(r'^[0-9]+[.][0-9]+[.][0-9]+$',v) else 1)" >nul 2>&1
if errorlevel 1 ( echo  Format muss x.y.z sein. & goto :ask_version )

echo.
echo  +------------------------------------------------+
echo  ^|  Wie dringend ist dieser Rollback?            ^|
echo  ^|                                               ^|
echo  ^|  [1] Nervig/kritischer Bug                    ^|
echo  ^|      Nutzer sehen ein Popup mit Wahl:         ^|
echo  ^|      "Jetzt zurueckrollen" oder "Spaeter"     ^|
echo  ^|                                               ^|
echo  ^|  [2] Sicherheitskritisch                      ^|
echo  ^|      Rollback wird ERZWUNGEN, kein Popup mit  ^|
echo  ^|      Wahlmoeglichkeit - nur eine Information   ^|
echo  +------------------------------------------------+
:ask_mandatory
set MANDATORY_CHOICE=
set /p MANDATORY_CHOICE="  Auswahl (1/2) > "
if "!MANDATORY_CHOICE!"=="1" ( set MANDATORY_PY=False & goto :confirm )
if "!MANDATORY_CHOICE!"=="2" ( set MANDATORY_PY=True & goto :confirm )
echo  Bitte 1 oder 2 eingeben.
goto :ask_mandatory

:confirm
echo.
echo  +------------------------------------------------+
echo  ^|  ZUSAMMENFASSUNG                              ^|
echo  +------------------------------------------------+
echo  Rollback-Ziel : v!ROLLBACK_VERSION!
echo  Erzwungen     : !MANDATORY_PY!
echo.
set C=
set /p C="  stable_version.json jetzt so setzen? (y/n) > "
if /i not "!C!"=="y" ( set ERRORS=1 & goto :ask_exit )

echo.
echo  [...] Setze stable_version.json...
> _dg_tmp.py echo import json
>> _dg_tmp.py echo from pathlib import Path
>> _dg_tmp.py echo data = {"version": "!ROLLBACK_VERSION!", "mandatory": !MANDATORY_PY!}
>> _dg_tmp.py echo text = json.dumps(data, indent=2)
>> _dg_tmp.py echo Path('stable_version.json').write_bytes(text.encode('utf-8'))
>> _dg_tmp.py echo print('stable_version.json gesetzt')
python _dg_tmp.py
del _dg_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] stable_version.json fehlgeschlagen! & set ERRORS=1 & goto :ask_exit )
echo  [  OK ] stable_version.json gesetzt

echo  [...] Signiere stable_version.json...
> _dgsig_tmp.py echo import sys
>> _dgsig_tmp.py echo sys.path.insert(0, r"%CD%\eve_toolbox")
>> _dgsig_tmp.py echo from core.release_crypto import sign_data
>> _dgsig_tmp.py echo from pathlib import Path
>> _dgsig_tmp.py echo data = Path('stable_version.json').read_bytes()
>> _dgsig_tmp.py echo sig = sign_data(data, Path('dev_privkey.pem'))
>> _dgsig_tmp.py echo Path('stable_version.json.sig').write_text(sig, encoding='utf-8')
>> _dgsig_tmp.py echo print('stable_version.json.sig erstellt')
python _dgsig_tmp.py
del _dgsig_tmp.py >nul 2>&1
if errorlevel 1 ( echo  [FEHLER] Signierung fehlgeschlagen! & set ERRORS=1 & goto :ask_exit )
echo  [  OK ] stable_version.json.sig erstellt
echo.

echo  +================================================+
echo  ^|  FERTIG                                       ^|
echo  +================================================+
echo.
echo  Jetzt in GitHub Desktop committen und pushen:
echo  [ GIT ] stable_version.json
echo  [ GIT ] stable_version.json.sig
echo.
echo  Alle Installationen pruefen das beim naechsten     
echo  Start automatisch — kein weiterer Schritt noetig.  
echo.
echo  Sobald du den eigentlichen Fix fertig hast: ganz   
echo  normal release.bat ausfuehren — das setzt           
echo  stable_version.json automatisch wieder auf die      
echo  neueste Version zurueck.                            
echo.

:ask_exit
set EXIT_CHOICE=
set /p EXIT_CHOICE="  Beenden? (x) > "
if /i "!EXIT_CHOICE!"=="x" exit
echo  Bitte x eingeben.
goto :ask_exit