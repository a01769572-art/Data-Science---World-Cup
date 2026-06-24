# CDD-MUNDIAL — Pronósticos del Mundial 2026

Sistema de ciencia de datos end-to-end que pronostica los resultados de la Copa del Mundo FIFA 2026 (11 jun – 19 jul 2026) combinando modelos estructurales (Elo dinámico, Dixon-Coles), machine learning (XGBoost) y simulación Monte Carlo del torneo completo, con actualización tras cada jornada de resultados reales.

> Proyecto de aprendizaje y portafolio. **No constituye asesoría de apuestas**: las cuotas de mercado se usan exclusivamente como benchmark académico de calibración.

## Que es este proyecto

Un proyecto de portafolio metodológicamente riguroso que enseña ciencia de datos end-to-end real: adquisición de datos con procedencia verificable, contratos de esquema estrictos, modelos estructurales y de ML con validación temporal, calibración de probabilidades y simulación estocástica de un torneo de 48 selecciones.

El valor central no es acertar pronósticos — es que el proceso sea sólido, reproducible y profundamente documentado. Todos los notebooks siguen una estructura didáctica obligatoria (celda markdown que documenta *qué y por qué* → celda de código → celda markdown que interpreta resultados), porque el repositorio es material de estudio.

**Roles:** Jesús (estudiante ITESM) dirige las decisiones metodológicas y valida críticamente; Claude (LLM) implementa el código bajo esa dirección. El flujo de trabajo humano-LLM es parte del experimento documentado.

## Estado del torneo y alcance

El torneo inició el 11 de junio de 2026 (México/EUA/Canadá, 48 selecciones, 12 grupos, 104 partidos). El proyecto se construye en modo exprés durante la fase de grupos: la simulación es **condicional al estado real del torneo** — los partidos ya jugados se fijan con su resultado y solo se simula lo restante — así que el sistema es válido en cualquier punto del calendario.

**Estado actual (24 jun 2026): Fases 1–5 completas; Fase 6 pendiente.** El sistema ya opera en vivo: publica snapshots oficiales append-only condicionados al estado real del torneo, congela benchmark de mercado al momento de publicación y renderiza un `report.html` estático por corrida. A la fecha se han publicado tres snapshots oficiales (`2026-06-13`, `2026-06-18` y `2026-06-24`); el más reciente es `2026-06-24T16-37-53Z_baseline-v1-2026-06-24-7404300`, condicionado a 48 partidos ya jugados.

El upgrade ML existe, pero la publicación oficial sigue gateada por desempeño: el snapshot del `2026-06-24` volvió a publicar el baseline estructural (`winner = baseline`, `promoted = false`) y dejó trazabilidad completa en `metadata.json`, el ledger canónico de calibración y el bundle congelado bajo `reports/snapshots/`.

Fuera de alcance: dashboards interactivos (la salida son reportes estáticos matplotlib/seaborn), deep learning (muestras pequeñas; gradient boosting es el techo razonable), datos a nivel jugador, y cualquier uso de apuestas reales.

## Arquitectura

Ensemble de tres capas que alimenta un simulador Monte Carlo:

1. **Estructural** — Elo dinámico recomputado del histórico + Dixon-Coles (Poisson bivariado con decaimiento temporal) que produce goles esperados (λ).
2. **ML** — clasificador XGBoost de 3 clases (1/X/2) con validación temporal estricta y calibración isotónica.
3. **Mercado** — probabilidades implícitas de-margined de casas de apuestas como benchmark externo.

```
data/raw/        capturas inmutables (gitignored las restringidas/generadas)
data/external/   CSVs de referencia revisados a mano (versionados)
data/processed/  parquet canónicos regenerables (gitignored)
data/metadata/   manifiestos de procedencia SHA-256 + políticas de proveedor
src/cdd_mundial/data/   módulos de ingesta y contratos pandera
notebooks/       walkthroughs didácticos (leen artefactos, importan src/)
tests/           gates estructurales y de aceptación por requisito
```

Cada artefacto canónico cruza un esquema pandera `strict=True, coerce=True` (`src/cdd_mundial/data/contracts.py`) antes de serializarse a parquet: la deriva de esquema falla ruidosamente, nunca en silencio.

## Instalacion

Requiere Python 3.11 o 3.12 (Windows, macOS o Linux):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   POSIX: source .venv/bin/activate
pip install -e ".[dev]"
```

La suite de pruebas corre completamente offline:

```bash
python -m pytest -q
```

Opcional (solo para refrescar el benchmark de cuotas con el proveedor en vivo): copiar `.env.example` a `.env` y colocar tu clave personal de The Odds API en la variable `ODDS_API_KEY`. El archivo `.env` está gitignored y la clave jamás aparece en código, logs ni artefactos.

## Reproducibilidad

Reglas duras del proyecto:

- **`data/raw/` es inmutable** — las capturas se escriben una sola vez con creación exclusiva; un payload distinto en la misma ruta lanza error en vez de sobrescribir.
- **Todo derivado es regenerable** — `data/processed/` no se versiona; se reconstruye desde raw + código versionado.
- **Procedencia verificable** — cada captura y cada parquet tiene un manifiesto en `data/metadata/` con fuente, URL, licencia, versión de snapshot, timestamp y checksum SHA-256.
- **Semillas fijas** en toda simulación destinada a reportes (Fases 3+).

Comandos de construcción de los datasets de Fase 1:

```bash
# Histórico martj42: descarga vía kagglehub (sin API key), resuelve identidades,
# valida y materializa el parquet con manifiestos de procedencia
python -m cdd_mundial.data.ingest_martj42 --source-version 2026-06-11

# Verificación de integridad de artefactos existentes (checksums + cobertura)
python -m cdd_mundial.data.ingest_martj42 --verify-only

# Snapshot Elo actual desde eloratings.net (TSV vía requests con captura inmutable)
python -c "from cdd_mundial.data.ingest_elo import fetch_elo_snapshot; fetch_elo_snapshot()"

# Benchmark de cuotas de-margined desde el payload crudo capturado (offline)
python -m cdd_mundial.data.ingest_odds
# ... o desde el fallback manual editable:
python -m cdd_mundial.data.ingest_odds --manual-csv data/external/odds_2026_template.csv
```

El fixture oficial 2026 ya está versionado en `data/external/fixture_2026.csv` y se valida estructuralmente en cada carga con `load_fixture_2026`.

## Data Sources and Licensing

| Fuente | Contenido | Licencia / términos | Almacenamiento |
|--------|-----------|---------------------|----------------|
| [martj42 — International football results](https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017) | 49,405 partidos internacionales 1872–2026, penales, nombres históricos | **CC0-1.0** (dominio público) | Raw versionable; parquet derivado regenerable |
| [eloratings.net](https://www.eloratings.net/) (`World.tsv`, `en.teams.tsv`) | Ratings Elo actuales y mapeo de códigos | El sitio no publica términos; captura documentada para investigación reproducible | Raw capturado localmente (gitignored); parquet derivado regenerable |
| [FIFA — fixture oficial 2026](https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures) | 104 partidos, grupos, sedes, horarios UTC | Datos fácticos del calendario, verificados a mano | CSV congelado y versionado en `data/external/` |
| [The Odds API v4](https://the-odds-api.com/) | Cuotas decimales tres-vías (h2h) de 24 casas | [Términos](https://the-odds-api.com/terms-and-conditions.html): uso analítico permitido; **prohibida la redistribución de datos crudos** | **Payloads crudos solo bajo `data/raw/odds/` (gitignored, nunca se versionan)**; solo derivados de-margined son publicables |

La política completa del proveedor de cuotas (evidencia del probe autenticado, reglas de almacenamiento, resumen de términos) está en `data/metadata/odds_provider_policy.json`. Los manifiestos de procedencia con checksums SHA-256 de cada artefacto viven en `data/metadata/*.provenance.json`.

**Ninguna clave de API ni dato de licencia restrictiva se versiona en este repositorio.** Los secretos viven únicamente en el `.env` local (gitignored) y los tests escanean los archivos versionados en busca de patrones de secretos.

## Convenciones de resultados

- **Los marcadores de martj42 incluyen tiempo extra y excluyen los penales.** Un partido de eliminatoria que terminó 3-3 tras 120 minutos y se definió por penales se almacena como `3-3`; el ganador de la tanda va en la columna separada `shootout_winner_team_id` y la bandera `result_after_extra_time` marca esos desenlaces. Los marcadores de la fuente nunca se modifican.
- **IDs canónicos**: slugs ASCII en minúsculas (`south-korea`), autorados y revisados a mano — nunca derivados durante la ingesta. Toda fuente se mapea vía alias exactos en `data/external/team_aliases.csv`; un nombre no revisado lanza `UnknownTeamError` (sin matching difuso).
- **`match_id` histórico**: `fecha-local-visitante` con sufijo determinista ante colisiones; reproducible desde raw sin estado externo.
- **Bandera `neutral`**: distingue sede neutral de localía real — crítica para modelar ventaja de local (en 2026 solo los anfitriones juegan en casa).
- **Timestamps**: siempre UTC con sufijo `Z`.
- **Cuotas**: solo mercados h2h de tres resultados exactos (local/empate/visitante) como precios *back*; las cuotas *lay* de exchanges se rechazan. `overround` guarda la suma de probabilidades implícitas crudas; `prob_home/draw/away` son las probabilidades de-margined (normalización multiplicativa) que suman exactamente 1.

## Validacion

```bash
# Suite completa (offline, sin red)
python -m pytest -q

# Gates de aceptación de Fase 1 (DATA-01..05, DOC-01, DOC-03)
python -m pytest -q tests/test_phase1_acceptance.py

# Lint
python -m ruff check src tests
```

Marcadores de pytest: `network` (acceso a servicios externos), `manual` (revisión humana), `data_acceptance` (exige artefactos reales materializados). Los gates de aceptación validan los artefactos generados cuando existen y, en entornos recién clonados sin datos, validan los parsers contra fixtures — las afirmaciones de completitud se derivan de los artefactos, no de la prosa.

Validación de modelos (Fases 2+): splits temporales estrictos (nunca aleatorios), holdouts = Mundiales 2018/2022, Euro 2024 y Copa América 2024; métricas reales = log-loss, Brier/RPS y diagramas de confiabilidad — accuracy es engañosa en fútbol.

## Roadmap

| Fase | Entregable | Estado |
|------|-----------|--------|
| 1. Fundación de datos | Histórico canónico, identidades, Elo snapshot, fixture congelado, benchmark de cuotas | ✅ Completa |
| 2. Features y Elo propio | Recomputación World Football Elo desde el histórico, features reproducibles | ✅ Completa |
| 3. Modelos y simulador | Dixon-Coles (λ), Monte Carlo con reglas FIFA 2026 completas | ✅ Completa |
| 4. Pipeline en vivo | Actualización por jornada: resultados → re-cálculo → re-simulación → reporte | ✅ Completa |
| 5. Ensemble ML | XGBoost + calibración isotónica (solo si vence al baseline en log-loss) | ✅ Completa |
| 6. Evaluación | Tracking de calibración vs. mercado, post-mortem final | ⏳ Siguiente |

**Hito cumplido:** el baseline (Fases 1–4) ya publica pronósticos antes del fin de la fase de grupos (`27 jun 2026`). El tercer snapshot oficial quedó publicado el `24 jun 2026`.

Nota de transparencia: el requisito DATA-03 cubre dos partes — la ingesta del snapshot Elo actual (completa, cobertura 48/48 verificada por tests) y la recomputación de Elo propio desde el histórico, que es el primer entregable de la Fase 2.
