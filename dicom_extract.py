#!/usr/bin/env python3
"""Standalone entry point for dicom-exporter CLI.

This script can be run directly without installing the package:
    python dicom_extract.py --input-file archive.zip --output-dir output/
"""
import sys
from pathlib import Path

# Add src to path so we can import the package
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from dicom_exporter.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
