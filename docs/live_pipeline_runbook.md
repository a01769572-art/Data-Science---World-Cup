# Runbook operativo — Pipeline de publicación diaria (Mundial 2026)

Este runbook documenta cómo el operador publica el snapshot oficial diario del
baseline (Elo + Dixon-Coles + Monte Carlo) y cómo manejar los modos de falla.
El pipeline oficial vive en `src/cdd_mundial/live/` y se dispara con **un solo
comando** reproducible (D-07). El notebook
`notebooks/04_primer_pronostico_pipeline.ipynb` es solo una **interfaz** sobre
ese comando — nunca redefine la lógica de producción (D-07, T-04-14).

> Todos los comandos usan el Python del entorno virtual del repo:
> `.\.venv\python.exe`. No se requiere que el operador ejecute pasos manuales de
> red ni de autenticación para el modo manual de odds.

---

## 1. Cadena oficial de publicación

`python -m cdd_mundial.live` ejecuta, en orden estricto e inviolable
(`order = [materialize, select_model, simulate, publish]`):

1. **Validación de resultados** — lee `data/external/results_2026.csv` (fuente
   canónica, D-01) y construye un `TournamentState` fail-closed.
2. **Materialización live-training inmutable** — escribe un artefacto derivado
   datado y content-addressed bajo `data/processed/live/` (mismo input → mismo
   SHA-256; nunca reescribe el histórico crudo) y refresca Elo/forma.
3. **Fingerprint + decisión reuse/refit** — reutiliza el modelo datado fijado si
   el fingerprint no cambió; refitea exactamente un artefacto nuevo
   (`baseline-v1-YYYY-MM-DD-<shortsha>`, D-13) si cambió.
4. **Simulación condicionada** — re-simula el resto del torneo con semilla fija.
5. **Snapshot append-only** — estadía en directorio sibling temporal, congela el
   benchmark de mercado a la hora de publicación (mediana de-margined entre
   casas, D-20/D-21), hace append al ledger canónico de calibración + slice
   local del snapshot, finaliza `metadata.json` **una sola vez** (con checksums
   de cada artefacto), y publica por `rename` atómico.
6. **Reporte HTML estático** — se renderiza junto al bundle a partir de los
   artefactos congelados + el ledger canónico (nunca re-simula, D-12, T-04-07).

### Comando oficial (worktree limpio)

```powershell
.\.venv\python.exe -m cdd_mundial.live `
  --official `
  --results-csv data/external/results_2026.csv `
  --manual-odds data/external/odds_2026_template.csv `
  --seed 20260613
```

- `--official` es un marcador explícito (la publicación es el modo por defecto).
- `--results-csv` es alias de `--results-path`.
- `--manual-odds` alimenta el benchmark de mercado cuando no hay clave de
  proveedor configurada (fallback manual aprobado, D-04). Sin odds usables el
  run publica igual, pero sin filas de calibración para esa corrida.
- `--seed` fija la semilla de simulación para reproducibilidad de reportes.

### Verificación sin escribir (dry-run)

```powershell
.\.venv\python.exe -m cdd_mundial.live `
  --official `
  --results-csv data/external/results_2026.csv `
  --manual-odds data/external/odds_2026_template.csv `
  --seed 20260613 `
  --verify-only
```

`--verify-only` valida prerequisitos, resuelve el artefacto de materialización y
el fingerprint que alimentarían la selección de modelo, e imprime el orden
previsto **sin** publicar ni escribir un snapshot.

---

## 2. Preflight (checklist antes de publicar)

1. **Worktree limpio**: `git status --porcelain` vacío. La publicación oficial
   exige worktree limpio por defecto (D-11). Si está sucio: ver §4.
2. **Resultados al día**: `data/external/results_2026.csv` contiene todos los
   partidos ya jugados relevantes para el bloque (D-05). El CSV canónico es la
   autoridad; cualquier scraper solo verifica (D-04).
3. **Dry-run verde**: correr `--verify-only` y confirmar
   `order = [materialize, select_model, simulate, publish]`, `published=false`.
4. **Boundary pre-kickoff**: la publicación debe completarse y commitearse
   **antes** del `kickoff_boundary_utc` (el próximo kickoff aún no iniciado).
   El pipeline calcula el boundary automáticamente desde el fixture.

---

## 3. Publicación y commit (worktree limpio)

```powershell
# 1. Publicar
.\.venv\python.exe -m cdd_mundial.live --official `
  --results-csv data/external/results_2026.csv `
  --manual-odds data/external/odds_2026_template.csv --seed 20260613

# 2. Commitear el bundle ANTES del kickoff boundary
git add reports/snapshots/<snapshot_id> data/processed/live/calibration/calibration_matches.parquet
git commit -m "publish(live): official snapshot <snapshot_id> pre-kickoff"
```

El snapshot publicado contiene:

- `metadata.json` — `generated_at_utc`, `kickoff_boundary_utc`, `git_commit`,
  `git_dirty`, `live_training_provenance` (path + sha256), `model_provenance`
  (fingerprint + sha256 + reuse/refit), `seed`, `preflight`,
  `publication_row_ids`, `checksums`.
- `team_probabilities.parquet`, `group_positions.parquet`,
  `upcoming_match_predictions.parquet`, `frozen_benchmark.parquet`.
- `report_inputs/calibration_publication_slice.parquet`.
- `report.html` + `assets/*.png`.

El ledger canónico `data/processed/live/calibration/calibration_matches.parquet`
es append-only: una fila por `(match_id, snapshot_id)`; re-append falla fuerte.

---

## 4. Modos de falla y manejo

| Falla | Síntoma | Acción |
|-------|---------|--------|
| **Resultados faltantes** | `IncompleteResultsError` | Completar `results_2026.csv` para los partidos ya jugados, o pasar un override explícito y trazable (D-05). Nunca publicar en silencio. |
| **Discrepancia scraper vs CSV** | `DiscrepancyError` | El CSV canónico es autoridad. Corregir el CSV o pasar override que registre la discrepancia (D-04). |
| **Drift de materialización** | `FileExistsError` al escribir `live_training_<fecha>.parquet` | El artefacto datado ya existe con contenido distinto: los inputs canónicos cambiaron sin cambiar la fecha. Investigar el cambio de resultados/parámetros; usar `as_of_date` correcto. |
| **Sin odds / sin clave de proveedor** | benchmark vacío | Usar `--manual-odds` con la plantilla aprobada `data/external/odds_2026_template.csv`. Si tampoco hay odds manuales, el run publica sin filas de calibración (documentado, no es falla). |
| **Worktree sucio** | `RuntimeError: ... requires a clean worktree` | **Decisión humana (D-11).** Opción A: commitear/limpiar y republicar. Opción B: aprobar explícitamente UNA publicación sucia con `--allow-dirty`; `metadata.json` registrará `git_dirty=true` y los archivos modificados. No se bypassa automáticamente. |
| **Colisión append-only de snapshot** | `FileExistsError` en publish | Ese `snapshot_id` ya está publicado; los snapshots son inmutables. No sobrescribir; generar uno nuevo (el id incluye timestamp). |
| **Lock transitorio de OneDrive** en el rename | `PermissionError` reintentado | El writer reintenta el rename atómico con backoff; si agota reintentos, reintentar el comando (el staging dir se descarta de forma segura). |

### Override de worktree sucio (solo con aprobación explícita)

```powershell
.\.venv\python.exe -m cdd_mundial.live --official `
  --results-csv data/external/results_2026.csv `
  --manual-odds data/external/odds_2026_template.csv `
  --seed 20260613 --allow-dirty
```

`--allow-dirty` **registra**, nunca oculta, el override: `metadata.json` queda
con `git_dirty=true`, `allow_dirty_override=true` y la lista de archivos
modificados. Documentar la razón en la nota de publicación de esa corrida.

---

## 5. Cadencia diaria

1. Actualizar `results_2026.csv` con los resultados de la jornada anterior.
2. Actualizar `odds_2026_template.csv` con las cuotas del próximo bloque (o
   capturar del proveedor si hay clave).
3. Correr preflight (§2), publicar y commitear antes del kickoff (§3).
4. El reporte `report.html` del snapshot es el artefacto publicable (LinkedIn /
   portafolio). El ledger acumula la calibración modelo-vs-mercado a lo largo de
   la fase de grupos (D-22).
