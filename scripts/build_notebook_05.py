"""Build and execute notebooks/05_ml_ensemble.ipynb deterministically.

This generator assembles the Phase-5 didactic notebook (markdown What-and-why ->
code -> markdown Interpretation), executes every code cell *in-process* (no Jupyter
kernel required, since jupyter_client is unavailable in this venv), captures real
outputs (stdout streams, the last-expression text result, and matplotlib PNGs), and
writes the .ipynb with non-empty deterministic outputs.

The notebook imports only production APIs (cdd_mundial.models / cdd_mundial.live) and
runs on a small synthetic-but-realistic dataset so it is fast and reproducible, while
exercising the real feature builder, ML candidate, calibration, ensemble comparison,
promotion gate, and the live dual-publication decision.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path
import sys
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import nbformat  # noqa: E402
from nbformat.v4 import (  # noqa: E402
    new_code_cell,
    new_markdown_cell,
    new_notebook,
    new_output,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks" / "05_ml_ensemble.ipynb"

# (markdown_what_and_why, code, markdown_interpretation) triples. Every code cell is
# flanked by the mandatory didactic markdown (DOC-01). Code cells never define
# functions/classes (logic lives in src/); they orchestrate production APIs only.
CELLS: list[tuple[str, str, str]] = [
    (
        "## Importaciones y APIs de produccion (What and why)\n\n"
        "Importamos las APIs de Phase 5 desde `cdd_mundial.models` (dataset de features, "
        "candidato ML, comparacion calibrada con gate) y de `cdd_mundial.live` "
        "(`build_dual_publication`, la decision por partido baseline/upgrade/fallback). "
        "Toda la logica vive en `src/`; el notebook solo orquesta y narra.",
        "import numpy as np\n"
        "import pandas as pd\n"
        "import matplotlib.pyplot as plt\n"
        "\n"
        "from cdd_mundial.models import build_ml_dataset, ML_FEATURE_COLUMNS\n"
        "from cdd_mundial.models import run_ml_comparison, evaluate_ml_gate\n"
        "from cdd_mundial.live import build_dual_publication\n"
        "\n"
        "print('features ML v1:', len(ML_FEATURE_COLUMNS))\n"
        "print(list(ML_FEATURE_COLUMNS))",
        "**Interpretation.** Quedan disponibles las cuatro piezas de la fase: el "
        "contrato de 12 features point-in-time, el harness de comparacion calibrada con "
        "gate, y la capa de seleccion live. El conteo confirma el set fijo de D-02.",
    ),
    (
        "## Tabla de features ML v1 (What and why)\n\n"
        "Construimos un historico sintetico reproducible y lo pasamos por "
        "`build_ml_dataset`, el mismo builder point-in-time que usan los backtests. "
        "Cada fila trae el target 3-way canonico, metadatos de elegibilidad (D-04) y las "
        "12 features en unidades naturales. Asi auditamos el contrato de datos sin tocar "
        "el parquet productivo.",
        "rng = np.random.default_rng(20260616)\n"
        "teams = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot']\n"
        "pairs = [(a, b) for a in teams for b in teams if a < b]\n"
        "# Holdouts evaluados (tournament, year, mes de disputa) -> el harness los\n"
        "# selecciona por nombre y year exactos; los demas meses son historia 'Friendly'.\n"
        "holdout_blocks = [('FIFA World Cup', 2018, 6), ('FIFA World Cup', 2022, 11),\n"
        "                  ('UEFA Euro', 2024, 6), ('Copa Am\\u00e9rica', 2024, 7)]\n"
        "rows = []\n"
        "idx = 0\n"
        "# Historia previa abundante (2010-2025) para garantizar elegibilidad (>=5 previos).\n"
        "for year in range(2010, 2026):\n"
        "    for month in (2, 3, 9):\n"
        "        for k, (home, away) in enumerate(pairs):\n"
        "            rows.append({'match_id': f'F-{idx:05d}',\n"
        "                'date': f'{year}-{month:02d}-{1 + k:02d}',\n"
        "                'home_team_id': home, 'away_team_id': away,\n"
        "                'home_team_source_name': home.title(), 'away_team_source_name': away.title(),\n"
        "                'home_score': int(rng.integers(0, 4)), 'away_score': int(rng.integers(0, 4)),\n"
        "                'tournament': 'Friendly', 'city': 'Town', 'country': 'Nowhere',\n"
        "                'neutral': True, 'shootout_winner_team_id': None,\n"
        "                'result_after_extra_time': False, 'source': 'synthetic',\n"
        "                'source_version': '2026-06-16'})\n"
        "            idx += 1\n"
        "# Bloques de holdout con tournament+year exactos.\n"
        "for tourn, year, month in holdout_blocks:\n"
        "    for k, (home, away) in enumerate(pairs):\n"
        "        rows.append({'match_id': f'HO-{idx:05d}',\n"
        "            'date': f'{year}-{month:02d}-{15 + (k % 10):02d}',\n"
        "            'home_team_id': home, 'away_team_id': away,\n"
        "            'home_team_source_name': home.title(), 'away_team_source_name': away.title(),\n"
        "            'home_score': int(rng.integers(0, 4)), 'away_score': int(rng.integers(0, 4)),\n"
        "            'tournament': tourn, 'city': 'Town', 'country': 'Nowhere',\n"
        "            'neutral': True, 'shootout_winner_team_id': None,\n"
        "            'result_after_extra_time': False, 'source': 'synthetic',\n"
        "            'source_version': '2026-06-16'})\n"
        "        idx += 1\n"
        "history = pd.DataFrame(rows)\n"
        "history['date'] = pd.to_datetime(history['date'])\n"
        "strength = {t: 1.0 + 0.25 * i for i, t in enumerate(teams)}\n"
        "dc_predict = lambda a, b, ctx: (\n"
        "    1.0 + 0.6 * strength[a] / (strength[a] + strength[b]),\n"
        "    1.0 + 0.6 * strength[b] / (strength[a] + strength[b]),\n"
        ")\n"
        "dataset = build_ml_dataset(frame=history, dc_predict=dc_predict)\n"
        "eligible = dataset[dataset['ml_eligible']]\n"
        "print('filas totales:', len(dataset), '| elegibles ML:', len(eligible))\n"
        "dataset[list(ML_FEATURE_COLUMNS)].describe().T[['mean', 'std', 'min', 'max']].round(3)",
        "**Interpretation.** El builder retiene todas las filas y marca la elegibilidad "
        "en vez de descartar en silencio (T-05-02). Las features estan en unidades "
        "naturales y sin escalado (D-05): probabilidades DC en [0,1], diferencias de Elo "
        "y de forma en sus escalas crudas, listas para XGBoost.",
    ),
    (
        "## Candidato ML, calibracion y ensemble: comparacion con gate (What and why)\n\n"
        "Ejecutamos `run_ml_comparison`, que para cada holdout temporal entrena el "
        "XGBoost acotado, selecciona empiricamente la calibracion (isotonic/Platt/none) y "
        "el peso del ensemble convexo en una rebanada interna estrictamente pre-cutoff, y "
        "evalua los tres candidatos (baseline, ML, ensemble). El gate de promocion solo "
        "asciende si un candidato vence al baseline en log-loss en TODOS los holdouts.",
        "report, predictions = run_ml_comparison(dataset=dataset, seed=20260616)\n"
        "gate = report['gate']\n"
        "rows = []\n"
        "for cand in ('baseline', 'ml', 'ensemble'):\n"
        "    rows.append({\n"
        "        'candidato': cand,\n"
        "        'log_loss_medio': round(gate['mean_log_loss'][cand], 4),\n"
        "        'vence_baseline_todos': gate['beats_baseline_all_holdouts'].get(cand, '-'),\n"
        "    })\n"
        "comparison = pd.DataFrame(rows)\n"
        "print('promovido:', gate['promoted'], '| ganador:', gate['winner'])\n"
        "print('criterio:', gate['criterion'])\n"
        "comparison",
        "**Interpretation.** La tabla muestra el log-loss medio por candidato y si cada "
        "uno vence al baseline en los cuatro holdouts. El veredicto del gate es un "
        "resultado de primera clase: si nadie lo supera estrictamente, 'baseline' gana y "
        "se mantiene como linea operativa (T-05-09). No se asume superioridad del ML.",
    ),
    (
        "## Calibracion por candidato (What and why)\n\n"
        "Graficamos el log-loss de calibracion por metodo (none/sigmoid/isotonic) para el "
        "ML y el ensemble, promediado sobre holdouts. La eleccion es empirica (D-12): "
        "'none' se prefiere en empates, asi que solo calibramos cuando mejora "
        "estrictamente. Esto hace visible que la calibracion no se asume, se mide.",
        "methods = ['none', 'sigmoid', 'isotonic']\n"
        "ml_acc = {m: [] for m in methods}\n"
        "ens_acc = {m: [] for m in methods}\n"
        "for h in report['per_holdout'].values():\n"
        "    for m in methods:\n"
        "        ml_acc[m].append(h['ml_calibration_log_loss_by_method'][m])\n"
        "        ens_acc[m].append(h['ensemble_calibration_log_loss_by_method'][m])\n"
        "ml_mean = [float(np.mean(ml_acc[m])) for m in methods]\n"
        "ens_mean = [float(np.mean(ens_acc[m])) for m in methods]\n"
        "fig, ax = plt.subplots(figsize=(6.5, 3.6))\n"
        "x = np.arange(len(methods))\n"
        "ax.bar(x - 0.18, ml_mean, width=0.36, label='ML')\n"
        "ax.bar(x + 0.18, ens_mean, width=0.36, label='Ensemble')\n"
        "ax.set_xticks(x)\n"
        "ax.set_xticklabels(methods)\n"
        "ax.set_ylabel('Log-loss de calibracion (medio)')\n"
        "ax.set_title('Eleccion empirica de calibracion por candidato')\n"
        "ax.legend()\n"
        "fig.tight_layout()\n"
        "plt.show()",
        "**Interpretation.** El metodo con menor log-loss de calibracion es el elegido por "
        "candidato y por holdout. Diferencias minimas frente a 'none' confirman que la "
        "calibracion solo se aplica cuando aporta; isotonic no es automaticamente mejor.",
    ),
    (
        "## Decision de publicacion: dual y fallback explicito (What and why)\n\n"
        "Llevamos el veredicto del gate a la capa live con `build_dual_publication`. "
        "Simulamos el proximo bloque de partidos con probabilidades baseline y, para los "
        "elegibles, probabilidades del candidato promovido. La invariante D-13/D-14: el "
        "baseline SIEMPRE se publica; el upgrade se publica JUNTO a el solo en partidos "
        "elegibles; lo demas cae al baseline con motivo explicito.",
        "baseline_preds = pd.DataFrame({\n"
        "    'match_id': ['WC26-001', 'WC26-002', 'WC26-003'],\n"
        "    'team_a': ['alpha', 'charlie', 'echo'],\n"
        "    'team_b': ['bravo', 'delta', 'foxtrot'],\n"
        "    'prob_a': [0.50, 0.40, 0.33],\n"
        "    'prob_draw': [0.27, 0.30, 0.34],\n"
        "    'prob_b': [0.23, 0.30, 0.33],\n"
        "})\n"
        "demo_gate = {'promoted': True, 'winner': gate['winner'] if gate['promoted'] else 'ensemble',\n"
        "             'mean_log_loss': gate['mean_log_loss']}\n"
        "ml_eligible = {'WC26-001': True, 'WC26-002': True, 'WC26-003': False}\n"
        "ml_probs = {'WC26-001': np.array([0.55, 0.25, 0.20]),\n"
        "            'WC26-002': np.array([0.42, 0.31, 0.27])}\n"
        "dual = build_dual_publication(baseline_predictions=baseline_preds,\n"
        "                              gate=demo_gate, ml_eligible=ml_eligible, ml_probs=ml_probs)\n"
        "print('resumen seleccion:', dual.summary)\n"
        "dual.published[['match_id', 'model_family', 'published_family', 'fallback_reason', 'prob_a']]",
        "**Interpretation.** Cada partido conserva su fila baseline; los dos elegibles "
        "ganan una fila 'upgrade' adicional (publicacion dual), y el inelegible queda solo "
        "en baseline con motivo `ml_ineligible`. Toda fila publicada lleva trazabilidad de "
        "que familia la produjo y por que (T-05-11), sin reemplazos silenciosos.",
    ),
    (
        "## Resultado final: promocion o no-promocion (What and why)\n\n"
        "Cerramos con el veredicto operativo de la fase: que decidio el gate sobre el "
        "dataset evaluado y que significa para la publicacion. Mostramos ambos caminos "
        "(ganar o no ganar el gate) para que el resultado negativo sea tan visible como "
        "el positivo (T-05-12).",
        "verdict = evaluate_ml_gate(\n"
        "    {h: v['candidates']['baseline']['metrics']['log_loss'] for h, v in report['per_holdout'].items()},\n"
        "    {h: v['candidates']['ml']['metrics']['log_loss'] for h, v in report['per_holdout'].items()},\n"
        "    {h: v['candidates']['ensemble']['metrics']['log_loss'] for h, v in report['per_holdout'].items()},\n"
        ")\n"
        "if verdict['promoted']:\n"
        "    print(f\"PROMOCION: '{verdict['winner']}' vence al baseline en todos los holdouts.\")\n"
        "    print('-> publicacion DUAL baseline + candidato promovido (el baseline sigue estable).')\n"
        "else:\n"
        "    print('SIN PROMOCION: ningun candidato supera al baseline en los cuatro holdouts.')\n"
        "    print('-> se publica solo el baseline; resultado negativo explicito y documentado.')\n"
        "verdict",
        "**Interpretation.** Sobre este dataset sintetico el gate decide segun la "
        "evidencia por holdout. En produccion, el mismo veredicto entra al pipeline via "
        "`run_official(ml_selection_provider=...)`, que escribe la tabla dual y un bloque "
        "`model_selection` en los metadatos, y el reporte lo hace legible para un revisor. "
        "Phase 5 cierra con claridad operativa, no con un swap oculto de modelo.",
    ),
]


def _capture(code: str, ns: dict) -> list[dict]:
    """Execute one code cell, returning nbformat outputs (stream/result/image)."""
    outputs: list[dict] = []
    stdout = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = stdout
    try:
        block = compile(code, "<cell>", "exec")
        # Re-compile so the final expression (if any) yields a result like Jupyter.
        lines = code.rstrip().splitlines()
        last = lines[-1] if lines else ""
        result_value = None
        try:
            last_expr = compile(last, "<cell>", "eval")
            head = "\n".join(lines[:-1])
            if head.strip():
                exec(compile(head, "<cell>", "exec"), ns)
            result_value = eval(last_expr, ns)
        except SyntaxError:
            exec(block, ns)
    finally:
        sys.stdout = real_stdout

    text = stdout.getvalue()
    if text:
        outputs.append(new_output("stream", name="stdout", text=text))

    # Any open matplotlib figures become PNG image outputs.
    for num in plt.get_fignums():
        fig = plt.figure(num)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=110)
        plt.close(fig)
        png = base64.b64encode(buf.getvalue()).decode("ascii")
        outputs.append(
            new_output(
                "display_data",
                data={"image/png": png, "text/plain": "<Figure>"},
            )
        )

    if result_value is not None:
        try:
            text_repr = repr(result_value)
        except Exception:  # pragma: no cover - defensive
            text_repr = "<unrepresentable>"
        data = {"text/plain": text_repr}
        if hasattr(result_value, "to_html"):
            data["text/html"] = result_value.to_html()
        outputs.append(new_output("execute_result", data=data))
    return outputs


def main() -> None:
    nb = new_notebook()
    nb.cells.append(
        new_markdown_cell(
            "# Phase 5 - ML + Ensemble (upgrade gated)\n\n"
            "Notebook didactico de evidencia: construye la tabla de features, entrena y "
            "calibra el candidato ML, compara baseline / ML / ensemble bajo validacion "
            "temporal estricta, aplica el gate de promocion honesto y lleva el veredicto a "
            "la publicacion dual con fallback explicito al baseline. Toda la logica vive en "
            "`src/cdd_mundial`; aqui solo orquestamos APIs de produccion."
        )
    )

    ns: dict = {}
    execution_count = 1
    for what, code, interp in CELLS:
        nb.cells.append(new_markdown_cell(what))
        cell = new_code_cell(code)
        cell["outputs"] = _capture(code, ns)
        cell["execution_count"] = execution_count
        execution_count += 1
        nb.cells.append(cell)
        nb.cells.append(new_markdown_cell(interp))

    nb.metadata["kernelspec"] = {
        "display_name": "Python 3 (ipykernel)",
        "language": "python",
        "name": "python3",
    }
    nb.metadata["language_info"] = {
        "name": "python",
        "version": ".".join(str(v) for v in sys.version_info[:3]),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, OUT)
    print(f"wrote {OUT} with {len(nb.cells)} cells")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
