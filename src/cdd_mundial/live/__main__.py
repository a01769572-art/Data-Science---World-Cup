"""CLI entrypoint for the official daily run: ``python -m cdd_mundial.live``.

The official path is one command (D-07). By default it publishes an append-only
snapshot and fails closed on a dirty worktree (D-11). ``--verify-only`` validates
prerequisites and prints the intended summary (materialization artifact /
fingerprint, model selection, run order) without writing anything. ``--allow-dirty``
only records the dirty override in ``metadata.json`` -- it never hides it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cdd_mundial.live.pipeline import DEFAULT_SEED, DEFAULT_XI, run_official, verify_official
from cdd_mundial.live.results import CANONICAL_RESULTS_PATH


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m cdd_mundial.live",
        description="Run the official daily forecast pipeline and publish a snapshot.",
    )
    parser.add_argument("--results-path", type=Path, default=CANONICAL_RESULTS_PATH)
    parser.add_argument(
        "--fixture-path", type=Path, default=Path("data/external/fixture_2026.csv")
    )
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--snapshots-root", type=Path, default=Path("reports/snapshots"))
    parser.add_argument("--n-sims", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--xi", type=float, default=DEFAULT_XI)
    parser.add_argument(
        "--as-of",
        type=str,
        default=None,
        help="ISO date/time gating completeness; defaults to now (UTC).",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Record (never hide) a dirty-worktree override in metadata.json.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Validate prerequisites and print the intended run without writing artifacts.",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    if args.verify_only:
        summary = verify_official(
            results_path=args.results_path,
            fixture_path=args.fixture_path,
            data_root=args.data_root,
            snapshots_root=args.snapshots_root,
            as_of=args.as_of,
            xi=args.xi,
            allow_dirty=args.allow_dirty,
        )
    else:
        summary = run_official(
            results_path=args.results_path,
            fixture_path=args.fixture_path,
            data_root=args.data_root,
            snapshots_root=args.snapshots_root,
            n_sims=args.n_sims,
            seed=args.seed,
            as_of=args.as_of,
            xi=args.xi,
            allow_dirty=args.allow_dirty,
        )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
