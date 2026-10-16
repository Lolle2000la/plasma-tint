# FAQ

### Is this a display calibration tool?

No — and the word is avoided on purpose. "Calibration" usually implies a
colorimeter and a measured profile (DisplayCAL, Argyll, hardware LUTs).
`plasma-tint` is a **per-channel colour adjustment**: you set red/green/blue
brightness, contrast and gamma, and it applies them through an ICC `vcgt`. It is
the Linux/HDR answer to the NVIDIA Control Panel's "Adjust desktop color
settings".

If you *do* have a colorimeter, generate a measured profile instead — but note
that HDR measurement is awkward, which is exactly where a light adjustment like
this is useful.

### Why is it KDE-only?

Because the correct, supported way to apply a per-display ICC profile on KDE is
the `kde-output-management-v2` protocol (`kscreen-doctor`), and KWin is the only
compositor that (since 6.7) applies a profile's `vcgt` **in HDR**. On other
compositors there is no comparable mechanism to drive.

### Does it survive a reboot?

Yes. KWin stores the applied profile path in `~/.config/kwinoutputconfig.json`
and re-applies it at login. The app does **not** need to keep running.

### Can I use it on X11 or on GNOME/Hyprland/etc.?

Not currently. It is built around KWin's colour management via
`kscreen-doctor`.

### Can it change colour temperature or saturation?

- **Saturation (Digital Vibrance):** no — that is a colour matrix; a per-channel
  LUT can't express it. Use [nvibrant](https://github.com/Tremeschin/nvibrant).
- **Colour temperature:** you can approximate a warm/cool shift with per-channel
  brightness, but it is not a proper white-point control.

### How is this different from nvibrant?

[nvibrant](https://github.com/Tremeschin/nvibrant) sets **Digital Vibrance** and
**dithering** by calling the NVIDIA driver directly (nvkms ioctls), which is
great for saturation. It exposes no per-channel controls and — crucially for HDR
— no per-channel calibration. `plasma-tint` is complementary: per-channel
level/gamma via KWin's colour management, working in HDR.

### Do I need an NVIDIA GPU?

No. The colour model mirrors nvidia-settings' parameterisation, but the profile
and the apply path have **no NVIDIA dependency** — the GPU/vendor is irrelevant;
only KWin matters.

### Multiple monitors?

Yes. Each output gets its own profile. Pick the output in the dropdown and apply;
KWin persists per-output.

### Where are my settings and profiles stored?

- Slider values: `~/.config/plasma-tint/settings.json`
- Generated ICC profiles: `$XDG_DATA_HOME/color/icc/plasma-tint/` (usually
  `~/.local/share/color/icc/plasma-tint/`)
