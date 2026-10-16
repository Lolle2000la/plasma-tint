# SPDX-License-Identifier: GPL-3.0-or-later
"""Read HDR luminance metadata from a display's EDID.

Only the CTA-861 "HDR Static Metadata Data Block" (extended tag 0x06) is
parsed. Luminance codes follow CTA-861.3:

* max / max-frame-average: ``L = 50 * 2 ** (code / 32)`` nits
* min: ``L = max * (code / 255) ** 2 / 100`` nits
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_CTA_EXTENSION_TAG = 0x02
_HDR_STATIC_METADATA = 0x06


@dataclass
class HdrLuminance:
    max_nits: float
    max_average_nits: float
    min_nits: float


def _edid_path(connector_name: str) -> Path | None:
    for path in Path("/sys/class/drm").glob(f"card*-{connector_name}/edid"):
        return path
    return None


def _decode_max(code: int) -> float:
    return 50.0 * (2.0 ** (code / 32.0))


def hdr_luminance(connector_name: str) -> HdrLuminance | None:
    """Return the display's HDR luminance, or ``None`` if unavailable."""
    path = _edid_path(connector_name)
    if path is None:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    return parse_luminance(data)


def parse_luminance(data: bytes) -> HdrLuminance | None:
    """Parse HDR static metadata from raw EDID bytes."""
    if len(data) < 128:
        return None

    for index in range(data[126]):
        block = data[128 * (index + 1) : 128 * (index + 2)]
        if len(block) < 128 or block[0] != _CTA_EXTENSION_TAG:
            continue

        dtd_offset = block[2]
        end = (2 + dtd_offset) if dtd_offset >= 4 else 127
        position = 4
        while position < end:
            tag = block[position] >> 5
            length = block[position] & 0x1F
            if tag == 7 and length >= 1:  # extended tag
                extended = block[position + 1]
                payload = block[position + 2 : position + 1 + length]
                if extended == _HDR_STATIC_METADATA and len(payload) >= 5:
                    max_code, average_code, min_code = payload[2], payload[3], payload[4]
                    maximum = _decode_max(max_code)
                    average = _decode_max(average_code)
                    minimum = maximum * (min_code / 255.0) ** 2 / 100.0
                    return HdrLuminance(maximum, average, minimum)
            position += 1 + length
    return None
