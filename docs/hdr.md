# HDR

HDR is the reason this tool exists, and it needs a genuinely different profile.
An SDR profile placed in KWin's HDR slot will visibly wreck the image. Here is
why, and what `plasma-tint` does instead.

## Why an SDR profile breaks HDR

KWin uses the profile in the **HDR slot** as the *description of the display
while it is in HDR*. In `DrmOutput::createColorDescription()` (KWin 6.8) it
hardcodes the content space and pulls everything else from the profile:

```cpp
nativeColorimetry = iccProfile->colorimetry();          // the display's gamut
if (effectiveHdr) {
    if (effectiveWcg) containerColorimetry = Colorimetry::BT2020;   // content
    maxAverageLuminance = iccProfile->maxFALL().value_or(200);      // no lumi -> 200
    maxLuminance        = iccProfile->maxCLL().value_or(maxAverageLuminance);
    transferFunction    = TransferFunction(gamma22, ...);
}
```

So an sRGB profile (Rec.709 primaries, sRGB TRC, no `lumi`) causes three faults
at once, which together look like "oversaturated and crushed to near-black":

1. the display is wrongly declared **Rec.709** while the HDR content is
   **BT.2020** → a gamut warp;
2. the **sRGB transfer function** is used where an HDR (PQ) encoding is needed;
3. with no `lumi` tag, KWin assumes the display peaks at **200 nits** → dimming.

## The HDR profile

`build_hdr_profile()` produces a profile shaped for KWin's HDR path:

- **BT.2020 / D65 primaries** (`chrm` and colorants), matching KWin's
  `Colorimetry::BT2020` exactly, so BT.2020 content maps one-to-one;
- a **`lumi` tag** whose `Y` is the display's peak frame-average luminance,
  read from the EDID (CTA-861 HDR static metadata);
- a minimal **`MHC2` tag** with an **identity matrix** and **`lutSize = 0`**;
- the same **`vcgt`** per-channel ramp;
- linear `rTRC/gTRC/bTRC` — unused on the MHC2 path, but present so KWin accepts
  the profile (it always parses the TRCs).

### Why MHC2 with no LUT

KWin checks for an `MHC2` tag and, when present, encodes to the wire itself with
its own exact PQ transfer function:

```cpp
if (iccProfile->hasMHC2Tag()) {
    colorPipeline.addMatrix(... iccProfile->mhc2Matrix() ...);
    colorPipeline.addInverseTransferFunction(TransferFunction(PQ, 0, 10'000), ...);
} else {
    colorPipeline.addMultiplier(1.0 / maxLuminance);
    colorPipeline.add1DLUT(iccProfile->inverseTransferFunction(), ...);
}
if (iccProfile->vcgt()) { colorPipeline.add1DLUT(iccProfile->vcgt(), ...); }
```

Two consequences:

- letting KWin do the PQ encoding avoids having to synthesise a PQ shaper
  ourselves (the `else` branch would require `TRC = min(PQ(x)/peak, 1)` to be
  exactly right);
- **but** if the `MHC2` tag carries per-channel curves, KWin *replaces* the
  `vcgt` with them. Hence `lutSize = 0` — the tag supplies the (identity) matrix
  and luminance only, and our `vcgt` survives.

## Things to know

- **HDR must be on** for the HDR profile to apply. It is an HDR-slot profile.
- **SDR white point:** in the ICC-HDR path KWin derives its SDR-white reference
  from `lumi × brightness` rather than from your SDR-white setting, so SDR
  content while HDR is on may look brighter than before. That is a KWin
  behaviour; adjust with the SDR-brightness slider if needed.
- **`lumi` comes from EDID.** If your display reports nothing useful, the profile
  falls back to a default peak. You can still export and adjust.
- To also correct SDR, untick "Apply as HDR profile" and Apply — that writes to
  the SDR slot, which uses the sRGB profile.
