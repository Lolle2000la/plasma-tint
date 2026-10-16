# Troubleshooting

## Only my first adjustment did anything

This was a real bug in early builds and is **fixed**: because libkscreen treats
an unchanged ICC path as a no-op, re-writing the same filename meant KWin never
re-read the file after the first apply. `plasma-tint` now writes each revision to
a content-hashed filename, so every change is a real path change.

Make sure you are on the latest version. If it still happens, please open an
issue with the output of `kscreen-doctor -o`.

## `kscreen-doctor -o` says `ICC profile: none` / `source: sRGB`

That is the **SDR** slot. The HDR profile lives in the **HDR** slot
(`hdrIccProfile` / `hdrColorProfileSource`) and is not shown by those lines.
Check the persisted config instead:

```sh
python3 - <<'PY'
import json, os
cfg = os.path.expanduser("~/.config/kwinoutputconfig.json")
for entry in json.load(open(cfg)):
    if entry.get("name") == "outputs":
        for o in entry["data"]:
            if o.get("hdrIccProfilePath"):
                print(o["connectorName"], o["hdrIccProfilePath"],
                      o.get("hdrColorProfileSource"), os.path.exists(o["hdrIccProfilePath"]))
PY
```

## Nothing happens at all

- Is a **display selected** in the dropdown? The status bar says
  "No output selected" if not.
- Is `kscreen-doctor` installed and working? `kscreen-doctor -o` should list
  your outputs. If not, install `kscreen`/`kscreen-doctor`.
- For HDR, is **HDR enabled** on that output? The profile only applies in HDR.
- Are you running the app **inside your Plasma session** (`WAYLAND_DISPLAY` set)?

## The image warped / went dark after applying in HDR

You applied an **SDR** profile to the HDR slot (or moved/replaced the file KWin
is pointing at). Untick nothing — instead press **Revert**, then re-open the app
and **Apply** with **"Apply as HDR profile"** ticked. See [hdr.md](hdr.md).

## How do I undo everything?

- In the app: **Revert** restores the default colour source for the selected
  output (sRGB/EDID).
- From a shell:

  ```sh
  # SDR
  kscreen-doctor output.DP-2.colorProfileSource.sRGB output.DP-2.iccprofile.
  # HDR
  kscreen-doctor output.DP-2.hdrColorProfileSource.EDID output.DP-2.hdrIccProfile.
  ```

## Screenshots / a colour picker don't show the change

Expected. The `vcgt` is applied at the CRTC/ICC stage, after the composited
buffer that screenshots capture. Use the neutral **On-screen pattern** tab and
your eyes (or a colorimeter).

## I want to make the correction stronger / weaker in fine steps

Use the **spin boxes** next to each slider — you can type exact values and step
precisely (gamma steps are adaptive around 1.0).

## Digital Vibrance / saturation does nothing

A per-channel 1-D LUT cannot change saturation — that needs a colour matrix, not
a LUT. Use [nvibrant](https://github.com/Tremeschin/nvibrant) for Digital
Vibrance; `plasma-tint` handles per-channel level/gamma.

## The generated profiles clutter my ICC directory

They live in `$XDG_DATA_HOME/color/icc/plasma-tint/` and are pruned: each new
apply deletes superseded revisions for that output. Only the currently-referenced
file (plus any you exported) remains.
