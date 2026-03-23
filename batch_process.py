# -*- coding: utf-8 -*-
"""
KOOB 2026 - Batch Processing Script
"""

import os
import csv
import glob
import time
import traceback
import datetime
import ImarisLib
import Imaris

INPUT_DIR  = "/Volumes/Sush/Automation/KOOB_2026/KOOB_FILES/batch2"
SCRIPT_DIR = "/Volumes/Sush/Automation/KOOB_2026/scripts"

BATCH_NAME = os.path.basename(INPUT_DIR)
CSV_PATH   = os.path.join(INPUT_DIR, f"{BATCH_NAME}_results.csv")
LOG_PATH   = os.path.join(INPUT_DIR, f"{BATCH_NAME}_batch.log")

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
    name_sub_lower = name_substring.lower()
    for i in range(scene.GetNumberOfChildren()):
        child = scene.GetChild(i)
        if child is None:
            continue
        if name_sub_lower in child.GetName().lower():
            surfs = app.GetFactory().ToSurfaces(child)
            if surfs is not None:
                return surfs.GetNumberOfSurfaces()
    return -1


# ─────────────────────────────────────────────
# COUNT ROI VOXELS BY NAME
# ─────────────────────────────────────────────

def count_roi_voxels(app, roi_name):
    ds = app.GetDataSet()
    if ds is None:
        return -1
    scene = app.GetSurpassScene()
    for i in range(scene.GetNumberOfChildren()):
        child = scene.GetChild(i)
        if child is None:
            continue
        if child.GetName() == roi_name:
            surf = Imaris.ISurfacesPrx.checkedCast(child)
            if surf is None:
                return -1
            sx, sy, sz = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ()
            min_x, max_x = ds.GetExtendMinX(), ds.GetExtendMaxX()
            min_y, max_y = ds.GetExtendMinY(), ds.GetExtendMaxY()
            min_z, max_z = ds.GetExtendMinZ(), ds.GetExtendMaxZ()
            mask_ds = surf.GetMask(min_x, min_y, min_z, max_x, max_y, max_z, sx, sy, sz, 0)
            total = 0
            for z in range(sz):
                plane = mask_ds.GetDataSubVolumeAs1DArrayBytes(0, 0, z, 0, 0, sx, sy, 1)
                total += sum(1 for v in plane if v > 0)
            return total
    log(f"   Surface '{roi_name}' not found in scene", level="WARN")
    return -1


# ─────────────────────────────────────────────
# SKIP ALREADY COMPLETED FILES
# ─────────────────────────────────────────────

def get_completed_files(csv_path):
    """Return set of filenames already successfully completed in the CSV."""
    completed = set()
    if not os.path.exists(csv_path):
        return completed
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "success":
                completed.add(row.get("filename"))
    return completed


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

    app = get_app(lib, app_id)
    rhctx_voxels = count_roi_voxels(app, "RhCTX")
    bla_voxels   = count_roi_voxels(app, "BLA")
    neun_count   = count_surfaces(app, "NeuN")
    gfap_count   = count_surfaces(app, "GFAP")

    log(f"   RhCTX voxels:  {rhctx_voxels}")
    log(f"   BLA voxels:    {bla_voxels}")
    log(f"   NeuN surfaces: {neun_count}")
    log(f"   GFAP surfaces: {gfap_count}")

    app.FileSave(ims_path, "")
    log(f"   Saved: {ims_path}")

    return rhctx_voxels, bla_voxels, neun_count, gfap_count


# ─────────────────────────────────────────────
# MAIN BATCH LOOP
# ─────────────────────────────────────────────

def run_batch():
    log("=" * 60)
    log(f"KOOB 2026 Batch Processing — START ({BATCH_NAME})")
    log(f"Input:  {INPUT_DIR}")
    log(f"CSV:    {CSV_PATH}")
    log(f"Log:    {LOG_PATH}")

    ims_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.ims")))
    if not ims_files:
        log(f"No .ims files found in {INPUT_DIR}", level="WARN")
        return

    # skip already completed files
    completed = get_completed_files(CSV_PATH)
    if completed:
        log(f"Skipping {len(completed)} already completed: {sorted(completed)}")
    ims_files = [f for f in ims_files if os.path.basename(f) not in completed]
    if not ims_files:
        log("All files already completed — nothing to do.")
        return
    log(f"Remaining to process: {len(ims_files)} file(s)")

    # write header only if CSV doesn't exist yet
    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as csvf:
            csv.writer(csvf).writerow([
                "filename", "rhctx_voxels", "bla_voxels",
                "neun_count", "gfap_count", "status", "error"
            ])

    lib, app_id = get_lib_and_id()
    log(f"Imaris app_id: {app_id}")

    for i, ims_path in enumerate(ims_files, 1):
        filename = os.path.basename(ims_path)
        log(f"\n[{i}/{len(ims_files)}] {filename}")
        rhctx_voxels, bla_voxels, neun_count, gfap_count = -1, -1, -1, -1
        status, error_msg = "success", ""

        try:
            rhctx_voxels, bla_voxels, neun_count, gfap_count = process_file(ims_path, lib, app_id)
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
            csv.writer(csvf).writerow([
                filename, rhctx_voxels, bla_voxels,
                neun_count, gfap_count, status, error_msg
            ])

    log("\n" + "=" * 60)
    log("BATCH COMPLETE")
    log(f"Results: {CSV_PATH}")
    log(f"Log:     {LOG_PATH}")
    log("=" * 60)


run_batch()
