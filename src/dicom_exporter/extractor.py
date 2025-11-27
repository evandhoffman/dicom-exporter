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


def _sanitize_filename(name: str) -> str:
    """Sanitize a string for use in a filename.

    Removes or replaces characters that are invalid in filenames.
    """
    # Replace common problematic characters
    replacements = {
        "/": "-",
        "\\": "-",
        ":": "-",
        "*": "",
        "?": "",
        '"': "",
        "<": "",
        ">": "",
        "|": "-",
        " ": "_",
        "^": "",
    }
    result = str(name)
    for char, replacement in replacements.items():
        result = result.replace(char, replacement)
    # Remove any remaining non-ASCII characters
    result = "".join(c for c in result if c.isalnum() or c in "_-.")
    return result


def generate_png_filename(dicom_path: str, original_filename: str) -> str:
    """Generate a descriptive PNG filename from DICOM metadata.

    Creates filename like:
    {PatientName}_{StudyDate}_{Modality}_{SeriesDescription}_{InstanceNumber}_{original}.png

    Args:
        dicom_path: Path to the DICOM file
        original_filename: Original DICOM filename (used as fallback)

    Returns:
        Generated PNG filename (without directory)
    """
    try:
        ds = pydicom.dcmread(dicom_path, stop_before_pixels=True)

        # Extract metadata components
        patient_name = _sanitize_filename(
            str(getattr(ds, "PatientName", "Unknown"))
        )
        study_date = str(getattr(ds, "StudyDate", "00000000"))
        modality = _sanitize_filename(
            str(getattr(ds, "Modality", "UNK"))
        )
        series_desc = _sanitize_filename(
            str(getattr(ds, "SeriesDescription", "NoSeries"))
        )
        instance_num = int(getattr(ds, "InstanceNumber", 0))

        # Get original base name for reference
        orig_base = os.path.splitext(original_filename)[0]

        # Build descriptive filename
        png_name = (
            f"{patient_name}_{study_date}_{modality}_"
            f"{series_desc}_{instance_num:04d}_{orig_base}.png"
        )
        return png_name

    except Exception as e:
        logger.debug("Could not generate PNG filename from metadata: %s", e)
        # Fall back to original filename
        orig_base = os.path.splitext(original_filename)[0]
        return f"{orig_base}.png"


def convert_dicom_to_png(
    dicom_path: str, png_path: str | None = None, export_dir: str | None = None
) -> str | None:
    """Convert a DICOM file to PNG with metadata overlay.

    Args:
        dicom_path: Path to the DICOM file
        png_path: Full path where the PNG should be saved (optional)
        export_dir: Directory for PNG output; if provided and png_path is None,
                    filename will be auto-generated from DICOM metadata

    Returns:
        Path to saved PNG file if successful, None otherwise
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

        # Determine output path
        if png_path is None and export_dir is not None:
            original_filename = os.path.basename(dicom_path)
            png_filename = generate_png_filename(dicom_path, original_filename)
            png_path = _unique_path(export_dir, png_filename)
        elif png_path is None:
            logger.error("Either png_path or export_dir must be provided")
            return None

        # Save as PNG
        image.save(png_path, "PNG")
        logger.info("Converted to PNG: %s", png_path)
        return png_path

    except Exception as e:
        logger.error("Failed to convert %s to PNG: %s", dicom_path, e)
        return None


def generate_html_index(export_dir: str, dicom_files: List[str]) -> None:
    """Generate an HTML index.html to display all PNG images.

    Args:
        export_dir: Directory containing PNG files
        dicom_files: List of DICOM source file paths
    """
    # Build a map of original DICOM base names to their full paths
    dicom_map = {}
    for dicom_path in dicom_files:
        base_name = os.path.splitext(os.path.basename(dicom_path))[0]
        dicom_map[base_name] = dicom_path

    # Scan export directory for PNG files
    png_files = [f for f in os.listdir(export_dir) if f.endswith(".png")]

    # Collect metadata from DICOM files for each PNG
    image_data = []
    for png_name in png_files:
        # Try to find matching DICOM file
        # PNG names are like: PatientName_StudyDate_0001_IMG0001.png
        # The original filename is the last part before .png
        png_base = os.path.splitext(png_name)[0]

        # Find matching DICOM by checking if original name is in PNG name
        matched_dicom = None
        for orig_base, dicom_path in dicom_map.items():
            if png_base.endswith(f"_{orig_base}"):
                matched_dicom = dicom_path
                break

        if not matched_dicom:
            # Fall back to old naming convention (base_name.png)
            if png_base in dicom_map:
                matched_dicom = dicom_map[png_base]

        if not matched_dicom:
            logger.debug("No DICOM match found for PNG: %s", png_name)
            continue

        try:
            ds = pydicom.dcmread(matched_dicom)
            # Check if file has pixel data
            if not hasattr(ds, "pixel_array"):
                continue

            image_data.append(
                {
                    "filename": png_name,
                    "patient_name": str(getattr(ds, "PatientName", "Unknown")),
                    "patient_id": str(getattr(ds, "PatientID", "N/A")),
                    "study_date": str(getattr(ds, "StudyDate", "N/A")),
                    "series_description": str(
                        getattr(ds, "SeriesDescription", "N/A")
                    ),
                    "series_number": int(getattr(ds, "SeriesNumber", 0)),
                    "modality": str(getattr(ds, "Modality", "N/A")),
                    "slice_location": float(
                        getattr(ds, "SliceLocation", 0.0)
                    ),
                    "instance_number": int(getattr(ds, "InstanceNumber", 0)),
                }
            )
        except Exception as e:
            logger.debug("Skipping %s for HTML index: %s", matched_dicom, e)
            continue

    if not image_data:
        logger.warning("No images found for HTML index generation")
        return

    # Sort by series number, then slice location, then instance number
    image_data.sort(
        key=lambda x: (x["series_number"], x["slice_location"], x["instance_number"])
    )

    # Group by series
    series_groups = {}
    for img in image_data:
        series_key = (img["series_number"], img["series_description"])
        if series_key not in series_groups:
            series_groups[series_key] = []
        series_groups[series_key].append(img)

    # Generate HTML
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DICOM Image Gallery</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        }
        h1 {
            color: #2d3748;
            margin-bottom: 10px;
            font-size: 2.5em;
            text-align: center;
        }
        .patient-info {
            background: #f7fafc;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border-left: 4px solid #667eea;
        }
        .patient-info p {
            margin: 5px 0;
            color: #4a5568;
            font-size: 1.1em;
        }
        .toc {
            background: #f7fafc;
            padding: 25px;
            border-radius: 8px;
            margin-bottom: 30px;
            border-left: 4px solid #764ba2;
        }
        .toc h2 {
            color: #2d3748;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        .toc-series {
            margin-bottom: 15px;
        }
        .toc-series-link {
            display: block;
            color: #667eea;
            font-weight: 600;
            font-size: 1.1em;
            text-decoration: none;
            margin-bottom: 8px;
            transition: color 0.3s;
        }
        .toc-series-link:hover {
            color: #764ba2;
        }
        .toc-images {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-left: 20px;
        }
        .toc-image-link {
            background: white;
            color: #4a5568;
            padding: 5px 12px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.9em;
            border: 1px solid #e2e8f0;
            transition: all 0.3s;
        }
        .toc-image-link:hover {
            background: #667eea;
            color: white;
            border-color: #667eea;
        }
        .series-section {
            margin-bottom: 50px;
            scroll-margin-top: 20px;
        }
        .series-header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 15px 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 1.3em;
            font-weight: 600;
        }
        .image-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 20px;
        }
        .image-card {
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            scroll-margin-top: 20px;
        }
        .image-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 20px rgba(0,0,0,0.2);
        }
        .image-card:target {
            box-shadow: 0 0 0 3px #667eea;
            animation: highlight 2s ease;
        }
        @keyframes highlight {
            0%, 100% { box-shadow: 0 0 0 3px #667eea; }
            50% { box-shadow: 0 0 0 6px #764ba2; }
        }
        .image-card img {
            width: 100%;
            height: 250px;
            object-fit: contain;
            background: #000;
            cursor: pointer;
        }
        .image-caption {
            padding: 15px;
            background: #f7fafc;
        }
        .image-caption p {
            margin: 5px 0;
            font-size: 0.9em;
            color: #4a5568;
        }
        .caption-label {
            font-weight: 600;
            color: #2d3748;
        }
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100vw;
            height: 100vh;
            background-color: rgba(40,40,40,0.98);
            animation: fadeIn 0.3s;
            align-items: center;
            justify-content: center;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .modal-content {
            position: relative;
            max-width: 95vw;
            max-height: 95vh;
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        .modal-content img {
            max-width: 95vw;
            max-height: 90vh;
            object-fit: contain;
            border-radius: 8px;
        }
        .modal-caption {
            color: white;
            padding: 15px;
            font-size: 1.2em;
            text-align: center;
        }
        .close {
            position: fixed;
            top: 20px;
            right: 40px;
            color: #fff;
            font-size: 50px;
            font-weight: bold;
            cursor: pointer;
            z-index: 1002;
            transition: color 0.3s;
        }
        .close:hover {
            color: #667eea;
        }
        .nav-button {
            position: fixed;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255,255,255,0.1);
            color: white;
            border: 2px solid rgba(255,255,255,0.3);
            font-size: 40px;
            padding: 20px 25px;
            cursor: pointer;
            z-index: 1002;
            transition: all 0.3s;
            border-radius: 8px;
        }
        .nav-button:hover {
            background: rgba(102,126,234,0.8);
            border-color: #667eea;
        }
        .nav-button.prev {
            left: 20px;
        }
        .nav-button.next {
            right: 20px;
        }
        .stats {
            text-align: center;
            padding: 20px;
            background: #f7fafc;
            border-radius: 8px;
            margin-top: 30px;
        }
        .stats p {
            font-size: 1.1em;
            color: #4a5568;
            margin: 5px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏥 DICOM Image Gallery</h1>
"""

    # Add patient info
    if image_data:
        first_img = image_data[0]
        html += f"""
        <div class="patient-info">
            <p><span class="caption-label">Patient:</span> {first_img['patient_name']}</p>
            <p><span class="caption-label">Patient ID:</span> {first_img['patient_id']}</p>
            <p><span class="caption-label">Study Date:</span> {first_img['study_date']}</p>
            <p><span class="caption-label">Modality:</span> {first_img['modality']}</p>
        </div>
"""

    # Add table of contents
    html += """
        <div class="toc">
            <h2>📋 Table of Contents</h2>
"""
    for (series_num, series_desc), images in sorted(series_groups.items()):
        series_id = f"series-{series_num}"
        html += f"""
            <div class="toc-series">
                <a href="#{series_id}" class="toc-series-link">
                    Series {series_num}: {series_desc} ({len(images)} images)
                </a>
                <div class="toc-images">
"""
        for img in images:
            img_id = f"img-{img['filename'].replace('.png', '')}"
            html += f"""
                    <a href="#{img_id}" class="toc-image-link">
                        Slice {img['slice_location']:.1f} (#{img['instance_number']})
                    </a>
"""
        html += """
                </div>
            </div>
"""
    html += """
        </div>
"""

    # Add series sections
    for (series_num, series_desc), images in sorted(series_groups.items()):
        series_id = f"series-{series_num}"
        html += f"""
        <div class="series-section" id="{series_id}">
            <div class="series-header">
                Series {series_num}: {series_desc} ({len(images)} images)
            </div>
            <div class="image-grid">
"""
        for img in images:
            img_id = f"img-{img['filename'].replace('.png', '')}"
            html += f"""
                <div class="image-card" id="{img_id}">
                    <img src="{img['filename']}" alt="Slice {img['slice_location']}" 
                         onclick="openModal('{img['filename']}')" />
                    <div class="image-caption">
                        <p><span class="caption-label">Instance:</span> {img['instance_number']}</p>
                        <p><span class="caption-label">Slice Location:</span> {img['slice_location']:.2f}</p>
                    </div>
                </div>
"""
        html += """
            </div>
        </div>
"""

    # Add stats
    html += f"""
        <div class="stats">
            <p><span class="caption-label">Total Images:</span> {len(image_data)}</p>
            <p><span class="caption-label">Series Count:</span> {len(series_groups)}</p>
        </div>
    </div>

    <!-- Modal for full-size image -->
    <div id="imageModal" class="modal" onclick="event.target === this && closeModal()">
        <span class="close" onclick="closeModal()">&times;</span>
        <button class="nav-button prev" onclick="navigateImage(-1); event.stopPropagation();">&#10094;</button>
        <button class="nav-button next" onclick="navigateImage(1); event.stopPropagation();">&#10095;</button>
        <div class="modal-content">
            <img id="modalImage" src="" alt="Full size image" onclick="event.stopPropagation();">
            <div class="modal-caption" id="modalCaption"></div>
        </div>
    </div>

    <script>
        const allImages = [{', '.join([f'"{img["filename"]}"' for img in image_data])}];
        let currentImageIndex = 0;

        function openModal(imageSrc) {{
            currentImageIndex = allImages.indexOf(imageSrc);
            document.getElementById('imageModal').style.display = 'flex';
            showImage(currentImageIndex);
        }}

        function closeModal() {{
            document.getElementById('imageModal').style.display = 'none';
        }}

        function navigateImage(direction) {{
            currentImageIndex = (currentImageIndex + direction + allImages.length) % allImages.length;
            showImage(currentImageIndex);
        }}

        function showImage(index) {{
            const img = allImages[index];
            document.getElementById('modalImage').src = img;
            document.getElementById('modalCaption').innerHTML = `Image ${{index + 1}} of ${{allImages.length}}`;
        }}

        // Keyboard navigation
        document.addEventListener('keydown', function(event) {{
            const modal = document.getElementById('imageModal');
            if (modal.style.display === 'flex') {{
                if (event.key === 'Escape') {{
                    closeModal();
                }} else if (event.key === 'ArrowLeft') {{
                    navigateImage(-1);
                }} else if (event.key === 'ArrowRight') {{
                    navigateImage(1);
                }}
            }}
        }});
    </script>
</body>
</html>
"""

    # Write HTML file
    index_path = os.path.join(export_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)

    logger.info("Generated HTML index: %s", index_path)


def extract_from_archive(
    input_path: str,
    out_dir: str,
    overwrite: bool = False,
    convert_to_png: bool = False,
    png_export_dir: str | None = None,
) -> List[str]:
    """Extract DICOM files from a ZIP or ISO archive into `out_dir`.

    The archive is first extracted to a deterministic temp directory under the
    system temp dir (for example `/tmp/<base>_zip/` or `/tmp/<base>_iso/`). The
    extracted tree is then scanned and DICOM files are copied into `out_dir`.

    If the output directory already contains files and overwrite=False, the
    extraction is skipped entirely.

    Args:
        input_path: Path to ZIP or ISO file
        out_dir: Directory where DICOM files will be extracted
        overwrite: If True, overwrite existing files
        convert_to_png: If True, convert DICOM files to PNG with metadata overlay
        png_export_dir: Custom directory for PNG export (default: out_dir/export)

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
            # If PNG conversion is requested, check if we need to convert
            if convert_to_png:
                if png_export_dir:
                    export_dir = png_export_dir
                else:
                    export_dir = os.path.join(out_dir, "export")
                # Check if export dir exists and has PNG files
                if os.path.exists(export_dir):
                    existing_pngs = set(
                        os.path.splitext(f)[0]
                        for f in os.listdir(export_dir)
                        if f.endswith(".png")
                    )
                    # Check if all DICOM files have corresponding PNGs
                    need_conversion = []
                    for fname in existing_files:
                        base_name = os.path.splitext(fname)[0]
                        if base_name not in existing_pngs:
                            src = os.path.join(out_dir, fname)
                            if is_dicom_file(src):
                                # Check if file has pixel data before adding
                                try:
                                    ds = pydicom.dcmread(src)
                                    if hasattr(ds, "pixel_array"):
                                        need_conversion.append(fname)
                                except Exception:
                                    pass
                    
                    if not need_conversion:
                        logger.warning(
                            "Output directory already contains %d file(s) "
                            "with %d PNG(s); skipping: %s",
                            len(existing_files),
                            len(existing_pngs),
                            out_dir,
                        )
                        # Regenerate HTML index even when skipping
                        existing_paths = [
                            os.path.join(out_dir, f) for f in existing_files
                        ]
                        generate_html_index(export_dir, existing_paths)
                        return existing_paths
                    
                    # Convert missing PNGs only
                    logger.info(
                        "Converting %d missing PNG file(s)",
                        len(need_conversion),
                    )
                    for fname in need_conversion:
                        src = os.path.join(out_dir, fname)
                        convert_dicom_to_png(src, export_dir=export_dir)
                    
                    # Generate HTML index
                    existing_paths = [os.path.join(out_dir, f) for f in existing_files]
                    generate_html_index(export_dir, existing_paths)
                    return existing_paths
                
                # Export dir doesn't exist, convert all files
                logger.info(
                    "DICOM files exist but PNG conversion needed, "
                    "converting %d file(s)",
                    len(existing_files),
                )
                os.makedirs(export_dir, exist_ok=True)
                for fname in existing_files:
                    src = os.path.join(out_dir, fname)
                    if is_dicom_file(src):
                        convert_dicom_to_png(src, export_dir=export_dir)
                
                # Generate HTML index
                existing_paths = [os.path.join(out_dir, f) for f in existing_files]
                generate_html_index(export_dir, existing_paths)
                return existing_paths
            else:
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
        if png_export_dir:
            export_dir = png_export_dir
        else:
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
                    convert_dicom_to_png(dest, export_dir=export_dir)

            else:
                logger.debug("Skipping non-DICOM file: %s", src)

    # Generate HTML index if PNGs were created
    if convert_to_png and export_dir and extracted_files:
        generate_html_index(export_dir, extracted_files)

    return extracted_files


# Backwards compatible alias
extract_from_zip = extract_from_archive
