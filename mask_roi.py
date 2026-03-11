# -*- coding: utf-8 -*-
"""
mask_roi.py

Step 1 of KOOB analysis pipeline.

Finds the surface named "Entorhinal CTX / BLA" in the Surpass scene,
extracts its binary voxel mask, clones the dataset, and writes 4 new
masked channels (one per original channel), zeroing out all voxels
outside the ROI.

Input channels (0-based API index):
  ch0 = DAPI
  ch1 = thr231 (tau)
  ch2 = NeuN
  ch3 = GFAP

Output channels appended to cloned dataset:
  ch4 = DAPI   (masked to ROI)
  ch5 = tau    (masked to ROI)
  ch6 = NeuN   (masked to ROI)
  ch7 = GFAP   (masked to ROI)
"""

import ImarisLib
import Imaris
import array
import sys

ROI_NAME = "Entorhinal CTX / BLA"

# ---- channel indices (0-based) ----
CH_DAPI = 0
CH_TAU  = 1
CH_NEUN = 2
CH_GFAP = 3

CHANNELS_TO_MASK = [CH_DAPI, CH_TAU, CH_NEUN, CH_GFAP]
CHANNEL_LABELS   = ["DAPI_masked", "tau_masked", "NeuN_masked", "GFAP_masked"]


# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #

def _find_roi_surface(app, name):
    """Walk the Surpass scene and return the ISurfaces object matching name."""
    scene = app.GetSurpassScene()
    n = scene.GetNumberOfChildren()
    print(f"[roi] Surpass scene has {n} children")
    for i in range(n):
        child = scene.GetChild(i)
        if child is None:
            print(f"[roi]   [{i}] None — skipping")
            continue
        child_name = child.GetName()
        print(f"[roi]   [{i}] '{child_name}'")
        if child_name == name:
            surf = Imaris.ISurfacesPrx.checkedCast(child)
            if surf is not None:
                print(f"[roi] Found ROI surface: '{name}' at index {i}")
                return surf
            else:
                print(f"[roi] WARNING: name matched but could not cast to ISurfaces")
    return None

def _get_roi_mask(roi_surf, ds):
    """
    Extract flat binary mask from ISurfaces object using GetMask.
    Returns a flat list of length sx*sy*sz where >0 = inside ROI.
    """
    sx = ds.GetSizeX()
    sy = ds.GetSizeY()
    sz = ds.GetSizeZ()

    min_x = ds.GetExtendMinX()
    min_y = ds.GetExtendMinY()
    min_z = ds.GetExtendMinZ()
    max_x = ds.GetExtendMaxX()
    max_y = ds.GetExtendMaxY()
    max_z = ds.GetExtendMaxZ()

    print(f"[mask] Physical extents: X[{min_x:.4f},{max_x:.4f}] Y[{min_y:.4f},{max_y:.4f}] Z[{min_z:.4f},{max_z:.4f}]")
    print(f"[mask] Voxel grid: ({sx},{sy},{sz})")
    print(f"[mask] Calling GetMask ...")

    mask_ds = roi_surf.GetMask(min_x, min_y, min_z, max_x, max_y, max_z, sx, sy, sz, 0)

    print(f"[mask] Reading mask dataset ...")
    mask = []
    for z in range(sz):
        plane = mask_ds.GetDataSubVolumeAs1DArrayBytes(0, 0, z, 0, 0, sx, sy, 1)
        mask.extend(plane)

    total_inside = sum(1 for v in mask if v > 0)
    total = sx * sy * sz
    print(f"[mask] ROI voxels inside: {total_inside} / {total} ({100.0*total_inside/total:.2f}%)")
    return mask, sx, sy, sz

def _clone_dataset(app, ds):
    """Clone dataset with identical XYZCT, copy all channels, switch app to clone."""
    sx, sy, sz = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ()
    sc, st     = ds.GetSizeC(), ds.GetSizeT()
    print(f"[clone] Cloning dataset XYZCT=({sx},{sy},{sz},{sc},{st}) ...")

    factory = app.GetFactory()
    clone = factory.CreateDataSet()
    clone.Create(Imaris.tType.eTypeUInt16, sx, sy, sz, sc, st)

    # spatial extents
    for axis in ("X", "Y", "Z"):
        try:
            getattr(clone, f"SetExtendMin{axis}")(getattr(ds, f"GetExtendMin{axis}")())
            getattr(clone, f"SetExtendMax{axis}")(getattr(ds, f"GetExtendMax{axis}")())
        except Exception as e:
            print(f"[clone] SetExtend*{axis} skipped: {e}")

    # copy all channels
    for c in range(sc):
        try: clone.SetChannelName(c, ds.GetChannelName(c))
        except Exception: pass
        try: clone.SetChannelColorRGBA(c, ds.GetChannelColorRGBA(c))
        except Exception: pass
        for t in range(st):
            for z in range(sz):
                plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, c, t, sx, sy, 1)
                clone.SetDataSubVolumeAs1DArrayFloats(plane, 0, 0, z, c, t, sx, sy, 1)
        try:
            nm = ds.GetChannelName(c)
        except Exception:
            nm = f"ch{c}"
        print(f"[clone] copied ch{c} ({nm})")

    app.SetDataSet(clone)
    print(f"[clone] Switched app to cloned dataset")
    return clone


def _grow_channels(app, ds, extra):
    """
    Grow dataset by `extra` channels.
    Falls back to a new dataset if in-place SetSizeC doesn't stick.
    Returns (dataset, first_new_index).
    """
    sc = ds.GetSizeC()
    target = sc + extra
    try:
        ds.SetSizeC(target)
        if ds.GetSizeC() == target:
            print(f"[grow] In-place grow succeeded, C={target}")
            return ds, sc
    except Exception as e:
        print(f"[grow] In-place SetSizeC failed: {e}")

    # fallback: build new dataset with target C, copy existing channels
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

    app.SetDataSet(ds2)
    print(f"[grow] Switched to target-C dataset, C={ds2.GetSizeC()}")
    return ds2, sc


def _write_masked_channel(ds, src_ch, out_ch, mask, label, sx, sy, sz):
    """
    For each plane: multiply raw channel by ROI mask (0 outside, keep inside).
    Writes result as UInt16 into out_ch.
    """
    st = ds.GetSizeT()
    plane_size = sx * sy
    named = False
    total_kept = 0

    for t in range(st):
        for z in range(sz):
            raw = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, src_ch, t, sx, sy, 1)
            out = array.array('H', [0] * plane_size)
            kept = 0
            for i in range(plane_size):
                if mask[i] > 0:
                    v = raw[i]
                    # clamp to UInt16 range
                    out[i] = 0 if v < 0 else (65535 if v > 65535 else int(v))
                    kept += 1
            total_kept += kept
            ds.SetDataSubVolumeAs1DArrayShorts(out, 0, 0, z, out_ch, t, sx, sy, 1)

            if not named:
                try: ds.SetChannelName(out_ch, label)
                except Exception: pass
                # keep same color as source channel
                try: ds.SetChannelColorRGBA(out_ch, ds.GetChannelColorRGBA(src_ch))
                except Exception: pass
                named = True

    print(f"[masked] ch{src_ch} -> ch{out_ch} '{label}': kept {total_kept} voxels inside ROI")


# ------------------------------------------------------------------ #
#  Main
# ------------------------------------------------------------------ #

def XT_Mask_ROI(aImarisApplicationID=0):
    lib = ImarisLib.ImarisLib()
    app = lib.GetApplication(aImarisApplicationID)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")

    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset open in Imaris.")

    print(f"[info] Dataset XYZCT=({ds.GetSizeX()},{ds.GetSizeY()},{ds.GetSizeZ()},{ds.GetSizeC()},{ds.GetSizeT()})")

    # 1) Find ROI surface
    roi_surf = _find_roi_surface(app, ROI_NAME)
    if roi_surf is None:
        raise RuntimeError(f"Could not find a surface named '{ROI_NAME}' in the Surpass scene.")

    # 2) Extract mask BEFORE cloning (mask is geometry-based, survives dataset swap)
    mask, sx, sy, sz = _get_roi_mask(roi_surf, ds)

    # 3) Clone dataset and switch app
    ds = _clone_dataset(app, ds)

    # 4) Grow by 4 channels (masked ch0-3)
    ds, start_out = _grow_channels(app, ds, extra=4)
    out_indices = [start_out + i for i in range(4)]
    print(f"[info] Output channel indices: {list(zip(CHANNEL_LABELS, out_indices))}")

    # 5) Write masked channels
    for i, src_ch in enumerate(CHANNELS_TO_MASK):
        _write_masked_channel(ds, src_ch, out_indices[i], mask, CHANNEL_LABELS[i], sx, sy, sz)

    print("[done] mask_roi.py complete.")
    print(f"[done] Masked channels written at indices: {out_indices}")
    print("[done] ch4=DAPI_masked  ch5=tau_masked  ch6=NeuN_masked  ch7=GFAP_masked")
    print("[next] Run step2_coloc.py next.")

if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    server = lib.GetServer()
    obj_id = server.GetObjectID(0)
    print(f"[connect] Using Imaris application ID: {obj_id}")
    XT_Mask_ROI(obj_id)
