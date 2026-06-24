---
status: complete
completed_at: "2026-06-24T10:39:00.831238"
snapshot_id: "2026-06-24T16-37-53Z_baseline-v1-2026-06-24-7404300"
---

# Resultado

Se publico el snapshot oficial `2026-06-24T16-37-53Z_baseline-v1-2026-06-24-7404300` con `model_version=baseline-v1-2026-06-24-7404300`.

Verificaciones clave:

- Preflight verde con `order = [materialize, select_model, simulate, publish]`.
- `published=true`.
- `kickoff_boundary_utc=2026-06-24T19:00:00Z`.
- 24 filas nuevas anexadas al ledger canonico de calibracion.
- Reporte congelado en `reports/snapshots/2026-06-24T16-37-53Z_baseline-v1-2026-06-24-7404300/report.html`.

Notas:

- La corrida uso `--allow-dirty` porque el worktree ya contenia los insumos actualizados de resultados y odds para esta publicacion.
- `gsd-sdk` no estaba disponible en el entorno; la tarea se registro manualmente siguiendo el formato del workflow quick.
