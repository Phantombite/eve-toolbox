"""
Hilfsskript für security_generator.bat: trägt den Inhalt von
dev_pubkey.pem automatisch zwischen die Marker-Kommentare
AUTO-TRUSTED-KEYS-START/END in core/release_crypto.py ein.

Wird NIE in der ausgelieferten App ausgeführt — nur einmalig vom
Entwickler über security_generator.bat.
"""
import sys
import re
from pathlib import Path

CRYPTO_FILE = Path(sys.argv[1])   # eve_toolbox/core/release_crypto.py
PUBKEY_FILE = Path(sys.argv[2])   # dev_pubkey.pem

START_MARKER = "# AUTO-TRUSTED-KEYS-START"
END_MARKER = "# AUTO-TRUSTED-KEYS-END"


def main():
    if not CRYPTO_FILE.exists():
        print(f"FEHLER: {CRYPTO_FILE} nicht gefunden")
        sys.exit(1)
    if not PUBKEY_FILE.exists():
        print(f"FEHLER: {PUBKEY_FILE} nicht gefunden")
        sys.exit(1)

    pubkey_pem = PUBKEY_FILE.read_text(encoding="utf-8").strip()
    content = CRYPTO_FILE.read_text(encoding="utf-8")

    if START_MARKER not in content or END_MARKER not in content:
        print(f"FEHLER: Marker {START_MARKER}/{END_MARKER} nicht in {CRYPTO_FILE} gefunden")
        print("        Datei wurde vermutlich von Hand verändert — bitte manuell pruefen.")
        sys.exit(1)

    new_block = (
        f"{START_MARKER}\n"
        f"TRUSTED_PUBLIC_KEYS_PEM = [\n"
        f'    """{pubkey_pem}""",\n'
        f"]\n"
        f"{END_MARKER}"
    )

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )
    if not pattern.search(content):
        print("FEHLER: Marker-Block konnte nicht eindeutig gefunden werden")
        sys.exit(1)

    # Backup vor dem Schreiben — falls irgendwas schiefgeht, ist die
    # vorherige Version nicht verloren.
    backup = CRYPTO_FILE.with_suffix(CRYPTO_FILE.suffix + ".bak")
    backup.write_text(content, encoding="utf-8")

    new_content = pattern.sub(new_block, content, count=1)
    CRYPTO_FILE.write_text(new_content, encoding="utf-8")

    print(f"Public Key erfolgreich in {CRYPTO_FILE.name} eingetragen.")
    print(f"(Backup der vorherigen Version: {backup.name})")


if __name__ == "__main__":
    main()