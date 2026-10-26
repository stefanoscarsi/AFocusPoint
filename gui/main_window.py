"""
main_window.py
--------------
Finestra principale: menu per aprire un CR3, visualizzatore immagine con
overlay AF a sinistra (con zoom/pan), pannello informazioni a destra.

The viewer is a QGraphicsView/QGraphicsScene, not a QLabel in a QScrollArea:
panning a QLabel-based view means re-rendering a large QPixmap on every
scroll step, which gets visibly jerky on a several-thousand-pixel-wide RAW
preview. QGraphicsView instead keeps the original pixmap untouched and pans
by translating the view transform -- Qt's own optimized path for exactly
this -- and its built-in ScrollHandDrag mode gives smooth click-drag
panning with the open/closed hand cursor for free.
"""

from __future__ import annotations

from pathlib import Path

from PIL.ImageQt import ImageQt
from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QAction, QKeySequence, QPainter, QPixmap
from PySide6.QtWidgets import (
    QFileDialog,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QWidget,
)

from core import exif_reader, frame_builder
from gui import af_overlay
from gui import zoom as zoom_utils
from gui.info_panel import InfoPanel
from version import __version__


class _ZoomableGraphicsView(QGraphicsView):
    """Forwards wheel/pinch/double-click events to the owning window, which
    holds the actual zoom state. Panning itself needs no wiring at all:
    ScrollHandDrag is Qt's built-in drag-to-pan mode, and QGraphicsView's own
    wheelEvent scrolls the view.

    Input mapping:
      - mouse wheel                -> zoom (Windows and Mac, as before)
      - trackpad two-finger scroll -> pan, like every Mac app
      - Cmd/Ctrl + scroll          -> zoom, also from a trackpad
      - trackpad pinch             -> zoom (macOS native gesture)
      - double click / two-finger double tap -> back to fit-to-view
    """

    def __init__(self, window: "MainWindow"):
        super().__init__()
        self._window = window
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.setDragMode(QGraphicsView.NoDrag)
        # MinimalViewportUpdate (the default) spends time computing exactly
        # which small region changed on every scroll step; with one item
        # that fills the whole viewport, that bookkeeping is pure overhead
        # since virtually the whole viewport is "dirty" on every pan step
        # anyway -- FullViewportUpdate skips it.
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)

    def wheelEvent(self, event) -> None:  # noqa: N802 - override Qt
        # Only a trackpad (or Magic Mouse) reports a pixel delta: Qt provides
        # it on macOS, while on Windows it's always null, so this branch
        # never changes the Windows behaviour. ControlModifier is the Cmd key
        # on macOS (Qt swaps the two there).
        is_trackpad_scroll = not event.pixelDelta().isNull()
        if is_trackpad_scroll and not event.modifiers() & Qt.ControlModifier:
            super().wheelEvent(event)
            return
        self._window._on_wheel(event)

    def viewportEvent(self, event) -> bool:  # noqa: N802 - override Qt
        # Native gestures arrive on the viewport (the widget under the
        # fingers), not on the view itself. They only exist on macOS.
        if event.type() == QEvent.NativeGesture:
            if event.gestureType() == Qt.ZoomNativeGesture:
                self._window._zoom_by(zoom_utils.pinch_zoom_factor(event.value()))
                return True
            if event.gestureType() == Qt.SmartZoomNativeGesture:
                self._window._reset_zoom()
                return True
        return super().viewportEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - override Qt
        self._window._reset_zoom()
        super().mouseDoubleClickEvent(event)


def _show_message(parent, icon, title: str, text: str) -> None:
    """Come QMessageBox.warning/critical, ma il testo e' sempre testo
    semplice: contiene nomi di file ed errori che arrivano dal file aperto,
    e con il formato automatico Qt lo interpreterebbe come HTML quando
    "sembra" HTML."""
    box = QMessageBox(icon, title, text, QMessageBox.Ok, parent)
    box.setTextFormat(Qt.PlainText)
    box.exec()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"AFocusPoint {__version__} — Punto di messa a fuoco")
        self.resize(1200, 800)

        self._zoom: float = zoom_utils.MIN_ZOOM
        # Scale fitInView last applied, i.e. what zoom=1.0 means for the
        # current photo -- needed to cap zoom relative to native resolution
        # (see gui/zoom.py) and to turn a relative zoom step into an
        # absolute QGraphicsView transform.
        self._base_scale: float = 1.0

        self._build_menu()
        self._build_layout()

        self._check_exiftool_on_startup()

    # ------------------------------------------------------------------
    # Costruzione interfaccia
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        open_action = QAction("Apri CR3...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file_dialog)

        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(open_action)

        # Keyboard zoom: Ctrl+/Ctrl- on Windows, Cmd+/Cmd- on Mac -- handy
        # with a Magic Mouse, which has no wheel and no pinch.
        zoom_in_action = QAction("Ingrandisci", self)
        zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        zoom_in_action.triggered.connect(lambda: self._zoom_by(zoom_utils.ZOOM_STEP, around_center=True))

        zoom_out_action = QAction("Riduci", self)
        zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        zoom_out_action.triggered.connect(lambda: self._zoom_by(1 / zoom_utils.ZOOM_STEP, around_center=True))

        fit_action = QAction("Adatta alla finestra", self)
        fit_action.setShortcut("Ctrl+0")
        fit_action.triggered.connect(self._reset_zoom)

        view_menu = self.menuBar().addMenu("&Vista")
        view_menu.addAction(zoom_in_action)
        view_menu.addAction(zoom_out_action)
        view_menu.addAction(fit_action)

        # "Informazioni" mostra la versione. Su macOS Qt sposta da solo questa
        # voce nel menu dell'applicazione (AFocusPoint -> Informazioni), dove
        # l'utente Mac se la aspetta; su Windows resta nel menu "Aiuto".
        about_action = QAction("Informazioni su AFocusPoint", self)
        about_action.triggered.connect(self._show_about)
        help_menu = self.menuBar().addMenu("&Aiuto")
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        _show_message(
            self,
            QMessageBox.Information,
            "Informazioni su AFocusPoint",
            f"AFocusPoint versione {__version__}\n\n"
            "Mostra il punto di messa a fuoco e il tipo di AF registrati "
            "dalla fotocamera in un file RAW Canon (CR3).",
        )

    def _build_layout(self) -> None:
        central = QWidget()
        layout = QHBoxLayout(central)

        self.scene = QGraphicsScene()
        self.pixmap_item = QGraphicsPixmapItem()
        # Caches the item's rendered (bilinear-interpolated) pixels in
        # device coordinates. Panning only translates the view -- it
        # doesn't change the item's transform relative to the viewport --
        # so Qt can blit this cache instead of re-interpolating the full
        # multi-megapixel source on every mouse-move step, which is what
        # made dragging feel heavy/sluggish on a large RAW preview.
        self.pixmap_item.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        self.scene.addItem(self.pixmap_item)
        self._overlay_items: list[QGraphicsItem] = []

        self.image_view = _ZoomableGraphicsView(self)
        self.image_view.setScene(self.scene)

        self.info_panel = InfoPanel()
        self.info_panel.setFixedWidth(320)

        layout.addWidget(self.image_view, stretch=3)
        layout.addWidget(self.info_panel, stretch=1)

        self.setCentralWidget(central)

    def _check_exiftool_on_startup(self) -> None:
        try:
            version = exif_reader.check_exiftool_available()
            self.statusBar().showMessage(f"ExifTool {version} pronto.")
        except exif_reader.ExifToolNotFoundError as exc:
            _show_message(self, QMessageBox.Critical, "ExifTool non trovato", str(exc))

    def resizeEvent(self, event) -> None:  # noqa: N802 - override Qt
        super().resizeEvent(event)
        # Only re-fit automatically while already at the fit-to-view zoom --
        # if the user has zoomed in, resizing the window shouldn't yank
        # their view back to "whole photo".
        if self._zoom <= zoom_utils.MIN_ZOOM:
            self._fit_to_view()

    # ------------------------------------------------------------------
    # Logica applicativa
    # ------------------------------------------------------------------

    def open_file_dialog(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Apri file CR3", "", "Canon RAW (*.cr3 *.CR3);;Tutti i file (*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str) -> None:
        path = Path(file_path)
        try:
            result = frame_builder.build_frame(path)
            self._show_frame(result)
            self.info_panel.update_data(result)
            self.statusBar().showMessage(f"Caricato: {path.name}")

        except Exception as exc:  # noqa: BLE001 - vogliamo mostrare l'errore, non crashare
            _show_message(
                self,
                QMessageBox.Warning,
                "Errore nel caricamento del file",
                f"Non sono riuscito a elaborare '{path.name}':\n\n{exc}",
            )

    def _show_frame(self, result: frame_builder.FrameResult) -> None:
        qt_image = ImageQt(result.image)
        pixmap = QPixmap.fromImage(qt_image)
        self.pixmap_item.setPixmap(pixmap)

        for item in self._overlay_items:
            self.scene.removeItem(item)
        self._overlay_items = af_overlay.build_items(result)
        for item in self._overlay_items:
            self.scene.addItem(item)

        self.scene.setSceneRect(QRectF(pixmap.rect()))
        self._fit_to_view()

    def _fit_to_view(self) -> None:
        self.image_view.resetTransform()
        if not self.pixmap_item.pixmap().isNull():
            self.image_view.fitInView(self.pixmap_item, Qt.KeepAspectRatio)
        self._base_scale = self.image_view.transform().m11()
        self._zoom = zoom_utils.MIN_ZOOM
        self._update_drag_mode()

    # ------------------------------------------------------------------
    # Zoom / pan
    # ------------------------------------------------------------------

    def _update_drag_mode(self) -> None:
        # ScrollHandDrag is what gives the open/closed hand cursor and the
        # actual click-drag panning -- both for free from Qt -- but only
        # once there's something to pan into.
        self.image_view.setDragMode(
            QGraphicsView.ScrollHandDrag if self._zoom > zoom_utils.MIN_ZOOM else QGraphicsView.NoDrag
        )

    def _reset_zoom(self) -> None:
        self._fit_to_view()

    def _on_wheel(self, event) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self._zoom_by(zoom_utils.wheel_zoom_factor(delta))

    def _zoom_by(self, factor: float, around_center: bool = False) -> None:
        if self.pixmap_item.pixmap().isNull():
            return

        max_zoom = zoom_utils.max_zoom_for_base_scale(self._base_scale)
        new_zoom = min(max(self._zoom * factor, zoom_utils.MIN_ZOOM), max_zoom)
        if new_zoom == self._zoom:
            return

        # QGraphicsView.scale() multiplies the CURRENT transform, so only
        # the relative step is needed -- AnchorUnderMouse (set in
        # _ZoomableGraphicsView) keeps the point under the cursor fixed on
        # screen across the change. Keyboard zoom has no meaningful "point under the mouse" (the cursor
        # may well be outside the view), so it zooms around the view center.
        step = new_zoom / self._zoom
        self._zoom = new_zoom
        if around_center:
            self.image_view.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.image_view.scale(step, step)
        if around_center:
            self.image_view.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._update_drag_mode()
