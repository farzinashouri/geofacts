# 001 — Publish `geofacts` to PyPI

## State

The name `geofacts` is unclaimed on both PyPI and TestPyPI (checked 2026-08-16;
both `/pypi/geofacts/json` endpoints return 404).

## Done

- **Metadata.** `pyproject.toml` gained `authors`, `[project.urls]`, and moved
  from `license = { file = "LICENSE" }` to the PEP 639 form
  (`license = "MIT"` + `license-files`). The
  `License :: OSI Approved :: MIT License` classifier was removed — a license
  expression and a license classifier cannot coexist, and newer build backends
  reject the pair.
- **Build verified locally.** `python -m build` → wheel 36.7 KB (the wheel
  budget is <100 KB), sdist 78 KB; `twine check` passes both. The wheel carries
  `py.typed` and all three `_witnesses/` files.
- **Installed-copy check.** `pip install --no-deps` of the built wheel into an
  empty venv, then `boa_offset(baseline="04.00") == -1000` and
  `check_witnesses() == []` — the property the package is sold on holds from
  the artifact, not just from the source tree.
- **Release workflow.** `.github/workflows/publish.yml`: `gate` (tests, ruff,
  mypy, vendored drift) → `build` (build, assert witnesses present in the
  wheel, twine check) → `testpypi` *or* `pypi`, both Trusted Publishing with
  `id-token: write`. Publishing a GitHub Release always takes the `pypi` path;
  `workflow_dispatch` defaults to `testpypi` so a manual run cannot burn a
  version number on the real index. The two jobs carry `environment: testpypi`
  and `environment: pypi` respectively — those strings must match the
  Environment name field of each index's pending publisher.
- **PR merged** as `0b66b2d`, so `main` holds the workflow — required, since
  `release` and `workflow_dispatch` only ever run the default branch's copy.
- **README.** The vendored-file `curl` line now points at the real raw URL
  instead of `https://raw.githubusercontent.com/...`.

## Remaining — needs the maintainer

1. ~~TestPyPI pending publisher~~ — done, environment `testpypi`.
2. Create the matching `testpypi` environment in GitHub repo settings, push
   the two-target workflow to `main`, then Actions → publish → Run workflow →
   target `testpypi` for the dry run.
3. Create the PyPI account, then add a **pending publisher** under
   Publishing: owner `farzinashouri`, repo `geofacts`, workflow
   `publish.yml`, environment `pypi`; and create the `pypi` GitHub
   environment.
4. Tag `v0.1.0` by publishing the GitHub Release — that fires the workflow
   down the `pypi` path.

## Notes

- Version `0.1.0` is single-use on PyPI. A mistake in the uploaded artifact
  costs a version bump, which is why the gate job duplicates CI rather than
  trusting that CI ran.
- The archive date in the README (2026-11-13) is a release-independent
  commitment; publishing does not move it.
