<!-- GSD:project-start source:PROJECT.md -->
## Project

**CDD-MUNDIAL — Pronósticos del Mundial 2026**

Sistema de ciencia de datos end-to-end que pronostica los resultados del Mundial 2026 (11 jun – 19 jul 2026) mediante machine learning y simulación Monte Carlo. Combina modelos estructurales (Elo dinámico, Dixon-Coles) con ML (XGBoost/scikit-learn) en un ensemble calibrado que alimenta simulaciones del torneo completo (≥10,000 corridas), actualizándose tras cada jornada con resultados reales. Es un proyecto de aprendizaje y portafolio para Jesús (estudiante ITESM), donde Claude actúa como gestor de proyecto y hard coder vía MCP Jupyter, y Jesús como Director que toma decisiones metodológicas y valida críticamente.

**Core Value:** Un proyecto de portafolio metodológicamente riguroso y profundamente documentado que enseña ciencia de datos end-to-end real — si los pronósticos fallan pero el proceso es sólido y el aprendizaje quedó capturado, el proyecto cumplió.

### Constraints

- **Timeline**: El torneo termina el 19 jul 2026 — el baseline (Elo + Dixon-Coles + Monte Carlo) debe estar publicando pronósticos antes del fin de la fase de grupos (27 jun); el ensemble ML es mejora incremental sobre un sistema ya funcionando
- **Pedagogía**: Estructura de notebook obligatoria en TODOS los notebooks: celda markdown que documenta (qué y por qué) → celda de código → celda markdown que interpreta resultados. El repo es material de estudio
- **Tech stack**: Python + pandas/numpy/scipy/scikit-learn/XGBoost; visualización solo matplotlib/seaborn; parquet para datos procesados; pandera para validación de esquemas
- **Datos**: `data/raw/` es inmutable; toda transformación produce archivos nuevos en `data/processed/` con metadatos de extracción
- **Reproducibilidad**: Todo pronóstico debe poder regenerarse desde raw + código versionado; semillas fijas en simulaciones para reportes
- **Repo**: GitHub público — README de calidad portafolio, sin claves ni datos con licencia restrictiva versionados
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 or 3.12 | Runtime | Floor required by pandas/numpy/scipy current releases (`>=3.11`). 3.11/3.12 are the most battle-tested with this stack on Windows. Avoid 3.13+ until needed — zero upside for this project, occasional wheel gaps. |
| pandas | **2.3.3 (pin `~=2.3.3`, NOT 3.x)** | Tabular data manipulation | **Critical pin.** pandas 3.0 shipped recently (3.0.3 on PyPI) with breaking changes (copy-on-write default, new string dtype). seaborn's last release (0.13.2) is from **Jan 2024**; its pandas-3.0 compatibility fix (PR mwaskom/seaborn#3894) is merged but **unreleased**. For a 5-week express project, pandas 2.3.x eliminates an entire class of debugging. |
| numpy | 2.x (latest, currently 2.4.6) | Vectorized Monte Carlo engine, array math | The simulation engine IS numpy. 10k–100k tournament sims of 104 matches is trivial vectorized (sample all group-stage scorelines as `(n_sims, n_matches)` Poisson arrays). No compiled extensions needed. |
| scipy | 1.17.x | Dixon-Coles MLE (`scipy.optimize.minimize`), Poisson/skellam distributions | `scipy.optimize.minimize(method="L-BFGS-B")` over the negative weighted log-likelihood is the standard way to fit Dixon-Coles. `scipy.stats.poisson` for PMFs/sampling checks. |
| scikit-learn | 1.9.0 | ML pipelines, temporal CV, calibration, metrics | `TimeSeriesSplit`, `CalibratedClassifierCV(method="isotonic")`, `log_loss`, `brier_score_loss`, `calibration_curve` — everything the validation/calibration layer needs in one audited library. |
| XGBoost | 3.2.0 | Gradient boosting: 3-class classifier (1/X/2) + Poisson goal regressors | Chosen over LightGBM (see Alternatives). One library covers both model types: `multi:softprob` for the classifier, `count:poisson` for goal regressors (ML alternative to Dixon-Coles λ). sklearn-compatible API plugs into the calibration/CV tooling. |
| pyarrow | 24.0.0 | Parquet read/write engine for pandas | Required by the parquet constraint. `pip install pyarrow` and use `df.to_parquet(...)` — pandas auto-detects it. |
| pandera | 0.31.1 (install as `pandera[pandas]`) | DataFrame schema validation at pipeline stage boundaries | Lightweight contract checks (dtypes, ranges, team names ∈ master table). **Note:** since 0.24 the canonical import is `import pandera.pandas as pa` — use this, not the legacy `import pandera as pa`. |
### Modeling Components: Build vs. Library (the key decisions)
| Component | Decision | Rationale | Confidence |
|-----------|----------|-----------|------------|
| **Dixon-Coles** | **Custom implementation** with scipy (`src/models/dixon_coles.py`); use **penaltyblog 1.11.0** as a verification benchmark only | (1) Pedagogy is a hard project requirement — DC's weighted likelihood, ρ low-score correction, and exponential time decay are exactly the learning content. (2) International football needs adaptations penaltyblog's league-oriented API doesn't expose cleanly: per-match neutral-venue flags (most World Cup matches), confederation-spanning team sets, tournament-importance weighting. (3) penaltyblog drags heavy deps (plotly, pulp, statsbombpy, networkx, kaleido, ipywidgets) — conflicts with the matplotlib/seaborn-only constraint if it leaks into reports. Custom DC is ~150 lines; cross-check λ outputs against penaltyblog's `DixonColesGoalModel` on a shared dataset, then drop it from the runtime path. | HIGH |
| **Elo ratings** | **Custom implementation** (~60 lines, `src/features/elo.py`) | No library implements the World Football Elo formula (eloratings.net variant): goal-margin multiplier, tournament-importance K (60 for World Cup … 20 for friendlies), +100 home advantage. Libraries like `elote` or penaltyblog's Elo are generic two-outcome Elo — you'd spend more time bending them than writing the real formula. Custom also lets you backtest K/home-advantage on the historical Kaggle data, which is a planned deliverable. | HIGH |
| **Monte Carlo engine** | **Custom vectorized numpy** (`src/simulation/`) | No off-the-shelf simulator implements the 2026 format (48 teams, 12 groups, 8 best third-places, FIFA tiebreakers). `numpy.random.Generator.poisson` with shape `(n_sims, n_matches)` + integer-array group-table accounting hits the <1 min target easily for 100k sims. **Skip numba** — it pins numpy `<2.5` (verified) and the vectorized version is already fast enough; only revisit if FIFA tiebreaker resolution (inherently branchy) becomes a measured bottleneck. | HIGH |
| **Calibration** | scikit-learn isotonic via `FrozenEstimator` | For calibrating an already-trained model on a held-out temporal slice: `CalibratedClassifierCV(FrozenEstimator(model), method="isotonic")`. **`cv="prefit"` is gone** — `sklearn.frozen.FrozenEstimator` (verified present in 1.9 stable docs) is the current pattern. Isotonic over Platt/sigmoid: no parametric-shape assumption, and with ~5k+ calibration samples (historical matches) it won't overfit. | HIGH |
| **Metrics (RPS)** | Custom ~10-line function; sklearn for log-loss/Brier | Ranked Probability Score isn't in sklearn. penaltyblog has one (`pb.metrics.rps`) usable as a cross-check, but a 10-line cumulative-sum implementation is the pedagogically correct move. | HIGH |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| kagglehub | 1.0.2 | Download Kaggle dataset | **No API key needed for public datasets** (verified in official README: "Authenticating is only needed to access public resources requiring user consent or private resources"). One line: `kagglehub.dataset_download("martj42/international-football-results-from-1872-to-2017")` (handle verified live, HTTP 200). Solves the "user has no Kaggle API key" friction entirely. |
| requests | latest | HTTP for eloratings.net TSV endpoints, FIFA fixture sources | See scraping section below — plain `requests` with a User-Agent header suffices; no browser automation needed. |
| beautifulsoup4 + lxml | 4.15.0 / latest | HTML parsing for FIFA rankings / Wikipedia fixture tables | Only for sources that are actual HTML. `pandas.read_html` (uses lxml) often suffices for Wikipedia tables. |
| statsmodels | 0.14.6 | GLM Poisson regression reference | Optional: fit a vanilla independent-Poisson GLM as the pedagogical stepping stone before Dixon-Coles, and as a sanity benchmark. Not on the production path. |
| matplotlib + seaborn | 3.10.9 / 0.13.2 | All reporting visuals | Project constraint. seaborn 0.13.2 is the latest release and works with pandas 2.3.x. Reliability diagrams, probability heatmaps per group, P(champion) bar races. |
| joblib | latest (ships with sklearn) | Model artifact persistence | `joblib.dump(model, "models/ensemble_2026-06-15.pkl")` — standard for sklearn-family objects. |
| penaltyblog | 1.11.0 | Verification benchmark for DC + RPS | Install in the venv for cross-checks during F2; never import in `src/` runtime code (heavy transitive deps). |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| JupyterLab + ipykernel | Notebook workflow via MCP Jupyter | Register the venv kernel: `python -m ipykernel install --user --name cdd-mundial`. |
| pytest | Unit tests for `rules_fifa.py` tiebreakers and Elo updates | The FIFA tiebreaker cascade (points → GD → GF → head-to-head → fair play → drawing of lots) is the highest-bug-risk code in the project; test against known historical group tables. |
| MCP Playwright | Scraping fallback ONLY | Keep available but unused — see scraping section. Do not reach for it first. |
## Data Acquisition Approach (verified live today)
### Kaggle historical results — kagglehub, zero-auth
# caches under ~/.cache/kagglehub/ — copy results.csv etc. into data/raw/ with extraction metadata
### eloratings.net — NO browser scraping needed (verified live, 2026-06-11)
- `https://www.eloratings.net/World.tsv` — current world ratings table (rank, 2-letter code, rating, rating-change columns, W/D/L aggregates). **Verified returning data today** (ES 2157, AR 2115, FR 2063, EN 2024, BR 1991 …).
- `https://www.eloratings.net/en.teams.tsv` — code → canonical name mapping incl. aliases (verified: `AR Argentina`, `AG Antigua and Barbuda Antigua & Barbuda …`). Feed this into the master teams table.
- Per-year endpoints exist with the same pattern (e.g. `World.tsv` variants by date) for historical snapshots if needed; the Kaggle dataset + custom Elo recomputation covers history regardless.
### FIFA rankings + 2026 fixture
- Fixture: Wikipedia's 2026 World Cup article tables via `pandas.read_html`, then hand-verify the 104 rows once and freeze as `data/external/fixture_2026.csv` (it's static except kickoff results).
- FIFA rankings: Kaggle mirror datasets via kagglehub, or scrape the official page with requests/bs4. Low frequency (monthly) — a one-time manual CSV is acceptable.
## Installation
# inside the cdd-mundial venv (Python 3.11/3.12)
# verification-only (optional, F2): pulls heavy deps — fine in venv, never import in src/
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| XGBoost 3.2.0 | LightGBM 4.6.0 | Both are excellent on small tabular data (~5k usable matches, ~20–40 features); performance difference here is noise. XGBoost wins on tie-breakers: design doc already names it, `count:poisson` objective is well-documented, richer docs/community for the calibration+sklearn integration. Switch to LightGBM only if you hit Windows build/wheel problems with XGBoost (unlikely — official wheels exist) or want its native categorical handling. **Do not run both** — doubles tuning surface for zero portfolio value. |
| pandas 2.3.3 | pandas 3.0.3 | Only after seaborn ships a release containing PR #3894, or if you drop seaborn. Revisit post-tournament, not during. |
| Custom Dixon-Coles | penaltyblog `DixonColesGoalModel` | If the express timeline collapses and F2 must ship in a day, penaltyblog gets you fitted λ fast. You lose neutral-venue/tournament-weight control and the learning content. |
| Custom Elo | `elote`, penaltyblog ratings | Never for this project — neither implements goal-margin/tournament-K World Football Elo. |
| kagglehub | manual CSV download from kaggle.com | Fine as one-time fallback; kagglehub is preferred because re-downloads (dataset updates during the tournament — martj42 updates regularly with new results) become reproducible code instead of a manual step. |
| isotonic calibration | Platt (sigmoid) calibration | If the calibration slice is small (<~1k samples) sigmoid is safer; with full historical validation sets, isotonic is strictly more flexible. Compare both on reliability diagrams — it's one parameter. |
| scipy MLE Dixon-Coles | Bayesian DC (PyMC / penaltyblog Bayesian models) | Posterior uncertainty on λ would be a nice F5+ extension; MCMC fit time and complexity don't fit the express timeline. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pandas 3.x (now) | seaborn 0.13.2 (Jan 2024, latest) predates it; its compat fix is merged-but-unreleased. Breaking changes (CoW, string dtype) mid-tournament is self-sabotage. | pandas ~=2.3.3 |
| `kaggle` CLI | Requires API token setup the user doesn't have; pure friction. | kagglehub (no auth for public datasets) |
| Playwright/Selenium for eloratings.net | The TSV endpoints make browser automation pointless: slower, fragile, and unnecessary. | `requests` + User-Agent on `World.tsv` / `en.teams.tsv` |
| numba | Pins numpy `<2.5` (verified), adds compile complexity; vectorized numpy already hits the <1 min/100k-sims target. | Pure vectorized numpy; profile first if slow |
| `cv="prefit"` in CalibratedClassifierCV | Deprecated/removed pattern in current sklearn. | `sklearn.frozen.FrozenEstimator` wrapper |
| Deep learning (PyTorch/TF) | ~5k relevant international matches; GBMs + structural models are the documented ceiling. Already out of scope per PROJECT.md. | XGBoost + Dixon-Coles ensemble |
| plotly / Streamlit | Out of scope per Director decision; penaltyblog pulls plotly transitively — keep it out of `src/`. | matplotlib + seaborn static reports |
| `pickle` directly for models | joblib is the sklearn-ecosystem standard, handles numpy arrays efficiently. | `joblib.dump/load` with date-versioned filenames |
## Stack Patterns by Variant
- Swap to LightGBM 4.6.0 with `objective="multiclass"` / `objective="poisson"`
- Because both expose sklearn APIs, the ensemble/calibration code is unchanged.
- Pandera schema on ingest fails loudly → fall back to recomputing Elo purely from the Kaggle results dataset (custom `elo.py` already does this for features)
- Because self-computed Elo removes the external dependency entirely; eloratings.net is then just a calibration cross-check.
- First reduce to 10k for daily reports (sampling error on P(champion) at 10k is ±~0.4pp, acceptable)
- Then profile; only then consider numba (accepting the numpy pin) or restructuring the tiebreaker code.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| seaborn 0.13.2 | pandas 2.3.x ✅ / pandas 3.x ⚠️ | Compat PR #3894 merged upstream but no release since 2024-01-25. THE pin driving the stack. |
| pandera 0.31.1 `[pandas]` extra | pandas >=2.1.1 ✅ | Verified from PyPI requires_dist; works with 2.3.x. Use `import pandera.pandas as pa`. |
| numba 0.65.1 | numpy >=1.22,<2.5 | Only relevant if numba is ever added; numpy 2.4.6 squeaks under the pin but blocks future numpy upgrades — another reason to skip it. |
| scikit-learn 1.9.0 | Python >=3.11 | `FrozenEstimator` available (since 1.6); confirmed in 1.9 stable docs. |
| pandas 2.3.3 | numpy 2.x ✅, pyarrow 24 ✅ | Standard combination, no known issues. |
| penaltyblog 1.11.0 | unpinned numpy/pandas/scipy deps | Installs cleanly alongside the stack (no upper pins, verified requires_dist), but pulls plotly/pulp/statsbombpy/networkx — quarantine to verification notebooks. |
## Sources
- PyPI JSON API (fetched 2026-06-11) — exact current versions and `requires_dist` for all 16 packages listed. **HIGH**
- https://www.eloratings.net/World.tsv and /en.teams.tsv — fetched live 2026-06-11, confirmed plain-TSV data with current ratings. **HIGH**
- github.com/Kaggle/kagglehub README (official) — no-auth public dataset downloads, `dataset_download` API. **HIGH**
- kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017 — handle verified live (HTTP 200). **HIGH**
- github.com/martineastwood/penaltyblog README (official) — Dixon-Coles/Bivariate Poisson/Elo/RPS feature set, Cython optimization, active maintenance (v1.11.0). **HIGH**
- github.com/mwaskom/seaborn — latest release v0.13.2 (2024-01-25) via GitHub API; PR #3894 "Address deprecation warnings with pandas 3.0 release candidate" merged but unreleased. **HIGH**
- scikit-learn.org stable docs — `sklearn.frozen.FrozenEstimator` page exists (HTTP 200); `CalibratedClassifierCV` docs reference FrozenEstimator, no `cv="prefit"` remaining. **HIGH**
- XGBoost `multi:softprob` / `count:poisson` objectives — training data, consistent with verified XGBoost 3.2.0 docs structure; standard long-stable API. **MEDIUM-HIGH**
- World Football Elo formula details (K=60 World Cup, goal-margin multiplier, +100 home) — training data, formula published on eloratings.net/about; verify exact constants when implementing `elo.py`. **MEDIUM**
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
