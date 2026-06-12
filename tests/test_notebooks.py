"""Structural pedagogy and hygiene gates for project notebooks (DOC-01).

Every notebook in ``notebooks/`` must follow the mandatory didactic contract:
markdown cell containing ``What and why`` -> code cell -> markdown cell containing
``Interpretation``. Notebooks read canonical artifacts and import production
functions from ``cdd_mundial.data``; they never redefine ingestion logic.
"""

import json
import re
from pathlib import Path

import nbformat
import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOKS_DIR = ROOT / "notebooks"
PHASE1_NOTEBOOK = NOTEBOOKS_DIR / "01_data_foundation.ipynb"

WHAT_AND_WHY = "What and why"
INTERPRETATION = "Interpretation"

# Literal secret assignments only: the value must be one contiguous token-like
# string (real credentials have no spaces) and must not be an environment-variable
# reference placeholder such as %VAR%, $VAR, or ${VAR}.
SECRET_PATTERNS = (
    re.compile(
        r"(?i)\b(api[_-]?key|apikey|secret|token|passwd|password)\b"
        r"\s*[:=]\s*[\"'](?![%$])[A-Za-z0-9_\-./+=]{8,}[\"']"
    ),
    re.compile(r"(?i)bearer\s+[a-z0-9_\-.]{16,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
)

REQUIRED_PHASE1_HEADINGS = (
    "objetivo",
    "procedencia",
    "identidades",
    "martj42",
    "neutrales",
    "elo",
    "fixture",
    "cuotas",
    "conclusiones",
)

FORBIDDEN_CODE_FRAGMENTS = (
    "def ",  # didactic cells must not define functions; logic lives in src/
    "class ",
    "import requests",
    "import kagglehub",
    "os.environ",
)


def project_notebooks() -> list[Path]:
    return sorted(NOTEBOOKS_DIR.glob("*.ipynb"))


def read_notebook(path: Path) -> nbformat.NotebookNode:
    return nbformat.read(path, as_version=4)


def assert_didactic_structure(notebook: nbformat.NotebookNode, name: str) -> None:
    """Enforce markdown(What and why) -> code -> markdown(Interpretation)."""
    cells = notebook.cells
    for index, cell in enumerate(cells):
        if cell.cell_type != "code":
            continue
        assert index > 0 and cells[index - 1].cell_type == "markdown", (
            f"{name}: code cell {index} lacks an immediately preceding markdown cell"
        )
        assert WHAT_AND_WHY in cells[index - 1].source, (
            f"{name}: markdown before code cell {index} must contain {WHAT_AND_WHY!r}"
        )
        assert index + 1 < len(cells) and cells[index + 1].cell_type == "markdown", (
            f"{name}: code cell {index} lacks an immediately following markdown cell"
        )
        assert INTERPRETATION in cells[index + 1].source, (
            f"{name}: markdown after code cell {index} must contain {INTERPRETATION!r}"
        )


def test_phase1_notebook_exists() -> None:
    assert PHASE1_NOTEBOOK.exists(), "DOC-01 requires notebooks/01_data_foundation.ipynb"


@pytest.mark.parametrize("path", project_notebooks(), ids=lambda path: path.name)
def test_notebook_has_no_empty_code_cells(path: Path) -> None:
    notebook = read_notebook(path)
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type == "code":
            assert cell.source.strip(), f"{path.name}: code cell {index} is empty"


@pytest.mark.parametrize("path", project_notebooks(), ids=lambda path: path.name)
def test_notebook_alternates_explanation_code_interpretation(path: Path) -> None:
    assert_didactic_structure(read_notebook(path), path.name)


@pytest.mark.parametrize("path", project_notebooks(), ids=lambda path: path.name)
def test_notebook_contains_no_secret_material(path: Path) -> None:
    """Sources AND rendered outputs must be free of secret-looking assignments."""
    serialized = json.dumps(json.loads(path.read_text(encoding="utf-8")))
    for pattern in SECRET_PATTERNS:
        match = pattern.search(serialized)
        assert match is None, (
            f"{path.name}: secret-looking content matches pattern {pattern.pattern!r}"
        )


def test_phase1_notebook_imports_production_package() -> None:
    notebook = read_notebook(PHASE1_NOTEBOOK)
    code = "\n".join(cell.source for cell in notebook.cells if cell.cell_type == "code")
    assert re.search(r"from\s+cdd_mundial\.data", code), (
        "the Phase 1 notebook must import production functions from cdd_mundial.data"
    )


def test_phase1_notebook_does_not_redefine_ingestion_logic() -> None:
    notebook = read_notebook(PHASE1_NOTEBOOK)
    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue
        for fragment in FORBIDDEN_CODE_FRAGMENTS:
            assert fragment not in cell.source, (
                f"code cell {index} contains forbidden fragment {fragment!r}; "
                "ingestion logic belongs in src/cdd_mundial/data"
            )


def test_phase1_notebook_has_required_section_headings() -> None:
    notebook = read_notebook(PHASE1_NOTEBOOK)
    headings = "\n".join(
        line.lower()
        for cell in notebook.cells
        if cell.cell_type == "markdown"
        for line in cell.source.splitlines()
        if line.startswith("#")
    )
    for keyword in REQUIRED_PHASE1_HEADINGS:
        assert keyword in headings, f"missing section heading containing {keyword!r}"


def test_phase1_notebook_uses_a_deterministic_python_kernel() -> None:
    notebook = read_notebook(PHASE1_NOTEBOOK)
    kernelspec = notebook.metadata.get("kernelspec", {})
    assert kernelspec.get("name") == "python3"
    assert kernelspec.get("language") == "python"
