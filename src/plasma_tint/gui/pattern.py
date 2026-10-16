# SPDX-License-Identifier: GPL-3.0-or-later
"""A test pattern for judging colour on the display.

The pattern is drawn *through* the LUTs when ``luts`` is given, which yields an
approximate in-app simulation. With identity LUTs it is a neutral pattern that
you look at on the (already corrected) screen.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

Lut = list[int]

_BARS: tuple[tuple[int, int, int], ...] = (
    (255, 255, 255),
    (255, 255, 0),
    (0, 255, 255),
    (0, 255, 0),
    (255, 0, 255),
    (255, 0, 0),
    (0, 0, 255),
    (0, 0, 0),
)


def _identity() -> tuple[Lut, Lut, Lut]:
    ramp = [i * 257 for i in range(256)]
    return (list(ramp), list(ramp), list(ramp))


def _to8(luts: tuple[Lut, Lut, Lut], r: int, g: int, b: int) -> QColor:
    return QColor(luts[0][r] >> 8, luts[1][g] >> 8, luts[2][b] >> 8)


def render_pattern(
    width: int, height: int, luts: tuple[Lut, Lut, Lut] | None = None
) -> QImage:
    """Render the test pattern at the given size, optionally through ``luts``."""
    width = max(2, width)
    height = max(2, height)
    lut = luts or _identity()

    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.black)
    painter = QPainter(image)

    bar_h = int(height * 0.5)
    gray_h = int(height * 0.16)
    band_h = max(1, (height - bar_h - gray_h) // 3)

    # top half: 8 solid colour bars (transformed through the LUTs)
    for index, (r, g, b) in enumerate(_BARS):
        x0 = width * index // len(_BARS)
        x1 = width * (index + 1) // len(_BARS)
        painter.fillRect(x0, 0, x1 - x0, bar_h, _to8(lut, r, g, b))

    # grayscale ramp
    _draw_ramp(painter, 0, bar_h, width, gray_h, lut, "gray")
    # R / G / B ramps
    y = bar_h + gray_h
    _draw_ramp(painter, 0, y, width, band_h, lut, "red")
    _draw_ramp(painter, 0, y + band_h, width, band_h, lut, "green")
    _draw_ramp(painter, 0, y + 2 * band_h, width, band_h, lut, "blue")

    painter.end()
    return image


def _draw_ramp(painter, x, y, width, height, luts, kind) -> None:
    last = max(1, width - 1)
    for column in range(width):
        t = round(column * 255 / last)
        if kind == "gray":
            color = QColor(luts[0][t] >> 8, luts[1][t] >> 8, luts[2][t] >> 8)
        elif kind == "red":
            color = QColor(luts[0][t] >> 8, 0, 0)
        elif kind == "green":
            color = QColor(0, luts[1][t] >> 8, 0)
        else:
            color = QColor(0, 0, luts[2][t] >> 8)
        painter.fillRect(column, y, 1, height, color)


class PatternWidget(QWidget):
    """Widget that displays the test pattern, optionally LUT-simulated."""

    def __init__(self, simulate: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._simulate = simulate
        self._luts: tuple[Lut, Lut, Lut] | None = None
        self._cache: QImage | None = None
        self.setMinimumSize(QSize(320, 200))

    def set_luts(self, luts: tuple[Lut, Lut, Lut] | None) -> None:
        self._luts = luts
        self._cache = None
        self.update()

    def set_simulate(self, simulate: bool) -> None:
        self._simulate = simulate
        self._cache = None
        self.update()

    def _picture(self) -> QImage:
        size = self.size()
        luts = self._luts if self._simulate else None
        return render_pattern(size.width(), size.height(), luts)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        if self._cache is None or self._cache.size() != self.size():
            self._cache = self._picture()
        painter = QPainter(self)
        painter.drawImage(0, 0, self._cache)

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._cache = None
        super().resizeEvent(event)
