# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.1.1] - 2026-10-24

### Added

- Release workflow that builds a self-contained x86_64 AppImage and attaches it
  (with SHA-256 checksums) to tagged GitHub releases.

### Fixed

- The AppImage no longer leaks PyInstaller's bundled library directory into
  `kscreen-doctor` via `LD_LIBRARY_PATH`, which made it load the bundled Qt and
  fail; displays and the active profile are detected again.

## [0.1.0]

Initial release.

### Added

- Per-channel **Red / Green / Blue × Brightness / Contrast / Gamma** adjustment,
  using the nvidia-settings `ComputeGammaRampVal` parameterisation.
- ICC v2.4 display profile generation with a `vcgt` calibration tag.
- Correct **HDR** profile for KWin's `hdrIccProfile` slot: BT.2020 primaries, a
  `lumi` tag (peak luminance read from EDID) and a minimal identity `MHC2` tag
  with no LUT, so KWin's own PQ encoder is used and the `vcgt` is preserved.
- Application through `kscreen-doctor` (`kde-output-management-v2`); live and
  persistent.
- Content-hashed profile filenames so KWin always reloads on change.
- PySide6 GUI with live preview, synced spin boxes for precise entry, a neutral
  test pattern and a simulated preview.
- `Revert` to restore the default colour source; `Save profile as…` to export an
  `.icc`.

[Unreleased]: https://github.com/Lolle2000la/plasma-tint/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Lolle2000la/plasma-tint/releases/tag/v0.1.1
[0.1.0]: https://github.com/Lolle2000la/plasma-tint/releases/tag/v0.1.0
