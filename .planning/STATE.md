# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-11)

**Core value:** Proyecto de portafolio metodológicamente riguroso y profundamente documentado que enseña ciencia de datos end-to-end real — si los pronósticos fallan pero el proceso es sólido y el aprendizaje quedó capturado, el proyecto cumplió.
**Current focus:** Phase 1 — Fundación de Datos

## Current Position

Phase: 1 of 6 (Fundación de Datos)
Plan: Not yet planned
Status: Ready to plan
Last activity: 2026-06-11 — Roadmap created (6 phases, 29/29 requirements mapped)

Progress: [░░░░░░░░░░] 0%

**HARD DEADLINE:** Fases 1-4 deben estar publicando pronósticos antes del 2026-06-27 (fin de fase de grupos). El torneo empezó HOY.

## Performance Metrics

**Velocity:**
- Total plans completed: 0
- Average duration: -
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**
- Last 5 plans: -
- Trend: -

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Fases 2 y 3 paralelizables vía contrato `predict_lambdas(team_a, team_b, ctx)` — el simulador se construye contra λs stub
- [Roadmap]: Fase 5 (ML) es upgrade gated, no critical path — solo reemplaza al baseline si lo vence en log-loss en los 4 holdouts
- [Roadmap]: El snapshot log append-only arranca con el PRIMER pronóstico publicado (Fase 4) — no se puede rellenar retroactivamente

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 3 prerequisito]: Reglamento oficial FIFA 2026 (orden de desempates, asignación de mejores terceros a R32, puntos fair-play) NO verificado en research — fetch del PDF oficial es la primera tarea del simulador
- [Phase 1]: Fuente de cuotas 2026 (disponibilidad/formato) sin verificar — confirmar durante ingesta
- [Phase 1]: Convenciones del dataset martj42 (penales-como-empates, semántica del flag neutral) — verificar empíricamente al ingestar
- [Stack]: Pin pandas ~=2.3.3 (NO 3.x — seaborn 0.13.2 incompatible); no tocar el pin a mitad de torneo

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-06-11
Stopped at: Roadmap + STATE created; requirements traceability updated
Resume file: None
