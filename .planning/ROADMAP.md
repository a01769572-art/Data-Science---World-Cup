# Roadmap: CDD-MUNDIAL — Pronósticos del Mundial 2026

## Overview

El torneo empezó HOY (2026-06-11) y termina 2026-07-19 — el roadmap está dictado por ese reloj externo. Fase 1 construye la fundación de datos (la tabla maestra de selecciones es la piedra angular contra la que mapea toda fuente). Fases 2 y 3 son paralelizables gracias al contrato `predict_lambdas(team_a, team_b, ctx)`: los modelos baseline (Elo + Dixon-Coles) y el simulador FIFA 2026 (el componente de mayor riesgo de defectos) se construyen en simultáneo, el simulador contra λs stub. Fase 4 es el hito duro: pipeline diario publicando pronósticos con snapshot append-only pre-kickoff ANTES del 27 de junio (fin de fase de grupos) — el archivo de pronósticos no se puede rellenar retroactivamente. Fase 5 es una mejora gated (el ensemble ML solo reemplaza al baseline si lo vence en los 4 holdouts). Fase 6 corre desde la Fase 4 hasta el cierre: operación diaria disciplinada, leverage por partido y post-mortem honesto.

## Timeline (deadlines externos duros)

- **2026-06-11**: Inicio del torneo (hoy)
- **2026-06-27**: Fin de fase de grupos — Fases 1-4 DEBEN estar publicando antes
- **2026-07-19**: Final del torneo — post-mortem después

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

- [ ] **Phase 1: Fundación de Datos** - Base histórica unificada, tabla maestra de selecciones, fixture 2026, Elo ratings y cuotas — todo validado con pandera
- [ ] **Phase 2: Modelos Baseline (Elo + Dixon-Coles)** - Elo dinámico custom y Dixon-Coles que expone `predict_lambdas`, validados temporalmente contra 4 torneos holdout
- [ ] **Phase 3: Simulador del Torneo** - Reglas FIFA 2026 completas (48 equipos, mejores terceros) + Monte Carlo vectorizado condicional al estado real — paralelizable con Fase 2
- [ ] **Phase 4: Primer Pronóstico + Pipeline Diario** - Pipeline de jornada de un comando, snapshot append-only pre-kickoff, primer reporte publicado ≤ 27 jun
- [ ] **Phase 5: ML + Ensemble (upgrade gated)** - XGBoost + ensemble calibrado que solo reemplaza al baseline si lo vence en los 4 holdouts
- [ ] **Phase 6: Operación en Vivo + Post-Mortem** - Disciplina diaria hasta el 19 jul, leverage por partido, post-mortem honesto y notas de aprendizaje

## Phase Details

### Phase 1: Fundación de Datos
**Goal**: Existe una base de datos limpia, unificada y validada donde toda fuente resuelve contra la tabla maestra canónica de selecciones — nada downstream puede romperse por mismatch de nombres
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DOC-01, DOC-03
**Success Criteria** (what must be TRUE):
  1. La base histórica (~48k partidos, Kaggle martj42 vía kagglehub sin API key) carga desde parquet, pasa esquemas pandera, con `data/raw/` inmutable y metadatos de extracción
  2. Las 48 selecciones del Mundial 2026 resuelven contra `teams.csv` en cada fuente (Kaggle, eloratings, FIFA, fixture, cuotas) y el test de cobertura pasa como gate duro
  3. Los ratings Elo actuales (eloratings.net TSV) y el fixture oficial 2026 (104 partidos, 12 grupos, sedes) están cargados, validados y versionados en `data/external/`
  4. Las probabilidades implícitas de-margined de una fuente de cuotas están disponibles como benchmark
  5. El repo vive en GitHub público con README de calidad portafolio y los notebooks existentes siguen la estructura MD→código→MD
**Plans**: TBD

### Phase 2: Modelos Baseline (Elo + Dixon-Coles)
**Goal**: El sistema produce goles esperados (λ) y probabilidades W/D/L de partido desde modelos estructurales custom, validados temporalmente — el contenido de aprendizaje core del proyecto
**Depends on**: Phase 1
**Requirements**: MODEL-01, MODEL-02, MODEL-03, MODEL-04
**Success Criteria** (what must be TRUE):
  1. El Elo dinámico custom (K por torneo, ventaja local condicional a sede neutral, multiplicador por margen, efecto anfitrión MEX/USA/CAN) está recomputado desde el histórico con parámetros optimizados
  2. `predict_lambdas(team_a, team_b, ctx)` devuelve goles esperados Dixon-Coles (ρ acotado, decaimiento temporal calibrado para selecciones, neutral-aware) para cualquier par de selecciones del Mundial — el contrato que consume el simulador queda congelado
  3. Las probabilidades W/D/L se derivan de la matriz de marcadores Dixon-Coles (no de un logistic sobre Elo) y la cuota de empates cae en el rango sano 24–28%
  4. Log-loss, Brier y RPS contra los 4 torneos holdout (Mundial 2018/2022, Euro 2024, Copa América 2024) están reportados y el baseline vence a los baselines naive (uniforme, solo-Elo)
**Plans**: TBD

### Phase 3: Simulador del Torneo
**Goal**: El motor Monte Carlo simula el formato 2026 completo con reglas FIFA verificadas contra el reglamento oficial, condicional al estado real del torneo — construible en paralelo con Fase 2 vía λs stub
**Depends on**: Phase 1 (fixture + teams). Paralelizable con Phase 2 vía el contrato `predict_lambdas` con stub
**Requirements**: SIM-01, SIM-02, SIM-03, SIM-04, SIM-05
**Success Criteria** (what must be TRUE):
  1. `rules_fifa.py` (funciones puras) implementa la cascada de desempates de grupo, ranking de mejores terceros y asignación oficial a R32 — verificado contra el PDF del reglamento oficial FIFA 2026 (prerequisito de la fase) y con tests unitarios contra casos históricos (incl. Grupo H 2018) y empates sintéticos a 3/4 bandas
  2. El motor corre ≥10,000 simulaciones del torneo (objetivo 100k) en menos de 1 minuto, vectorizado en numpy, con semilla fija reproducible
  3. Los partidos ya jugados se fijan con su resultado real y solo se simula lo restante (TournamentState)
  4. El sistema produce tablas P(R32), P(R16), P(QF), P(SF), P(Final), P(Campeón) por selección
  5. Las eliminatorias se resuelven con modelo de tiempo extra y penales (~50/50 ajustado) con desempate aleatorio por simulación, sin sesgo de orden
**Plans**: TBD

### Phase 4: Primer Pronóstico + Pipeline Diario
**Goal**: El sistema publica pronósticos reproducibles cada jornada con un solo comando y archivo append-only pre-kickoff — SHIP antes del 27 de junio; cada día sin publicar encoge permanentemente el diferenciador del proyecto
**Depends on**: Phase 2, Phase 3
**Requirements**: DATA-06, LIVE-01, LIVE-02, LIVE-03, LIVE-04, DOC-02
**Success Criteria** (what must be TRUE):
  1. Un comando corre el pipeline de jornada completo: ingesta de resultados → actualización Elo/forma → refresh Dixon-Coles → re-simulación (common random numbers entre jornadas) → reporte generado
  2. La ingesta de resultados del torneo tiene fallback manual editable (`results_2026.csv`) — un scraper roto nunca bloquea la corrida diaria
  3. Cada pronóstico se persiste como snapshot append-only con timestamp UTC y `model_version`, commiteado a git ANTES del kickoff, desde el primer pronóstico publicado
  4. Cada jornada genera un reporte estático matplotlib/seaborn: tabla de avance, barras P(Campeón), distribución de posiciones por grupo, evolución de probabilidades en el tiempo
  5. El tracker de calibración en vivo muestra log-loss/RPS acumulado vs. benchmark de mercado de-margined, y todo pronóstico es regenerable desde raw + código versionado con seeds fijas
**Plans**: TBD

### Phase 5: ML + Ensemble (upgrade gated)
**Goal**: Un ensemble ML calibrado mejora medible y honestamente al baseline — o el resultado negativo queda documentado como hallazgo; el baseline sigue publicando en paralelo en todo momento
**Depends on**: Phase 4 (el baseline debe estar publicando antes de tocar ML)
**Requirements**: ML-01, ML-02, ML-03, ML-04
**Success Criteria** (what must be TRUE):
  1. La matriz de features point-in-time (diferencia Elo, forma reciente, rolling de goles, ranking FIFA point-in-time vía merge_asof, anfitrión, descanso) existe sin leakage temporal (disciplina shift(1))
  2. El clasificador XGBoost de 3 clases (constrained: depth ≤ 3–4, ≤ ~10 features) está entrenado y evaluado con la misma validación temporal que el baseline
  3. El gate de aceptación pre-registrado se aplica: el ensemble solo reemplaza al baseline si lo vence en log-loss en los 4 torneos holdout — si no, el resultado negativo se documenta y el baseline sigue
  4. La calibración isotónica vs. Platt se compara empíricamente en folds temporales y se elige por evidencia (isotónica no asumida superior con <1,000 muestras)
**Plans**: TBD

### Phase 6: Operación en Vivo + Post-Mortem
**Goal**: El sistema opera con disciplina diaria hasta el 19 de julio y cierra con evaluación final honesta y aprendizaje capturado — corre desde Fase 4 en adelante; el post-mortem está fijado al final del torneo
**Depends on**: Phase 4 (corre en paralelo con Phase 5 durante el torneo)
**Requirements**: LIVE-05, DOC-04, DOC-05
**Success Criteria** (what must be TRUE):
  1. Cada reporte de jornada incluye leverage por partido próximo: ΔP(avanzar) condicionado a victoria/empate/derrota vía simulaciones condicionales
  2. El rules engine está replay-validado contra los standings reales conforme avanza la fase de grupos (validación post-jornada 2)
  3. Las notas de aprendizaje de conceptos (Elo, Dixon-Coles, calibración, Monte Carlo) existen en el vault de Obsidian (SecondBrain) al cierre de cada fase — todas presentes al cerrar el proyecto
  4. El post-mortem está publicado con la evaluación final honesta: log-loss real de los 104 partidos vs. benchmarks (mercado, naive), qué funcionó, qué no, y lecciones
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 ∥ 3 → 4 → 5 ∥ 6 (2-3 paralelizables vía λ-stub; 6 corre desde 4 en adelante)

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Fundación de Datos | 0/TBD | Not started | - |
| 2. Modelos Baseline | 0/TBD | Not started | - |
| 3. Simulador del Torneo | 0/TBD | Not started | - |
| 4. Primer Pronóstico + Pipeline Diario | 0/TBD | Not started | - |
| 5. ML + Ensemble (gated) | 0/TBD | Not started | - |
| 6. Operación en Vivo + Post-Mortem | 0/TBD | Not started | - |

---
*Created: 2026-06-11 — deadline-driven roadmap; Phases 1-4 must complete before 2026-06-27*
