# -*- coding: utf-8 -*-
import ImarisLib
import Imaris
import sys

NEUN_CHANNEL       = 8
NEUN_SMOOTH_WIDTH  = 0.7
NEUN_BG_WIDTH      = 150.0
NEUN_THRESHOLD     = 2500.0
NEUN_MIN_VOLUME    = 25.0    # µm³ — remove small spurious NeuN detections
NEUN_NAME          = "NeuN Surfaces"

GFAP_CHANNEL       = 9
GFAP_SMOOTH_WIDTH  = 1.5
GFAP_BG_WIDTH      = 150.0
GFAP_THRESHOLD     = 50.0   # was 5000.0 — raised to suppress dim process signal
GFAP_MIN_VOLUME    = 15.0    # µm³ — astrocyte bodies are larger than neurons
GFAP_NAME          = "GFAP Surfaces"


def _connect(app_id):
    lib = ImarisLib.ImarisLib()
    app = lib.GetApplication(app_id)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")
    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset open in Imaris.")
    print(f"[info] Connected. Dataset C={ds.GetSizeC()}")
    return app, ds


def _filter_by_volume(surfaces, min_volume, name):
    """
    Remove surfaces smaller than min_volume.
    Collects IDs first, converts to indices, removes in reverse order
    so indices don't shift during deletion.
    """
    n_before = surfaces.GetNumberOfSurfaces()
    print(f"[filter] '{name}': {n_before} surfaces before volume filter (min={min_volume} µm³)")

    if min_volume <= 0 or n_before == 0:
        return

    # collect all surface IDs and their volumes
    all_stats = surfaces.GetStatistics()
    ids_to_remove = []

    for j, stat_name in enumerate(all_stats.mNames):
        if "Volume" in stat_name:
            surf_id = all_stats.mIds[j]
            vol     = all_stats.mValues[j]
            if vol < min_volume:
                ids_to_remove.append(surf_id)

    if not ids_to_remove:
        print(f"[filter] No surfaces below {min_volume} µm³ — nothing removed")
        return

    print(f"[filter] Removing {len(ids_to_remove)} surfaces below {min_volume} µm³ ...")

    # build id -> index map from current ordered list
    all_ids = list(surfaces.GetIds())
    id_to_idx = {id_val: idx for idx, id_val in enumerate(all_ids)}

    # get indices and remove in reverse order so earlier indices stay valid
    indices_to_remove = sorted(
        [id_to_idx[sid] for sid in ids_to_remove if sid in id_to_idx],
        reverse=True
    )
    for idx in indices_to_remove:
        surfaces.RemoveSurface(idx)

    n_after = surfaces.GetNumberOfSurfaces()
    print(f"[filter] '{name}': {n_after} surfaces after volume filter")


def _detect_surfaces(app, ds, channel, smooth_width, bg_width, threshold, min_volume, name):
    print(f"\n[detect] '{name}': channel={channel}, smooth={smooth_width}, bg={bg_width}, threshold={threshold}, min_vol={min_volume}")

    image_proc = app.GetImageProcessing()
    surfaces = image_proc.DetectSurfaces(
        ds,
        [],
        channel,
        smooth_width,
        bg_width,
        True,
        threshold,
        ""
    )

    if surfaces is None:
        print(f"[detect] WARNING: DetectSurfaces returned None for '{name}'")
        return None

    print(f"[detect] Raw detection: {surfaces.GetNumberOfSurfaces()} surfaces")

    _filter_by_volume(surfaces, min_volume, name)

    surfaces.SetName(name)
    surfaces.SetVisible(True)
    app.GetSurpassScene().AddChild(surfaces, -1)
    print(f"[detect] '{name}' added to scene: {surfaces.GetNumberOfSurfaces()} surfaces")

    return surfaces


def XT_Detect_Surfaces(aImarisApplicationID=0):
    lib = ImarisLib.ImarisLib()
    app = lib.GetApplication(aImarisApplicationID)
    if app is None:
        raise RuntimeError("Could not connect to Imaris.")
    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset open in Imaris.")

    neun_surf = _detect_surfaces(app, ds, NEUN_CHANNEL, NEUN_SMOOTH_WIDTH, NEUN_BG_WIDTH, NEUN_THRESHOLD, NEUN_MIN_VOLUME, NEUN_NAME)
    gfap_surf = _detect_surfaces(app, ds, GFAP_CHANNEL, GFAP_SMOOTH_WIDTH, GFAP_BG_WIDTH, GFAP_THRESHOLD, GFAP_MIN_VOLUME, GFAP_NAME)

    print("\n" + "="*50)
    print("RESULTS SUMMARY")
    print("="*50)
    if neun_surf: print(f"  NeuN surfaces:  {neun_surf.GetNumberOfSurfaces()}")
    if gfap_surf: print(f"  GFAP surfaces:  {gfap_surf.GetNumberOfSurfaces()}")
    print("="*50)
    print("[done] detect_surfaces.py complete.")


if __name__ == "__main__":
    lib = ImarisLib.ImarisLib()
    obj_id = lib.GetServer().GetObjectID(0)
    XT_Detect_Surfaces(obj_id)
