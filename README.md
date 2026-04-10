# KOOB

Automated fluorescence microscopy analysis pipeline for brain section `.ims` files using Imaris XTensions (Python).

Quantifies NeuN+ neurons, GFAP+ astrocytes, and TAU pathology within manually defined brain regions (RhCTX, BLA).

---

## Scripts

| Script | Description |
|--------|-------------|
| `mask_roi.py` | Masks brain regions of interest and writes masked channels to dataset |
| `coloc.py` | Builds NeuN+DAPI and GFAP+DAPI colocalization channels |
| `detect_surfaces.py` | Detects and counts NeuN and GFAP cell surfaces |
| `batch_process.py` | Batch loop - processes all `.ims` files in a folder automatically |
| `tauanalysis.py` | TAU analysis on currently open image |
| `tau_analysis_batch.py` | Batch version of TAU analysis, exports results to CSV |

---

## Requirements

No pip packages required. All dependencies are bundled with Imaris or part of the Python standard library.

- **Imaris 10.2.0** - license required
- Python standard library: `os`, `sys`, `csv`, `glob`, `time`, `traceback`, `datetime`, `array`

See `requirements.txt` for details.
