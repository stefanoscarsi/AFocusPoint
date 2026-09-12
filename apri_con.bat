@echo off
REM Wrapper per "Apri con..." / editor esterno di DxO PhotoLab, da usare SOLO
REM se stai eseguendo il programma dai sorgenti (con l'ambiente virtuale
REM "venv"), non con l'eseguibile CanonAFPointViewer.exe.
REM
REM Perche' serve: Explorer/DxO possono lanciare solo un .exe passandogli il
REM percorso del file, ma per eseguire i sorgenti serve invocare
REM "pythonw.exe main.py <file>" - due parti separate che Explorer non sa
REM comporre da solo. Questo wrapper fa da tramite: registralo TU come
REM "Apri con..." al posto di python.exe, e lui si occupa di richiamare
REM correttamente main.py passandogli il file ricevuto.
REM
REM Usa "pythonw.exe" (non "python.exe") per evitare che si apra anche una
REM finestra nera di console insieme all'app.

cd /d "%~dp0"

if exist venv\Scripts\pythonw.exe (
    start "" venv\Scripts\pythonw.exe main.py %1
) else (
    start "" pythonw main.py %1
)
