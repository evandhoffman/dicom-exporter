# dicom-exporter

CLI tool to extract DICOM images from an exporter DICOM MRI zip file.

Usage
------

After installing dependencies (see `requirements.txt`), run:

```
dicom-extract path/to/archive.zip path/to/output/dir
```

Options:
- `--overwrite` - overwrite existing files in the output directory
- `-v/--verbose` - verbose logging

This tool will extract the zip archive to a temporary location, detect which files are valid DICOM files, and copy those files into the output directory.
