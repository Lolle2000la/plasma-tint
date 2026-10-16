# SPDX-License-Identifier: GPL-3.0-or-later
"""Build ICC display profiles carrying a ``vcgt`` calibration LUT.

Two flavours, because KWin interprets them very differently:

* **SDR** (:func:`build_profile`) — an exact sRGB profile (Rec.709 primaries,
  D65, sRGB parametric TRC). KWin's SDR pipeline uses the profile as a normal
  ICC display profile, so this is a verified identity transform plus ``vcgt``.

* **HDR** (:func:`build_hdr_profile`) — used in KWin's ``hdrIccProfile`` slot.
  There KWin hardcodes the content space as **BT.2020** and (with an ``MHC2``
  tag) uses its own PQ encoder, so the profile must describe the display *in
  HDR*: BT.2020 primaries, a ``lumi`` tag (peak luminance) and a minimal
  ``MHC2`` tag with an identity matrix and **no LUT** (a non-empty MHC2 LUT
  would override our ``vcgt``). The ``rTRC/gTRC/bTRC`` must exist and be
  invertible but are otherwise unused on this path.
"""

from __future__ import annotations

import struct
from pathlib import Path

Lut = list[int]

# -- constants ---------------------------------------------------------------

_D50 = (0.9642, 1.0, 0.8249)
# D65 as KWin computes it from xy(0.3127, 0.3290)
_D65 = (0.950456, 1.0, 1.089058)

_SRGB_PRIMARIES = ((0.64, 0.33), (0.30, 0.60), (0.15, 0.06))
# KWin's Colorimetry::BT2020 (src/core/colorspace.cpp)
_BT2020_PRIMARIES = ((0.708, 0.292), (0.170, 0.797), (0.131, 0.046))

_BRADFORD = (
    (0.8951, 0.2664, -0.1614),
    (-0.7502, 1.7135, 0.0367),
    (0.0389, -0.0685, 1.0296),
)


# -- low level writers -------------------------------------------------------


def _u16(value: int) -> bytes:
    return struct.pack(">H", value & 0xFFFF)


def _u32(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFFFF)


def _s15f16(value: float) -> bytes:
    return struct.pack(">i", int(round(value * 65536.0)))


def _pad4(data: bytes) -> bytes:
    return data + b"\x00" * ((4 - (len(data) % 4)) % 4)


# -- 3x3 linear algebra ------------------------------------------------------


def _matvec(matrix, vector):
    return [sum(matrix[i][k] * vector[k] for k in range(3)) for i in range(3)]


def _inv3(m):
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    a_, b_, c_ = e * i - f * h, -(d * i - f * g), d * h - e * g
    d_, e_, f_ = -(b * i - c * h), a * i - c * g, -(a * h - b * g)
    g_, h_, i_ = b * f - c * e, -(a * f - c * d), a * e - b * d
    det = a * a_ + b * b_ + c * c_
    return [
        [a_ / det, d_ / det, g_ / det],
        [b_ / det, e_ / det, h_ / det],
        [c_ / det, f_ / det, i_ / det],
    ]


def _diag(values):
    return [[values[0], 0, 0], [0, values[1], 0], [0, 0, values[2]]]


def _adapt(xyz, source_white, dest_white):
    inv = _inv3(_BRADFORD)
    src = _matvec(_BRADFORD, source_white)
    dst = _matvec(_BRADFORD, dest_white)
    ratios = [dst[i] / src[i] for i in range(3)]
    return _matvec(inv, _matvec(_diag(ratios), _matvec(_BRADFORD, xyz)))


def _rgb_to_xyz(primaries_xy, white):
    columns = [(x / y, 1.0, (1.0 - x - y) / y) for (x, y) in primaries_xy]
    matrix = [[columns[j][i] for j in range(3)] for i in range(3)]
    scale = _matvec(_inv3(matrix), list(white))
    return [[matrix[i][j] * scale[j] for j in range(3)] for i in range(3)]


def _colorants_and_chad(primaries_xy, white):
    matrix = _rgb_to_xyz(primaries_xy, white)
    colorants = [
        _adapt([matrix[0][j], matrix[1][j], matrix[2][j]], white, _D50) for j in range(3)
    ]
    basis = [_adapt(unit, white, _D50) for unit in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]
    chad = [[basis[j][i] for j in range(3)] for i in range(3)]
    return colorants, chad


# -- tag element builders ----------------------------------------------------


def _xyz_tag(x, y, z):
    return b"XYZ " + b"\x00" * 4 + _s15f16(x) + _s15f16(y) + _s15f16(z)


def _chad_tag(matrix):
    return b"sf32" + b"\x00" * 4 + b"".join(
        _s15f16(matrix[i][j]) for i in range(3) for j in range(3)
    )


def _chrm_tag(primaries_xy):
    body = _u16(3) + _u16(3)  # numberOfDeviceChannels, numberOfColorants
    for x, y in primaries_xy:
        body += _s15f16(x) + _s15f16(y)
    return b"chrm" + b"\x00" * 4 + body


def _para_srgb_tag():
    params = (2.4, 1.0 / 1.055, 0.055 / 1.055, 1.0 / 12.92, 0.04045)
    body = _u16(3) + _u16(0) + b"".join(_s15f16(v) for v in params)
    return b"para" + b"\x00" * 4 + body


def _curv_table_tag(values):
    return b"curv" + b"\x00" * 4 + _u32(len(values)) + b"".join(_u16(v) for v in values)


def _linear_curv_tag(size: int = 1024):
    return _curv_table_tag([int(round(i / (size - 1) * 65535)) for i in range(size)])


def _text_desc_tag(text: str):
    ascii_bytes = text.encode("ascii", "replace") + b"\x00"
    unicode_bytes = text.encode("utf-16-be") + b"\x00\x00"
    return (
        b"desc"
        + b"\x00" * 4
        + _u32(len(ascii_bytes))
        + _pad4(ascii_bytes)
        + _u32(0)  # unicode language code
        + _u32(len(unicode_bytes) // 2)
        + unicode_bytes
        + _u16(0)
        + b"\x00"
        + b"\x00" * 67
    )


def _text_tag(text: str):
    return b"text" + b"\x00" * 4 + text.encode("ascii", "replace") + b"\x00"


def _vcgt_tag(luts: tuple[Lut, Lut, Lut]):
    """vcgt table form: TagType(u32), nChannels, nElems, nBytes, channel-major."""
    count = len(luts[0])
    out = b"vcgt" + b"\x00" * 4
    out += _u32(0) + _u16(3) + _u16(count) + _u16(2)
    for channel in luts:
        out += b"".join(_u16(max(0, min(0xFFFF, int(v)))) for v in channel)
    return out


def _mhc2_tag(peak_luminance: float, min_luminance: float = 0.0):
    """Minimal MHC2: identity matrix (offset 36), no LUT (so vcgt survives)."""
    identity = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0)
    out = b"MHC2" + b"\x00" * 4
    out += _u32(0)  # lutSize = 0
    out += _s15f16(min_luminance)
    out += _s15f16(peak_luminance)
    out += _u32(36)  # matrixOffset
    out += _u32(0) + _u32(0) + _u32(0)  # red/green/blue LUT offsets
    out += b"".join(_s15f16(v) for v in identity)
    return out


def _header(size: int) -> bytes:
    header = struct.pack(">I", size)
    header += struct.pack(">I", 0)  # preferred CMM
    header += struct.pack(">I", 0x02400000)  # version 2.4.0
    header += b"mntr"  # device class: display
    header += b"RGB "  # data colour space
    header += b"XYZ "  # PCS
    header += struct.pack(">HHHHHH", 2026, 1, 1, 0, 0, 0)  # creation date
    header += b"acsp"  # profile file signature
    header += struct.pack(">I", 0)  # primary platform
    header += struct.pack(">I", 0)  # flags
    header += struct.pack(">I", 0)  # device manufacturer
    header += struct.pack(">I", 0)  # device model
    header += struct.pack(">Q", 0)  # device attributes
    header += struct.pack(">I", 0)  # rendering intent
    header += struct.pack(">III", 0x0000F6D6, 0x00010000, 0x0000D32D)  # PCS illuminant D50
    header += struct.pack(">I", 0)  # profile creator
    header += bytes(16)  # profile ID
    header += bytes(28)  # reserved
    assert len(header) == 128, len(header)
    return header


def _assemble(tags: list[tuple[bytes, bytes]]) -> bytes:
    tags = sorted(tags, key=lambda item: item[0])
    offset = 128 + 4 + 12 * len(tags)
    table = struct.pack(">I", len(tags))
    blocks = b""
    for signature, data in tags:
        padded = _pad4(data)
        table += signature + _u32(offset) + _u32(len(data))
        blocks += padded
        offset += len(padded)
    total = 128 + len(table) + len(blocks)
    return _header(total) + table + blocks


def _normalise_luts(luts: tuple[Lut, Lut, Lut]) -> tuple[Lut, Lut, Lut]:
    return tuple(  # type: ignore[return-value]
        [max(0, min(0xFFFF, int(v))) for v in channel] for channel in luts
    )


# -- public builders ---------------------------------------------------------


def build_profile(
    luts: tuple[Lut, Lut, Lut],
    description: str = "plasma-tint per-channel colour adjustment",
    copyright_text: str = "Public Domain",
) -> bytes:
    """SDR ICC v2 profile: exact sRGB identity + ``vcgt``."""
    colorants, chad = _colorants_and_chad(_SRGB_PRIMARIES, _D65)
    trc = _para_srgb_tag()
    tags = [
        (b"desc", _text_desc_tag(description)),
        (b"cprt", _text_tag(copyright_text)),
        (b"wtpt", _xyz_tag(*_D50)),
        (b"chad", _chad_tag(chad)),
        (b"chrm", _chrm_tag(_SRGB_PRIMARIES)),
        (b"rXYZ", _xyz_tag(*colorants[0])),
        (b"gXYZ", _xyz_tag(*colorants[1])),
        (b"bXYZ", _xyz_tag(*colorants[2])),
        (b"rTRC", trc),
        (b"gTRC", trc),
        (b"bTRC", trc),
        (b"vcgt", _vcgt_tag(_normalise_luts(luts))),
    ]
    return _assemble(tags)


def build_hdr_profile(
    luts: tuple[Lut, Lut, Lut],
    peak_luminance: float = 1000.0,
    max_fall: float | None = None,
    min_luminance: float = 0.0,
    description: str = "plasma-tint HDR per-channel colour adjustment",
    copyright_text: str = "Public Domain",
) -> bytes:
    """HDR ICC v2 profile for KWin's ``hdrIccProfile`` slot.

    BT.2020 primaries, ``lumi`` (peak), and a minimal MHC2 (identity, no LUT) so
    KWin uses its own PQ encoder and keeps our ``vcgt``. ``rTRC/gTRC/bTRC`` are
    linear and unused on the MHC2 path but must exist.
    """
    if max_fall is None:
        max_fall = peak_luminance
    colorants, chad = _colorants_and_chad(_BT2020_PRIMARIES, _D65)
    trc = _linear_curv_tag()
    tags = [
        (b"desc", _text_desc_tag(description)),
        (b"cprt", _text_tag(copyright_text)),
        (b"wtpt", _xyz_tag(*_D50)),
        (b"chad", _chad_tag(chad)),
        (b"chrm", _chrm_tag(_BT2020_PRIMARIES)),
        (b"rXYZ", _xyz_tag(*colorants[0])),
        (b"gXYZ", _xyz_tag(*colorants[1])),
        (b"bXYZ", _xyz_tag(*colorants[2])),
        (b"rTRC", trc),
        (b"gTRC", trc),
        (b"bTRC", trc),
        (b"lumi", _xyz_tag(0.0, float(max_fall), 0.0)),
        (b"MHC2", _mhc2_tag(float(peak_luminance), float(min_luminance))),
        (b"vcgt", _vcgt_tag(_normalise_luts(luts))),
    ]
    return _assemble(tags)


def write_profile(
    luts: tuple[Lut, Lut, Lut], path: str | Path, *, hdr: bool = False, **kwargs
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    builder = build_hdr_profile if hdr else build_profile
    path.write_bytes(builder(luts, **kwargs))
    return path
