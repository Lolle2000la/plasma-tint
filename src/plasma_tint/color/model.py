# SPDX-License-Identifier: GPL-3.0-or-later
"""Convert NVIDIA-style per-channel color parameters into 3×N gamma ramps.

This is a faithful port of nvidia-settings' ``ComputeGammaRampVal`` and
``NvCtrlUpdateGammaRamp`` (``src/libXNVCtrlAttributes/NvCtrlAttributes.c``),
which is what the NVIDIA Control Panel's brightness/contrast/gamma sliders
feed. Contrast and brightness are additive around neutral (``0.0``), *not*
multiplicative, and gamma is applied as a power of ``1/gamma``.

One deliberate difference: upstream left-justifies the result into 16 bits
(``val << shift``), which makes the neutral white point ``0xFF00`` (65280) for
a 256-entry ramp rather than 65535. For an ICC ``vcgt`` we want a true identity
at neutral, so :func:`build_luts` rescales the ``[0, size-1]`` result to the
full ``[0, 65535]`` range instead.
"""

from __future__ import annotations

from ..settings import Channel, ColorSettings

LUT_SIZE = 256
LUT_MAX = 65535


def compute_gamma_ramp_val(
    size: int, i: int, contrast: float, brightness: float, gamma: float
) -> int:
    """Port of NVIDIA's ``ComputeGammaRampVal`` returning an index in ``[0, size-1]``."""
    num = size - 1
    if num <= 0:
        return 0

    scale = num / 3.0
    j = float(i)

    # -- contrast: expand/compress about the midpoint; 0.0 == identity --
    c = contrast * scale
    if c > 0.0:
        half = num / 2.0 - 1.0
        j = (j - half) * (half / (half - c)) + half
    else:
        half = num / 2.0
        j = (j - half) * ((half + c) / half) + half

    # -- brightness: plain offset --
    j += brightness * scale
    j = min(max(j, 0.0), float(num))

    # -- gamma: power of 1/gamma --
    g = 1.0 / gamma if gamma else 1.0
    if g == 1.0:
        return int(j)
    return int((j / num) ** g * num + 0.5)


def channel_ramp(
    channel: Channel, size: int = LUT_SIZE, maximum: int = LUT_MAX
) -> list[int]:
    """Build a single channel's ramp as ``size`` ints in ``[0, maximum]``."""
    num = size - 1
    ramp: list[int] = []
    for i in range(size):
        val = compute_gamma_ramp_val(
            size, i, channel.contrast, channel.brightness, channel.gamma
        )
        ramp.append(int(round(val * maximum / num)) if num else 0)
    return ramp


def build_luts(
    settings: ColorSettings, size: int = LUT_SIZE, maximum: int = LUT_MAX
) -> tuple[list[int], list[int], list[int]]:
    """Return ``(red, green, blue)`` ramps for the given settings."""
    ramps = [
        channel_ramp(channel, size=size, maximum=maximum)
        for channel in settings.channels()
    ]
    return (ramps[0], ramps[1], ramps[2])


def identity_luts(size: int = LUT_SIZE, maximum: int = LUT_MAX) -> tuple[list[int], list[int], list[int]]:
    ramp = [int(round(i * maximum / (size - 1))) for i in range(size)]
    return (list(ramp), list(ramp), list(ramp))
