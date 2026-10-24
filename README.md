# plasma-tint

**Per-channel display colour adjustment for KDE Plasma — including HDR.**

[![License: GPL-3.0-or-later](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)

A small PySide6 GUI that gives you the NVIDIA-Control-Panel-style per-channel
controls — **Red / Green / Blue × Brightness / Contrast / Gamma** — and applies
them to a display on **KDE Plasma / Wayland**, *including while HDR is enabled*.

That last part is the point. When HDR is on, the monitor's own colour controls
usually lock out, and the X11-era tools stop working:

- `nvidia-settings` colour correction is X11-only and does not survive HDR;
- `xrandr --gamma` needs an X server (it is read-only on Wayland);
- `redshift` / `gammastep` are temperature-only and need a compositor protocol
  KWin does not implement.

`plasma-tint` instead builds a **3×256 gamma ramp** from the sliders, wraps it in
an **ICC profile carrying a `vcgt` tag**, and hands it to KWin. KWin applies the
`vcgt` as a per-channel 1-D LUT — and, since Plasma 6.7, does so **in HDR too**.
So it is a genuine fix for a display with an unwanted colour cast that only
appears (or can only be corrected) in HDR.

## Features

- Per-channel **R/G/B brightness, contrast and gamma**, matching nvidia-settings'
  parameterisation and ranges.
- **Live preview** — it re-applies as you drag.
- Separate, correct profiles for **SDR and HDR** (see [HDR](docs/hdr.md)).
- Exact numeric entry via spin boxes for precise adjustment.
- Revert to the default colour source at the click of a button.
- Saves a standalone `.icc` you can keep, share, or apply elsewhere.

## Requirements

- **KDE Plasma on Wayland**, with KWin.
  - HDR: **Plasma 6.7+** (ICC profiles in HDR were added in 6.7).
  - SDR: Plasma 6.0+.
- `kscreen-doctor` on `PATH`.
- Python 3.10+ with PySide6.

## Install

### AppImage (no installation)

Download `plasma-tint-<version>-x86_64.AppImage` from
[Releases](https://github.com/Lolle2000la/plasma-tint/releases), then:

```sh
chmod +x plasma-tint-*-x86_64.AppImage
./plasma-tint-*-x86_64.AppImage
```

The AppImage bundles Python and PySide6; it still needs KDE Plasma and
`kscreen-doctor` on `PATH` (both are part of a Plasma installation), and FUSE 2
for the AppImage runtime. Without FUSE, run it with
`--appimage-extract-and-run`.

### Python

```sh
pipx install plasma-tint
# or
pip install --user plasma-tint
```

From source:

```sh
git clone https://github.com/Lolle2000la/plasma-tint
cd plasma-tint
python -m venv .venv && . .venv/bin/activate
pip install -e .
plasma-tint
```

Without installing:

```sh
PYTHONPATH=src python -m plasma_tint
```

## Usage

1. Pick the **display** (HDR-capable outputs are marked and selected by default).
2. Choose what the sliders edit: **All channels**, or a single **Red / Green /
   Blue** channel.
3. Drag a slider, or type an exact value in the spin box. **Live preview** is on
   by default, so the screen updates as you go.
4. For a display you use in **HDR**, tick **Apply as HDR profile**.
5. **Revert** restores the default colour source (sRGB / EDID).
6. **Save profile as…** exports the generated `.icc` (kept, shared, or attached
   to an issue).

Applying a profile is immediately live **and persistent**: KWin records it in
`~/.config/kwinoutputconfig.json` and re-applies it at login, so the app does
not need to run in the background.

## How it works

```
R/G/B brightness / contrast / gamma
        │  colour model (nvidia-settings ComputeGammaRampVal port)
        ▼
3×256 gamma ramps
        │  wrapped in an ICC display profile with a `vcgt` tag
        ▼
<output>.icc
        │  kscreen-doctor  (kde-output-management-v2)
        ▼
KWin applies the vcgt to the output — SDR (iccprofile) or HDR (hdrIccProfile)
```

See **[docs/how-it-works.md](docs/how-it-works.md)** for the details, and
**[docs/hdr.md](docs/hdr.md)** for why HDR needs a different profile.

## Limitations

- **Per-channel only.** A 1-D per-channel LUT cannot express *saturation*
  (Digital Vibrance) — that is a colour matrix, not a LUT. Use
  [nvibrant](https://github.com/Tremeschin/nvibrant) for saturation.
- **KWin-specific.** It drives KWin through `kscreen-doctor`; it is not a
  generic Wayland or X11 tool.
- **Not a measurement tool.** "Calibration" here means adjusting an existing
  display response by eye or by a target, not colorimeter profiling. If you have
  a colorimeter, generate a profiled ICC instead — this compliments that use
  case for HDR, where measurement tools are awkward.
- Screenshots and on-screen colour pickers capture the buffer *before* the
  adjustment, so they will not show the effect.

## Troubleshooting

Common issues (nothing happens on a channel, `kscreen-doctor` reports
`ICC profile: none`, HDR quirks, reverting) are covered in
**[docs/troubleshooting.md](docs/troubleshooting.md)**.

## Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

[GPL-3.0-or-later](LICENSE).

## Credits

- The colour model is a port of `ComputeGammaRampVal` from
  [nvidia-settings](https://github.com/NVIDIA/nvidia-settings)
  (`libXNVCtrlAttributes/NvCtrlAttributes.c`).
- Made to work with KWin's colour management, whose source was the reference for
  the ICC/`vcgt` and HDR handling.
