# Requirements — CDD-MUNDIAL (Mundial 2026)

**Defined:** 2026-06-11
**Core value:** Proyecto de portafolio metodológicamente riguroso y profundamente documentado que enseña ciencia de datos end-to-end real.
**Hard deadline:** El baseline debe publicar pronósticos antes del fin de la fase de grupos (2026-06-27). El torneo termina 2026-07-19.

## v1 Requirements

### Datos

- [x] **DATA-01**: El sistema cuenta con una base histórica unificada de partidos internacionales (Kaggle `martj42` vía kagglehub, sin API key) almacenada en parquet y validada con esquemas pandera, con `data/raw/` inmutable
- [x] **DATA-02**: Existe una tabla maestra canónica de selecciones (`teams.csv`) contra la que se mapea toda fuente, con tests de cobertura que garantizan que las 48 selecciones del Mundial resuelven en cada fuente
- [x] **DATA-03**: El sistema ingesta ratings Elo actuales (eloratings.net TSV vía requests) con cobertura completa de las 48 selecciones; la recomputación Elo propia desde el histórico se implementa como `MODEL-01`
- [x] **DATA-04**: El fixture oficial 2026 (104 partidos, 12 grupos, sedes, horarios) está cargado, validado y versionado en `data/external/`
- [x] **DATA-05**: El sistema ingesta cuotas de mercado de una fuente y calcula probabilidades implícitas de-margined para usar como benchmark
- [ ] **DATA-06**: Existe un pipeline de ingesta de resultados del torneo en curso con fallback manual editable (`results_2026.csv`) para que un scraper roto nunca bloquee la corrida diaria

### Modelos baseline

- [ ] **MODEL-01**: El sistema calcula un Elo dinámico custom (estilo World Football Elo: K por torneo, ventaja local, margen de victoria) con parámetros optimizados en histórico
- [ ] **MODEL-02**: El sistema entrena un modelo Dixon-Coles (Poisson bivariado con corrección de marcadores bajos y decaimiento temporal calibrado para fútbol de selecciones) que expone la interfaz `predict_lambdas(team_a, team_b, ctx)` — el contrato que consume el simulador
- [ ] **MODEL-03**: El sistema deriva probabilidades W/D/L de la matriz de marcadores Dixon-Coles (la probabilidad de empate sale del modelo de goles, no de un logistic Elo)
- [ ] **MODEL-04**: Todo modelo se valida con splits temporales estrictos contra 4 torneos holdout (Mundial 2018, Mundial 2022, Euro 2024, Copa América 2024) usando log-loss, Brier y RPS

### Simulador

- [ ] **SIM-01**: `rules_fifa.py` implementa las reglas completas del formato 2026 — desempates de grupo FIFA (puntos → DG → GF → head-to-head → fair play → sorteo), ranking de mejores terceros y su asignación oficial a la Ronda de 32 — verificadas contra el reglamento oficial FIFA y con tests unitarios contra casos históricos conocidos
- [ ] **SIM-02**: El motor Monte Carlo vectorizado en numpy corre ≥10,000 simulaciones del torneo (objetivo 100k con common random numbers entre jornadas) en menos de 1 minuto
- [ ] **SIM-03**: La simulación es condicional al estado real del torneo: partidos jugados se fijan con su resultado y solo se simula lo restante
- [ ] **SIM-04**: El sistema produce tablas de probabilidad de avance por selección: P(R32), P(R16), P(QF), P(SF), P(Final), P(Campeón)
- [ ] **SIM-05**: Las eliminatorias se resuelven con modelo de tiempo extra y penales (~50/50 ajustado) y desempate aleatorio por simulación (sin sesgo de orden)

### ML y ensemble

- [ ] **ML-01**: Pipeline de features para ML: diferencia de Elo, forma reciente ponderada, rolling de goles, ranking FIFA point-in-time, condición de anfitrión, descanso entre partidos
- [ ] **ML-02**: Clasificador XGBoost de 3 clases (1/X/2) entrenado y evaluado con la misma validación temporal que el baseline
- [ ] **ML-03**: Ensemble ponderado (estructural + ML) con gate de aceptación pre-registrado: solo reemplaza al baseline si lo vence en log-loss en los 4 torneos holdout
- [ ] **ML-04**: Calibración de probabilidades comparando isotónica vs. Platt empíricamente en folds de validación temporal (isotónica no se asume superior con <1,000 muestras)

### Operación en vivo

- [ ] **LIVE-01**: El pipeline de jornada corre con un comando: ingesta de resultados → actualización Elo/forma → re-simulación → reporte generado
- [ ] **LIVE-02**: Cada pronóstico se persiste como snapshot append-only con timestamp y `model_version`, commiteado a git ANTES del kickoff, desde el primer pronóstico publicado — habilita gráficas de evolución y evaluación honesta sin posibilidad de edición retrospectiva
- [ ] **LIVE-03**: Cada jornada genera un reporte estático con matplotlib/seaborn: tabla de avance, barras P(Campeón), distribución de posiciones por grupo, evolución de probabilidades en el tiempo
- [ ] **LIVE-04**: El sistema trackea calibración en vivo: log-loss/RPS acumulado del modelo vs. benchmark de mercado de-margined sobre los partidos ya jugados
- [ ] **LIVE-05**: El sistema calcula leverage por partido próximo: ΔP(avanzar) condicionado a victoria/empate/derrota vía simulaciones condicionales

### Documentación y pedagogía

- [x] **DOC-01**: Todo notebook sigue la estructura didáctica obligatoria: celda markdown que documenta (qué/por qué) → celda de código → celda markdown que interpreta resultados
- [ ] **DOC-02**: Todo pronóstico publicado es reproducible: seeds fijas en simulación, raw inmutable, datos procesados con metadatos de extracción, artefactos de modelo versionados por fecha
- [x] **DOC-03**: El repo vive en GitHub público con README de calidad portafolio (sin claves ni datos de licencia restrictiva)
- [ ] **DOC-04**: Al cerrar cada fase se escriben notas de aprendizaje de conceptos (Elo, Dixon-Coles, calibración, Monte Carlo) en el vault de Obsidian (SecondBrain)
- [ ] **DOC-05**: Al terminar el torneo se publica un post-mortem con la evaluación final honesta: log-loss real de los 104 partidos vs. benchmarks, qué funcionó, qué no, lecciones

## v2 Requirements

Deferred — valiosos pero no bloquean el valor core de v1:

- [ ] **EVAL-V2-01**: Skill scores vs. baselines naive (uniforme 33/33/33, solo-Elo, solo-ranking-FIFA) por jornada
- [ ] **EVAL-V2-02**: Diagramas de confiabilidad sobre partidos reales acumulados (~30+ partidos, bins agrupados)
- [ ] **ML-V2-01**: Feature importance / SHAP para interpretación del clasificador
- [ ] **DATA-V2-01**: Valor de plantilla (Transfermarkt) como feature escalar por selección
- [ ] **EVAL-V2-03**: De-margin con método de Shin / agregación multi-bookmaker

## Out of Scope

| Exclusión | Razón |
|-----------|-------|
| Dashboard interactivo (Streamlit/Dash) | El tiempo de frontend compite con el de modelado durante un torneo de 5 semanas; reportes estáticos satisfacen al consumidor. Posible milestone futuro |
| Deep learning | ~48k partidos con covariables débiles es small data; GBM + estructurales es el techo documentado (consenso Kaggle + académico) |
| Modelado a nivel jugador (alineaciones, lesiones) | Costo de extracción alto, ganancia marginal a nivel selección, superficie de leakage enorme |
| Win probability en vivo (in-game) | Requiere datos evento-a-evento y otra clase de modelo; cero valor para pronóstico pre-partido |
| Predicción de marcador exacto como output principal | El marcador más probable ronda 8-12%; perseguir accuracy de marcador degrada la calidad probabilística. Se reportan distribuciones |
| Estrategia de apuestas / Kelly / value bets | Scope creep + exposición ética/legal; las cuotas son benchmark académico estrictamente |
| Automatización cloud / cron | Infra para 5 semanas con un trigger manual diario no se justifica; runbook documentado |
| Re-entrenamiento ad hoc a mitad del torneo | Cambios no versionados destruyen la validez del experimento de calibración en vivo; si se revisa, se versiona (v1/v2) y se reporta por versión |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | Complete |
| DATA-02 | Phase 1 | Complete |
| DATA-03 | Phase 1 | Complete |
| DATA-04 | Phase 1 | Complete |
| DATA-05 | Phase 1 | Complete |
| DATA-06 | Phase 4 | Pending |
| MODEL-01 | Phase 2 | Pending |
| MODEL-02 | Phase 2 | Pending |
| MODEL-03 | Phase 2 | Pending |
| MODEL-04 | Phase 2 | Pending |
| SIM-01 | Phase 3 | Pending |
| SIM-02 | Phase 3 | Pending |
| SIM-03 | Phase 3 | Pending |
| SIM-04 | Phase 3 | Pending |
| SIM-05 | Phase 3 | Pending |
| ML-01 | Phase 5 | Pending |
| ML-02 | Phase 5 | Pending |
| ML-03 | Phase 5 | Pending |
| ML-04 | Phase 5 | Pending |
| LIVE-01 | Phase 4 | Pending |
| LIVE-02 | Phase 4 | Pending |
| LIVE-03 | Phase 4 | Pending |
| LIVE-04 | Phase 4 | Pending |
| LIVE-05 | Phase 6 | Pending |
| DOC-01 | Phase 1 | Complete |
| DOC-02 | Phase 4 | Pending |
| DOC-03 | Phase 1 | Complete |
| DOC-04 | Phase 6 | Pending |
| DOC-05 | Phase 6 | Pending |

**Coverage:** 29/29 v1 requirements mapped — no orphans, no duplicates.

**Notas de mapeo:**
- DATA-03 cubre la ingesta del snapshot Elo actual; la recomputación Elo propia permanece explícitamente en MODEL-01 para evitar duplicar o sobredeclarar alcance
- DATA-06 (ingesta de resultados en vivo) vive en Phase 4, no Phase 1 — es parte del pipeline diario, no de la fundación histórica
- DOC-01 (estructura didáctica) se establece como convención en Phase 1 y se aplica como constraint en todas las fases siguientes
- DOC-02 (reproducibilidad) se verifica en Phase 4 — el primer pronóstico publicado es donde la regeneración end-to-end se vuelve comprobable
- DOC-04 (notas Obsidian) se ejecuta al cierre de CADA fase (ritual de transición) y se verifica completo en Phase 6

---
*Defined: 2026-06-11 — initial v1 scoping after domain research*
*Traceability mapped: 2026-06-11 — roadmap v1 (6 phases)*
