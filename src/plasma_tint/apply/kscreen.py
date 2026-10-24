# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply an ICC profile to a KWin output via ``kscreen-doctor``.

This is the correct path on KDE Plasma 6: the colord integration was removed
from KWin before Plasma 6.0, and ICC profiles are now set through the
``kde-output-management-v2`` protocol (which ``kscreen-doctor`` drives). KWin
applies the profile's ``vcgt`` tag as a per-channel 1-D LUT, including while
HDR is enabled (Plasma 6.7+).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass

ANSI = re.compile(r"\x1b\[[0-9;]*m")


class KScreenError(RuntimeError):
    pass


@dataclass
class Output:
    index: int
    name: str
    hdr: str = "unknown"  # "incapable" | "disabled" | "enabled"
    icc_profile: str = ""
    color_profile_source: str = ""

    @property
    def hdr_capable(self) -> bool:
        return self.hdr.lower() in ("disabled", "enabled")

    @property
    def label(self) -> str:
        return f"{self.name} ({self.hdr})"


def _child_env() -> dict[str, str]:
    """Environment for ``kscreen-doctor`` and other system binaries.

    A frozen build (PyInstaller, used for the AppImage) puts its private Qt and
    support libraries in ``_MEIPASS`` and prepends that directory to
    ``LD_LIBRARY_PATH``. Child processes inherit it, so ``kscreen-doctor``
    would load the bundled Qt instead of the system Qt and fail to initialise a
    platform plugin. Unfrozen runs are left untouched.
    """
    env = os.environ.copy()
    if not getattr(sys, "frozen", False):
        return env

    # PyInstaller saves the pre-bundle value here.
    original = env.pop("LD_LIBRARY_PATH_ORIG", None)
    if original:
        env["LD_LIBRARY_PATH"] = original
    else:
        env.pop("LD_LIBRARY_PATH", None)

    # Likewise, drop plugin paths that point into the bundle.
    for name in ("QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "QML2_IMPORT_PATH"):
        env.pop(name, None)
    return env


def _run(*args: str) -> str:
    try:
        result = subprocess.run(
            ["kscreen-doctor", *args],
            capture_output=True,
            text=True,
            check=False,
            env=_child_env(),
        )
    except FileNotFoundError as exc:
        raise KScreenError("kscreen-doctor was not found on PATH") from exc
    if result.returncode != 0:
        raise KScreenError(
            f"kscreen-doctor {' '.join(args)} failed:\n{result.stderr.strip()}"
        )
    return result.stdout


def list_outputs() -> list[Output]:
    """Parse ``kscreen-doctor -o`` into a list of outputs."""
    text = ANSI.sub("", _run("-o"))
    outputs: list[Output] = []
    current: Output | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Output:"):
            parts = line.split()
            current = Output(index=int(parts[1]), name=parts[2])
            outputs.append(current)
            continue
        if current is None or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "hdr":
            current.hdr = value
        elif key == "icc profile":
            current.icc_profile = "" if value == "none" else value
        elif key == "color profile source":
            current.color_profile_source = value

    return outputs


def _profile_args(name: str, path: str, hdr: bool) -> list[str]:
    if hdr:
        return [
            f"output.{name}.hdrIccProfile.{path}",
            f"output.{name}.hdrColorProfileSource.ICC",
        ]
    return [
        f"output.{name}.iccprofile.{path}",
        f"output.{name}.colorProfileSource.ICC",
    ]


def _revert_args(name: str, hdr: bool) -> list[str]:
    if hdr:
        return [
            f"output.{name}.hdrColorProfileSource.EDID",
            f'output.{name}.hdrIccProfile.',
        ]
    return [
        f"output.{name}.colorProfileSource.sRGB",
        f'output.{name}.iccprofile.',
    ]


def apply_profile(name: str, path: str, hdr: bool = False) -> None:
    """Assign ``path`` to output ``name`` and select the ICC source (live)."""
    _run(*_profile_args(name, path, hdr))


def revert(name: str, hdr: bool = False) -> None:
    """Restore the output to its default (sRGB / EDID) color source."""
    _run(*_revert_args(name, hdr))
