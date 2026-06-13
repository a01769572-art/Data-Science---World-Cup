"""Tests for the snapshot-only static HTML report renderer (LIVE-03, DOC-02).

These tests freeze the report contract resolved during planning:

* the renderer reads **only** finalized snapshot-local artifacts plus the
  top-level authoritative calibration ledger -- it never fits a model or runs a
  simulation (D-12, T-04-07);
* the rendered HTML carries every required section (D-15): an executive summary
  with mixed KPI + highlighted visual top block (D-16), the next-block matches,
  the tournament probabilities, the temporal evolution, and a methodology note;
* the temporal comparison contrasts the current snapshot against both the
  immediately previous snapshot and the first-ever published snapshot (D-17);
* cumulative model-vs-market log-loss / RPS and a calibration-evolution time
  series are rendered from the canonical ledger (D-22).

A small but realistic frozen snapshot tree is assembled on disk per test (no
business logic), and the renderer is exercised purely against those frozen
files. Tests use the workspace-local `test_workspace` fixture rather than OS
temp dirs (Phase 1 Windows/OneDrive ACL decision).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from cdd_mundial.live import report


# --------------------------------------------------------------------------- #
# Frozen-snapshot fixtures                                                     #
# --------------------------------------------------------------------------- #


def _team_probabilities() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team_id": ["esp", "arg", "fra", "bra"],
            "p_r32": [0.99, 0.98, 0.97, 0.96],
            "p_r16": [0.85, 0.84, 0.80, 0.79],
            "p_qf": [0.60, 0.58, 0.55, 0.52],
            "p_sf": [0.40, 0.38, 0.34, 0.30],
            "p_final": [0.26, 0.24, 0.20, 0.18],
            "p_champion": [0.16, 0.15, 0.12, 0.10],
        }
    )


def _group_positions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "team_id": ["esp", "arg", "fra", "bra"],
            "group": ["A", "A", "B", "B"],
            "p_1st": [0.55, 0.20, 0.50, 0.25],
            "p_2nd": [0.25, 0.35, 0.30, 0.35],
            "p_3rd": [0.15, 0.30, 0.15, 0.30],
            "p_4th": [0.05, 0.15, 0.05, 0.10],
        }
    )


def _upcoming() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ["WC26-010", "WC26-011"],
            "team_a": ["esp", "fra"],
            "team_b": ["arg", "bra"],
            "prob_a": [0.45, 0.50],
            "prob_draw": [0.27, 0.25],
            "prob_b": [0.28, 0.25],
        }
    )


def _frozen_benchmark() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "match_id": ["WC26-010", "WC26-011"],
            "captured_at_utc": ["2026-06-13T18:00:00Z", "2026-06-13T18:00:00Z"],
            "prob_home": [0.46, 0.49],
            "prob_draw": [0.26, 0.26],
            "prob_away": [0.28, 0.25],
        }
    )


def _publication_slice(snapshot_id: str, *, resolved: bool) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "match_id": ["WC26-010", "WC26-011"],
            "snapshot_id": [snapshot_id, snapshot_id],
            "model_version": ["baseline-v1-2026-06-13-aaaaaaa"] * 2,
            "team_a": ["esp", "fra"],
            "team_b": ["arg", "bra"],
            "prob_a": [0.45, 0.50],
            "prob_draw": [0.27, 0.25],
            "prob_b": [0.28, 0.25],
            "market_prob_a": [0.46, 0.49],
            "market_prob_draw": [0.26, 0.26],
            "market_prob_b": [0.28, 0.25],
            "outcome_idx": [0, 2] if resolved else [pd.NA, pd.NA],
        }
    )
    frame["outcome_idx"] = frame["outcome_idx"].astype("Int64")
    return frame


def _write_snapshot(
    root: Path,
    snapshot_id: str,
    *,
    published_at_utc: str,
    resolved: bool = True,
) -> Path:
    """Assemble a frozen snapshot directory exactly like the official run does."""
    snap = root / snapshot_id
    (snap / "report_inputs").mkdir(parents=True)
    _team_probabilities().to_parquet(snap / "team_probabilities.parquet", index=False)
    _group_positions().to_parquet(snap / "group_positions.parquet", index=False)
    _upcoming().to_parquet(snap / "upcoming_match_predictions.parquet", index=False)
    _frozen_benchmark().to_parquet(snap / "frozen_benchmark.parquet", index=False)
    _publication_slice(snapshot_id, resolved=resolved).to_parquet(
        snap / "report_inputs" / "calibration_publication_slice.parquet", index=False
    )
    metadata = {
        "snapshot_id": snapshot_id,
        "published_at_utc": published_at_utc,
        "as_of_date": published_at_utc[:10],
        "model_version": "baseline-v1-2026-06-13-aaaaaaa",
        "n_sims": 10000,
        "seed": 20260613,
        "artifacts": [
            "team_probabilities.parquet",
            "group_positions.parquet",
            "upcoming_match_predictions.parquet",
            "frozen_benchmark.parquet",
            "report_inputs/calibration_publication_slice.parquet",
        ],
    }
    (snap / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return snap


def _write_ledger(path: Path, snapshot_ids: list[str]) -> Path:
    """Write a top-level authoritative calibration ledger with resolved rows."""
    frames = []
    for snapshot_id in snapshot_ids:
        frames.append(_publication_slice(snapshot_id, resolved=True))
    ledger = pd.concat(frames, ignore_index=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    ledger.to_parquet(path, index=False)
    return path


@pytest.fixture
def snapshots_root(test_workspace: Path) -> Path:
    # Short root keeps absolute paths under the Windows MAX_PATH (260) limit when
    # snapshot ids embed the dated model_version (same pitfall as plan 04-02).
    root = test_workspace / "s"
    root.mkdir()
    return root


@pytest.fixture
def three_snapshots(snapshots_root: Path) -> list[str]:
    ids = [
        "2026-06-11T18-00-00Z_v1",  # first ever
        "2026-06-12T18-00-00Z_v1",  # previous
        "2026-06-13T18-00-00Z_v1",  # current
    ]
    _write_snapshot(snapshots_root, ids[0], published_at_utc="2026-06-11T18:00:00Z")
    _write_snapshot(snapshots_root, ids[1], published_at_utc="2026-06-12T18:00:00Z")
    _write_snapshot(snapshots_root, ids[2], published_at_utc="2026-06-13T18:00:00Z")
    return ids


# --------------------------------------------------------------------------- #
# Data-source discipline (T-04-07 / D-12)                                       #
# --------------------------------------------------------------------------- #


def test_renderer_reads_only_snapshot_and_ledger(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    """No model fitting / simulation: the only file inputs are snapshot + ledger."""
    import cdd_mundial.models.dixon_coles as dc
    import cdd_mundial.simulation.engine as engine

    def _boom(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("renderer must not invoke business logic")

    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]

    orig_fit = dc.fit_dixon_coles
    orig_sim = engine.simulate_tournaments
    dc.fit_dixon_coles = _boom  # type: ignore[assignment]
    engine.simulate_tournaments = _boom  # type: ignore[assignment]
    try:
        result = report.render_snapshot_report(
            current, snapshots_root=snapshots_root, ledger_path=ledger
        )
    finally:
        dc.fit_dixon_coles = orig_fit  # type: ignore[assignment]
        engine.simulate_tournaments = orig_sim  # type: ignore[assignment]

    html_path = Path(result["html_path"])
    assert html_path.exists()
    assert html_path.parent == current


def test_render_is_deterministic_markup(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    """Re-rendering the same frozen snapshot yields the same HTML markup."""
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]

    first = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )
    html_a = Path(first["html_path"]).read_text(encoding="utf-8")
    html_b = Path(first["html_path"]).read_text(encoding="utf-8")
    # idempotent re-render into a sibling output dir
    out = test_workspace / "rerender"
    second = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger, output_dir=out
    )
    html_c = Path(second["html_path"]).read_text(encoding="utf-8")
    assert html_a == html_b == html_c


# --------------------------------------------------------------------------- #
# Required sections (D-15) + mixed KPI/visual top block (D-16)                  #
# --------------------------------------------------------------------------- #


def test_html_contains_required_sections(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]
    result = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )
    html = Path(result["html_path"]).read_text(encoding="utf-8")

    for section_id in (
        "executive-summary",
        "next-block",
        "tournament-probabilities",
        "temporal-evolution",
        "methodology",
    ):
        assert f'id="{section_id}"' in html, f"missing section {section_id}"


def test_top_block_mixes_kpis_and_highlighted_visual(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    """D-16: executive top block carries KPI figures AND a highlighted visual asset."""
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]
    result = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )
    html = Path(result["html_path"]).read_text(encoding="utf-8")

    # KPI figures: at least the leading champion probability surfaces as a KPI.
    assert 'class="kpi' in html
    # Highlighted visual: a PNG asset (under assets/) referenced in the HTML.
    names = {Path(p).name for p in result["assets"]}
    assert any(name.endswith(".png") for name in names)
    # PNG assets live in an assets/ subdirectory and are referenced as such.
    assert any(f'src="assets/{name}"' in html for name in names if name.endswith(".png"))
    for asset_path in result["assets"]:
        assert Path(asset_path).parent.name == "assets"


# --------------------------------------------------------------------------- #
# Temporal comparison vs previous AND first snapshot (D-17)                     #
# --------------------------------------------------------------------------- #


def test_temporal_comparison_uses_previous_and_first(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]
    result = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )

    comparison = result["temporal_comparison"]
    assert comparison["previous_snapshot_id"] == three_snapshots[-2]
    assert comparison["first_snapshot_id"] == three_snapshots[0]

    html = Path(result["html_path"]).read_text(encoding="utf-8")
    assert "vs anterior" in html.lower() or "vs previous" in html.lower()
    assert "vs primero" in html.lower() or "vs first" in html.lower()


def test_single_snapshot_has_no_prior_baselines(
    snapshots_root: Path, test_workspace: Path
) -> None:
    """The first-ever snapshot has no previous/first peer -- renderer still works."""
    only_id = "2026-06-11T18-00-00Z_v1"
    _write_snapshot(snapshots_root, only_id, published_at_utc="2026-06-11T18:00:00Z")
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", [only_id]
    )
    current = snapshots_root / only_id
    result = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )
    comparison = result["temporal_comparison"]
    assert comparison["previous_snapshot_id"] is None
    assert comparison["first_snapshot_id"] == only_id
    assert Path(result["html_path"]).exists()


# --------------------------------------------------------------------------- #
# Cumulative model-vs-market metrics + calibration evolution (D-22)            #
# --------------------------------------------------------------------------- #


def test_cumulative_metrics_and_evolution_rendered(
    snapshots_root: Path, three_snapshots: list[str], test_workspace: Path
) -> None:
    ledger = _write_ledger(
        test_workspace / "data" / "calibration_matches.parquet", three_snapshots
    )
    current = snapshots_root / three_snapshots[-1]
    result = report.render_snapshot_report(
        current, snapshots_root=snapshots_root, ledger_path=ledger
    )

    metrics = result["cumulative_metrics"]
    assert metrics["n_matches"] > 0
    assert "log_loss" in metrics["model"] and "rps" in metrics["model"]
    assert "log_loss" in metrics["market"] and "rps" in metrics["market"]

    # A calibration-evolution time-series PNG asset is produced and embedded.
    assets = {Path(p).name for p in result["assets"]}
    assert any("evolution" in name or "calibration" in name for name in assets)

    html = Path(result["html_path"]).read_text(encoding="utf-8")
    assert "log-loss" in html.lower() or "log_loss" in html.lower()
    assert "rps" in html.lower()
