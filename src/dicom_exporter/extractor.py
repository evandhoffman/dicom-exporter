"""Extraction logic for exporter DICOM MRI zip files.

This module extracts a zip archive to a temporary directory, scans files and copies
those that are valid DICOM files into the provided output directory.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from typing import List

import pydicom
from pydicom.errors import InvalidDicomError

logger = logging.getLogger(__name__)


def is_dicom_file(path: str) -> bool:
    """Return True if the file at `path` is a readable DICOM file.

    We attempt a light-weight read (stop_before_pixels) and return False on
    InvalidDicomError or other read errors.
    """
    try:
        pydicom.dcmread(path, stop_before_pixels=True)
        return True
    except (InvalidDicomError, Exception):
        return False


def _unique_path(out_dir: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = filename
    i = 1
    while os.path.exists(os.path.join(out_dir, candidate)):
        candidate = f"{base}_{i}{ext}"
        i += 1
    return os.path.join(out_dir, candidate)


def extract_from_zip(
    zip_path: str, out_dir: str, overwrite: bool = False, verbose: bool = False
) -> List[str]:
    """Extract DICOM files from `zip_path` into `out_dir`.

    Returns a list of written file paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    extracted_files: List[str] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        for root, _dirs, files in os.walk(tmpdir):
            for fname in files:
                src = os.path.join(root, fname)
                if is_dicom_file(src):
                    dest = os.path.join(out_dir, fname)
                    if os.path.exists(dest) and not overwrite:
                        dest = _unique_path(out_dir, fname)
                    shutil.copy2(src, dest)
                    extracted_files.append(dest)
                    if verbose:
                        logger.info("Extracted DICOM: %s -> %s", src, dest)
                else:
                    if verbose:
                        logger.debug("Skipping non-DICOM file: %s", src)

    return extracted_files
