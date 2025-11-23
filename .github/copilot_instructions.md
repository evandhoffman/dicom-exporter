# Project guidelines for contributors and Copilot

This project is a small CLI that extracts DICOM images from an exporter ZIP archive.
These notes describe the recommended development environment (local venv or Docker),
testing, and coding conventions. They're intended for contributors and for automated
assistants that generate or suggest code.

## Target environment

- Target Python version: 3.13.2 (exact). Use `pyenv` or Docker to ensure the exact runtime
  when building or running in CI.
- The package source is under `src/` so prefer installing the package in editable
  mode or run tests with `PYTHONPATH=src`.

## Run locally (venv)

Recommended workflow for macOS / zsh:

```bash
# create venv using the system or pyenv-installed Python 3.13.2
python3.13 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# run tests
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Notes:
- If `python3.13` is not available, use `pyenv` to install `3.13.2` and run the same
  commands from that interpreter.
- Alternatively, install the package into the venv with `pip install -e .` and call
  the console script `dicom-extract` after activation.

## Run in Docker

Use Docker when you want a portable, reproducible environment. Example `Dockerfile` (suggested base):

```dockerfile
FROM python:3.13.2-slim
WORKDIR /app
COPY pyproject.toml requirements.txt README.md /app/
COPY src/ /app/src/
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt
ENTRYPOINT ["dicom-extract"]
CMD ["--help"]
```

Build and run:

```bash
docker build -t dicom-exporter:latest .
docker run --rm -v $(pwd)/example:/data dicom-exporter:latest /data/archive.zip /data/out
```

Adjust volume mounts and the `ENTRYPOINT` as needed. Using Docker ensures the exact
Python runtime (3.13.2) is used consistently.

## Type hints and static typing

- All new code must include type hints for public functions and methods. Prefer
  explicit return types and argument annotations.
- Use the standard `typing` module (for example `list[str]`, `dict[str, Any]`).
- Run `mypy` (or CI-configured type checker) against `src/` and `tests/` before merging.

Example contract for functions:

- Inputs: typed path-like strings (`str`) or `pathlib.Path` if preferred.
- Outputs: explicit types (for example `list[str]` for a list of file paths).
- Error handling: raise appropriate exceptions or return empty lists for "no result" cases.

## Formatting and linting

- Use `black` for formatting and `isort` for imports. Keep max line length to 88 (black default)
  or follow the project's existing style if different.
- Run `flake8` / `ruff` for linting to catch common issues.
- Consider a `pre-commit` configuration to enforce formatting and basic checks locally.

## Tests

- Tests use `pytest` and are located in `tests/`.
- Prefer small, fast unit tests that don't require large datasets. Use `tmp_path` and
  temporary zip archives for file-based tests.
- Run tests with `PYTHONPATH=src` or by installing the package into the venv.

## CLI and packaging

- The console script entry point is `dicom-extract` (configured via `pyproject.toml`).
- The CLI uses the standard library `argparse` for argument parsing (no external CLI
  dependencies). Keep the CLI thin: parsing, validation, logging, and delegation to
  functions in `src/dicom_exporter/`.

## Logging

- Use the standard library `logging` module for all runtime messages. Do not use
  `print()` for normal program output or diagnostics; reserve `print()` only for
  user-facing output when appropriate. The CLI should configure logging (for
  example via a `--verbose` flag) and libraries should obtain a logger with
  `logger = logging.getLogger(__name__)` and call `logger.debug/info/warning/error`.
- Keep logs at appropriate levels:
  - `DEBUG` for detailed developer-level trace information.
  - `INFO` for high-level progress and successful operations.
  - `WARNING` for recoverable issues.
  - `ERROR` for failures.
- Configure a simple, readable formatter for CLI mode (for example `%(levelname)s: %(message)s`).
- For production or machine-readable logs, consider JSON formatting. Use a
  pluggable handler so the format can be swapped without changing library code.
- When extracting archives or performing file IO, log the following events at
  the indicated levels:
  - `INFO`: start and finish of archive extraction, number of files extracted,
    final output directory.
  - `DEBUG`: temp directory locations, individual files processed, skipped files.
  - `ERROR`: extraction failures, mount failures, permission problems.
- Propagate logging configuration from the CLI; libraries should not call
  `basicConfig()` — only the top-level CLI entry should configure logging.
- Tests should capture logs (pytest `caplog`) when asserting on logging output.


## CI and reproducibility

- CI should pin Python to `3.13.2` (use the official `setup-python` action or Docker image).
- CI tasks should install dependencies, run `mypy` (if enabled), run formatters as checks,
  and run `pytest`.

## Cross-platform support

- Although development will commonly happen on macOS, this project must run
  reliably on Linux and Windows as well, and inside containers. When making
  implementation choices, prefer cross-platform libraries and the Python
  standard library over OS-specific tools.
- Avoid macOS-only commands (for example `hdiutil`) in library code. If ISO
  handling is required on multiple OSes, prefer a pure-Python library such as
  `pycdlib` to read ISO contents programmatically rather than mounting images.
- Use `pathlib.Path` or `os.path` for path operations. Do not hardcode `/tmp`
  in code — use `tempfile.gettempdir()` to locate the system temp directory and
  `os.path.join()` (or `Path`) to construct paths.
- Be mindful of Windows differences: path separators, max path length, case
  sensitivity, and file locking semantics. Use binary-safe file operations and
  ensure tests run on Windows or in a Windows CI runner when possible.
- For temporary extraction directories, follow the deterministic naming
  convention described in the project, but build the path using the system
  temp directory API rather than a literal `/tmp` prefix so it works on all
  platforms.
- Test cross-platform behavior in CI with a matrix that includes at least
  macOS, Ubuntu (or Debian), and Windows runners. Also validate behavior
  inside a Linux container image (Docker) since that is a common deployment
  environment.


## Contribution notes

- When opening a PR, include a brief description of changes and which tests were added
  or updated.
- Prefer small, focused changes. Add unit tests for bug fixes and new behavior.

## Quick checklist for PRs

- [ ] All new public functions/methods have type annotations.
- [ ] New code is formatted with `black` and imports sorted with `isort`.
- [ ] Tests added for new behavior; existing tests pass locally.
- [ ] `pyproject.toml` / `requirements.txt` updated for new dependencies.

---

If you want, I can also add a `Dockerfile`, a basic `mypy.ini`, and a `pre-commit` config as follow-ups.
