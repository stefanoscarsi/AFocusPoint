#!/bin/bash
# Genera l'app Mac (.app) e un installer .dmg pronto da aprire.
#
# Uso, dal Terminale, dentro la cartella del progetto:
#     chmod +x build_mac.sh     # solo la prima volta
#     ./build_mac.sh
#
# Lo script fa tutto da solo: crea l'ambiente virtuale se manca, installa le
# dipendenze, compila l'app e la impacchetta in un .dmg.
#
# NOTA: va eseguito SUL MAC. Non e' possibile generare un'app Mac da Windows
# (PyInstaller non fa cross-compilazione: compila per il sistema su cui gira).

set -u
cd "$(dirname "$0")"

APP_NAME="AFocusPoint"
DMG_PATH="dist/${APP_NAME}.dmg"
DMG_STAGING="dist/dmg-staging"

fail() {
    echo ""
    echo "[ERRORE] $1"
    read -r -p "Premi INVIO per chiudere..."
    exit 1
}

# --- 1. Python ------------------------------------------------------------

if ! command -v python3 >/dev/null 2>&1; then
    fail "python3 non trovato. Installalo (es. 'brew install python') e riprova."
fi

PY_OK=$(python3 -c 'import sys; print(1 if sys.version_info >= (3, 10) else 0)')
if [ "$PY_OK" != "1" ]; then
    fail "Serve Python 3.10 o superiore (trovato $(python3 --version))."
fi

# --- 2. Ambiente virtuale e dipendenze ------------------------------------

if [ ! -f venv/bin/python3 ]; then
    echo "Ambiente virtuale non trovato: lo creo adesso..."
    python3 -m venv venv || fail "Creazione dell'ambiente virtuale fallita."
fi

echo "Installo le dipendenze (PySide6, Pillow, PyExifTool) e PyInstaller..."
venv/bin/python3 -m pip install --upgrade pip --quiet
venv/bin/python3 -m pip install -r requirements.txt --quiet \
    || fail "Installazione delle dipendenze fallita. Controlla la connessione internet."
venv/bin/python3 -m pip install pyinstaller --quiet \
    || fail "Installazione di PyInstaller fallita. Controlla la connessione internet."

# --- 3. Compilazione dell'app --------------------------------------------

echo ""
echo "Creo l'app Mac: puo' richiedere qualche minuto e produce un pacchetto"
echo "di circa 115 MB, perche' include il framework grafico Qt necessario"
echo "per l'interfaccia. E' normale."
echo ""

# Tutte le opzioni (icona, bundle .app, associazione ai file CR3 per
# "Apri con..." del Finder) sono in AFocusPoint-mac.spec.
venv/bin/python3 -m PyInstaller \
    --noconfirm \
    AFocusPoint-mac.spec \
    || fail "La creazione dell'app e' fallita. Copia il messaggio sopra per capire cosa e' successo."

[ -d "dist/${APP_NAME}.app" ] || fail "PyInstaller non ha prodotto dist/${APP_NAME}.app."

# --- 4. Creazione del .dmg ------------------------------------------------

echo ""
echo "Impacchetto l'app in un installer .dmg..."

rm -rf "$DMG_STAGING"
mkdir -p "$DMG_STAGING"
cp -R "dist/${APP_NAME}.app" "$DMG_STAGING/"
# Collegamento ad Applicazioni: apre il classico "trascina qui per installare".
ln -s /Applications "$DMG_STAGING/Applications"

rm -f "$DMG_PATH"
hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_STAGING" \
    -ov -format UDZO \
    "$DMG_PATH" \
    || fail "Creazione del .dmg fallita."

rm -rf "$DMG_STAGING"

# --- 5. Riepilogo ---------------------------------------------------------

echo ""
echo "============================================"
echo "Fatto! Trovi l'installer pronto in:"
echo "  ${DMG_PATH}"
echo ""
echo "Aprilo con un doppio click e trascina ${APP_NAME} dentro Applicazioni."
echo ""
echo "NOTA: al primo avvio macOS potrebbe bloccarla come app non verificata"
echo "(Gatekeeper, perche' non e' firmata con un account sviluppatore Apple"
echo "a pagamento). Se succede: tasto destro sull'app -> Apri -> Apri comunque."
echo ""

if command -v exiftool >/dev/null 2>&1; then
    echo "ExifTool trovato: $(exiftool -ver). Tutto pronto."
else
    echo "ATTENZIONE: ExifTool NON e' installato, e l'app non puo' funzionare"
    echo "senza (non e' incluso nel pacchetto). Installalo con:"
    echo "    brew install exiftool"
fi
echo "============================================"
read -r -p "Premi INVIO per chiudere..."
