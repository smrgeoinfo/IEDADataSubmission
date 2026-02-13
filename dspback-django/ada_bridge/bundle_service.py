"""
Bundle introspection service.

Inspects uploaded ZIP bundles to extract metadata hints from individual
files.  The results are returned as a dict suitable for pre-populating
form fields in the frontend (variableMeasured, file descriptions, etc.).
"""

from __future__ import annotations

import logging
import os
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Dict, List

from ada_bridge.inspectors import (
    inspect_csv,
    inspect_excel,
    inspect_hdf5,
    inspect_netcdf,
    inspect_pdf,
    inspect_text,
)

logger = logging.getLogger(__name__)

# File extension sets for dispatch
_CSV_EXTENSIONS = {".csv", ".tsv", ".tab"}
_EXCEL_EXTENSIONS = {".xlsx", ".xls"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
_HDF5_EXTENSIONS = {".h5", ".hdf5", ".he5", ".hdf"}
_NETCDF_EXTENSIONS = {".nc", ".nc4", ".cdf"}
_PDF_EXTENSIONS = {".pdf"}
_TEXT_EXTENSIONS = {".txt", ".text", ".md", ".rst"}


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
        "archive_size": 0,
        "warnings": [],
    }

    if not zipfile.is_zipfile(file_path):
        result["warnings"].append("Uploaded file is not a valid ZIP archive.")
        return result

    # Total size of the ZIP archive itself
    result["archive_size"] = os.path.getsize(file_path)

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

    return result


def _get_manifest(file_path: str) -> List[str]:
    """Return the list of file paths inside a ZIP archive."""
    with zipfile.ZipFile(file_path, "r") as zf:
        return [
            name for name in zf.namelist()
            if not name.endswith("/")  # skip directories
        ]


def introspect_directory(dir_path: str) -> Dict[str, Any]:
    """
    Inspect files in a directory (as if they were ZIP contents).

    Parameters
    ----------
    dir_path : str
        Path to the directory on disk.

    Returns
    -------
    dict
        ``{"manifest": [...], "files": {...}, "archive_size": ..., "warnings": [...]}``
    """
    result: Dict[str, Any] = {
        "manifest": [],
        "files": {},
        "archive_size": 0,
        "warnings": [],
    }

    if not os.path.isdir(dir_path):
        result["warnings"].append(f"Path is not a valid directory: {dir_path}")
        return result

    total_size = 0
    manifest: List[str] = []

    for root, dirs, files in os.walk(dir_path):
        # Skip hidden directories in-place
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        for filename in files:
            # Skip hidden files
            if filename.startswith("."):
                continue

            full_path = os.path.join(root, filename)
            relative_path = os.path.relpath(full_path, dir_path)
            # Normalise to forward slashes for consistency with ZIP manifests
            relative_path = relative_path.replace("\\", "/")

            manifest.append(relative_path)
            try:
                total_size += os.path.getsize(full_path)
            except OSError:
                pass

    result["manifest"] = manifest
    result["archive_size"] = total_size

    for relative_path in manifest:
        full_path = os.path.join(dir_path, relative_path)
        if not os.path.isfile(full_path):
            continue

        ext = Path(relative_path).suffix.lower()
        inspection = _inspect_file(full_path, ext)
        if inspection:
            result["files"][relative_path] = inspection

    return result


def zip_directory(dir_path: str) -> str:
    """
    Create a ZIP archive from a directory.

    Parameters
    ----------
    dir_path : str
        Path to the directory to compress.

    Returns
    -------
    str
        Path to the temporary ZIP file. Caller is responsible for cleanup.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    tmp.close()

    with zipfile.ZipFile(tmp.name, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                if filename.startswith("."):
                    continue
                full_path = os.path.join(root, filename)
                arcname = os.path.relpath(full_path, dir_path).replace("\\", "/")
                zf.write(full_path, arcname)

    return tmp.name


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _inspect_file(full_path: str, ext: str) -> Dict[str, Any] | None:
    """Dispatch to the appropriate inspector based on file extension."""
    try:
        if ext in _CSV_EXTENSIONS:
            return inspect_csv(full_path)

        if ext in _EXCEL_EXTENSIONS:
            return inspect_excel(full_path)

        if ext in _HDF5_EXTENSIONS:
            return inspect_hdf5(full_path)

        if ext in _NETCDF_EXTENSIONS:
            return inspect_netcdf(full_path)

        if ext in _PDF_EXTENSIONS:
            return inspect_pdf(full_path)

        if ext in _TEXT_EXTENSIONS:
            return inspect_text(full_path)

        # For unrecognized types, return basic file info
        return {
            "size": os.path.getsize(full_path),
            "warnings": [],
        }
    except Exception:
        logger.exception("Inspector failed for %s", full_path)

    return None
