@echo off
REM Genera un vero eseguibile .exe standalone per Windows, usando PyInstaller.
REM Esegui questo script UNA SOLA VOLTA (o ogni volta che modifichi il codice)
REM per creare/aggiornare l'exe. Per l'uso quotidiano userai poi solo l'exe
REM generato, senza bisogno ne' di Python ne' di questo script.

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [ERRORE] Ambiente virtuale "venv" non trovato in questa cartella.
    echo Esegui prima l'installazione descritta nel README ^(pip install -r requirements.txt^),
    echo poi riprova.
    pause
    exit /b 1
)

echo Installo PyInstaller nell'ambiente virtuale...
venv\Scripts\python.exe -m pip install pyinstaller --quiet
if errorlevel 1 (
    echo [ERRORE] Installazione di PyInstaller fallita. Controlla la connessione internet.
    pause
    exit /b 1
)

echo.
echo Creo l'eseguibile Windows: puo' richiedere qualche minuto e produce
echo un file abbastanza grande ^(200-350 MB^), perche' include l'intero
echo framework grafico Qt necessario per l'interfaccia. E' normale.
echo.
venv\Scripts\python.exe -m PyInstaller ^
    --name "CanonAFPointViewer" ^
    --windowed ^
    --onefile ^
    --icon "assets\icon.ico" ^
    --add-data "assets\icon.png;assets" ^
    --collect-all PySide6 ^
    --noconfirm ^
    main.py

if errorlevel 1 (
    echo.
    echo [ERRORE] La creazione dell'eseguibile e' fallita. Copia il messaggio
    echo sopra per capire cosa e' successo.
    pause
    exit /b 1
)

echo.
echo ============================================
echo Fatto! Trovi il file pronto in:
echo   dist\CanonAFPointViewer.exe
echo.
echo Puoi copiarlo/spostarlo dove vuoi ^(es. Desktop^): funziona da solo,
echo non serve piu' questa cartella di progetto per lanciarlo.
echo.
echo NOTA IMPORTANTE: questo exe richiede comunque che ExifTool sia
echo installato e nel PATH di sistema, come descritto nel README.
echo Non e' incluso dentro l'exe.
echo ============================================
pause
