"""The icons recovered from the native binary, ready to draw.

The recovered PNGs are the icon ALREADY COMPOSITED over the window face
(#f0f0f0): where the icon is transparent the asset carries the face
colour. Drawing an asset as it is would paint a grey box over the white
source pane, so the face has to be keyed out and the alpha recovered.

For one pixel of a one-colour icon, composited over ``FACE`` with ink
``C`` and alpha ``a``::

    asset = C*a + FACE*(1-a)

The icon's darkest pixel is the ink, so the luminance gives the blend
factor ``a = (FACE - L) / (FACE - Ldark)`` and ``C`` follows from the
asset. The result composites over ANY background the way the native one
does, which matters because the same icon is drawn over white (the mic in
the source pane) and over a button (the service strip).

The service icons are in colour, and a coloured icon's luminance says
nothing about its alpha, so those keep their own pixels and only the
exact face colour is keyed out.
"""
from __future__ import annotations

import os

from PySide6.QtGui import QColor, QImage, QPixmap

FACE = 240

_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "assets")
_CACHE: dict[tuple[str, str], QPixmap] = {}


def _luma(c: QColor) -> int:
    return (c.red() * 299 + c.green() * 587 + c.blue() * 114) // 1000


def _recover(img: QImage) -> QImage:
    """Key the face out and rebuild the alpha, so the icon composites."""
    w, h = img.width(), img.height()
    pixels = [[img.pixelColor(x, y) for x in range(w)] for y in range(h)]
    lum = [[_luma(c) for c in row] for row in pixels]
    face_n = sum(1 for row in pixels for c in row
                 if (c.red(), c.green(), c.blue()) == (FACE, FACE, FACE))
    if not face_n:
        return img                      # nothing to key: the icon is solid
    spread = max(max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue())
                 for row in pixels for c in row)
    dark = min(v for row in lum for v in row)
    if dark >= FACE:
        dark = FACE - 1
    out = QImage(w, h, QImage.Format_ARGB32)
    for y in range(h):
        for x in range(w):
            c = pixels[y][x]
            if (c.red(), c.green(), c.blue()) == (FACE, FACE, FACE):
                out.setPixelColor(x, y, QColor(0, 0, 0, 0))
                continue
            if spread > 24:
                out.setPixelColor(x, y, QColor(c.red(), c.green(), c.blue(), 255))
                continue
            a = min(1.0, max(0.0, (FACE - lum[y][x]) / float(FACE - dark)))
            if a <= 0.02:
                out.setPixelColor(x, y, QColor(0, 0, 0, 0))
                continue
            ink = []
            for v in (c.red(), c.green(), c.blue()):
                ink.append(max(0, min(255, int(round((v - FACE * (1 - a)) / a)))))
            out.setPixelColor(x, y, QColor(ink[0], ink[1], ink[2], int(a * 255)))
    return out


def pixmap(kind: str, name: str) -> QPixmap:
    """The icon ``name`` from ``assets/<kind>`` (``ui_icons``,
    ``service_icons``), with its background keyed out."""
    key = (kind, name)
    if key in _CACHE:
        return _CACHE[key]
    path = os.path.join(_ASSETS, kind, name + ".png")
    img = QImage(path)
    pm = QPixmap.fromImage(_recover(img)) if not img.isNull() else QPixmap()
    _CACHE[key] = pm
    return pm
