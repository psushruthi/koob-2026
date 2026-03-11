# -*- coding: utf-8 -*-
"""
step2_preprocess.py

Step 2 of KOOB analysis pipeline (run BEFORE step3_coloc.py).

Preprocesses the masked channels in-place to remove background haze
and smooth signal before colocalization and surface detection.

Operates on:
  ch4 = DAPI_masked
  ch6 = NeuN_masked
  ch7 = GFAP_masked

Processing order per channel:
  1. SubtractBackgroundChannel  — rolling ball background removal
  2. GaussFilterChannel         — light smoothing to consolidate soma signal
"""

import ImarisLib
import sys

# ------------------------------------------------------------------ #
#  CONFIG — tune if needed
# ------------------------------------------------------------------ #

# DAPI — compact nuclear signal
DAPI_CH        = 4
DAPI_BG_RADIUS = 9.0   # microns — larger than a nucleus diameter
DAPI_GAUSS     = 0.3    # microns — light smoothing

# NeuN — compact nuclear/perinuclear signal
NEUN_CH        = 6
NEUN_BG_RADIUS = 9.0   # microns
NEUN_GAUSS     = 0.5    # microns

# GFAP — diffuse branching cytoskeletal signal
GFAP_CH        = 7
GFAP_BG_RADIUS = 15.0   # microns — larger to capture broad background under processes
GFAP_GAUSS     = 0.8   # microns — more smoothing to consolidate soma blob

# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _connect():
    lib = ImarisLib.ImarisLib()
    server = lib.GetServer()
    obj_id = server.GetObjectID(0)
    print(f"[connect] Using Imaris application ID: {obj_id}")
    app = lib.GetApplication(obj_id)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")
    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset open in Imaris.")
    print(f"[info] Dataset XYZCT=({ds.GetSizeX()},{ds.GetSizeY()},{ds.GetSizeZ()},{ds.GetSizeC()},{ds.GetSizeT()})")
    return app, ds


def _check_channel(ds, ch, label):
    sc = ds.GetSizeC()
    if ch >= sc:
        raise RuntimeError(
            f"Channel {ch} ({label}) does not exist — dataset only has {sc} channels. "
            f"Did you run mask_roi.py first?"
        )
    try:
        name = ds.GetChannelName(ch)
        print(f"[info] ch{ch} = '{name}' ✓")
    except Exception:
        print(f"[info] ch{ch} exists (name unavailable)")


def _preprocess_channel(image_proc, ds, ch, label, bg_radius, gauss_sigma):
    print(f"\n[preprocess] Processing ch{ch} '{label}' ...")

    print(f"[preprocess]   SubtractBackground radius={bg_radius} microns ...")
    try:
        image_proc.SubtractBackgroundChannel(ds, ch, bg_radius)
        print(f"[preprocess]   SubtractBackground done ✓")
    except Exception as e:
        print(f"[preprocess]   SubtractBackground failed: {e}")
        raise

    print(f"[preprocess]   GaussFilter sigma={gauss_sigma} microns ...")
    try:
        image_proc.GaussFilterChannel(ds, ch, gauss_sigma)
        print(f"[preprocess]   GaussFilter done ✓")
    except Exception as e:
        print(f"[preprocess]   GaussFilter failed: {e}")
        raise

    # print new intensity distribution after preprocessing
    sx, sy = ds.GetSizeX(), ds.GetSizeY()
    plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, 0, ch, 0, sx, sy, 1)
    nonzero = sorted([v for v in plane if v > 0])
    if nonzero:
        n = len(nonzero)
        p75 = nonzero[int(n*0.75)]
        p90 = nonzero[int(n*0.90)]
        p95 = nonzero[int(n*0.95)]
        p99 = nonzero[int(n*0.99)]
        print(f"[preprocess]   Post-processing distribution: nonzero={n}, p75={p75:.0f}, p90={p90:.0f}, p95={p95:.0f}, p99={p99:.0f}, max={nonzero[-1]:.0f}")
    else:
        print(f"[preprocess]   WARNING: no nonzero voxels after preprocessing — check parameters")


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def XT_Preprocess(aImarisApplicationID=0):
    app, ds = _connect()

    print("\n[info] Verifying channels ...")
    _check_channel(ds, DAPI_CH, "DAPI_masked")
    _check_channel(ds, NEUN_CH, "NeuN_masked")
    _check_channel(ds, GFAP_CH, "GFAP_masked")

    image_proc = app.GetImageProcessing()

    _preprocess_channel(image_proc, ds, DAPI_CH, "DAPI_masked", DAPI_BG_RADIUS, DAPI_GAUSS)
    _preprocess_channel(image_proc, ds, NEUN_CH, "NeuN_masked", NEUN_BG_RADIUS, NEUN_GAUSS)
    _preprocess_channel(image_proc, ds, GFAP_CH, "GFAP_masked", GFAP_BG_RADIUS, GFAP_GAUSS)

    print("\n" + "="*50)
    print("PREPROCESSING COMPLETE")
    print("="*50)
    print("  ch4 DAPI_masked  — background subtracted + smoothed")
    print("  ch6 NeuN_masked  — background subtracted + smoothed")
    print("  ch7 GFAP_masked  — background subtracted + smoothed")
    print("="*50)
    print("[next] Run step3_coloc.py next.")
    print("[note] Post-processing distributions printed above —")
    print("       use those values to set thresholds in step3_coloc.py")


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    server = lib.GetServer()
    obj_id = server.GetObjectID(0)
    print(f"[connect] Using Imaris application ID: {obj_id}")
    XT_Preprocess(obj_id)
