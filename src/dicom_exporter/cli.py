"""Command-line interface for dicom-exporter using argparse.

This CLI is intentionally small and uses the standard library `argparse` so
there are no external runtime dependencies for argument parsing.
"""

from __future__ import annotations

import argparse
import logging
import sys
import os
from typing import List

from .extractor import extract_from_zip


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dicom-extract",
        description="Extract DICOM files from a ZIP archive",
    )
    parser.add_argument(
        "--input-file",
        dest="input_file",
        required=True,
        help="Path to exporter input file (ZIP or ISO)",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir",
        required=True,
        help="Destination directory for extracted DICOM files",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in output dir",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    return parser


def main(argv: List[str] | None = None) -> int:
    """Parse args and run the extractor.

    Returns an exit code that can be passed to `sys.exit()` by callers.
    """
    args = build_parser().parse_args(argv)

    logging.basicConfig(
        level=(logging.INFO if args.verbose else logging.WARNING), format="%(message)s"
    )

    # Basic extension check: allow .zip or .iso (case-insensitive)
    ext = os.path.splitext(args.input_file)[1].lower()
    if ext not in (".zip", ".iso"):
        print(
            "Input file must have extension .zip or .iso (case-insensitive)",
            file=sys.stderr,
        )
        return 2

    extracted = extract_from_zip(
        args.input_file, args.output_dir, overwrite=args.overwrite
    )

    if extracted:
        print(f"Extracted {len(extracted)} DICOM file(s) to: {args.output_dir}")
        for p in extracted:
            print(f" - {p}")
        return 0
    else:
        print("No DICOM files found in archive.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
