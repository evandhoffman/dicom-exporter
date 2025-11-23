# CLAUDE.md - AI Assistant Guide for dicom-exporter

## Project Overview

**dicom-exporter** is a lightweight CLI tool that extracts DICOM medical image files from ZIP archives. It validates files using pydicom, filters for valid DICOM formats, and copies them to a designated output directory with intelligent conflict resolution.

- **Version:** 0.1.0
- **Python:** 3.9+ (target: 3.13.2)
- **Single runtime dependency:** pydicom

## Directory Structure

```
dicom-exporter/
├── src/dicom_exporter/
│   ├── __init__.py      # Package init, version export
│   ├── cli.py           # CLI argument parsing (argparse)
│   └── extractor.py     # Core extraction logic
├── tests/
│   └── test_extractor.py
├── pyproject.toml       # Package config, dependencies
├── requirements.txt     # Dev dependencies
└── .pre-commit-config.yaml
```

## Development Commands

```bash
# Setup environment
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run tests
PYTHONPATH=src python -m pytest -q

# Format code
black src/ tests/

# Type check
mypy --ignore-missing-imports src/

# Run pre-commit hooks
pre-commit run --all-files

# Run CLI
dicom-extract <zipfile> <outdir> [--overwrite] [-v/--verbose]
```

## Code Conventions

### Type Hints
- All functions must have complete type annotations
- Use `from __future__ import annotations` at module top
- Use modern union syntax: `List[str] | None`

### Formatting
- **black** with 88 character line length
- Imports: stdlib first, then third-party, then local

### Logging
- Module-level logger: `logger = logging.getLogger(__name__)`
- Debug for skipped/filtered items, info for successes
- Controlled by `--verbose` flag

### Error Handling
- Graceful degradation - invalid files skipped, not fatal
- Return empty list for "no results" rather than raising
- User-friendly error messages to stderr

### File Operations
- Use `os.path.join()` for cross-platform paths
- `os.makedirs(..., exist_ok=True)` pattern
- `shutil.copy2()` to preserve timestamps
- Temporary directories with context managers

## Architecture

- **cli.py**: Argument parsing only, delegates to extractor
- **extractor.py**: Pure business logic, testable independently
- Clean separation enables easy testing and extension

## Testing

- Framework: pytest
- Use `tmp_path` fixture for filesystem tests
- Create real DICOM files using pydicom's FileDataset API
- No mocking; test with actual filesystem artifacts

## Pre-commit Hooks

1. **black** - Code formatting
2. **mypy** - Type checking
3. **check-yaml** - YAML validation
4. **end-of-file-fixer** - File endings
5. **trailing-whitespace** - Whitespace cleanup

## Key Design Decisions

- **Minimal dependencies**: Only pydicom at runtime, uses stdlib argparse
- **Memory efficient**: `stop_before_pixels=True` for validation
- **Conflict resolution**: Appends `_1`, `_2`, etc. for duplicate filenames
- **Exit codes**: 0 for success, 2 for no files found

## When Making Changes

1. Run `black` and `mypy` before committing
2. Add tests for new functionality
3. Maintain type hints on all functions
4. Keep cli.py thin - business logic goes in extractor.py
5. Use existing logging patterns for consistency
