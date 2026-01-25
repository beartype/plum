"""Nox setup."""

import sys
from pathlib import Path

import nox
from nox_uv import session

nox.needs_version = ">=2024.3.2"
nox.options.default_venv_backend = "uv"

DIR = Path(__file__).parent.resolve()

# =============================================================================
# Linting


@session(uv_groups=["lint"], reuse_venv=True)
def lint(s: nox.Session, /) -> None:
    """Run the linter."""
    s.notify("precommit")
    s.notify("pylint")


@session(uv_groups=["lint"], reuse_venv=True)
def precommit(s: nox.Session, /) -> None:
    """Run pre-commit."""
    s.run("pre-commit", "run", "--all-files", *s.posargs)


@session(uv_groups=["lint"], reuse_venv=True)
def pylint(s: nox.Session, /) -> None:
    """Run PyLint."""
    s.run("pylint", "src/plum", *s.posargs)


# =============================================================================
# Testing


@session(uv_groups=["test_static", "test_runtime"], reuse_venv=True)
def test(s: nox.Session, /) -> None:
    """Run all tests."""
    s.notify("typecheck")
    s.notify("pytest", posargs=s.posargs)
    s.notify("benchmark", posargs=s.posargs)


@session(uv_groups=["test_static"], reuse_venv=True)
def typecheck(s: nox.Session, /) -> None:
    """Run the type checker."""
    s.run(
        "mypy", "--enable-error-code=no-redef", "src/plum", "tests/static", *s.posargs
    )
    s.run("pyright", "tests/static", *s.posargs)


@session(uv_groups=["test_runtime"], reuse_venv=True)
def pytest(s: nox.Session, /) -> None:
    """Run the unit and regular tests."""
    # Compute from the Python in this `nox`/`uv` environment.
    pragma_version = ".".join(map(str, sys.version_info[:2]))
    s.env["PRAGMA_VERSION"] = pragma_version

    # Run `pytest`.
    s.run("pytest", *s.posargs)


@session(uv_groups=["test_runtime"], reuse_venv=True)
def benchmark(s: nox.Session, /) -> None:
    """Run the benchmarks."""
    s.run("python", "tests/benchmark.py", *s.posargs)
