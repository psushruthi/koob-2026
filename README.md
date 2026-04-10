# KOOB 2026 — Automated Fluorescence Microscopy Analysis Pipeline

Automated image analysis pipeline for quantifying neurons (NeuN), astrocytes (GFAP), and tau pathology in brain sections using Imaris XTensions (Python).

**Lab:** MODEL-AD Lab, Stark Neurosciences Research Institute, Indiana University School of Medicine  
**PI:** Dr. Bruce Lamb, Dr. Adrian Oblak  
**Software:** Imaris 10.2.0 | Python (bundled with Imaris)

---

## Overview

This pipeline processes `.ims` fluorescence microscopy files to:
- Mask brain regions of interest (RhCTX, BLA) using manually drawn surfaces
- Build colocalization channels for NeuN, GFAP, and TAU with DAPI
- Detect and count NeuN+ neurons and GFAP+ astrocytes as surfaces
- Quantify TAU distribution across cell types (neurons, astrocytes, other)
- Export all results to CSV per batch

---

## Pipeline Steps

### Main Pipeline (run via `batch_process.py` or `koob_pipeline.py`)

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `mask_roi.py` | Finds RhCTX surface in scene, extracts voxel mask, clones dataset, writes 4 masked channels (DAPI, TAU, NeuN, GFAP masked to ROI) |
| 2 | `coloc.py` | Builds binary colocalization channels: NeuN+DAPI and GFAP+DAPI using constant value thresholding |
| 3 | `detect_surfaces.py` | Detects NeuN and GFAP surfaces on the coloc channels, filters by volume, adds to Surpass scene |

### TAU Analysis (run separately after main pipeline)

| Script | What it does |
|--------|--------------|
| `tauanalysis.py` | Standalone: runs TAU analysis on currently open image |
| `tau_analysis_batch.py` | Batch version: processes all images in a folder, exports full results to CSV |

### Utilities

| Script | What it does |
|--------|--------------|
| `koob_pipeline.py` | Orchestrator: runs mask → coloc → detect in sequence on the currently open image |
| `get_voxels.py` | Counts non-zero voxels for masked channels 4–7 |
| `count_voxels.py` | Voxel counting utility |

---

## Channel Map (post mask_roi.py)

| Channel | Name |
|---------|------|
| ch0 | DAPI (raw) |
| ch1 | TAU / thr231 (raw) |
| ch2 | NeuN (raw) |
| ch3 | GFAP (raw) |
| ch4 | DAPI masked |
| ch5 | TAU masked |
| ch6 | NeuN masked |
| ch7 | GFAP masked |
| ch8 | NeuN_DAPI_coloc |
| ch9 | GFAP_DAPI_coloc |

---

## Key Thresholds

| Parameter | Value |
|-----------|-------|
| THR_NEUN | 150 |
| THR_GFAP | 2000 |
| THR_DAPI (coloc) | 10 |
| THR_TAU | 200 |
| THR_DAPI (nuclei) | 65 |

---

## TAU Analysis Output Columns

| Column | Description |
|--------|-------------|
| filename | Image file name |
| dapi_thr | DAPI threshold used |
| tau_thr | TAU threshold used |
| ec_voxels | RhCTX (entorhinal cortex) ROI voxel count |
| bla_voxels | BLA ROI voxel count |
| neun_dapi_coloc_voxels | Total voxels in NeuN+DAPI coloc channel |
| gfap_dapi_coloc_voxels | Total voxels in GFAP+DAPI coloc channel |
| tau_voxels | TAU voxels above threshold in ch5 |
| dapi_count | Total DAPI nuclei detected (cell count) |
| neun_count | NeuN surfaces detected |
| gfap_count | GFAP surfaces detected |
| tau_in_roi | TAU % area within RhCTX |
| tau_in_neun | % of TAU voxels overlapping NeuN coloc channel |
| tau_in_gfap | % of TAU voxels overlapping GFAP coloc channel |
| status | success or error |
| error | Error message if status = error |

---

## Requirements

No pip-installable packages required. All dependencies are either bundled with Imaris or part of the Python standard library.

- **Imaris 10.2.0** (Bitplane / Oxford Instruments) — license required
- **ImarisLib**, **Imaris** — bundled with Imaris XTensions
- Standard library: `os`, `sys`, `csv`, `glob`, `time`, `traceback`, `datetime`, `array`

See `requirements.txt` for full details.

---

## How to Run

```bash
# Navigate to Imaris bundled Python
cd /Applications/Imaris\ 10.2.0.app/Contents/SharedSupport/XT/python3

# Start Python
python3

# Run batch pipeline (update INPUT_DIR in script first)
>>> exec(open("/path/to/scripts/batch_process.py").read())

# Run TAU analysis batch (update INPUT_DIR in script first)
>>> exec(open("/path/to/scripts/tau_analysis_batch.py").read())
```

---

## Notes

- Update `INPUT_DIR` / `SCRIPT_DIR` paths in `batch_process.py`, `koob_pipeline.py`, and `tau_analysis_batch.py` to match your local file paths before running
- RhCTX and BLA surfaces must be manually drawn in Imaris before running the pipeline
- The skip-already-completed logic in batch scripts allows safe reruns after interruptions
