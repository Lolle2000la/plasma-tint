# How it works

`plasma-tint` is deliberately small. It does one thing: turn per-channel colour
settings into a gamma ramp, put that ramp into an ICC profile, and ask KWin to
use it. This page explains each step.

## 1. Colour model — sliders to gamma ramps

`plasma_tint/color/model.py` is a faithful port of nvidia-settings'
`ComputeGammaRampVal` (`libXNVCtrlAttributes/NvCtrlAttributes.c`). The parameters
and ranges match NVIDIA's:

| Parameter | Range | Neutral |
|---|---|---|
| `brightness` | −1.0 … 1.0 | 0.0 |
| `contrast` | −1.0 … 1.0 | 0.0 |
| `gamma` | 0.1 … 10.0 | 1.0 |

Contrast and brightness are **additive around neutral** (not multiplicative),
and gamma is applied as a power of `1/gamma`:

1. **contrast** — expand/compress the ramp about the midpoint;
   `0.0` is the identity;
2. **brightness** — a plain offset, clamped to the ramp range;
3. **gamma** — `out = in ** (1 / gamma)`.

The result is a 3×256 table of 16-bit values.

> One deliberate difference from NVIDIA: upstream left-justifies into 16 bits
> (`val << shift`), so its neutral white point is `0xFF00` (65280), not 65535.
> For an ICC `vcgt` we want a true identity at neutral, so `plasma-tint`
> re-scales to the full `[0, 65535]` range.

## 2. ICC profile with a `vcgt` tag

`plasma_tint/color/icc.py` writes a minimal ICC v2.4 **display** profile
(class `mntr`, colour space `RGB `, PCS `XYZ `) whose only non-identity effect is
the `vcgt` (video card gamma table) tag.

### SDR profile

For SDR the profile is an **exact sRGB identity**:

- `wtpt` = D50 plus a Bradford D65→D50 `chad`;
- `chrm` = Rec.709 primaries;
- `rXYZ/gXYZ/bXYZ` = Rec.709 colorants adapted to D50;
- `rTRC/gTRC/bTRC` = the sRGB `parametricCurveType` (function type 3).

Because the profile describes exactly the sRGB space the content is already in,
KWin's colour conversion becomes a no-op and only the `vcgt` alters the image.
(Tests assert this: an lcms2 sRGB→profile transform is identity within one code.)

### The `vcgt` tag

```text
'vcgt' , reserved             (8-byte element header)
u32   TagType   = 0 (table)
u16   nChannels = 3
u16   nElems    = 256
u16   nBytes    = 2
u16   red[256]  , green[256] , blue[256]   (big-endian, channel-major)
```

This is the Apple/OpenICC layout, and it is exactly what lcms2's `Type_vcgt_Read`
expects (so KWin, which reads the tag through lcms2, interprets it correctly).

## 3. Applying it

KWin does **not** use colord — the colord integration was removed before
Plasma 6.0. ICC profiles are set through the `kde-output-management-v2` protocol,
which `kscreen-doctor` drives (`plasma_tint/apply/kscreen.py`):

```sh
# SDR
kscreen-doctor output.DP-2.iccprofile."/path/p.icc" output.DP-2.colorProfileSource.ICC
# HDR
kscreen-doctor output.DP-2.hdrIccProfile."/path/p.icc" output.DP-2.hdrColorProfileSource.ICC
```

KWin loads the profile with lcms2, applies the `vcgt` as a 1-D LUT, and records
the path in `~/.config/kwinoutputconfig.json` so it persists across logins.

### Why the generated filenames contain a hash

libkscreen's `Output::setHdrIccProfilePath` (and its SDR sibling) early-returns
when the new path equals the current one:

```cpp
if (d->hdrIccProfilePath != path) { d->hdrIccProfilePath = path; /* emit */ }
```

If we always wrote to the same filename, `kscreen-doctor` would send an
unchanged value, KWin would treat it as a no-op, and **the modified file would
never be re-read** — so only the first change would ever take effect.
`plasma-tint` therefore writes to a **content-hashed** filename
(`DP-2.hdr.<sha1>.icc`), so the path changes whenever the pixels do, and prunes
superseded revisions. This is why "only my first adjustment worked" does not
happen.

## 4. Code map

| File | Responsibility |
|---|---|
| `color/model.py` | NVIDIA colour model → 3×256 ramps |
| `color/icc.py` | ICC v2 profile authoring (SDR + HDR, incl. `vcgt`, `lumi`, `MHC2`) |
| `apply/kscreen.py` | `kscreen-doctor` backend (list outputs, apply, revert) |
| `edid.py` | Read HDR peak/avg/min luminance from the display's EDID |
| `settings.py` | Parameter model + persisted slider values |
| `paths.py` | `$XDG_DATA_HOME`/`$XDG_CONFIG_HOME` locations |
| `gui/` | PySide6 window and test pattern |

See [hdr.md](hdr.md) for the HDR-specific profile.
