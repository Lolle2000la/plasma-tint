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


# -- environment handed to external binaries (frozen/AppImage builds) --------


def test_child_env_drops_bundle_library_path(monkeypatch):
    monkeypatch.setattr(kscreen.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/_internal:/opt/lib")
    monkeypatch.delenv("LD_LIBRARY_PATH_ORIG", raising=False)
    monkeypatch.setenv("QT_PLUGIN_PATH", "/bundle/PySide6/Qt/plugins")

    env = kscreen._child_env()

    assert "LD_LIBRARY_PATH" not in env
    assert "QT_PLUGIN_PATH" not in env


def test_child_env_restores_pre_bundle_library_path(monkeypatch):
    monkeypatch.setattr(kscreen.sys, "frozen", True, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/bundle/_internal")
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/opt/nvidia/lib")

    assert kscreen._child_env()["LD_LIBRARY_PATH"] == "/opt/nvidia/lib"


def test_child_env_untouched_outside_a_frozen_build(monkeypatch):
    monkeypatch.delattr(kscreen.sys, "frozen", raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/custom/lib")

    assert kscreen._child_env()["LD_LIBRARY_PATH"] == "/custom/lib"

