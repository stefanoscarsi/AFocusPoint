"""Numero di versione dell'app, in un UNICO posto.

Lo usano: la finestra principale (titolo e finestra "Informazioni"), gli
script di build (nel nome/metadati del pacchetto) e i tag git delle
release. Per pubblicare una nuova versione: cambia qui il numero, aggiorna
CHANGELOG.md e crea il tag git corrispondente (es. v1.0.1).

Schema: versionamento semantico MAJOR.MINOR.PATCH
  - PATCH: correzioni che non cambiano cosa fa l'app (es. 1.0.0 -> 1.0.1)
  - MINOR: nuove funzioni compatibili (es. 1.0.1 -> 1.1.0)
  - MAJOR: cambiamenti importanti/incompatibili (es. 1.1.0 -> 2.0.0)
"""

__version__ = "1.0.0"
