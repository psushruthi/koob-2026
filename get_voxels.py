# -*- coding: utf-8 -*-
"""
get_roi_area.py

Gets the true volume (µm³) and voxel count of the RhCTX and BLA ROI surfaces
directly from Imaris surface statistics.
Run this on any open .ims file that has the ROI surfaces drawn.
"""

import ImarisLib
import Imaris

ROI_NAMES = ["RhCTX", "BLA"]


def get_roi_stats(aImarisApplicationID=0):
    lib = ImarisLib.ImarisLib()
    app = lib.GetApplication(aImarisApplicationID)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")

    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset open in Imaris.")

    scene = app.GetSurpassScene()

    print("=" * 50)
    print("ROI STATISTICS")
    print("=" * 50)

    for roi_name in ROI_NAMES:
        print(f"\n[ROI] '{roi_name}'")

        # find the surface in the scene
        surf = None
        for i in range(scene.GetNumberOfChildren()):
            child = scene.GetChild(i)
            if child is None:
                continue
            if child.GetName() == roi_name:
                surf = Imaris.ISurfacesPrx.checkedCast(child)
                break

        if surf is None:
            print(f"  Not found in scene — skipping")
            continue

        # --- Method 1: Volume from Imaris surface statistics (sum all surfaces) ---
        try:
            stats = surf.GetStatistics()
            total_volume = 0.0
            volume_count = 0
            for j, name in enumerate(stats.mNames):
                if "Volume" in name:
                    total_volume += stats.mValues[j]
                    volume_count += 1
            print(f"  Number of surfaces:  {volume_count}")
            print(f"  Volume (Imaris):     {total_volume:,.2f} µm³")
        except Exception as e:
            print(f"  Could not read surface statistics: {e}")

        # --- Debug: print all stat names and values (uncomment if needed) ---
        # try:
        #     stats = surf.GetStatistics()
        #     for j, name in enumerate(stats.mNames):
        #         print(f"  {name}  =  {stats.mValues[j]}")
        # except Exception as e:
        #     print(f"  Could not read raw statistics: {e}")

        # --- Method 2: Voxel count from GetMask ---
        try:
            sx, sy, sz = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ()
            min_x, max_x = ds.GetExtendMinX(), ds.GetExtendMaxX()
            min_y, max_y = ds.GetExtendMinY(), ds.GetExtendMaxY()
            min_z, max_z = ds.GetExtendMinZ(), ds.GetExtendMaxZ()

            mask_ds = surf.GetMask(
                min_x, min_y, min_z,
                max_x, max_y, max_z,
                sx, sy, sz, 0
            )

            voxel_count = 0
            for z in range(sz):
                plane = mask_ds.GetDataSubVolumeAs1DArrayBytes(0, 0, z, 0, 0, sx, sy, 1)
                voxel_count += sum(1 for v in plane if v > 0)

            vox_x = (max_x - min_x) / sx
            vox_y = (max_y - min_y) / sy
            vox_z = (max_z - min_z) / sz
            voxel_vol = vox_x * vox_y * vox_z
            total_vol = voxel_count * voxel_vol

            print(f"  Voxel count:         {voxel_count:,}")
            print(f"  Voxel size:          {vox_x:.4f} x {vox_y:.4f} x {vox_z:.4f} µm")
            print(f"  Volume (from voxels):{total_vol:,.2f} µm³")

        except Exception as e:
            print(f"  Could not compute voxel-based volume: {e}")

    print("\n" + "=" * 50)
    print("[done] get_roi_area.py complete.")


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    obj_id = lib.GetServer().GetObjectID(0)
    get_roi_stats(obj_id)
