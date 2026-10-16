# SPDX-License-Identifier: GPL-3.0-or-later
"""Filesystem locations used by plasma-tint."""

from __future__ import annotations

import os
from pathlib import Path


def data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def profile_dir() -> Path:
    """Directory where generated ICC profiles are stored."""
    path = data_home() / "color" / "icc" / "plasma-tint"
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path(output_name: str, hdr: bool = False) -> Path:
    suffix = ".hdr.icc" if hdr else ".icc"
    return profile_dir() / f"{output_name}{suffix}"
