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

## Building an AppImage

The release workflow and local builds share one implementation:

```sh
packaging/build-appimage.sh
```

It creates a throwaway venv under `build/appimage/`, runs PyInstaller, and
writes `dist/plasma-tint-<version>-<arch>.AppImage` plus the matching `.zsync`
delta-update file. `appimagetool` is downloaded on first use. Set `VERSION`,
`ARCH`, `PYTHON`, `OUTDIR` or `GITHUB_REPOSITORY` to override the defaults. You
need `python3`, `curl`, `zsyncmake` (package `zsync`) and network access; `uv` is
used for installs when available.

The AppImage bundles Python, PySide6 and the application. System libraries that
every Plasma desktop provides (glibc, libGL, fontconfig, Wayland/X11 client
libraries) and `kscreen-doctor` are deliberately not bundled.

## Releasing

1. Bump the version in `pyproject.toml` and `src/plasma_tint/__init__.py`
   (they must match) and move the changelog entries from `[Unreleased]` into a
   new section.
2. Commit, then tag and push:

   ```sh
   git tag v0.2.0
   git push origin main --tags
   ```

The `Release` workflow runs the tests, checks that the tag matches the project
version, builds the AppImage, and publishes it with a `SHA256SUMS` file.
Re-running an existing release is possible via *Actions → Release →
Run workflow* with the same version.

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
