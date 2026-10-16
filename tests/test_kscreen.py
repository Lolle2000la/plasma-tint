# SPDX-License-Identifier: GPL-3.0-or-later
from plasma_tint.apply import kscreen


def test_profile_args_sdr():
    args = kscreen._profile_args("DP-2", "/tmp/x.icc", hdr=False)
    assert args == [
        "output.DP-2.iccprofile./tmp/x.icc",
        "output.DP-2.colorProfileSource.ICC",
    ]


def test_profile_args_hdr():
    args = kscreen._profile_args("DP-2", "/tmp/x.icc", hdr=True)
    assert args == [
        "output.DP-2.hdrIccProfile./tmp/x.icc",
        "output.DP-2.hdrColorProfileSource.ICC",
    ]


def test_revert_args_sdr():
    args = kscreen._revert_args("DP-2", hdr=False)
    assert args[0] == "output.DP-2.colorProfileSource.sRGB"
    assert args[1] == "output.DP-2.iccprofile."


def test_output_hdr_capable():
    assert kscreen.Output(1, "DP-1", hdr="disabled").hdr_capable
    assert kscreen.Output(2, "DP-2", hdr="enabled").hdr_capable
    assert not kscreen.Output(3, "DP-3", hdr="incapable").hdr_capable
