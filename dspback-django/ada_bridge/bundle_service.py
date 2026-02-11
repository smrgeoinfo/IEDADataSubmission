"""
Bundle introspection service.

Integrates inspectors from the ``ada_metadata_forms`` package to extract
metadata hints from uploaded ZIP bundles.  The results are returned as a
dict suitable for pre-populating form fields in the frontend.

If ``ada_metadata_forms`` is not installed, introspection gracefully
returns an empty result with a warning.
"""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional imports — ada_metadata_forms may not be installed
# ---------------------------------------------------------------------------

try:
    from bundle_ingestion.services.zip_inspector import ZipInspector

    _HAS_ZIP_INSPECTOR = True
except ImportError:
    _HAS_ZIP_INSPECTOR = False

try:
    from bundle_ingestion.services.csv_inspector import CSVInspector

    _HAS_CSV_INSPECTOR = True
except ImportError:
    _HAS_CSV_INSPECTOR = False

try:
    from bundle_ingestion.services.image_inspector import ImageInspector

    _HAS_IMAGE_INSPECTOR = True
except ImportError:
    _HAS_IMAGE_INSPECTOR = False

try:
    from bundle_ingestion.services.hdf5_inspector import HDF5Inspector

    _HAS_HDF5_INSPECTOR = True
except ImportError:
    _HAS_HDF5_INSPECTOR = False

# File extension sets for dispatch
_CSV_EXTENSIONS = {".csv", ".tsv"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_HDF5_EXTENSIONS = {".h5", ".hdf5", ".he5", ".hdf"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def introspect_bundle(file_path: str) -> Dict[str, Any]:
    """
    Inspect a ZIP bundle and return extracted metadata.

    Parameters
    ----------
    file_path : str
        Path to the ZIP file on disk.

    Returns
    -------
    dict
        ``{"manifest": [...], "files": {...}, "warnings": [...]}``

        - ``manifest``: list of file paths inside the ZIP
        - ``files``: mapping of filename -> inspector results
        - ``warnings``: list of non-fatal warning messages
    """
    result: Dict[str, Any] = {
        "manifest": [],
        "files": {},
        "warnings": [],
    }

    if not zipfile.is_zipfile(file_path):
        result["warnings"].append("Uploaded file is not a valid ZIP archive.")
        return result

    # Step 1: Get manifest
    manifest = _get_manifest(file_path)
    result["manifest"] = manifest

    # Step 2: Extract and inspect individual files
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(file_path, "r") as zf:
            zf.extractall(tmpdir)

        for relative_path in manifest:
            full_path = os.path.join(tmpdir, relative_path)
            if not os.path.isfile(full_path):
                continue

            ext = Path(relative_path).suffix.lower()
            inspection = _inspect_file(full_path, ext)
            if inspection:
                result["files"][relative_path] = inspection

    if not any([_HAS_CSV_INSPECTOR, _HAS_IMAGE_INSPECTOR, _HAS_HDF5_INSPECTOR]):
        result["warnings"].append(
            "ada_metadata_forms is not installed; introspection is limited to "
            "ZIP manifest only."
        )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_manifest(file_path: str) -> List[str]:
    """Return the list of file paths inside a ZIP archive."""
    if _HAS_ZIP_INSPECTOR:
        try:
            inspector = ZipInspector(file_path)
            return inspector.get_manifest()
        except Exception:
            logger.exception("ZipInspector failed, falling back to zipfile")

    # Fallback: use stdlib zipfile
    with zipfile.ZipFile(file_path, "r") as zf:
        return [
            name for name in zf.namelist()
            if not name.endswith("/")  # skip directories
        ]


def _inspect_file(full_path: str, ext: str) -> Dict[str, Any] | None:
    """Dispatch to the appropriate inspector based on file extension."""
    try:
        if ext in _CSV_EXTENSIONS and _HAS_CSV_INSPECTOR:
            inspector = CSVInspector(full_path)
            return inspector.inspect()

        if ext in _IMAGE_EXTENSIONS and _HAS_IMAGE_INSPECTOR:
            inspector = ImageInspector(full_path)
            return inspector.inspect()

        if ext in _HDF5_EXTENSIONS and _HAS_HDF5_INSPECTOR:
            inspector = HDF5Inspector(full_path)
            return inspector.inspect()
    except Exception:
        logger.exception("Inspector failed for %s", full_path)

    return None
