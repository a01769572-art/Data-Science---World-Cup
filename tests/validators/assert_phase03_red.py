"""Validate that selected Phase 3 Wave 0 tests are red for intended missing behavior."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence


RULE_NODES = (
    "tests/test_rules_fifa.py::test_points_gd_gf_order",
    "tests/test_rules_fifa.py::test_head_to_head_subtable",
    "tests/test_rules_fifa.py::test_best_thirds_order",
)
SLOT_NODES = (
    "tests/test_slot_resolution.py::test_official_third_place_mapping_cases",
    "tests/test_slot_resolution.py::test_all_official_combinations_resolve_uniquely",
    "tests/test_slot_resolution.py::test_assignment_respects_slot_tokens",
)
TARGETS = {
    "rules": (RULE_NODES, "cdd_mundial.simulation.rules_fifa"),
    "slots": (SLOT_NODES, "cdd_mundial.simulation.slots"),
}


def _run_expected_red(nodes: Sequence[str], missing_module: str) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            *nodes,
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    output = f"{completed.stdout}\n{completed.stderr}"
    if completed.returncode == 0:
        raise SystemExit(
            f"RED gate unexpectedly passed for {missing_module}; implementation may already exist"
        )

    missing_import = (
        missing_module in output
        and (
            "ModuleNotFoundError" in output
            or "ImportError" in output
            or "cannot import name" in output
        )
    )
    deliberate_placeholder = "NotImplementedError" in output and (
        missing_module in output or any(node.split("::", maxsplit=1)[0] in output for node in nodes)
    )
    if not (missing_import or deliberate_placeholder):
        print(output)
        raise SystemExit(
            f"RED gate failed for an unrelated reason; expected missing {missing_module} behavior"
        )

    print(f"PASS: intended RED state confirmed for {missing_module}")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in {"rules", "slots", "all"}:
        raise SystemExit("usage: assert_phase03_red.py {rules|slots|all}")

    modes = ("rules", "slots") if mode == "all" else (mode,)
    for selected in modes:
        nodes, missing_module = TARGETS[selected]
        _run_expected_red(nodes, missing_module)


if __name__ == "__main__":
    main()
