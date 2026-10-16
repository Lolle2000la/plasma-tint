# SPDX-License-Identifier: GPL-3.0-or-later
from plasma_tint import edid


def _synthetic_edid(max_code: int, average_code: int, min_code: int) -> bytes:
    base = bytearray(128)
    base[126] = 1  # one extension block
    block = bytearray(128)
    block[0] = 0x02  # CTA-861
    block[1] = 0x03  # revision
    block[2] = 0x0D  # DTD offset -> data block collection ends at byte 15
    # extended tag 0x06 (HDR static metadata), length 6 (ext tag + 5 payload)
    block[4] = (0x07 << 5) | 6
    block[5] = 0x06
    block[6] = 0x00  # EOTF flags
    block[7] = 0x00  # static metadata descriptor
    block[8] = max_code
    block[9] = average_code
    block[10] = min_code
    return bytes(base) + bytes(block)


def test_parse_hdr_luminance():
    data = _synthetic_edid(max_code=104, average_code=104, min_code=37)
    luminance = edid.parse_luminance(data)
    assert luminance is not None
    assert luminance.max_nits == 475.6834411621094 or 475 < luminance.max_nits < 476
    assert 475 < luminance.max_average_nits < 476
    assert 0.05 < luminance.min_nits < 0.2


def test_parse_without_hdr_block_returns_none():
    base = bytearray(128)
    base[126] = 0
    assert edid.parse_luminance(bytes(base)) is None
