# Phase 04: Primer Pronostico + Pipeline Diario - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-06-13
**Phase:** 04-primer-pronostico-pipeline-diario
**Areas discussed:** Ingesta de resultados en vivo, Snapshot append-only, Reporte estatico diario, Tracker de calibracion vs mercado, Refresh del modelo

---

## Ingesta de resultados en vivo

| Option | Description | Selected |
|--------|-------------|----------|
| `results_2026.csv` canonico | El CSV manda; scraper solo ayuda o valida. | ✓ |
| Scraper principal | El proveedor externo manda y el CSV queda como fallback. | |
| Reconciliacion dual | Scraper + CSV con reconciliacion mas pesada. | |

**User's choice:** `results_2026.csv` canónico, minimalista, con scraper como verificación y falla por defecto cuando el CSV esté incompleto.
**Notes:** El usuario quería entender el workflow simple: actualizar el CSV para fijar el presente real, re-simular el futuro condicionado en ese presente y publicar por jornada o bloque relevante, no tras cada partido necesariamente.

---

## Snapshot append-only

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot minimo | Solo probabilidades por equipo. | |
| Snapshot medio | Probabilidades + metadata básica. | |
| Snapshot rico | Probabilidades por equipo, pronosticos proximos y metadata fuerte. | ✓ |

**User's choice:** snapshot rico en carpeta propia, con commit hash obligatorio, worktree limpio por defecto, datos canónicos siempre versionados y reporte renderizado cuando la corrida sea publicación oficial.
**Notes:** Se aclaró que "snapshot publicable" significa la foto oficial del pronóstico en un momento dado, la que idealmente se commitea a git antes del kickoff correspondiente.

---

## Reporte estatico diario

| Option | Description | Selected |
|--------|-------------|----------|
| HTML + matplotlib/seaborn | Reporte HTML con visuales clasicos. | |
| HTML + Plotly | Reporte HTML mas interactivo/moderno. | |
| Mixto | HTML estático oficial con mezcla de matplotlib/seaborn y Plotly cuando aporte. | ✓ |

**User's choice:** HTML estático oficial mixto, con secciones obligatorias de resumen, bloque próximo, probabilidades del torneo, evolución temporal y nota metodológica; grupos queda opcional.
**Notes:** Esta decisión reemplazó la restricción anterior de usar solo `matplotlib`/`seaborn`; el notebook queda como interfaz de inspección/orquestación, no como mecanismo oficial de publicación.

---

## Tracker de calibracion vs mercado

| Option | Description | Selected |
|--------|-------------|----------|
| Por jornada agregada | Solo métricas agregadas por bloque/jornada. | |
| Por partido | Base canónica partido a partido. | |
| Ambas, base por partido | Detalle por partido y agregados derivados. | ✓ |

**User's choice:** tracker canónico por partido, benchmark de mercado agregado con mediana de probabilidades de-margined, y benchmark principal congelado al momento de publicar el snapshot.
**Notes:** El usuario corrigió la primera preferencia sobre D-20: no usar la última cuota pre-kickoff como benchmark principal, sino la cuota capturada cuando se publica el snapshot oficial.

---

## Refresh del modelo

| Option | Description | Selected |
|--------|-------------|----------|
| Rebuild oficial siempre | Todo se rehace desde artefactos canónicos en cada corrida. | |
| Incremental oficial | La publicación corre sobre actualización incremental. | |
| Mixto | Publicación oficial reproducible + modo rápido incremental solo para exploración. | ✓ |

**User's choice:** modo mixto.
**Notes:** La publicación oficial queda del lado reproducible y auditable; el modo rápido puede existir, pero no como camino oficial de publicación.

---

## the agent's Discretion

- Balancear `matplotlib`/`seaborn` y `Plotly` dentro del HTML sin convertir el reporte en una app viva.
- Elegir el layout exacto de carpetas y archivos del snapshot.
- Elegir cuándo mostrar sección detallada de grupos según contexto competitivo de la jornada.

## Deferred Ideas

- Publicar snapshot después de cada partido individual.
- Convertir el reporte diario en dashboard persistente.
- Hacer del flujo incremental el camino oficial de publicación.
