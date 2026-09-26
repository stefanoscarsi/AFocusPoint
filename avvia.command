#!/bin/bash
# Avvia AFocusPoint con un doppio click dal Finder: e' l'equivalente Mac di
# avvia.bat. Si posiziona da solo nella cartella dove si trova questo file,
# quindi funziona indipendentemente da dove lo lanci.

cd "$(dirname "$0")"

if [ -x venv/bin/python3 ]; then
    venv/bin/python3 main.py
else
    echo "[ATTENZIONE] Ambiente virtuale \"venv\" non trovato in questa cartella."
    echo "Provo con il Python di sistema..."
    python3 main.py
fi

if [ $? -ne 0 ]; then
    echo ""
    echo "============================================"
    echo "Si e' verificato un errore all'avvio."
    echo "Copia il messaggio sopra e mostralo per capire cosa e' successo."
    echo "============================================"
    read -r -p "Premi INVIO per chiudere..."
fi
