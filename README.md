# dicom-exporter

CLI tool to extract DICOM images from exporter DICOM MRI archives (ZIP or ISO format).

## Features

- ✅ **Multi-format support**: Extract from ZIP or ISO archives
- ✅ **Cross-platform**: Pure Python implementation using pycdlib for ISO support
- ✅ **PNG conversion**: Convert DICOM images to PNG with metadata overlay
- ✅ **HTML gallery**: Automatically generated index.html with full-screen viewer
- ✅ **Smart caching**: Skip re-extraction when files already exist
- ✅ **Flexible output**: Optional output directory with sensible defaults

## Installation

### Local Installation (venv)

Requires Python 3.9+. Python 3.13.2 recommended.

```bash
# Create and activate virtual environment
python3.13 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install the package in editable mode
pip install -e .
```

### Docker Installation

```bash
# Build the Docker image
docker build -t dicom-exporter:latest .

# Run using Docker
docker run --rm -v $(pwd)/data:/data dicom-exporter:latest \
  --input-file /data/archive.iso \
  --convert-to-png
```

## Usage

### Basic Extraction

Extract DICOM files from an archive:

```bash
dicom-extract --input-file path/to/archive.zip --output-dir /output/directory
```

### With PNG Conversion

Convert DICOM images to PNG with metadata overlay and generate HTML gallery:

```bash
dicom-extract --input-file path/to/archive.iso --convert-to-png
```

When using `--convert-to-png` without specifying `--output-dir`:
- DICOM files are extracted to: `/tmp/<basename>_iso/` (or `_zip` for ZIP files)
- PNG files are saved to: `<archive_directory>/<basename>_iso_export/`
- HTML gallery is created at: `<png_directory>/index.html`

### All Options

```bash
dicom-extract --input-file <path> [--output-dir <path>] [--convert-to-png] [--overwrite] [-v]
```

#### Required Arguments
- `--input-file PATH`: Path to the ZIP or ISO archive to extract (required)

#### Optional Arguments
- `--output-dir PATH`: Destination directory for extracted DICOM files
  - If omitted, uses system temp directory with name based on input file
  - Example: `/tmp/my_archive_iso/`
- `--convert-to-png`: Convert DICOM files to PNG with metadata overlay
  - Creates PNG files in an export subdirectory
  - Generates an interactive HTML gallery (`index.html`)
  - Metadata overlaid on images: Patient Name, ID, Study Date, Series, Modality, Slice Location, Instance Number
- `--overwrite`: Overwrite existing files in output directory
  - By default, extraction is skipped if output directory already contains files
- `-v, --verbose`: Enable verbose logging (currently enabled by default at INFO level)

## Examples

### Extract ZIP to specific directory
```bash
dicom-extract --input-file scan.zip --output-dir ./extracted_scans
```

### Extract ISO and create PNG gallery
```bash
dicom-extract --input-file patient_scan.iso --convert-to-png
# Creates PNGs in ./patient_scan_iso_export/
# Open ./patient_scan_iso_export/index.html in browser
```

### Force re-extraction and conversion
```bash
dicom-extract --input-file scan.iso --output-dir ./output --convert-to-png --overwrite
```

### Docker Example
```bash
# Extract and convert ISO to PNG gallery
docker run --rm \
  -v /path/to/archives:/data \
  dicom-exporter:latest \
  --input-file /data/scan.iso \
  --convert-to-png
```

## HTML Gallery Features

When using `--convert-to-png`, an interactive HTML gallery is automatically generated:

- **Organized by Series**: Images grouped by series description and number
- **Sorted by Slice**: Within each series, images sorted by slice location
- **Full-Screen Viewer**: Click any image for full-screen view
- **Keyboard Navigation**: 
  - `Escape`: Close viewer
  - `←` / `→`: Navigate between images
- **Visual Navigation**: On-screen buttons for previous/next
- **Metadata Display**: Patient info and image details shown in captions
- **Responsive Design**: Works on desktop and mobile browsers

Simply open `index.html` in any modern web browser to view your DICOM images.

## Output Structure

### Default (no --output-dir specified)
```
/tmp/my_scan_iso/               # Extracted DICOM files
    ├── IM000001.
    ├── IM000002.
    └── ...

/path/to/archive/my_scan_iso_export/  # PNG exports (with --convert-to-png)
    ├── index.html              # Interactive gallery
    ├── IM000001.png
    ├── IM000002.png
    └── ...
```

### With explicit --output-dir
```
/specified/output/dir/          # Extracted DICOM files
    ├── IM000001.
    ├── IM000002.
    └── ...
    └── export/                 # PNG exports (with --convert-to-png)
        ├── index.html          # Interactive gallery
        ├── IM000001.png
        └── ...
```

## Logging

The tool uses Python's logging module. All operations are logged at appropriate levels:
- `INFO`: Extraction progress, file actions (extracted/overwritten/skipped), completion
- `WARNING`: Skipped operations (files exist, no overwrite)
- `ERROR`: Conversion failures, missing pixel data

## Supported Formats

- **Input**: ZIP and ISO archives
- **DICOM Files**: Validated using pydicom
- **Output Images**: PNG format with RGB conversion
- **Metadata**: Extracted from DICOM headers

## Requirements

- Python 3.9+
- pydicom >= 2.3.0
- pycdlib >= 1.0.0 (for ISO support)
- numpy >= 1.24.0 (for image processing)
- Pillow >= 10.0.0 (for PNG generation)

See `requirements.txt` for complete list.

## Troubleshooting

### ISO files not extracting
- Ensure pycdlib is installed: `pip install pycdlib`
- Check that the ISO file is not corrupted

### PNG conversion fails
- Some DICOM files (like DICOMDIR) don't contain pixel data and will be skipped
- Check that numpy and Pillow are installed

### Fonts not rendering on Linux
- Install system fonts: `apt-get install fonts-dejavu-core` (Debian/Ubuntu)

## Development

See `.github/copilot_instructions.md` for detailed development guidelines, including:
- Environment setup
- Testing procedures
- Formatting and linting
- Cross-platform considerations

## License

See LICENSE file for details.
