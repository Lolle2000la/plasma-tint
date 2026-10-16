# Contributing

Thanks for helping improve `plasma-tint`! This is a small project; issues and
pull requests are both welcome.

## Development setup

```sh
git clone https://github.com/Lolle2000la/plasma-tint
cd plasma-tint
python -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
```

`PySide6` is the only runtime dependency. The tests additionally use `pytest`
and `Pillow`, and load the system `liblcms2` (via `ctypes`) to validate the
generated ICC profiles the same way KWin does.

## Running the tests

```sh
pytest -q
```

The lcms2-based tests are skipped automatically if `liblcms2` isn't available
(on Debian/Ubuntu: `apt install liblcms2-2`). Please keep them passing.

## Running from source

```sh
PYTHONPATH=src python -m plasma_tint
```

## Code layout

See the table at the end of [docs/how-it-works.md](docs/how-it-works.md). In
short:

- `color/model.py` — colour maths (sliders → gamma ramps)
- `color/icc.py` — ICC profile authoring (`vcgt`, and the HDR `lumi`/`MHC2`)
- `apply/kscreen.py` — the `kscreen-doctor` backend
- `edid.py` — EDID HDR luminance
- `gui/` — the PySide6 interface

## Guidelines

- **Test on real hardware where possible.** A lot of this project is about
  matching what KWin actually does; please state your Plasma/KWin version and
  GPU when reporting or fixing behaviour.
- Keep the per-channel semantics identical to nvidia-settings
  (`ComputeGammaRampVal`); if you change the model, update the tests.
- If you touch ICC generation, add or extend a test that reads the profile back
  through lcms2.
- Format with `ruff format` / `ruff check` if you have it; otherwise match the
  existing style (4-space indent, type hints on public functions).
- New source files should carry `# SPDX-License-Identifier: GPL-3.0-or-later`.

## Commit / PR

- Keep commits focused and describe the *why*.
- Reference the issue a PR fixes.
- By contributing you agree your work is licensed under GPL-3.0-or-later.

## Reporting bugs

Please include:

- Plasma / KWin version (`plasmashell --version`, `kwin_wayland --version`)
- GPU and driver
- `kscreen-doctor -o`
- whether HDR was enabled, and the app's status-bar message
