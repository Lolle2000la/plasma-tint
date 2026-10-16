# SPDX-License-Identifier: GPL-3.0-or-later
"""Validate the generated ICC profiles with lcms2 (the library KWin uses)."""

import ctypes
import ctypes.util
import io
import struct

import pytest

from plasma_tint.color import icc, model
from plasma_tint.settings import Channel, ColorSettings

VCGT_TAG = 0x76636774
CHRM_TAG = 0x6368726D
LUMI_TAG = 0x6C756D69
MHC2_TAG = 0x4D484332


class _XY(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double), ("Y", ctypes.c_double)]


class _XYTriple(ctypes.Structure):
    _fields_ = [("Red", _XY), ("Green", _XY), ("Blue", _XY)]


class _XYZ(ctypes.Structure):
    _fields_ = [("X", ctypes.c_double), ("Y", ctypes.c_double), ("Z", ctypes.c_double)]


_lib = None
for name in ("liblcms2.so.2", "liblcms2.so", "liblcms2.dylib"):
    try:
        _lib = ctypes.CDLL(name)
        break
    except OSError:
        continue
if _lib is None:
    found = ctypes.util.find_library("lcms2")
    try:
        _lib = ctypes.CDLL(found) if found else None
    except OSError:
        _lib = None

pytestmark = pytest.mark.skipif(_lib is None, reason="lcms2 not available")

if _lib is not None:
    _lib.cmsOpenProfileFromMem.restype = ctypes.c_void_p
    _lib.cmsOpenProfileFromMem.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _lib.cmsReadTag.restype = ctypes.c_void_p
    _lib.cmsReadTag.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _lib.cmsIsTag.restype = ctypes.c_int
    _lib.cmsIsTag.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    _lib.cmsReadRawTag.restype = ctypes.c_uint32
    _lib.cmsReadRawTag.argtypes = [
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    ]
    _lib.cmsEvalToneCurveFloat.restype = ctypes.c_float
    _lib.cmsEvalToneCurveFloat.argtypes = [ctypes.c_void_p, ctypes.c_float]
    _lib.cmsCloseProfile.argtypes = [ctypes.c_void_p]


def _open(data: bytes):
    buffer = ctypes.create_string_buffer(data, len(data))
    profile = _lib.cmsOpenProfileFromMem(buffer, len(data))
    assert profile, "lcms2 could not open the generated profile"
    return profile


def _read_vcgt(data: bytes):
    profile = _open(data)
    tag = _lib.cmsReadTag(profile, VCGT_TAG)
    curves = None
    if tag:
        pointers = ctypes.cast(tag, ctypes.POINTER(ctypes.c_void_p))
        curves = [
            [_lib.cmsEvalToneCurveFloat(pointers[ch], x / 255.0) for x in (0, 128, 255)]
            for ch in range(3)
        ]
    _lib.cmsCloseProfile(profile)
    return curves


def _read_primaries(data: bytes):
    profile = _open(data)
    triple = ctypes.cast(
        _lib.cmsReadTag(profile, CHRM_TAG), ctypes.POINTER(_XYTriple)
    ).contents
    result = [
        (round(triple.Red.x, 3), round(triple.Red.y, 3)),
        (round(triple.Green.x, 3), round(triple.Green.y, 3)),
        (round(triple.Blue.x, 3), round(triple.Blue.y, 3)),
    ]
    _lib.cmsCloseProfile(profile)
    return result


# -- SDR ---------------------------------------------------------------------


def test_profile_has_readable_vcgt():
    curves = _read_vcgt(icc.build_profile(model.identity_luts()))
    assert curves is not None
    for channel in curves:
        assert channel[0] == pytest.approx(0.0, abs=1e-4)
        assert channel[1] == pytest.approx(0.5, abs=1e-2)
        assert channel[2] == pytest.approx(1.0, abs=1e-4)


def test_sdr_primaries_are_srgb():
    assert _read_primaries(icc.build_profile(model.identity_luts())) == [
        (0.64, 0.33),
        (0.3, 0.6),
        (0.15, 0.06),
    ]


def test_vcgt_reflects_per_channel_correction():
    data = icc.build_profile(model.build_luts(ColorSettings(red=Channel(gamma=2.0))))
    red, green, blue = _read_vcgt(data)
    assert red[1] > 0.5  # gamma > 1 brightens
    assert green[1] == pytest.approx(0.5, abs=1e-2)
    assert blue[1] == pytest.approx(0.5, abs=1e-2)


def test_color_transform_is_identity():
    """The ICC transform (excluding vcgt) must be a no-op against sRGB."""
    from PIL import Image, ImageCms

    data = icc.build_profile(model.identity_luts())
    source = ImageCms.createProfile("sRGB")
    target = ImageCms.getOpenProfile(io.BytesIO(data))
    transform = ImageCms.buildTransform(
        source,
        target,
        "RGB",
        "RGB",
        renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
    )
    for value in (0, 64, 128, 192, 255):
        pixel = Image.new("RGB", (1, 1), (value, value, value))
        result = transform.apply(pixel).getpixel((0, 0))[0]
        assert abs(result - value) <= 1, f"gray {value} -> {result} is not identity"


# -- HDR ---------------------------------------------------------------------


def _build_hdr():
    return icc.build_hdr_profile(
        model.identity_luts(), peak_luminance=475.683, max_fall=475.683, min_luminance=0.1
    )


def test_hdr_primaries_are_bt2020():
    assert _read_primaries(_build_hdr()) == [
        (0.708, 0.292),
        (0.17, 0.797),
        (0.131, 0.046),
    ]


def test_hdr_has_vcgt_lumi_and_mhc2():
    data = _build_hdr()
    assert _read_vcgt(data) is not None

    profile = _open(data)
    # lumi tag holds the peak luminance in Y
    luminance = ctypes.cast(_lib.cmsReadTag(profile, LUMI_TAG), ctypes.POINTER(_XYZ)).contents
    assert luminance.Y == pytest.approx(475.683, abs=0.01)

    # MHC2 present, with lutSize 0 (so KWin keeps our vcgt) and matching peak
    assert _lib.cmsIsTag(profile, MHC2_TAG)
    raw = ctypes.create_string_buffer(84)
    size = _lib.cmsReadRawTag(profile, MHC2_TAG, raw, 84)
    assert size == 84
    assert struct.unpack(">I", raw[8:12])[0] == 0  # lutSize
    assert struct.unpack(">i", raw[16:20])[0] / 65536.0 == pytest.approx(475.683, abs=0.01)
    _lib.cmsCloseProfile(profile)
