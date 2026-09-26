# -*- mode: python ; coding: utf-8 -*-
# Ricetta PyInstaller per l'app Mac, usata da build_mac.sh.
#
# E' un file separato da AFocusPoint.spec (quello Windows, rigenerato da
# build_windows.bat) per due motivi:
#   - il bundle .app ha bisogno di un Info.plist che dichiari che l'app sa
#     aprire i CR3: senza, il Finder non la propone in "Apri con..." e non
#     le si possono trascinare sopra i file. Questo si puo' impostare solo
#     da un file .spec, non dalle opzioni da riga di comando;
#   - lanciare PyInstaller con le opzioni da riga di comando riscrive
#     AFocusPoint.spec, cosi' ogni build su Mac modificava il file Windows.

# Niente collect_all('PySide6') (che invece build_windows.bat usa): gli hook
# di PySide6 inclusi in PyInstaller raccolgono gia' i moduli Qt davvero
# importati. collect_all copiava nel bundle TUTTO PySide6 -- anche Qt
# Designer/Assistant/Linguist, esempi QML e file oggetto di compilazione --
# con due effetti su Mac: app di oltre 600 MB e bundle impossibile da
# firmare correttamente (i link simbolici di quelle app annidate mandano in
# errore codesign), cioe' l'app risulta "danneggiata" una volta copiata su
# un altro Mac.
datas = [('assets/icon.png', 'assets')]
binaries = []
hiddenimports = []


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AFocusPoint',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    # False: i file aperti dal Finder arrivano come QFileOpenEvent, gestito
    # direttamente in main.py (funziona anche con l'app gia' aperta).
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/icon.icns'],
)
# Niente --onefile qui: su macOS il formato nativo e' gia' un bundle .app
# (una cartella), quindi --onefile aggiungerebbe solo una decompressione ad
# ogni avvio -- app piu' lenta ad aprirsi, senza alcun vantaggio.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AFocusPoint',
)
app = BUNDLE(
    coll,
    name='AFocusPoint.app',
    icon='assets/icon.icns',
    bundle_identifier='com.stefanoscarsi.afocuspoint',
    info_plist={
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Canon CR3 RAW',
                # Viewer: l'app legge i CR3 ma non li modifica.
                'CFBundleTypeRole': 'Viewer',
                # Alternate: compare in "Apri con..." senza proporsi come
                # app predefinita per i CR3 (resta quella scelta da te).
                'LSHandlerRank': 'Alternate',
                'LSItemContentTypes': ['com.canon.cr3-raw-image'],
            },
        ],
    },
)
