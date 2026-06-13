from pathlib import Path
import subprocess
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)


@pytest.fixture(scope="module")
def gitignore_lines() -> set[str]:
    return {
        line.strip()
        for line in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }


def test_python_and_tournament_safe_dependency_pins(pyproject: dict) -> None:
    expected = {
        "pandas~=2.3.3",
        "numpy>=2,<2.5",
        "pyarrow>=18",
        "pandera[pandas]~=0.31",
        "kagglehub>=1,<2",
        "requests>=2.32,<3",
        "python-dotenv>=1,<2",
        "scipy~=1.17",
        "scikit-learn~=1.9",
        "matplotlib~=3.10",
        "seaborn==0.13.2",
        "joblib>=1.4",
        "Jinja2>=3.1,<4",
    }
    expected_dev = {
        "pytest>=8,<9",
        "ruff>=0.11,<1",
        "jupyterlab>=4,<5",
        "ipykernel>=6,<7",
        "nbformat>=5,<6",
    }
    assert pyproject["project"]["requires-python"] == ">=3.11,<3.13"
    assert expected == set(pyproject["project"]["dependencies"])
    assert expected_dev == set(pyproject["project"]["optional-dependencies"]["dev"])


def test_pytest_markers_and_ruff_configuration(pyproject: dict) -> None:
    markers = pyproject["tool"]["pytest"]["ini_options"]["markers"]
    assert any(marker.startswith("network:") for marker in markers)
    assert any(marker.startswith("manual:") for marker in markers)
    assert pyproject["tool"]["ruff"]["target-version"] == "py311"
    assert pyproject["tool"]["ruff"]["line-length"] == 100


def test_sensitive_and_generated_paths_are_ignored(gitignore_lines: set[str]) -> None:
    expected = {
        ".env",
        ".venv/",
        ".ipynb_checkpoints/",
        ".pytest-tmp/",
        "pytest-cache-files-*/",
        ".test-artifacts/",
        "data/raw/restricted/",
        "data/raw/odds/",
        # Processed contents are ignored via a globbing pattern so the official
        # snapshot bundles + canonical calibration ledger can be re-included
        # (versioned per D-12/D-18) while transient byproducts stay ignored.
        "data/processed/**",
        "models/",
        "artifacts/",
    }
    assert expected <= gitignore_lines


def test_reference_csvs_and_metadata_manifests_are_allowed(
    gitignore_lines: set[str],
) -> None:
    assert "!data/external/**/*.csv" in gitignore_lines
    assert "!data/metadata/**/*.json" in gitignore_lines


def test_documentation_artifacts_are_tracked_and_secrets_are_not() -> None:
    tracked = set(
        subprocess.run(
            ["git", "ls-files"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.splitlines()
    )
    assert "README.md" in tracked, "DOC-03 requires the portfolio README to be committed"
    assert "notebooks/01_data_foundation.ipynb" in tracked, (
        "DOC-01 requires the didactic Phase 1 notebook to be committed"
    )
    assert ".env" not in tracked
    assert ".env.example" in tracked


def test_env_example_declares_only_an_empty_api_key() -> None:
    lines = [
        line
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert lines == ["ODDS_API_KEY="]
