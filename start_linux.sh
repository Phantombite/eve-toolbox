#!/bin/bash
# EVE Toolbox - Linux Starter
# Macht das gleiche wie die Windows .exe

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/eve_toolbox"

# Python prüfen
if ! command -v python3 &>/dev/null; then
    echo "Python 3 nicht gefunden. Bitte installieren:"
    echo "  sudo pacman -S python    (Arch/CachyOS)"
    echo "  sudo apt install python3 (Ubuntu/Debian)"
    exit 1
fi

# PyQt6 prüfen
if ! python3 -c "import PyQt6" &>/dev/null; then
    echo "PyQt6 nicht gefunden. Installieren mit:"
    echo "  pip install PyQt6 --break-system-packages"
    exit 1
fi

# Starten (kein Terminal-Fenster wenn von Desktop gestartet)
python3 main.py "$@"