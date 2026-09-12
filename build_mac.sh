#!/bin/bash
# Genera una vera app .app standalone per Mac, usando PyInstaller.
# Esegui questo script UNA SOLA VOLTA (o ogni volta che modifichi il codice)
# per creare/aggiornare l'app. Per l'uso quotidiano userai poi solo l'app
# generata, senza bisogno ne' di Python ne' di questo script.

cd "$(dirname "$0")"

if [ ! -f venv/bin/python3 ]; then
    echo "[ERRORE] Ambiente virtuale 'venv' non trovato in questa cartella."
    echo "Esegui prima l'installazione descritta nel README (pip install -r requirements.txt),"
    echo "poi riprova."
    read -p "Premi INVIO per chiudere..."
    exit 1
fi

echo "Installo PyInstaller nell'ambiente virtuale..."
venv/bin/python3 -m pip install pyinstaller --quiet
if [ $? -ne 0 ]; then
    echo "[ERRORE] Installazione di PyInstaller fallita. Controlla la connessione internet."
    read -p "Premi INVIO per chiudere..."
    exit 1
fi

echo ""
echo "Creo l'app Mac: puo' richiedere qualche minuto e produce un pacchetto"
echo "abbastanza grande (200-350 MB), perche' include l'intero framework"
echo "grafico Qt necessario per l'interfaccia. E' normale."
echo ""
venv/bin/python3 -m PyInstaller \
    --name "AFocusPoint" \
    --windowed \
    --onefile \
    --icon "assets/icon.icns" \
    --add-data "assets/icon.png:assets" \
    --collect-all PySide6 \
    --noconfirm \
    main.py

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERRORE] La creazione dell'app e' fallita. Copia il messaggio sopra"
    echo "per capire cosa e' successo."
    read -p "Premi INVIO per chiudere..."
    exit 1
fi

echo ""
echo "============================================"
echo "Fatto! Trovi l'app pronta in:"
echo "  dist/AFocusPoint.app"
echo ""
echo "Trascinala pure nella cartella Applicazioni: funziona da sola,"
echo "non serve piu' questa cartella di progetto per lanciarla."
echo ""
echo "NOTA: al primo avvio macOS potrebbe bloccarla come app non"
echo "verificata (Gatekeeper, perche' non e' firmata con un account"
echo "sviluppatore Apple a pagamento). Se succede: tasto destro sull'app"
echo "-> Apri -> Apri comunque."
echo ""
echo "NOTA IMPORTANTE: questa app richiede comunque che ExifTool sia"
echo "installato e nel PATH di sistema, come descritto nel README."
echo "Non e' incluso dentro l'app."
echo "============================================"
read -p "Premi INVIO per chiudere..."
