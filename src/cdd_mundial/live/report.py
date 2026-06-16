"""Snapshot-only static HTML report renderer (LIVE-03, DOC-02).

This module turns a *frozen* official snapshot into a publishable static HTML
report. It is the shortest reproducible path from a published snapshot to a
shareable artifact and it obeys one hard discipline (D-12, T-04-07): the
renderer reads **only** finalized snapshot-local parquet/JSON files plus the
top-level authoritative calibration ledger. It never fits a model and never runs
a simulation -- all forecasts were already frozen upstream by ``run_official``.

The rendered report carries the required D-15 sections:

* **executive summary** with a mixed KPI + highlighted-visual top block (D-16),
* the **next block** of unresolved match predictions,
* the **tournament probabilities** (advancement / champion),
* the **temporal evolution** comparing the current snapshot against both the
  immediately previous and the first-ever published snapshot (D-17), together
  with cumulative model-vs-market log-loss / RPS and a calibration-evolution
  time series derived from the canonical ledger (D-22), and
* a short **methodology note**.

Visuals are produced strictly with Matplotlib/Seaborn (project constraint) using
the non-interactive ``Agg`` backend so rendering is headless and deterministic.
Jinja2 templates live under ``templates/`` and carry no business logic.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless, deterministic; no display required.

import json

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from jinja2 import Environment, FileSystemLoader, select_autoescape

from cdd_mundial.live.calibration import cumulative_metrics

# Snapshot-local artifact names (frozen by the official run / calibration plan).
_TEAM_PROBS = "team_probabilities.parquet"
_GROUP_POSITIONS = "group_positions.parquet"
_UPCOMING = "upcoming_match_predictions.parquet"
_FROZEN_BENCHMARK = "frozen_benchmark.parquet"
_PUBLICATION_SLICE = "report_inputs/calibration_publication_slice.parquet"
_METADATA = "metadata.json"

_TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
_DAILY_TEMPLATE = "report_daily.html.jinja"

# How many leading teams (by champion probability) to surface in summary visuals.
_TOP_N = 8

# Deterministic seaborn theme; fixed so re-renders are byte-stable.
_PALETTE = "crest"

# Single point of control for figure resolution (IN-05). Fixed so re-renders of
# the same data produce byte-stable PNGs across all report plots.
_FIG_DPI = 110


# --------------------------------------------------------------------------- #
# Snapshot discovery (read-only over snapshots_root)                          #
# --------------------------------------------------------------------------- #


def _published_at(snapshot_dir: Path) -> str:
    metadata = json.loads((snapshot_dir / _METADATA).read_text(encoding="utf-8"))
    # A missing published_at_utc is a hard error during discovery (IN-04):
    # directory names (<ts>_<model_version>) and ISO instants do not share a
    # sort space, so silently substituting the directory name could order a
    # malformed bundle incorrectly relative to well-formed ones. All official
    # bundles set this field; its absence signals a corrupt/foreign bundle.
    published_at = metadata.get("published_at_utc")
    if published_at is None:
        raise ValueError(
            f"snapshot bundle is missing 'published_at_utc' in metadata: {snapshot_dir}"
        )
    return str(published_at)


def _discover_baselines(
    current: Path, snapshots_root: Path
) -> tuple[Path | None, Path | None]:
    """Return ``(previous_dir, first_dir)`` ordered by published instant (D-17).

    Snapshot directories are enumerated from ``snapshots_root`` (ignoring staging
    dirs that start with a dot); ordering uses each bundle's ``published_at_utc``
    so the comparison baselines are read from frozen metadata, not mutable state
    (T-04-09).
    """
    candidates = [
        d
        for d in snapshots_root.iterdir()
        if d.is_dir() and not d.name.startswith(".") and (d / _METADATA).exists()
    ]
    ordered = sorted(candidates, key=lambda d: (_published_at(d), d.name))
    current_resolved = current.resolve()
    current_at = _published_at(current)

    earlier = [d for d in ordered if (_published_at(d), d.name) < (current_at, current.name)]
    previous = earlier[-1] if earlier else None
    first = ordered[0] if ordered else None
    if first is not None and first.resolve() == current_resolved and not earlier:
        # current IS the first-ever snapshot
        first = current
    return previous, first


# --------------------------------------------------------------------------- #
# Formatting helpers                                                           #
# --------------------------------------------------------------------------- #


def _pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _signed_pct(delta: float) -> str:
    return f"{'+' if delta >= 0 else ''}{delta * 100:.1f} pp"


def _delta_class(delta: float) -> str:
    if delta > 1e-9:
        return "delta-up"
    if delta < -1e-9:
        return "delta-down"
    return ""


# --------------------------------------------------------------------------- #
# Visual assets (matplotlib / seaborn only)                                   #
# --------------------------------------------------------------------------- #


def _champion_barplot(top: pd.DataFrame, out_path: Path, *, title: str) -> Path:
    sns.set_theme(style="whitegrid")
    fig, ax = plt.subplots(figsize=(7.0, 4.0))
    sns.barplot(
        data=top,
        x="p_champion",
        y="team_id",
        hue="team_id",
        palette=_PALETTE,
        legend=False,
        ax=ax,
    )
    ax.set_xlabel("P(Campeon)")
    ax.set_ylabel("")
    ax.set_title(title)
    for container in ax.containers:
        ax.bar_label(container, fmt=lambda v: f"{v * 100:.1f}%", padding=3, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=_FIG_DPI)
    plt.close(fig)
    return out_path


def _evolution_plot(series: pd.DataFrame, out_path: Path) -> Path:
    """Plot cumulative model-vs-market log-loss and RPS across snapshots (D-22)."""
    sns.set_theme(style="whitegrid")
    fig, axes = plt.subplots(1, 2, figsize=(9.0, 3.6))
    for ax, metric, label in ((axes[0], "log_loss", "Log-loss"), (axes[1], "rps", "RPS")):
        ax.plot(series["order"], series[f"model_{metric}"], marker="o", label="Modelo")
        ax.plot(series["order"], series[f"market_{metric}"], marker="s", label="Mercado")
        ax.set_title(f"{label} acumulado")
        ax.set_xlabel("Snapshot (orden)")
        ax.set_ylabel(label)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path, dpi=_FIG_DPI)
    plt.close(fig)
    return out_path


# --------------------------------------------------------------------------- #
# Ledger-derived evolution series                                             #
# --------------------------------------------------------------------------- #


def _evolution_series(ledger: pd.DataFrame) -> pd.DataFrame:
    """Per-snapshot cumulative model/market metrics, ordered by snapshot id.

    The canonical ledger is the single source of truth (D-18/D-22); this is a
    pure derived aggregation -- cumulative metrics are recomputed from base rows
    in published order, never read from a second stored summary.
    """
    snapshot_ids = sorted(ledger["snapshot_id"].dropna().unique())
    rows: list[dict[str, Any]] = []
    seen: list[str] = []
    for order, snapshot_id in enumerate(snapshot_ids, start=1):
        seen.append(snapshot_id)
        cumulative = cumulative_metrics(ledger[ledger["snapshot_id"].isin(seen)])
        if cumulative["n_matches"] == 0 or cumulative["model"] is None:
            continue
        rows.append(
            {
                "order": order,
                "snapshot_id": snapshot_id,
                "model_log_loss": cumulative["model"]["log_loss"],
                "model_rps": cumulative["model"]["rps"],
                "market_log_loss": cumulative["market"]["log_loss"],
                "market_rps": cumulative["market"]["rps"],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Phase 5 model-selection view-model                                          #
# --------------------------------------------------------------------------- #

# Human-readable Spanish labels for the explicit fallback reasons, so the negative
# result is surfaced legibly rather than as an internal token (T-05-12).
_FALLBACK_LABELS = {
    "gate_not_promoted": "El gate no promovio ningun candidato (se mantiene baseline)",
    "ml_ineligible": "Partido inelegible para ML (cobertura insuficiente, D-04)",
    "ml_probability_unavailable": "Sin probabilidad ML disponible para el partido",
}


def _selection_view(selection: dict[str, Any]) -> dict[str, Any]:
    """Turn the raw ``model_selection`` metadata into a legible report view-model.

    Surfaces the upgrade decision (promoted family + dual-publication semantics) or,
    when no candidate cleared the gate, the explicit negative result and why the
    baseline stays live (D-13/D-14, T-05-12).
    """
    promoted = bool(selection.get("promoted", False))
    winner = str(selection.get("winner", "baseline"))
    reasons = selection.get("fallback_reasons", {}) or {}
    fallback_rows = [
        {"reason": _FALLBACK_LABELS.get(key, key), "count": int(count)}
        for key, count in sorted(reasons.items())
    ]
    mean_ll = selection.get("gate_mean_log_loss", {}) or {}
    log_loss_rows = [
        {"candidate": name, "log_loss": f"{float(value):.4f}"}
        for name, value in sorted(mean_ll.items())
    ]
    if promoted:
        headline = (
            f"Upgrade promovido ({winner}): publicacion DUAL baseline + candidato. "
            "El baseline permanece como linea operativa estable."
        )
    else:
        headline = (
            "Sin promocion: ningun candidato vencio al baseline en los cuatro holdouts. "
            "Se publica unicamente el baseline (resultado negativo explicito)."
        )
    return {
        "promoted": promoted,
        "winner": winner,
        "headline": headline,
        "n_baseline_published": int(selection.get("n_baseline_published", 0)),
        "n_upgrade_published": int(selection.get("n_upgrade_published", 0)),
        "n_baseline_fallback": int(selection.get("n_baseline_fallback", 0)),
        "fallback_rows": fallback_rows,
        "log_loss_rows": log_loss_rows,
    }


# --------------------------------------------------------------------------- #
# Public renderer                                                             #
# --------------------------------------------------------------------------- #


def render_snapshot_report(
    snapshot_dir: Path,
    *,
    snapshots_root: Path,
    ledger_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Render a frozen snapshot into a static HTML report plus PNG assets.

    Parameters
    ----------
    snapshot_dir:
        The published snapshot bundle to render (read-only).
    snapshots_root:
        Root holding all published snapshots; used only to locate the previous
        and first-ever snapshots for the temporal comparison (D-17).
    ledger_path:
        Top-level authoritative calibration ledger
        (``calibration_matches.parquet``) for cumulative metrics / evolution.
    output_dir:
        Where to write ``report.html`` and image assets. Defaults to
        ``snapshot_dir`` so the report lives beside the bundle it describes.

    Returns a reference dict with ``html_path``, ``assets``,
    ``temporal_comparison``, and ``cumulative_metrics``.
    """
    snapshot_dir = Path(snapshot_dir)
    snapshots_root = Path(snapshots_root)
    ledger_path = Path(ledger_path)
    out = Path(output_dir) if output_dir is not None else snapshot_dir
    out.mkdir(parents=True, exist_ok=True)
    # Image assets live in an ``assets/`` subdirectory beside ``report.html`` so a
    # published snapshot bundle keeps its visuals grouped (referenced as
    # ``assets/<name>`` in the HTML).
    assets_dir = out / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # --- read ONLY frozen snapshot-local artifacts -------------------------
    metadata = json.loads((snapshot_dir / _METADATA).read_text(encoding="utf-8"))
    advancement = pd.read_parquet(snapshot_dir / _TEAM_PROBS)
    upcoming = pd.read_parquet(snapshot_dir / _UPCOMING)

    advancement_sorted = advancement.sort_values("p_champion", ascending=False).reset_index(
        drop=True
    )
    top = advancement_sorted.head(_TOP_N)

    # --- temporal comparison baselines (read frozen metadata only) ---------
    previous_dir, first_dir = _discover_baselines(snapshot_dir, snapshots_root)
    temporal_comparison = {
        "previous_snapshot_id": previous_dir.name if previous_dir is not None else None,
        "first_snapshot_id": first_dir.name if first_dir is not None else None,
    }

    def _champion_map(directory: Path | None) -> dict[str, float]:
        if directory is None:
            return {}
        frame = pd.read_parquet(directory / _TEAM_PROBS)
        return dict(zip(frame["team_id"], frame["p_champion"], strict=True))

    prev_champ = _champion_map(previous_dir)
    first_champ = (
        _champion_map(first_dir)
        if (first_dir is not None and first_dir.resolve() != snapshot_dir.resolve())
        else {}
    )

    temporal_rows: list[dict[str, Any]] = []
    if prev_champ or first_champ:
        for row in top.itertuples(index=False):
            cur = float(row.p_champion)
            d_prev = cur - prev_champ.get(row.team_id, cur)
            d_first = cur - first_champ.get(row.team_id, cur)
            temporal_rows.append(
                {
                    "team_id": row.team_id,
                    "current": _pct(cur),
                    "delta_prev": _signed_pct(d_prev),
                    "delta_prev_class": _delta_class(d_prev),
                    "delta_first": _signed_pct(d_first),
                    "delta_first_class": _delta_class(d_first),
                }
            )

    # --- cumulative metrics + evolution from the canonical ledger (D-22) ----
    # A snapshot published before any market benchmark exists has no ledger yet;
    # treat that as an empty (no resolved matches) calibration history.
    if ledger_path.exists():
        ledger = pd.read_parquet(ledger_path)
    else:
        ledger = pd.DataFrame(
            columns=[
                "match_id",
                "snapshot_id",
                "model_version",
                "prob_a",
                "prob_draw",
                "prob_b",
                "market_prob_a",
                "market_prob_draw",
                "market_prob_b",
                "outcome_idx",
            ]
        )
    cumulative = cumulative_metrics(ledger)
    evolution = _evolution_series(ledger)

    # --- visuals (matplotlib / seaborn only) -------------------------------
    # Asset references in the HTML are snapshot-relative ``assets/<name>``.
    assets: list[str] = []
    highlight_path = _champion_barplot(
        top, assets_dir / "highlight_champion.png", title="Favoritos al titulo"
    )
    highlight_ref = f"assets/{highlight_path.name}"
    assets.append(highlight_ref)
    champion_path = _champion_barplot(
        top, assets_dir / "tournament_champion.png", title="Probabilidad de campeon"
    )
    champion_ref = f"assets/{champion_path.name}"
    assets.append(champion_ref)

    evolution_ref: str | None = None
    if not evolution.empty:
        evolution_path = _evolution_plot(evolution, assets_dir / "calibration_evolution.png")
        evolution_ref = f"assets/{evolution_path.name}"
        assets.append(evolution_ref)

    # --- KPIs (D-16 mixed KPI + highlighted visual) ------------------------
    leader = advancement_sorted.iloc[0]
    kpis = [
        {"label": "Favorito", "value": str(leader["team_id"]).upper()},
        {"label": "P(Campeon) lider", "value": _pct(float(leader["p_champion"]))},
        {"label": "Partidos proximos", "value": str(len(upcoming))},
        {"label": "Partidos evaluados", "value": str(cumulative["n_matches"])},
    ]

    # --- table view-models -------------------------------------------------
    upcoming_rows = [
        {
            "match_id": r.match_id,
            "team_a": r.team_a,
            "team_b": r.team_b,
            "prob_a": _pct(float(r.prob_a)),
            "prob_draw": _pct(float(r.prob_draw)),
            "prob_b": _pct(float(r.prob_b)),
        }
        for r in upcoming.itertuples(index=False)
    ]
    advancement_rows = [
        {
            "team_id": r.team_id,
            "p_r16": _pct(float(r.p_r16)),
            "p_qf": _pct(float(r.p_qf)),
            "p_sf": _pct(float(r.p_sf)),
            "p_final": _pct(float(r.p_final)),
            "p_champion": _pct(float(r.p_champion)),
        }
        for r in top.itertuples(index=False)
    ]

    def _fmt_block(block: dict[str, float] | None) -> dict[str, str]:
        if not block:
            return {"log_loss": "-", "rps": "-", "brier": "-"}
        return {
            "log_loss": f"{block['log_loss']:.4f}",
            "rps": f"{block['rps']:.4f}",
            "brier": f"{block['brier']:.4f}",
        }

    cumulative_fmt = {
        "model": _fmt_block(cumulative["model"]),
        "market": _fmt_block(cumulative["market"]),
    }

    snapshot_view = {
        "snapshot_id": metadata.get("snapshot_id", snapshot_dir.name),
        "published_at_utc": metadata.get("published_at_utc", ""),
        "as_of_date": metadata.get("as_of_date", ""),
        "model_version": metadata.get("model_version", ""),
        "n_sims": metadata.get("n_sims", ""),
        "seed": metadata.get("seed", ""),
    }

    # --- Phase 5 model-selection block (D-13/D-14, T-05-12) ----------------
    # The upgrade decision (or its absence) must be legible to a reviewer without
    # reading raw artifacts. A snapshot with no ``model_selection`` block is a
    # legacy/baseline-only run; we synthesize an explicit baseline-only summary so
    # the section never silently disappears.
    selection = metadata.get(
        "model_selection",
        {
            "promoted": False,
            "winner": "baseline",
            "n_baseline_published": 0,
            "n_upgrade_published": 0,
            "n_baseline_fallback": 0,
            "fallback_reasons": {},
            "gate_mean_log_loss": {},
        },
    )
    selection_view = _selection_view(selection)

    # --- render ------------------------------------------------------------
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml", "jinja"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = env.get_template(_DAILY_TEMPLATE)
    html = template.render(
        snapshot=snapshot_view,
        kpis=kpis,
        highlight_visual=highlight_ref,
        champion_visual=champion_ref,
        evolution_visual=evolution_ref or "",
        upcoming_rows=upcoming_rows,
        advancement_rows=advancement_rows,
        temporal=temporal_comparison,
        temporal_rows=temporal_rows,
        cumulative=cumulative,
        cumulative_fmt=cumulative_fmt,
        selection=selection_view,
    )

    html_path = out / "report.html"
    html_path.write_text(html, encoding="utf-8", newline="\n")

    return {
        "html_path": str(html_path),
        "assets": [str(out / ref) for ref in assets],
        "temporal_comparison": temporal_comparison,
        "cumulative_metrics": cumulative,
        "model_selection": selection_view,
    }


__all__ = ["render_snapshot_report"]
