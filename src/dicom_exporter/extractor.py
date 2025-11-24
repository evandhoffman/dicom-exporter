"""Extraction logic for exporter DICOM MRI archives (ZIP or ISO).

This module extracts an archive (ZIP or ISO) to a deterministic temporary
directory under the system temp dir (for example `/tmp/file_abc_zip/`), scans
the extracted tree for valid DICOM files and copies those files into the
provided output directory.

Extraction preserves the archive's internal directory structure. If the target
temporary extraction directory already exists, it will be skipped unless
`overwrite=True` is provided.
"""

from __future__ import annotations

import logging
import os
import shutil
import tempfile
import zipfile
from typing import List, Tuple

import numpy as np
import pycdlib
import pydicom
from PIL import Image, ImageDraw, ImageFont
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


def convert_dicom_to_png(dicom_path: str, png_path: str) -> bool:
    """Convert a DICOM file to PNG with metadata overlay.

    Args:
        dicom_path: Path to the DICOM file
        png_path: Path where the PNG should be saved

    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Read the DICOM file
        ds = pydicom.dcmread(dicom_path)

        # Get pixel array and normalize to 0-255
        pixel_array = ds.pixel_array

        # Normalize the image data
        pixel_array = pixel_array.astype(float)
        pixel_array = (
            (pixel_array - pixel_array.min())
            / (pixel_array.max() - pixel_array.min())
            * 255.0
        )
        pixel_array = pixel_array.astype(np.uint8)

        # Convert to PIL Image
        image = Image.fromarray(pixel_array)

        # Convert to RGB to allow colored text overlay
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Create drawing context
        draw = ImageDraw.Draw(image)

        # Try to use a reasonable font, fall back to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
        except Exception:
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
                )
            except Exception:
                font = ImageFont.load_default()

        # Collect metadata to overlay
        metadata_lines = []

        # Add key DICOM metadata
        metadata_fields = [
            ("PatientName", "Patient"),
            ("PatientID", "ID"),
            ("StudyDate", "Study Date"),
            ("SeriesDescription", "Series"),
            ("Modality", "Modality"),
            ("SliceLocation", "Slice"),
            ("InstanceNumber", "Instance"),
        ]

        for dicom_tag, label in metadata_fields:
            if hasattr(ds, dicom_tag):
                value = getattr(ds, dicom_tag)
                if value:
                    metadata_lines.append(f"{label}: {value}")

        # Draw metadata on the image
        y_offset = 10
        for line in metadata_lines:
            draw.text((10, y_offset), line, fill=(255, 255, 0), font=font)
            y_offset += 15

        # Save as PNG
        image.save(png_path, "PNG")
        logger.info("Converted to PNG: %s", png_path)
        return True

    except Exception as e:
        logger.error("Failed to convert %s to PNG: %s", dicom_path, e)
        return False


def extract_from_archive(
    input_path: str, out_dir: str, overwrite: bool = False, convert_to_png: bool = False
) -> List[str]:
    """Extract DICOM files from a ZIP or ISO archive into `out_dir`.

    The archive is first extracted to a deterministic temp directory under the
    system temp dir (for example `/tmp/<base>_zip/` or `/tmp/<base>_iso/`). The
    extracted tree is then scanned and DICOM files are copied into `out_dir`.

    If the output directory already contains files and overwrite=False, the
    extraction is skipped entirely.

    Returns a list of written file paths.
    """
    os.makedirs(out_dir, exist_ok=True)
    extracted_files: List[str] = []

    # Check if output directory already has content
    if not overwrite and os.path.exists(out_dir):
        existing_files = [
            f for f in os.listdir(out_dir) if os.path.isfile(os.path.join(out_dir, f))
        ]
        if existing_files:
            logger.warning(
                "Output directory already contains %d file(s) and "
                "overwrite=False; skipping extraction: %s",
                len(existing_files),
                out_dir,
            )
            # Return the existing files
            return [os.path.join(out_dir, f) for f in existing_files]

    base = os.path.splitext(os.path.basename(input_path))[0]
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".zip":
        tmpdir = os.path.join(tempfile.gettempdir(), f"{base}_zip")
    else:
        tmpdir = os.path.join(tempfile.gettempdir(), f"{base}_iso")

    logger.debug("Extraction target temporary directory: %s", tmpdir)

    # If tmpdir exists and overwrite is False, skip extraction step.
    if os.path.exists(tmpdir):
        if overwrite:
            logger.info("Overwriting existing temp dir: %s", tmpdir)
            shutil.rmtree(tmpdir)
            os.makedirs(tmpdir, exist_ok=True)
        else:
            logger.info(
                "Temp dir already exists and overwrite=False; skipping extraction: %s",
                tmpdir,
            )
    else:
        os.makedirs(tmpdir, exist_ok=True)

    # Perform extraction if tmpdir is empty (or was just recreated)
    if ext == ".zip":
        logger.info("Extracting ZIP archive %s -> %s", input_path, tmpdir)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(tmpdir)
    elif ext == ".iso":
        logger.info("Extracting ISO archive %s -> %s", input_path, tmpdir)
        iso = pycdlib.PyCdlib()
        try:
            iso.open(input_path)

            def _extract_iso_dir(
                iso_obj: pycdlib.PyCdlib,
                iso_path: str,
                out_path: str,
                path_type: str = "iso_path",
            ) -> None:
                """
                Recursively extract directory from ISO.
                path_type can be 'iso_path', 'joliet_path', or 'rr_name'
                """
                try:
                    # List children using the specified path type
                    if path_type == "joliet_path":
                        children = iso_obj.list_children(joliet_path=iso_path)
                    elif path_type == "rr_name":
                        children = iso_obj.list_children(rr_name=iso_path)
                    else:
                        children = iso_obj.list_children(iso_path=iso_path)
                except Exception as e:
                    logger.error(
                        "pycdlib failed to list children for %s (type=%s): %s",
                        iso_path,
                        path_type,
                        e,
                    )
                    return

                for child in children:
                    # child may be a PyCdlibDirectoryRecord
                    try:
                        fid = child.file_identifier().decode("utf-8")
                    except Exception:
                        fid = str(child)
                    # Skip '.' and '..' entries
                    if fid in (".", ".."):
                        continue
                    name = fid.rstrip(";1")
                    src_iso_path = os.path.join(iso_path, fid)
                    dst = os.path.join(out_path, name)
                    if getattr(child, "is_dir", lambda: False)():
                        os.makedirs(dst, exist_ok=True)
                        _extract_iso_dir(iso_obj, src_iso_path, dst, path_type)
                    else:
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with open(dst, "wb") as f:
                            try:
                                # Use the same path type for extraction
                                if path_type == "joliet_path":
                                    iso_obj.get_file_from_iso_fp(
                                        f, joliet_path=src_iso_path
                                    )
                                elif path_type == "rr_name":
                                    iso_obj.get_file_from_iso_fp(
                                        f, rr_name=src_iso_path
                                    )
                                else:
                                    iso_obj.get_file_from_iso_fp(
                                        f, iso_path=src_iso_path
                                    )
                            except Exception as exc:
                                logger.error(
                                    "Failed to extract %s from ISO: %s",
                                    src_iso_path,
                                    exc,
                                )

            # Start extraction at root - detect which path type to use
            # Try in order: ISO9660, Joliet, Rock Ridge
            path_type = "iso_path"
            for test_type in ["iso_path", "joliet_path", "rr_name"]:
                try:
                    if test_type == "joliet_path":
                        iso.list_children(joliet_path="/")
                    elif test_type == "rr_name":
                        iso.list_children(rr_name="/")
                    else:
                        iso.list_children(iso_path="/")
                    path_type = test_type
                    logger.debug("Using ISO path type: %s", path_type)
                    break
                except Exception:
                    continue

            _extract_iso_dir(iso, "/", tmpdir, path_type)
        finally:
            iso.close()
    else:
        raise ValueError("Unsupported archive type: %s" % ext)

    # Create export subdirectory if converting to PNG
    export_dir = None
    if convert_to_png:
        export_dir = os.path.join(out_dir, "export")
        os.makedirs(export_dir, exist_ok=True)
        logger.info("Created export directory: %s", export_dir)

    # Walk the extracted tree and copy DICOM files into out_dir
    for root, _dirs, files in os.walk(tmpdir):
        for fname in files:
            src = os.path.join(root, fname)
            if is_dicom_file(src):
                rel_path = os.path.relpath(src, tmpdir)
                dest = os.path.join(out_dir, os.path.basename(rel_path))

                # Determine action: extracted, overwritten, or skipped
                if os.path.exists(dest):
                    if overwrite:
                        shutil.copy2(src, dest)
                        extracted_files.append(dest)
                        logger.info("Overwritten: %s", dest)
                    else:
                        # File exists, find unique name
                        dest = _unique_path(out_dir, os.path.basename(rel_path))
                        shutil.copy2(src, dest)
                        extracted_files.append(dest)
                        logger.info("Extracted (renamed): %s", dest)
                else:
                    shutil.copy2(src, dest)
                    extracted_files.append(dest)
                    logger.info("Extracted: %s", dest)

                # Convert to PNG if requested
                if convert_to_png and export_dir:
                    base_name = os.path.splitext(os.path.basename(dest))[0]
                    png_path = os.path.join(export_dir, f"{base_name}.png")
                    convert_dicom_to_png(dest, png_path)

            else:
                logger.debug("Skipping non-DICOM file: %s", src)

    return extracted_files


# Backwards compatible alias
extract_from_zip = extract_from_archive
