# -*- coding: utf-8 -*-
"""
count_voxel.py

Run this FIRST on a freshly opened image before any pipeline steps.
Counts voxels inside RhCTX and BLA surfaces and prints to console.
"""

import ImarisLib
import Imaris

ROI_NAMES = ["RhCTX", "BLA"]


def count_voxels(app, roi_name):
    ds = app.GetDataSet()
    if ds is None:
        print(f"[error] No dataset open.")
        return -1

    scene = app.GetSurpassScene()
    for i in range(scene.GetNumberOfChildren()):
        child = scene.GetChild(i)
        if child is None:
            continue
        if child.GetName() == roi_name:
            surf = Imaris.ISurfacesPrx.checkedCast(child)
            if surf is None:
                print(f"[warn] '{roi_name}' found but could not cast to ISurfaces.")
                return -1
            sx, sy, sz = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ()
            min_x, max_x = ds.GetExtendMinX(), ds.GetExtendMaxX()
            min_y, max_y = ds.GetExtendMinY(), ds.GetExtendMaxY()
            min_z, max_z = ds.GetExtendMinZ(), ds.GetExtendMaxZ()
            print(f"[info] '{roi_name}' found. Computing mask on {sx}x{sy}x{sz} grid ...")
            mask_ds = surf.GetMask(min_x, min_y, min_z, max_x, max_y, max_z, sx, sy, sz, 0)
            total = 0
            for z in range(sz):
                plane = mask_ds.GetDataSubVolumeAs1DArrayBytes(0, 0, z, 0, 0, sx, sy, 1)
                total += sum(1 for v in plane if v > 0)
            print(f"[result] '{roi_name}' voxel count: {total}")
            return total

    print(f"[warn] Surface '{roi_name}' not found in scene.")
    return -1


def XT_Count_Voxels(aImarisApplicationID=0):
    lib = ImarisLib.ImarisLib()
    app = lib.GetApplication(aImarisApplicationID)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")

    print("\n" + "="*50)
    print("VOXEL COUNT — original dataset")
    print("="*50)
    for roi in ROI_NAMES:
        count_voxels(app, roi)
    print("="*50 + "\n")


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    obj_id = lib.GetServer().GetObjectID(0)
    XT_Count_Voxels(obj_id)
