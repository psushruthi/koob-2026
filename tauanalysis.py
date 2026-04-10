# -*- coding: utf-8 -*-
"""
tau_analysis_batch.py

Batch version of tau_analysis.py.
Runs on all .ims files in INPUT_DIR.
Requires mask_roi.py, coloc.py, and detect_surfaces.py to have
already been run on each file (main pipeline must be complete).

Change INPUT_DIR to switch batches.

Columns exported to CSV:
  filename, dapi_thr, tau_thr,
  rhctx_voxels, bla_voxels,
  neun_dapi_coloc_voxels, gfap_dapi_coloc_voxels,
  tau_voxels, dapi_count, neun_count, gfap_count,
  tau_in_roi, tau_in_neun, tau_in_gfap,
  status, error
"""

import os
import csv
import glob
import time
import traceback
import datetime
import ImarisLib
import Imaris

# ── Change this to switch batches ─────────────────────────────────────
INPUT_DIR = "/Volumes/Sush_KOOB/images/merge"

# ── Channels ──────────────────────────────────────────────────────────
CH_DAPI       = 4
CH_TAU        = 5
CH_NEUN_COLOC = 8
CH_GFAP_COLOC = 9

# ── DAPI surface detection ────────────────────────────────────────────
DAPI_SMOOTH_WIDTH = 0.5
DAPI_BG_WIDTH     = 100.0
DAPI_THRESHOLD    = 65.0
DAPI_MIN_VOLUME   = 10.0
DAPI_SURF_NAME    = "DAPI Nuclei"

# ── TAU voxel threshold ───────────────────────────────────────────────
THR_TAU = 200.0

# ── ROI and surface names ─────────────────────────────────────────────
ROI_RHCTX      = "RhCTX"
ROI_BLA        = "BLA"
NEUN_SURF_NAME = "NeuN Surfaces"
GFAP_SURF_NAME = "GFAP Surfaces"

# ── Output paths ──────────────────────────────────────────────────────
BATCH_NAME = os.path.basename(INPUT_DIR)
CSV_PATH   = os.path.join(INPUT_DIR, f"{BATCH_NAME}_tau_analysis.csv")
LOG_PATH   = os.path.join(INPUT_DIR, f"{BATCH_NAME}_tau_analysis.log")


# ─────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────

def log(msg, level="INFO"):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_PATH, "a") as f:
        f.write(line + "\n")


# ─────────────────────────────────────────────────────────────────────
# IMARIS CONNECTION
# ─────────────────────────────────────────────────────────────────────

def get_lib_and_id():
    lib = ImarisLib.ImarisLib()
    app_id = lib.GetServer().GetObjectID(0)
    return lib, app_id

def get_app(lib, app_id):
    return lib.GetApplication(app_id)


# ─────────────────────────────────────────────────────────────────────
# SKIP ALREADY COMPLETED FILES
# ─────────────────────────────────────────────────────────────────────

def get_completed_files(csv_path):
    completed = set()
    if not os.path.exists(csv_path):
        return completed
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("status") == "success":
                completed.add(row.get("filename"))
    return completed


# ─────────────────────────────────────────────────────────────────────
# COUNT ROI VOXELS BY NAME
# ─────────────────────────────────────────────────────────────────────

def _count_roi_voxels(app, ds, roi_name):
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
            log(f"   '{roi_name}' voxels: {total:,}")
            return total
    log(f"   WARNING: '{roi_name}' not found in scene", level="WARN")
    return -1


# ─────────────────────────────────────────────────────────────────────
# COUNT SURFACES BY NAME
# ─────────────────────────────────────────────────────────────────────

def _count_surfaces(app, surf_name):
    scene = app.GetSurpassScene()
    for i in range(scene.GetNumberOfChildren()):
        child = scene.GetChild(i)
        if child is None:
            continue
        if child.GetName() == surf_name:
            surf = Imaris.ISurfacesPrx.checkedCast(child)
            if surf is not None:
                count = surf.GetNumberOfSurfaces()
                log(f"   '{surf_name}': {count} surfaces")
                return count
    log(f"   WARNING: '{surf_name}' not found in scene", level="WARN")
    return -1


# ─────────────────────────────────────────────────────────────────────
# DETECT DAPI NUCLEI
# ─────────────────────────────────────────────────────────────────────

def _detect_dapi_nuclei(app, ds):
    sc = ds.GetSizeC()
    if CH_DAPI >= sc:
        raise RuntimeError(f"DAPI channel (ch{CH_DAPI}) not found — dataset has {sc} channels.")

    log(f"   Detecting DAPI nuclei: smooth={DAPI_SMOOTH_WIDTH}, bg={DAPI_BG_WIDTH}, "
        f"threshold={DAPI_THRESHOLD}, min_vol={DAPI_MIN_VOLUME}")

    image_proc = app.GetImageProcessing()
    surfaces = image_proc.DetectSurfaces(
        ds, [], CH_DAPI,
        DAPI_SMOOTH_WIDTH, DAPI_BG_WIDTH,
        True, DAPI_THRESHOLD, ""
    )

    if surfaces is None:
        log("   WARNING: DAPI DetectSurfaces returned None", level="WARN")
        return 0

    log(f"   DAPI raw detection: {surfaces.GetNumberOfSurfaces()} nuclei")

    if DAPI_MIN_VOLUME > 0 and surfaces.GetNumberOfSurfaces() > 0:
        all_stats = surfaces.GetStatistics()
        ids_to_remove = []
        for j, stat_name in enumerate(all_stats.mNames):
            if "Volume" in stat_name:
                if all_stats.mValues[j] < DAPI_MIN_VOLUME:
                    ids_to_remove.append(all_stats.mIds[j])
        if ids_to_remove:
            all_ids = list(surfaces.GetIds())
            id_to_idx = {id_val: idx for idx, id_val in enumerate(all_ids)}
            indices_to_remove = sorted(
                [id_to_idx[sid] for sid in ids_to_remove if sid in id_to_idx],
                reverse=True
            )
            for idx in indices_to_remove:
                surfaces.RemoveSurface(idx)

    dapi_count = surfaces.GetNumberOfSurfaces()
    surfaces.SetName(DAPI_SURF_NAME)
    surfaces.SetVisible(True)
    app.GetSurpassScene().AddChild(surfaces, -1)
    log(f"   DAPI nuclei after filter: {dapi_count}")
    return dapi_count


# ─────────────────────────────────────────────────────────────────────
# COUNT TAU VOXELS AND BUILD MASK
# ─────────────────────────────────────────────────────────────────────

def _count_tau_voxels(ds):
    sx, sy, sz, st = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ(), ds.GetSizeT()
    tau_voxels = 0
    tau_mask = []
    for t in range(st):
        for z in range(sz):
            plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, CH_TAU, t, sx, sy, 1)
            row = [1 if v >= THR_TAU else 0 for v in plane]
            tau_voxels += sum(row)
            tau_mask.extend(row)
    log(f"   TAU voxels >= {THR_TAU}: {tau_voxels:,}")
    return tau_voxels, tau_mask


# ─────────────────────────────────────────────────────────────────────
# COUNT TAU OVERLAP WITH COLOC CHANNEL
# ─────────────────────────────────────────────────────────────────────

def _count_tau_in_coloc(ds, coloc_ch, ch_name, tau_mask):
    sc = ds.GetSizeC()
    if coloc_ch >= sc:
        log(f"   WARNING: {ch_name} (ch{coloc_ch}) not found", level="WARN")
        return -1, -1

    sx, sy, sz, st = ds.GetSizeX(), ds.GetSizeY(), ds.GetSizeZ(), ds.GetSizeT()
    coloc_voxels = 0
    tau_in_coloc = 0
    idx = 0

    for t in range(st):
        for z in range(sz):
            plane = ds.GetDataSubVolumeAs1DArrayFloats(0, 0, z, coloc_ch, t, sx, sy, 1)
            for i, v in enumerate(plane):
                if v > 0:
                    coloc_voxels += 1
                    if tau_mask[idx + i] > 0:
                        tau_in_coloc += 1
            idx += sx * sy

    log(f"   '{ch_name}': coloc voxels={coloc_voxels:,}, TAU inside={tau_in_coloc:,}")
    return coloc_voxels, tau_in_coloc


# ─────────────────────────────────────────────────────────────────────
# PROCESS ONE FILE
# ─────────────────────────────────────────────────────────────────────

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

    ds = app.GetDataSet()
    if ds is None:
        raise RuntimeError("No dataset found after opening file.")

    rhctx_voxels      = _count_roi_voxels(app, ds, ROI_RHCTX)
    bla_voxels        = _count_roi_voxels(app, ds, ROI_BLA)
    neun_count        = _count_surfaces(app, NEUN_SURF_NAME)
    gfap_count        = _count_surfaces(app, GFAP_SURF_NAME)
    dapi_count        = _detect_dapi_nuclei(app, ds)
    tau_voxels, tau_mask = _count_tau_voxels(ds)

    tau_pct_roi = (tau_voxels / rhctx_voxels * 100.0) if rhctx_voxels > 0 else -1.0

    neun_coloc_voxels, tau_in_neun = _count_tau_in_coloc(ds, CH_NEUN_COLOC, "NeuN_DAPI_coloc", tau_mask)
    tau_pct_neun = (tau_in_neun / tau_voxels * 100.0) if tau_voxels > 0 else -1.0

    gfap_coloc_voxels, tau_in_gfap = _count_tau_in_coloc(ds, CH_GFAP_COLOC, "GFAP_DAPI_coloc", tau_mask)
    tau_pct_gfap = (tau_in_gfap / tau_voxels * 100.0) if tau_voxels > 0 else -1.0

    log(f"   tau_in_roi:  {tau_pct_roi:.4f}%")
    log(f"   tau_in_neun: {tau_pct_neun:.2f}%")
    log(f"   tau_in_gfap: {tau_pct_gfap:.2f}%")

    app.FileSave(ims_path, "")
    log(f"   Saved: {ims_path}")

    return (
        rhctx_voxels, bla_voxels,
        neun_coloc_voxels, gfap_coloc_voxels,
        tau_voxels, dapi_count, neun_count, gfap_count,
        tau_pct_roi, tau_pct_neun, tau_pct_gfap
    )


# ─────────────────────────────────────────────────────────────────────
# MAIN BATCH LOOP
# ─────────────────────────────────────────────────────────────────────

def run_tau_analysis_batch():
    log("=" * 60)
    log(f"TAU ANALYSIS BATCH — START ({BATCH_NAME})")
    log(f"Input:      {INPUT_DIR}")
    log(f"CSV:        {CSV_PATH}")
    log(f"THR_TAU  >= {THR_TAU}")
    log(f"THR_DAPI >= {DAPI_THRESHOLD}")
    log("=" * 60)

    ims_files = sorted(glob.glob(os.path.join(INPUT_DIR, "*.ims")))
    if not ims_files:
        log(f"No .ims files found in {INPUT_DIR}", level="WARN")
        return

    completed = get_completed_files(CSV_PATH)
    if completed:
        log(f"Skipping {len(completed)} already completed: {sorted(completed)}")
    ims_files = [f for f in ims_files if os.path.basename(f) not in completed]

    if not ims_files:
        log("All files already completed — nothing to do.")
        return

    log(f"Remaining to process: {len(ims_files)} file(s)")

    if not os.path.exists(CSV_PATH):
        with open(CSV_PATH, "w", newline="") as csvf:
            csv.writer(csvf).writerow([
                "filename",
                "dapi_thr", "tau_thr",
                "ec_voxels", "bla_voxels",
                "neun_dapi_coloc_voxels", "gfap_dapi_coloc_voxels",
                "tau_voxels",
                "dapi_count", "neun_count", "gfap_count",
                "tau_in_roi", "tau_in_neun", "tau_in_gfap",
                "status", "error"
            ])

    lib, app_id = get_lib_and_id()
    log(f"Imaris app_id: {app_id}")

    for i, ims_path in enumerate(ims_files, 1):
        filename = os.path.basename(ims_path)
        log(f"\n[{i}/{len(ims_files)}] {filename}")

        status, error_msg = "success", ""
        rhctx_voxels = bla_voxels = -1
        neun_coloc_voxels = gfap_coloc_voxels = -1
        tau_voxels = dapi_count = neun_count = gfap_count = -1
        tau_pct_roi = tau_pct_neun = tau_pct_gfap = -1.0

        try:
            (
                rhctx_voxels, bla_voxels,
                neun_coloc_voxels, gfap_coloc_voxels,
                tau_voxels, dapi_count, neun_count, gfap_count,
                tau_pct_roi, tau_pct_neun, tau_pct_gfap
            ) = process_file(ims_path, lib, app_id)

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
                filename,
                DAPI_THRESHOLD, THR_TAU,
                rhctx_voxels, bla_voxels,
                neun_coloc_voxels, gfap_coloc_voxels,
                tau_voxels,
                dapi_count, neun_count, gfap_count,
                round(tau_pct_roi, 4), round(tau_pct_neun, 2), round(tau_pct_gfap, 2),
                status, error_msg
            ])

    log("\n" + "=" * 60)
    log(f"TAU ANALYSIS BATCH COMPLETE — {BATCH_NAME}")
    log(f"Results: {CSV_PATH}")
    log("=" * 60)


run_tau_analysis_batch()
