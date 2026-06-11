---
phase: 1
slug: fundaci-n-de-datos
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 1 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pyproject.toml` - Wave 0 creates it |
| **Quick run command** | `python -m pytest -q {target_test_file}` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | Under 30 seconds without network tests |

---

## Sampling Rate

- **After every task commit:** Run the targeted pytest file named by the task.
- **After every plan wave:** Run `python -m pytest -q`.
- **Before `$gsd-verify-work`:** Full suite must be green.
- **Max feedback latency:** 30 seconds for the default non-network suite.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | DOC-03 | T-01-01 | Secrets and restricted raw captures are excluded | config | `python -m pytest -q tests/test_repository.py` | No - W0 | pending |
| 01-01-02 | 01 | 1 | DATA-01 | T-01-02 | Canonical outputs reject schema drift and invalid invariants | unit | `python -m pytest -q tests/test_contracts.py` | No - W0 | pending |
| 01-02-01 | 02 | 2 | DATA-02 | T-01-03 | Runtime fuzzy matching is rejected | unit | `python -m pytest -q tests/test_identities.py` | Yes | green |
| 01-02-02 | 02 | 2 | DATA-01 | T-01-04 | Scores preserve source semantics | contract | `python -m pytest -q tests/test_ingest_martj42.py` | Yes | green |
| 01-02-03 | 02 | 2 | DATA-01, DATA-02 | T-01-03 | Unresolved identities fail the pipeline | integration | `python -m pytest -q tests/test_data_foundation.py` | Yes | green |
| DATA-01-ACCEPTANCE | remediation | gate | DATA-01 | T-01-03, T-01-04 | Real parquet, complete historical identities, raw captures, and provenance checksums are required | acceptance | `python -m pytest -q -m data_acceptance tests/test_data01_acceptance.py` | Yes | green |
| 01-03-01 | 03 | 2 | DATA-03 | T-01-05 | HTTP responses are bounded, checked, and cached | contract | `python -m pytest -q tests/test_ingest_elo.py` | No - W0 | pending |
| 01-03-02 | 03 | 2 | DATA-04 | T-01-06 | Fixture IDs/timestamps are unique and canonical | contract | `python -m pytest -q tests/test_fixture.py` | No - W0 | pending |
| 01-04-01 | 04 | 2 | DATA-05 | T-01-01 | API key never enters artifacts or logs | unit | `python -m pytest -q tests/test_odds.py` | No - W0 | pending |
| 01-04-02 | 04 | 2 | DATA-05 | T-01-07 | Unsupported/two-way markets fail explicitly | contract | `python -m pytest -q tests/test_odds.py` | No - W0 | pending |
| 01-05-01 | 05 | 3 | DOC-01 | - | N/A | structural | `python -m pytest -q tests/test_notebooks.py` | No - W0 | pending |
| 01-05-02 | 05 | 3 | DOC-03 | T-01-01 | Public docs expose no credentials | structural | `python -m pytest -q tests/test_repository.py` | No - W0 | pending |
| 01-05-03 | 05 | 3 | DATA-01..05 | T-01-03 | Coverage report exposes all unresolved source mappings | integration | `python -m pytest -q` | No - W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` - package metadata, dependencies, pytest markers, ruff configuration.
- [ ] `tests/conftest.py` - temporary data roots and source fixture helpers.
- [ ] `tests/fixtures/` - small martj42, Elo, fixture, and odds payloads.
- [ ] `tests/test_repository.py` - secret/gitignore/README structure checks.
- [ ] `tests/test_contracts.py` - strict pandera schema and invariant tests.
- [ ] `tests/test_provenance.py` - metadata and checksum tests.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| FIFA fixture matches the currently published official schedule | DATA-04 | Official presentation/download may change and requires authoritative visual cross-check | Compare all 104 match IDs, kickoff times, venues, and group assignments against the current FIFA artifact; record URL and verification timestamp. |
| Odds provider terms permit the chosen repository storage policy | DATA-05, DOC-03 | Redistribution terms are legal/provider-specific | Read current provider terms, record the license/terms URL in provenance, and confirm raw payload commit/ignore policy. |
| GitHub repository visibility and rendered README quality | DOC-03 | Remote hosting and visual presentation are external | Confirm repository is public, README renders, installation commands are accurate, and no secret scanning alert exists. |

---

## Validation Sign-Off

- [x] All planned tasks have an automated command or Wave 0 dependency.
- [x] Sampling continuity has no three consecutive tasks without automated verification.
- [x] Wave 0 covers all missing test references.
- [x] No watch-mode flags are used.
- [x] Expected feedback latency is under 30 seconds.
- [x] `nyquist_compliant: true` is set in frontmatter.

**Approval:** approved 2026-06-11
