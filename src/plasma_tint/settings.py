# SPDX-License-Identifier: GPL-3.0-or-later
"""Color parameter model shared by the GUI, the LUT builder and the ICC writer.

Values and ranges mirror nvidia-settings' ``NvCtrlAttributes.h`` exactly:

* ``brightness``  -1.0 .. 1.0, default 0.0
* ``contrast``    -1.0 .. 1.0, default 0.0   (0.0 is neutral!)
* ``gamma``        0.1 .. 10.0, default 1.0

The UI presents brightness/contrast as -100..100 (``value/100``) and gamma as a
0.10..10.00 slider. The authoritative mapping from these parameters to a 3×N
gamma ramp lives in :mod:`plasma_tint.color.model`.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

CHANNELS = ("red", "green", "blue")

BRIGHTNESS_MIN, BRIGHTNESS_MAX, BRIGHTNESS_DEFAULT = -1.0, 1.0, 0.0
CONTRAST_MIN, CONTRAST_MAX, CONTRAST_DEFAULT = -1.0, 1.0, 0.0
GAMMA_MIN, GAMMA_MAX, GAMMA_DEFAULT = 0.1, 10.0, 1.0


@dataclass
class Channel:
    """One color channel's correction parameters."""

    brightness: float = BRIGHTNESS_DEFAULT  # -1.0 .. 1.0
    contrast: float = CONTRAST_DEFAULT  # -1.0 .. 1.0
    gamma: float = GAMMA_DEFAULT  # 0.1 .. 10.0

    def is_identity(self) -> bool:
        return (
            abs(self.brightness) < 1e-9
            and abs(self.contrast) < 1e-9
            and abs(self.gamma - 1.0) < 1e-9
        )


@dataclass
class ColorSettings:
    """The full per-channel correction state."""

    red: Channel = field(default_factory=Channel)
    green: Channel = field(default_factory=Channel)
    blue: Channel = field(default_factory=Channel)

    def channels(self) -> tuple[Channel, Channel, Channel]:
        return (self.red, self.green, self.blue)

    def get(self, name: str) -> Channel:
        return getattr(self, name)

    def set(self, name: str, channel: Channel) -> None:
        setattr(self, name, channel)

    def is_identity(self) -> bool:
        return all(c.is_identity() for c in self.channels())

    def reset(self) -> None:
        for name in CHANNELS:
            setattr(self, name, Channel())

    def copy(self) -> "ColorSettings":
        return replace(self, **{n: replace(getattr(self, n)) for n in CHANNELS})

    # -- (de)serialisation -------------------------------------------------

    def to_dict(self) -> dict:
        return {name: asdict(self.get(name)) for name in CHANNELS}

    @classmethod
    def from_dict(cls, data: dict) -> "ColorSettings":
        settings = cls()
        for name in CHANNELS:
            values = data.get(name, {})
            settings.set(
                name,
                Channel(
                    brightness=float(values.get("brightness", BRIGHTNESS_DEFAULT)),
                    contrast=float(values.get("contrast", CONTRAST_DEFAULT)),
                    gamma=float(values.get("gamma", GAMMA_DEFAULT)),
                ),
            )
        return settings


def config_path() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "plasma-tint" / "settings.json"


def load_settings() -> ColorSettings:
    path = config_path()
    try:
        return ColorSettings.from_dict(json.loads(path.read_text("utf-8")))
    except (OSError, ValueError):
        return ColorSettings()


def save_settings(settings: ColorSettings) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.to_dict(), indent=2), "utf-8")
