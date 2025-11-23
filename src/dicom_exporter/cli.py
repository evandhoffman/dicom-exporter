"""Command-line interface for dicom-exporter."""
from __future__ import annotations

import logging
import sys
from typing import Optional

import click

from .extractor import extract_from_zip


@click.command()
@click.argument("zipfile", type=click.Path(exists=True, dir_okay=False))
@click.argument("outdir", type=click.Path(file_okay=False))
@click.option("--overwrite", is_flag=True, help="Overwrite existing files in output dir")
@click.option("-v", "--verbose", is_flag=True, help="Verbose logging")
def main(zipfile: str, outdir: str, overwrite: bool, verbose: bool) -> None:
    """Extract DICOM files from ZIPFILE into OUTDIR.

    Example: dicom-extract archive.zip /tmp/out
    """
    logging.basicConfig(level=(logging.INFO if verbose else logging.WARNING), format="%(message)s")

    extracted = extract_from_zip(zipfile, outdir, overwrite=overwrite, verbose=verbose)
    if extracted:
        click.echo(f"Extracted {len(extracted)} DICOM file(s) to: {outdir}")
        for p in extracted:
            click.echo(f" - {p}")
        sys.exit(0)
    else:
        click.echo("No DICOM files found in archive.", err=True)
        sys.exit(2)


if __name__ == "__main__":
    main()
