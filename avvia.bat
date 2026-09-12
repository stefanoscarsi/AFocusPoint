@echo off
REM Avvia Canon AF Point Viewer con un doppio click.
REM Si posiziona da solo nella cartella dove si trova questo file,
REM quindi funziona indipendentemente da dove lo lanci.

cd /d "%~dp0"

if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe main.py
) else (
    echo [ATTENZIONE] Ambiente virtuale "venv" non trovato in questa cartella.
    echo Provo con il Python di sistema...
    python main.py
)

if errorlevel 1 (
    echo.
    echo ============================================
    echo Si e' verificato un errore all'avvio.
    echo Copia il messaggio sopra e mostralo per capire cosa e' successo.
    echo ============================================
    pause
)
