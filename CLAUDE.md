# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -e ".[dev]"          # pytest, ruff, mypy
pytest -q                        # full suite (testpaths = tests)
pytest tests/test_spec_fidelity.py::test_name    # single test
ruff check src tests
mypy src                         # strict, python_version 3.11

python scripts/build_vendored.py           # regenerate vendored/geospatial_spec.py
python scripts/build_vendored.py --check    # CI drift gate
python scripts/prune_witness.py <src.xml> <dst.xml>   # trim a large S1 annotation to the read subtrees
```

CI ([.github/workflows/ci.yml](.github/workflows/ci.yml)) runs three jobs: the test/lint/type matrix on 3.11–3.13; a `pip install --no-deps` job proving the package imports and self-verifies with nothing installed; and the vendored-file drift check.

## Architecture

The product is a *constraint*, not a data table: no public name may hand back a value without being told the scope that makes the value correct. Three mechanisms enforce that, and changes must preserve all three.

**1. Guards, not constants.** [src/geospatial_spec/_table.py](src/geospatial_spec/_table.py) holds a private `FactTable` keyed by fact name. Public modules ([sentinel2.py](src/geospatial_spec/sentinel2.py), [sentinel1.py](src/geospatial_spec/sentinel1.py), [common.py](src/geospatial_spec/common.py)) expose only callables that require a scope argument (`baseline=`, `product=`, …) and then call `table.get_as(...)`. Missing scope raises `ScopeRequired`. [tests/test_no_bare_constants.py](tests/test_no_bare_constants.py) mechanically fails any public name in a public module that is not a callable, exception, or enum — adding a module-level constant breaks the build by design. `SpecFact` ([_types.py](src/geospatial_spec/_types.py)) is a *return value* of `explain()`, never a module-level accessor.

**2. Witnesses.** Every fact registers a `cite` (spec document) and ideally a `witness` — a zero-arg callable returning `dict[str, object]`, built by [_witness.py](src/geospatial_spec/_witness.py) (`from_xml`, `from_json`, `from_mapping`). Real ESA metadata lives in [src/geospatial_spec/_witnesses/](src/geospatial_spec/_witnesses/) and ships in the wheel, so an installed copy can verify itself. `FactTable.check_witnesses()` returns disagreements; [tests/test_spec_fidelity.py](tests/test_spec_fidelity.py) asserts it is empty. `from_mapping` is the weak form (transcription, not verification) — use sparingly; `unwitnessed()` tracks the liability list.

**3. Vendorability.** [scripts/build_vendored.py](scripts/build_vendored.py) concatenates the package into [vendored/geospatial_spec.py](vendored/geospatial_spec.py) with the XML witnesses gzip+base64-embedded, so a curl'd copy still checks itself. `MODULES` there is an explicit dependency-ordered list — a new module must be added to it. [tests/test_vendored.py](tests/test_vendored.py) imports the generated file from an isolated sandbox dir and runs the package's properties against it.

## Workflow

- **TDD, always.** Every plan and every implementation starts with a failing unit test that pins the behavior, then the code that makes it pass. No production change lands without a test that would have failed before it.
- **Plans are documents.** After planning, save the plan to `docs/plans/` with a numeric prefix (`001-<slug>.md`, `002-…`). If the plan changes mid-flight, update that same doc rather than leaving it stale or writing a second one.
- **Docs track the repo.** Any change to the repo carries the corresponding update to existing docs ([README.md](README.md), [docs/FACTS.md](docs/FACTS.md), `_witnesses/PROVENANCE.md`, the plan doc) in the same change.
- **Never commit or push.** Claude does not run `git commit` or `git push` — stage nothing on the user's behalf; leave the working tree for the user to review and commit themselves. Enforced by deny rules and a PreToolUse hook in [.claude/settings.json](.claude/settings.json).

## Constraints

- **Zero runtime dependencies, permanently.** This is the adoption argument and CI enforces it in an isolated job. Never add to `dependencies`, and never import from `geocase`.
- Package data (witnesses) must stay small; the wheel targets <100 KB. Prune large artifacts with `prune_witness.py` and record what was dropped in `_witnesses/PROVENANCE.md`.
- Sentinel-1 is **frozen** — port nothing new into it. See the README roadmap for what ranks ahead.
- The README states the project's claims carefully (what this is *not*: bug discovery, a silent-bias claim). Keep code docstrings consistent with that framing; several modules restate it deliberately.
