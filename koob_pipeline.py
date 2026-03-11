# -*- coding: utf-8 -*-
"""
koob_pipeline.py

Orchestrator: runs the full KOOB pipeline for the currently open image.
  1. mask_roi.py       -> XT_Mask_ROI
  2. coloc.py          -> XT_Build_Coloc
  3. detect_surfaces.py -> XT_Detect_Surfaces

Run this directly in the Imaris XTension console to process
whichever image is currently open.
"""

import ImarisLib
import traceback
import os

SCRIPT_DIR = "/Volumes/Sush/Automation/KOOB_2026/scripts"

STEPS = [
    ("mask_roi.py",        "XT_Mask_ROI"),
    ("coloc.py",           "XT_Build_Coloc"),
    ("detect_surfaces.py", "XT_Detect_Surfaces"),
]


def get_app_id():
    lib = ImarisLib.ImarisLib()
    return lib.GetServer().GetObjectID(0)


def run_pipeline(app_id=None):
    if app_id is None:
        app_id = get_app_id()
    print(f"[pipeline] Using Imaris app ID: {app_id}")

    for script_name, fn_name in STEPS:
        path = os.path.join(SCRIPT_DIR, script_name)
        print("\n" + "="*50)
        print(f"STEP: {script_name}  ->  {fn_name}()")
        print("="*50)
        try:
            with open(path, "r") as f:
                code = f.read()
            ns = {}
            exec(compile(code, path, "exec"), ns)
            if fn_name not in ns:
                raise RuntimeError(f"Function '{fn_name}' not found in {script_name}")
            ns[fn_name](app_id)
            print(f"[done] {script_name}")
        except Exception as e:
            print(f"[ERROR] {script_name} failed: {e}")
            print(traceback.format_exc())
            print("[abort] Pipeline stopped.")
            raise

    print("\n" + "="*50)
    print("PIPELINE COMPLETE")
    print("="*50)


if __name__ == "__main__":
    run_pipeline()
