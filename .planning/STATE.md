---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Phase 3 context updated and pending plans revised
last_updated: "2026-06-13T01:25:16.498Z"
last_activity: 2026-06-13
progress:
  total_phases: 6
  completed_phases: 2
  total_plans: 15
  completed_plans: 12
  percent: 80
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-11)

**Core value:** Proyecto de portafolio metodológicamente riguroso y profundamente documentado que enseña ciencia de datos end-to-end real — si los pronósticos fallan pero el proceso es sólido y el aprendizaje quedó capturado, el proyecto cumplió.
**Current focus:** Phase 03 — simulador-del-torneo

## Current Position

Phase: 03 (simulador-del-torneo) — EXECUTING
Plan: 3 of 5
Status: Ready to execute
Last activity: 2026-06-13

Progress: [███████░░░] 67%

**HARD DEADLINE:** Fases 1-4 deben estar publicando pronósticos antes del 2026-06-27 (fin de fase de grupos). El torneo empezó HOY.

## Performance Metrics

**Velocity:**

- Total plans completed: 5
- Average duration: 19 min
- Total execution time: 93 min

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 | 5 | 93 min | 19 min |

**Recent Trend:**

- Last 5 plans: 20 min, 4 min, 18 min, 35 min, 16 min
- Trend: Phase 1 closed in 93 active minutes; external credential and human-verification waits are excluded

*Updated after each plan completion*
| Phase 01 P01 | 20min | 3 tasks | 11 files |
| Phase 01 P02 | 4min | 3 tasks | 9 files |
| Phase 01 P03 | 18min | 2 tasks | 14 files |
| Phase 01 P04 | 35min | 2 tasks + 1 checkpoint | 10 files |
| Phase 01 P05 | 16min | 2 tasks | 5 files |
| Phase 02 P01 | 14min | 3 tasks | 11 files |
| Phase 02 P02 | 9min | 3 tasks | 7 files |
| Phase 02 P03 | 10min | 2 tasks | 3 files |
| Phase 02 P04 | 25min | 2 tasks | 7 files |
| Phase 02 P05 | 13min | 2 tasks | 3 files |
| Phase 03 P01 | 14min | 2 tasks + 1 fix tasks | 5 files files |
| Phase 03 P02 | 7min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Phase 02]: xi=0.00095 selected by mean log-loss across four holdouts; D-13 passed (DC 0.9672 < solo-Elo 0.9830 < uniform 1.0986).
- [Phase 02]: L-BFGS-B now starts gamma at zero with explicit convergence options to avoid a degenerate recent-window basin.

- [Roadmap]: Fases 2 y 3 paralelizables vía contrato `predict_lambdas(team_a, team_b, ctx)` — el simulador se construye contra λs stub
- [Roadmap]: Fase 5 (ML) es upgrade gated, no critical path — solo reemplaza al baseline si lo vence en log-loss en los 4 holdouts
- [Roadmap]: El snapshot log append-only arranca con el PRIMER pronóstico publicado (Fase 4) — no se puede rellenar retroactivamente
- [Phase 01]: Canonical Pandera schemas inherit strict=True and coerce=True from one shared base contract. — Keeps every canonical stage exit consistent and rejects schema drift.
- [Phase 01]: Immutable captures use exclusive creation and checksum comparison. — Identical replay is safe while changed payloads cannot mutate raw history.
- [Phase 01]: Tests use workspace-local unique artifacts. — Windows and OneDrive temp ACLs were unreliable in the execution environment.
- [Phase 01]: Canonical IDs are authored lowercase ASCII slugs and are never derived during ingestion. — Stable reviewed identities prevent silent cross-source merges.
- [Phase 01]: Martj42 scores remain unchanged while shootout winners are stored separately. — This preserves the source's full-time-including-extra-time semantics.
- [Phase 01]: Historical match IDs use date and original source names with deterministic collision suffixes. — IDs remain reproducible without depending on runtime canonical slug generation.
- [Phase 01]: External TSV acquisition uses bounded timeouts, limited retries, response validation, and immutable captures. — Prevents unbounded provider access and rejects non-tabular error responses.
- [Phase 01]: Knockout participants remain official slot references until results determine canonical teams. — Avoids guessing future participants while preserving a stable tournament bracket.
- [Phase 01]: The official 2026 fixture cross-check is accepted after explicit human approval: Todo correcto. — Closes the plan's blocking integrity checkpoint.
- [Phase 01 debug]: DATA-01 completion requires a production materialization gate, not only mocked acquisition and fixture round-trips. — Prevents tests from passing while required data artifacts are absent.
- [Phase 01]: The Odds API v4 is the odds provider; raw payloads live only under gitignored data/raw/odds/ and only de-margined derivatives are publishable. — Terms permit analytical use but forbid raw redistribution.
- [Phase 01]: Exchange lay quotes (h2h_lay) are never consumed as back prices in the odds benchmark. — Lay prices invert market semantics and would corrupt implied probabilities.
- [Phase 01]: Multiple reviewed alias name variants per (team, source) are legitimate coverage. — Live providers spell names differently than expected; resolution stays keyed by exact source_name.
- [Phase 01]: Didactic notebooks import cdd_mundial.data production functions and enforce What and why -> code -> Interpretation structurally. — Keeps teaching artifacts synchronized with tested production logic.
- [Phase 01]: Phase acceptance validates materialized artifacts when present and committed parser fixtures in clean environments. — Prevents silent skips while keeping the non-network suite reproducible from a fresh clone.
- [Phase 01]: Public-repository completion requires automated leak gates, GitHub visibility verification, and explicit human approval of rendered documentation. — Combines machine-verifiable hygiene with human judgment of portfolio quality.
- [Phase 01]: DATA-03 Phase 1 evidence covers the complete current Elo snapshot; custom historical Elo recomputation remains the Phase 2 MODEL-01 deliverable. — Preserves the accepted phase boundary without overstating what the snapshot proves.
- [Phase 02]: Tabla K canonica WFE de 5 niveles (60/50/40/30/20) con continentales=50 — D-01 ordena seguir la fuente canonica WFE y la tabla literal de D-01 difiere de ella (pitfall 3)
- [Phase 02]: Nations Leagues clasifican qualifier_major K=40 (A2); predecesores continentales historicos en other K=30 — Assumption A2 del RESEARCH; impacto marginal por decaimiento temporal
- [Phase 02]: Partidos con ET o penales se etiquetan empate de 90 minutos en load_matches — Los marcadores martj42 son FT+ET y no definen el outcome en esos 677 partidos (D-05, pitfall 6)
- [Phase 02]: Ventaja local +100 aplicada a home_team_id cuando neutral==False en TODO el historico (OQ1) — Reconciliacion WFE del Director; D-02 (solo MEX/USA/CAN) aplica unicamente a prediccion 2026
- [Phase 02]: Margen de victoria = variante FiveThirtyEight con rama de empate factor 1.0 — La formula cruda da log(1)=0 y congelaria el 22.7% de partidos empatados (pitfall 1); atribucion documentada
- [Phase 02]: Baseline solo-Elo = ordered logit con MLE sobre (c1, d, log_s) libres — Resuelve OQ4 con la recomendacion del RESEARCH; reparametrizacion garantiza c1<c2 y scale>0 sin bounds
- [Phase 02]: Cold-start 1000 sobre todo el historico; validacion por Spearman (0.979 vs eloratings.net) — Warm-start inviable: el snapshot cubre 48 de 336 equipos (pitfall 9); solo los rangos/diferencias importan
- [Phase 02]: Identifiabilidad Dixon-Coles via penalizacion suave 1000*(sum att^2 + sum dfn^2) en la NLL con gradiente exacto — Elimina la direccion plana sin reparametrizar a n-1 libres (pitfall 7c); sumas del fit < 0.01 verificadas por test
- [Phase 02]: Contrato D-09 congelado con cache de produccion por (path, mtime) y test de firma inspect.signature — Phase 3 consume predict_lambdas a ciegas; el cache evita releer JSON por llamada y se invalida solo con cada re-fit diario (T-02-12)
- [Phase 03]: El fallback oficial de desempate FIFA 2026 (Art. 13 paso 3) es el ranking FIFA, NO sorteo; head-to-head va primero — rules_fifa.py debe seguir el texto oficial pineado, no el wording previo de SIM-01/D-03
- [Phase 03]: El PDF oficial del reglamento no se versiona (data/raw/regulations/ gitignored); la evidencia commiteada es el manifest de procedencia + fixtures con sha256 cruzado, validados fail-closed
- [Phase 03]: Las combinaciones esperadas de mejores terceros se derivan independientemente de C(12,8) + Art. 12.6, nunca de la tabla parseada del Anexo C; el mapping commiteado cubre las 495 con biyeccion y compatibilidad de tokens
- [Phase 03]: TournamentState delgado validado contra fixture: solo resultados jugados team_a/team_b; advanced_team requerido en empates de eliminatoria y prohibido en grupos; fair-play como conduct scores observados (<=0), nunca simulados
- [Phase 03]: Resolver compacto post-empate: q=p_win/(p_win+p_loss) con shrink opcional hacia 0.5; complemento exacto al intercambiar equipos, sin lambdas de ET (D-07/D-08); el engine debe alimentar uniformes de streams keyed por match_id + semilla

### Pending Todos

None yet.

### Blockers/Concerns

- ~~[Phase 3 prerequisito]: Reglamento oficial FIFA 2026 NO verificado~~ — RESUELTO en 03-01: reglamento oficial (edicion MAY 2026) pineado con SHA-256, Art. 13 + Anexo C (495 combinaciones) extraidos y validados fail-closed. OJO: el orden oficial difiere del wording de SIM-01 (head-to-head primero; fallback = ranking FIFA, no sorteo).
- [Phase 3 planning override]: `03-03` modifica 10 archivos de fixtures/tests; el Director aceptó la advertencia de tamaño porque no quedan blockers funcionales ni de cobertura.
- [Stack]: Pin pandas ~=2.3.3 (NO 3.x — seaborn 0.13.2 incompatible); no tocar el pin a mitad de torneo

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-13T01:25:16.485Z
Stopped at: Phase 3 context updated and pending plans revised
Resume file: .planning/phases/03-simulador-del-torneo/03-CONTEXT.md
