"""Image search window -- the .tmp ``wikimedia-reference`` plugin's
CommonsImageSearchService plus its ImageSearchDialog.

Reference: ui-swing .../imagesearch/ImageSearchDialogStateMapping.kt and
core .../lookup/SearchImagesUseCase.kt. In .tmp the dialog opens from
the main window's input panel for a term, queries the active
ServiceRole.IMAGE_SEARCH service, and shows a thumbnail grid where
every tile carries its attribution and licence (Commons licences
require credit on display, so the fields are populated rather than
left to the host to chase).

The port has a single built-in backend -- Wikimedia Commons, which
needs no key -- behind ``qtranslate.services.commons_images``. The
dialog mirrors the native shape: a term field, a results grid of
thumbnails with title + attribution + licence under each, and a
status line. Search and thumbnail fetches run on worker threads;
QPixmap delivery happens on the GUI thread through signals.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

_COLS = 4
_THUMB = 120
_UA = {"User-Agent": "QTranslate/6.10 (image search)"}


class _Signals(QObject):
    """Cross-thread delivery: lives on the GUI thread, emitted by
    workers (queued connection), carrying plain data only."""

    results = Signal(object)                    # list[dict] | Exception
    thumb = Signal(object, object)              # (tile_id, QPixmap)


def _fetch_pixmap(url):
    """Download one thumbnail; returns QPixmap (may be null)."""
    try:
        import urllib.request
        from qtranslate import common
        req = urllib.request.Request(url, headers=_UA)
        with common.http_open(req) as resp:
            data = resp.read()
        pm = QPixmap()
        pm.loadFromData(data)
        return pm
    except Exception:
        return QPixmap()


class _Tile(QFrame):
    """One result: thumbnail, then title + attribution/licence caption."""

    _next_id = 0

    def __init__(self, parent, result):
        super().__init__(parent)
        self.result = result
        self.tile_id = _Tile._next_id
        _Tile._next_id += 1
        self.setFrameShape(QFrame.StyledPanel)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        self.img = QLabel("…", self)
        self.img.setFixedSize(_THUMB, _THUMB)
        self.img.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.img, 0, Qt.AlignHCenter)
        self.cap = QLabel(self._caption(result), self)
        self.cap.setWordWrap(True)
        lay.addWidget(self.cap)

    @staticmethod
    def _caption(r):
        bits = [r.get("title") or ""]
        credit = " · ".join(x for x in (r.get("attribution"),
                                        r.get("license")) if x)
        if credit:
            bits.append(credit)
        return "\n".join(b for b in bits if b)

    def set_pixmap(self, pm):
        try:
            if pm.isNull():
                self.img.setPixmap(QPixmap())
                self.img.setText("?")
            else:
                self.img.setPixmap(pm.scaled(
                    _THUMB, _THUMB, Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))
        except RuntimeError:
            pass                                    # dialog closed


def _imgsearch_cfg():
    """The ``ImageSearch`` section: AutoPosition / Transparency /
    LastKnownPosition / LastKnownSize (.tmp imageSearch* fields)."""
    try:
        from qtranslate import config as _C
        return (_C.load() or {}).get("ImageSearch", {}) or {}
    except Exception:
        return {}


def _imgsearch_save(**kw):
    try:
        from qtranslate import config as _C
        cfg = _C.load() or {}
        sec = cfg.setdefault("ImageSearch", {})
        sec.update(kw)
        _C.save(cfg)
    except Exception:
        pass


class ImageSearchDialog(QDialog):
    """Search Commons for a term; grid of licensed thumbnails."""

    def __init__(self, app, term="", parent=None):
        super().__init__(parent)
        self.app = app
        self.setWindowTitle("Image search")
        cfg = _imgsearch_cfg()
        # .tmp ImageSearchDialogStateMapping: transparency is a percent
        # (5..50); opacity = (100 - pct) / 100.
        try:
            pct = int(cfg.get("Transparency", 5))
        except Exception:
            pct = 5
        pct = max(5, min(50, pct))
        self.setWindowOpacity((100 - pct) / 100.0)
        # AutoPosition on -> the default centred placement; off ->
        # restore the geometry the dialog was last closed with.
        restored = False
        if not bool(cfg.get("AutoPosition", True)):
            try:
                w, h = (int(v) for v in
                        str(cfg.get("LastKnownSize") or "").split(","))
                x, y = (int(v) for v in
                        str(cfg.get("LastKnownPosition") or "")
                        .split(","))
                if w > 200 and h > 200:
                    self.resize(w, h)
                    self.move(x, y)
                    restored = True
            except Exception:
                pass
        if not restored:
            self.resize(580, 500)
        self._sig = _Signals(self)
        self._sig.results.connect(self._results)
        self._sig.thumb.connect(self._set_thumb)
        self._tiles = {}

        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.term = QLineEdit(term or "", self)
        self.term.setPlaceholderText("Search Wikimedia Commons…")
        self.term.returnPressed.connect(self.search)
        row.addWidget(self.term, 1)
        self.go = QPushButton("Search", self)
        self.go.clicked.connect(self.search)
        row.addWidget(self.go)
        lay.addLayout(row)

        self.status = QLabel("", self)
        lay.addWidget(self.status)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.grid_host = QWidget(self.scroll)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setSpacing(6)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll.setWidget(self.grid_host)
        lay.addWidget(self.scroll, 1)

        if term:
            self.search()

    # ------------------------------------------------------------- search
    def search(self):
        term = self.term.text().strip()
        if not term:
            return
        self.status.setText("Searching…")
        self._clear_grid()
        # .tmp LookupSessions.ImageLookupSession: a new search
        # supersedes the previous one's delivery.
        self._search_gen = getattr(self, "_search_gen", 0) + 1
        gen = self._search_gen
        threading.Thread(
            target=self._run_guarded,
            args=(term, "BOTH", gen),
            daemon=True).start()

    def _run_guarded(self, term, media, gen):
        try:
            from qtranslate.services import commons_images as CI
            res = CI.search_images(term, media=media)
        except Exception as exc:                            # noqa: BLE001
            res = exc
        if gen == getattr(self, "_search_gen", 0):
            self._sig.results.emit(res)

    def _results(self, res):
        self._clear_grid()
        self._tiles.clear()
        if isinstance(res, Exception):
            self.status.setText("Search failed")
            return
        if not res:
            self.status.setText("No images found")
            return
        self.status.setText(
            "%d results — images from Wikimedia Commons, under the "
            "licence shown with each result." % len(res))
        for i, r in enumerate(res):
            tile = _Tile(self.grid_host, r)
            self._tiles[tile.tile_id] = tile
            self.grid.addWidget(tile, i // _COLS, i % _COLS)
            threading.Thread(
                target=self._fetch_one,
                args=(tile.tile_id, r["thumbnail"]),
                daemon=True).start()

    def _fetch_one(self, tile_id, url):
        self._sig.thumb.emit(tile_id, _fetch_pixmap(url))

    def _set_thumb(self, tile_id, pm):
        tile = self._tiles.get(tile_id)
        if tile is not None:
            tile.set_pixmap(pm)

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def closeEvent(self, event):                 # noqa: N802 (Qt name)
        # Persist the geometry for the next open when AutoPosition is
        # off (.tmp imageSearchLastKnownPosition/Size).
        try:
            g = self.geometry()
            _imgsearch_save(
                LastKnownSize="%d,%d" % (g.width(), g.height()),
                LastKnownPosition="%d,%d" % (g.x(), g.y()))
        except Exception:
            pass
        super().closeEvent(event)


def open_image_search(app, term="", parent=None):
    """Open the image search dialog for ``term``."""
    dlg = ImageSearchDialog(app, term=term, parent=parent)
    dlg.show()
    return dlg
