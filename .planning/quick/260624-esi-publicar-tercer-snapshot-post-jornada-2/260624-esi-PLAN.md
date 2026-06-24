---
created_at: "2026-06-24T10:39:00.831238"
---

# Publicar el tercer snapshot oficial del 2026-06-24 post jornada 2

Objetivo: publicar el snapshot oficial del 2026-06-24 despues del cierre de la jornada 2 del 2026-06-23, usando los resultados canonicos ya actualizados y el bloque de odds del siguiente tramo del torneo.

Pasos ejecutados:

1. Reparar el entorno Python 3.12 del repo para poder correr `cdd_mundial.live`.
2. Correr `--verify-only` con `--allow-dirty` porque `results_2026.csv` y `odds_2026_template.csv` ya estaban modificados para la publicacion.
3. Publicar el snapshot oficial y verificar `snapshot_id`, `report.html` y append al ledger de calibracion.
4. Registrar la tarea rapida en `.planning/quick/` y `STATE.md`.

Artefactos esperados:

- `reports/snapshots/2026-06-24T16-37-53Z_baseline-v1-2026-06-24-7404300/`
- `data/processed/live/calibration/calibration_matches.parquet`
- commit `publish(live): official snapshot 2026-06-24T16-37-53Z pre-kickoff`
