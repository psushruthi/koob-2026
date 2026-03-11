# -*- coding: utf-8 -*-
"""
KOOB 2026 - Batch Processing Script

Finds all .ims files in INPUT_DIR, runs the full pipeline on each,
saves back in place, and writes a CSV with NeuN + GFAP counts.
"""

import os
import csv
import glob
import time
import traceback
import datetime
import ImarisLib

INPUT_DIR  = "/Volumes/Sush/Automation/KOOB_2026"
SCRIPT_DIR = "/Volumes/Sush/Automation/KOOB_2026/scripts"
CSV_PATH   = os.path.join(INPUT_DIR, "koob_results.csv")
LOG_PATH   = os.path.join(INPUT_DIR, "koob_batch.log")

STEPS = [
    ("mask_roi.py",        "XT_Mask_ROI"),
    ("coloc.py",           "XT_Build_Coloc"),
    ("detect_surfaces.py", "XT_Detect_Surfaces"),
]


# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────

def log(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


# ─────────────────────────────────────────────
# IMARIS CONNECTION
# ─────────────────────────────────────────────

def get_lib_and_id():
    lib = ImarisLib.ImarisLib()
    app_id = lib.GetServer().GetObjectID(0)
    return lib, app_id


def get_app(lib, app_id):
    return lib.GetApplication(app_id)


# ─────────────────────────────────────────────
# RUN ONE PIPELINE STEP
# ─────────────────────────────────────────────

def run_step(script_name, fn_name, app_id):
    path = os.path.join(SCRIPT_DIR, script_name)
    with open(path, "r") as f:
        code = f.read()
    ns = {}
    exec(compile(code, path, "exec"), ns)
    if fn_name not in ns:
        raise RuntimeError(f"Function '{fn_name}' not found in {script_name}")
    ns[fn_name](app_id)


# ─────────────────────────────────────────────
# COUNT SURFACES BY NAME
# ─────────────────────────────────────────────

def count_surfaces(app, name_substring):
    scene = app.GetSurpassScene()
    n = scene.GetNumberOfChildren()
    name_sub_lower = name_substring.lower()
    for i in range(n):
        child = scene.GetChild(i)
        if child is None:
            continue
        if name_sub_lower in child.GetName().lower():
            surfs = app.GetFactory().ToSurfaces(child)
            if surfs is not None:
                return surfs.GetNumberOfSurfaces()
    return -1


# ─────────────────────────────────────────────
# PROCESS ONE FILE
# ─────────────────────────────────────────────

def process_file(ims_path, lib, app_id):
    filename = os.path.basename(ims_path)
    app = get_app(lib, app_id)

    log(f"── Opening: {filename}")
    app.FileOpen(ims_path, "")
    time.sleep(5)

    opened = app.GetCurrentFileName()
    if not opened or os.path.basename(opened) != filename:
        raise RuntimeError(f"FileOpen mismatch — Imaris reports: {opened!r}")
    log(f"   Confirmed open: {opened}")

    for script_name, fn_name in STEPS:
        log(f"   Running {script_name} -> {fn_name}() ...")
        run_step(script_name, fn_name, app_id)
        log(f"   Done: {script_name}")

    # re-fetch app handle to get updated scene
    app = get_app(lib, app_id)
    neun_count = count_surfaces(app, "NeuN")
    gfap_count = count_surfaces(app, "GFAP")
    log(f"   NeuN surfaces: {neun_count}")
    log(f"   GFAP surfaces: {gfap_count}")

    app.FileSave(ims_path, "")
    log(f"   Saved: {ims_path}")

    return neun_count, gfap_count


# ─────────────────────────────────────────────
# MAIN BATCH LOOP
# ─────────────────────────────────────────────

def run_batch():
    log("=" * 60)
    log("KOOB 2026 Batch Processing — START")

    ims_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.ims")))
    if not ims_files:
        log(f"No .ims files found in {INPUT_DIR}", level="WARN")
        return

    log(f"Found {len(ims_files)} file(s): {[os.path.basename(f) for f in ims_files]}")

    with open(CSV_PATH, "w", newline="") as csvf:
        csv.writer(csvf).writerow(["filename", "neun_count", "gfap_count", "status", "error"])

    lib, app_id = get_lib_and_id()
    log(f"Imaris app_id: {app_id}")

    for i, ims_path in enumerate(ims_files, 1):
        filename = os.path.basename(ims_path)
        log(f"\n[{i}/{len(ims_files)}] {filename}")
        neun_count, gfap_count = -1, -1
        status, error_msg = "success", ""

        try:
            neun_count, gfap_count = process_file(ims_path, lib, app_id)
        except Exception as e:
            status = "error"
            error_msg = str(e)
            log(f"   ERROR: {e}", level="ERROR")
            log(traceback.format_exc(), level="ERROR")
            try:
                lib, app_id = get_lib_and_id()
                log("   Reconnected to Imaris.")
            except Exception as re:
                log(f"   Reconnect failed: {re}", level="ERROR")

        with open(CSV_PATH, "a", newline="") as csvf:
            csv.writer(csvf).writerow([filename, neun_count, gfap_count, status, error_msg])

    log("\n" + "=" * 60)
    log("BATCH COMPLETE")
    log(f"Results: {CSV_PATH}")
    log(f"Log:     {LOG_PATH}")
    log("=" * 60)


run_batch()
