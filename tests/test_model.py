# SPDX-License-Identifier: GPL-3.0-or-later
from plasma_tint.color import model
from plasma_tint.settings import Channel, ColorSettings


def test_identity_is_identity():
    luts = model.build_luts(ColorSettings())
    for ramp in luts:
        assert ramp[0] == 0
        assert ramp[-1] == 65535
        assert ramp[128] == round(128 * 65535 / 255)


def test_neutral_channel_params_are_identity():
    assert Channel().is_identity()
    assert not Channel(brightness=0.1).is_identity()
    assert not Channel(contrast=0.1).is_identity()
    assert not Channel(gamma=1.1).is_identity()


def test_gamma_brightens_when_above_one():
    # gamma > 1 -> exponent < 1 -> brighter midtones
    lum = model.build_luts(ColorSettings(red=Channel(gamma=2.0)))[0]
    assert lum[128] > round(128 * 65535 / 255)


def test_per_channel_isolation():
    luts = model.build_luts(ColorSettings(red=Channel(gamma=0.8)))
    baseline = model.build_luts(ColorSettings())
    assert luts[0] != baseline[0]
    assert luts[1] == baseline[1]
    assert luts[2] == baseline[2]


def test_brightness_offset_clamps():
    ramp = model.build_luts(ColorSettings(blue=Channel(brightness=-0.5)))[2]
    assert ramp[0] == 0
    assert ramp[-1] < 65535
