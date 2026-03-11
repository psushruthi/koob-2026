# -*- coding: utf-8 -*-
import ImarisLib
import Imaris
import sys

NEUN_CHANNEL       = 8
NEUN_SMOOTH_WIDTH  = 0.5
NEUN_BG_WIDTH      = 75.0
NEUN_THRESHOLD     = 3000.0
NEUN_NAME          = "NeuN Surfaces"

GFAP_CHANNEL       = 9
GFAP_SMOOTH_WIDTH  = 0.9
GFAP_BG_WIDTH      = 100.0
GFAP_THRESHOLD     = 5000.0
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


def _detect_surfaces(app, ds, channel, smooth_width, bg_width, threshold, name):
    print(f"\n[detect] '{name}': channel={channel}, smooth={smooth_width}, bg={bg_width}, threshold={threshold}")
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
    n = surfaces.GetNumberOfSurfaces()
    print(f"[detect] '{name}': {n} surfaces detected")
    surfaces.SetName(name)
    surfaces.SetVisible(True)
    app.GetSurpassScene().AddChild(surfaces, -1)
    print(f"[detect] '{name}' added to Surpass scene")
    return surfaces


def XT_Detect_Surfaces(aImarisApplicationID=0):
    app, ds = _connect(aImarisApplicationID)
    neun_surf = _detect_surfaces(app, ds, NEUN_CHANNEL, NEUN_SMOOTH_WIDTH, NEUN_BG_WIDTH, NEUN_THRESHOLD, NEUN_NAME)
    gfap_surf = _detect_surfaces(app, ds, GFAP_CHANNEL, GFAP_SMOOTH_WIDTH, GFAP_BG_WIDTH, GFAP_THRESHOLD, GFAP_NAME)
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
