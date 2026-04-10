# -*- coding: utf-8 -*-
"""
coloc.py

Step 2 of KOOB 2026 pipeline.

Builds binary colocalization channels using Constant Value (65535).
A voxel is set to 65535 if it meets ALL threshold criteria, otherwise 0.

Input channels (must exist after mask_roi.py):
  ch4 = DAPI_masked
  ch6 = NeuN_masked
  ch7 = GFAP_masked

Output channels appended to dataset:
  ch8  = NeuN_DAPI_coloc  (NeuN >= THR_NEUN AND DAPI >= THR_DAPI)
  ch9  = GFAP_DAPI_coloc  (GFAP >= THR_GFAP AND DAPI >= THR_DAPI)
"""

import ImarisLib
import Imaris
import array
import sys

CH_DAPI = 4
CH_NEUN = 6
CH_GFAP = 7

THR_DAPI = 25
THR_NEUN = 250.0
THR_GFAP = 2000.0

OUT_NEUN_NAME = "NeuN_DAPI_coloc"
OUT_GFAP_NAME = "GFAP_DAPI_coloc"
COLOR_NEUN    = 0xFF6600FF
COLOR_GFAP    = 0x00FF88FF


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
        try:
            ds2.SetChannelName(c, ds.GetChannelName(c))
        except Exception:
            pass
        try:
            ds2.SetChannelColorRGBA(c, ds.GetChannelColorRGBA(c))
        except Exception:
            pass
        for t in range(st):
            for z in range(sz):
                plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, c, t, sx, sy, 1)
                ds2.SetDataSubVolumeAs1DArrayFloats(plane, 0, 0, z, c, t, sx, sy, 1)
        try:
            nm = ds.GetChannelName(c)
        except Exception:
            nm = f"ch{c}"
        print(f"[grow] copied ch{c} ({nm})")

    app.SetDataSet(ds2)
    print(f"[grow] Switched to target-C dataset, C={ds2.GetSizeC()}")
    return ds2, sc


def _write_constant_coloc(ds, ch_marker, thr_marker, ch_dapi, thr_dapi, out_ch, name, color):
    """
    Write colocalization channel using Constant Value (65535).
    A voxel is set to 65535 if:
      - marker channel >= thr_marker
      - DAPI channel   >= thr_dapi
    Otherwise 0.
    """
    sx, sy, sz, st = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ(), ds.GetSizeT()
    plane_size = sx * sy
    total_true = 0
    named = False

    print(f"[coloc] Building '{name}': ch{ch_marker}(thr={thr_marker}) AND ch{ch_dapi}(thr={thr_dapi}) -> ch{out_ch}")

    for t in range(st):
        for z in range(sz):
            marker = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, ch_marker, t, sx, sy, 1)
            dapi   = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, ch_dapi,   t, sx, sy, 1)
            out = array.array('H', [0] * plane_size)
            cnt = 0
            for i in range(plane_size):
                if marker[i] >= thr_marker and dapi[i] >= thr_dapi:
                    out[i] = 65535
                    cnt += 1
            total_true += cnt
            ds.SetDataSubVolumeAs1DArrayShorts(out, 0, 0, z, out_ch, t, sx, sy, 1)

            if not named:
                try:
                    ds.SetChannelName(out_ch, name)
                except Exception:
                    pass
                try:
                    ds.SetChannelColorRGBA(out_ch, color)
                except Exception:
                    pass
                named = True

    total = plane_size * sz * st
    print(f"[coloc] '{name}' -> ch{out_ch}: true voxels={total_true} / {total} ({100.0 * total_true / total:.4f}%)")


def XT_Build_Coloc(aImarisApplicationID=0):
    app, ds = _connect()

    print("\n[info] Verifying input channels ...")
    _check_channel(ds, CH_DAPI, "DAPI_masked")
    _check_channel(ds, CH_NEUN, "NeuN_masked")
    _check_channel(ds, CH_GFAP, "GFAP_masked")

    ds, start_out = _grow_channels(app, ds, extra=2)
    out_neun = start_out
    out_gfap = start_out + 1
    print(f"\n[info] Output indices: {OUT_NEUN_NAME}->ch{out_neun}, {OUT_GFAP_NAME}->ch{out_gfap}")

    _write_constant_coloc(ds, CH_NEUN, THR_NEUN, CH_DAPI, THR_DAPI, out_neun, OUT_NEUN_NAME, COLOR_NEUN)
    _write_constant_coloc(ds, CH_GFAP, THR_GFAP, CH_DAPI, THR_DAPI, out_gfap, OUT_GFAP_NAME, COLOR_GFAP)

    print("\n" + "=" * 50)
    print("COLOCALIZATION SUMMARY")
    print("=" * 50)
    print(f"  Method:         Constant Value (65535)")
    print(f"  THR_DAPI  >= {THR_DAPI}")
    print(f"  THR_NEUN  >= {THR_NEUN}")
    print(f"  THR_GFAP  >= {THR_GFAP}")
    print("=" * 50)


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    obj_id = lib.GetServer().GetObjectID(0)
    XT_Build_Coloc(obj_id)
