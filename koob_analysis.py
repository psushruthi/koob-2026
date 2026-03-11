# -*- coding: utf-8 -*-
"""
koob_analysis.py

Master script — runs the full KOOB pipeline in order:
  1. mask_roi.py
  2. coloc.py
  3. detect_surfaces.py
"""

import traceback

scripts = [
    "/Volumes/Sush/Automation/KOOB_2026/mask_roi.py",
    "/Volumes/Sush/Automation/KOOB_2026/coloc.py",
    "/Volumes/Sush/Automation/KOOB_2026/detect_surfaces.py",
]

for path in scripts:
    print("\n" + "="*50)
    print(f"RUNNING: {path}")
    print("="*50)
    try:
        with open(path, "r") as f:
            code = f.read()
        exec(compile(code, path, "exec"), globals())
        print(f"[done] Finished: {path}")
    except Exception as e:
        print(f"[ERROR] Script failed: {path}")
        print(traceback.format_exc())
        print("[abort] Pipeline stopped. Fix the error above and re-run.")
        break

print("\n" + "="*50)
print("PIPELINE COMPLETE")
print("="*50)
