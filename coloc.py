# -*- coding: utf-8 -*-
"""
step2_coloc.py

Step 2 of KOOB analysis pipeline.

Builds two binary AND colocalization channels from the masked channels
produced by mask_roi.py:
  ch8 = NeuN x DAPI  (binary mask, 65535 where both above threshold)
  ch9 = GFAP x DAPI  (binary mask, 65535 where both above threshold)

These channels will be used by step3_surfaces.py for cell detection.

Input channels (from mask_roi.py):
  ch4 = DAPI_masked
  ch6 = NeuN_masked
  ch7 = GFAP_masked

Thresholds — tune at the top if results look wrong:
  THR_DAPI = 0   (p90 of DAPI_masked distribution)
  THR_NEUN = 8000  (between p75-p90 of NeuN_masked — permissive, DAPI gates)
  THR_GFAP = 10000  (just above p75 of GFAP_masked — permissive, DAPI gates)
"""

import ImarisLib
import Imaris
import array
import sys

# ------------------------------------------------------------------ #
#  CONFIG — tune these if results look over/under-segmented
# ------------------------------------------------------------------ #

CH_DAPI = 4   # DAPI_masked
CH_NEUN = 6   # NeuN_masked
CH_GFAP = 7   # GFAP_masked

THR_DAPI = 0.0
THR_NEUN = 4000.0
THR_GFAP = 8000.0

OUT_NEUN_NAME  = "NeuN_DAPI_coloc"
OUT_GFAP_NAME  = "GFAP_DAPI_coloc"
COLOR_NEUN     = 0xFF6600FF   # orange — distinct from raw red NeuN
COLOR_GFAP     = 0x00FF88FF   # mint green — distinct from raw yellow GFAP

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


def _grow_channels(app, ds, extra):
    """Add `extra` new channels. Falls back to new dataset if in-place grow fails."""
    sc = ds.GetSizeC()
    target = sc + extra
    try:
        ds.SetSizeC(target)
        if ds.GetSizeC() == target:
            print(f"[grow] In-place grow succeeded, C={target}")
            return ds, sc
    except Exception as e:
        print(f"[grow] In-place SetSizeC failed: {e}")

    print(f"[grow] Fallback: building new dataset with C={target}")
    sx, sy, sz, st = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ(), ds.GetSizeT()
    factory = app.GetFactory()
    ds2 = factory.CreateDataSet()
    ds2.Create(Imaris.tType.eTypeUInt16, sx, sy, sz, target, st)

    for axis in ("X", "Y", "Z"):
        try:
            getattr(ds2, f"SetExtendMin{axis}")(getattr(ds, f"GetExtendMin{axis}")())
            getattr(ds2, f"SetExtendMax{axis}")(getattr(ds, f"GetExtendMax{axis}")())
        except Exception:
            pass

    for c in range(sc):
        try: ds2.SetChannelName(c, ds.GetChannelName(c))
        except Exception: pass
        try: ds2.SetChannelColorRGBA(c, ds.GetChannelColorRGBA(c))
        except Exception: pass
        for t in range(st):
            for z in range(sz):
                plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, c, t, sx, sy, 1)
                ds2.SetDataSubVolumeAs1DArrayFloats(plane, 0, 0, z, c, t, sx, sy, 1)
        try:    nm = ds.GetChannelName(c)
        except: nm = f"ch{c}"
        print(f"[grow] copied ch{c} ({nm})")

    app.SetDataSet(ds2)
    print(f"[grow] Switched to target-C dataset, C={ds2.GetSizeC()}")
    return ds2, sc


def _write_binary_coloc(ds, ch_a, thr_a, ch_b, thr_b, out_ch, name, color):
    """
    Binary AND mask: out[i] = 65535 if a[i]>=thr_a AND b[i]>=thr_b, else 0.
    Writes into pre-allocated out_ch.
    """
    sx, sy, sz, st = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ(), ds.GetSizeT()
    plane_size = sx * sy
    total_true = 0
    named = False

    print(f"[coloc] Building '{name}': ch{ch_a}(thr={thr_a}) AND ch{ch_b}(thr={thr_b}) -> ch{out_ch}")

    for t in range(st):
        for z in range(sz):
            a = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, ch_a, t, sx, sy, 1)
            b = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, ch_b, t, sx, sy, 1)
            out = array.array('H', [0] * plane_size)
            cnt = 0
            for i in range(plane_size):
                if a[i] >= thr_a and b[i] >= thr_b:
                    out[i] = 65535
                    cnt += 1
            total_true += cnt
            ds.SetDataSubVolumeAs1DArrayShorts(out, 0, 0, z, out_ch, t, sx, sy, 1)

            if not named:
                try: ds.SetChannelName(out_ch, name)
                except Exception: pass
                try: ds.SetChannelColorRGBA(out_ch, color)
                except Exception: pass
                named = True

    total = plane_size * sz * st
    print(f"[coloc] '{name}' -> ch{out_ch}: true voxels={total_true} / {total} ({100.0*total_true/total:.4f}%)")


def _print_coloc_summary(ds, out_neun, out_gfap):
    print("\n" + "="*50)
    print("COLOCALIZATION SUMMARY")
    print("="*50)
    for ch, label in [(out_neun, OUT_NEUN_NAME), (out_gfap, OUT_GFAP_NAME)]:
        try:
            name = ds.GetChannelName(ch)
            print(f"  ch{ch} '{name}' created ✓")
        except Exception:
            print(f"  ch{ch} '{label}' created ✓")
    print(f"\n  Thresholds used:")
    print(f"    DAPI >= {THR_DAPI}")
    print(f"    NeuN >= {THR_NEUN}")
    print(f"    GFAP >= {THR_GFAP}")
    print("="*50)
    print("[next] Run step3_surfaces.py next.")


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def XT_Build_Coloc(aImarisApplicationID=0):
    app, ds = _connect()

    # verify input channels exist
    print("\n[info] Verifying input channels ...")
    _check_channel(ds, CH_DAPI, "DAPI_masked")
    _check_channel(ds, CH_NEUN, "NeuN_masked")
    _check_channel(ds, CH_GFAP, "GFAP_masked")

    # grow dataset by 2 channels
    ds, start_out = _grow_channels(app, ds, extra=2)
    out_neun = start_out       # ch8
    out_gfap = start_out + 1   # ch9
    print(f"\n[info] Output indices: {OUT_NEUN_NAME}->ch{out_neun}, {OUT_GFAP_NAME}->ch{out_gfap}")

    # build coloc channels
    _write_binary_coloc(ds, CH_NEUN, THR_NEUN, CH_DAPI, THR_DAPI, out_neun, OUT_NEUN_NAME, COLOR_NEUN)
    _write_binary_coloc(ds, CH_GFAP, THR_GFAP, CH_DAPI, THR_DAPI, out_gfap, OUT_GFAP_NAME, COLOR_GFAP)

    _print_coloc_summary(ds, out_neun, out_gfap)


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    server = lib.GetServer()
    obj_id = server.GetObjectID(0)
    print(f"[connect] Using Imaris application ID: {obj_id}")
    XT_Build_Coloc(obj_id)
