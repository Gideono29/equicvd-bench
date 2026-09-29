# Release checklist — v1.0.0 (November 2026)

Zenodo archives every **published GitHub release** of this repository and mints a DOI for it, using the
metadata in `.zenodo.json` (not `CITATION.cff`). Tags without a published release do not trigger it.

## One-time Zenodo setup (done by the maintainer, before the first release)

1. Go to <https://zenodo.org> and choose **Log in → Log in with GitHub** (authorize Zenodo when GitHub asks).
2. Link your ORCID: Zenodo **Account settings → Linked accounts → ORCID** (optional but recommended).
3. Open **Account menu → GitHub**. Click **Sync now** if `Gideono29/equicvd-bench` is not listed.
4. Switch **On** the toggle next to `Gideono29/equicvd-bench`.
5. Check on GitHub: **repository Settings → Webhooks** now lists a `zenodo.org` webhook.

Do **not** publish any GitHub release until you are ready for v1.0.0. Each published release becomes a
permanent Zenodo record with its own DOI.

## Before tagging

- [ ] 30 October calibration-scope decision recorded in `CHANGELOG.md` and reflected in `docs/methods.md`.
- [ ] Version bumped from `1.0.0rc1` to `1.0.0` in **all three** of `pyproject.toml`, `equicvd/__init__.py` and
      `CITATION.cff` (`tests/test_release_metadata.py` fails if they disagree).
- [ ] `CITATION.cff` `date-released:` set to the release date.
- [ ] Full rerun from public data, then commit refreshed `outputs/`:
      `python -m equicvd.cli download`, `cohort`, `bench -B 200`, `sensitivity -B 200`.
- [ ] `pytest -q` passes locally; GitHub Actions is green on `main`.
- [ ] `CHANGELOG.md` has a `## 1.0.0` entry.

## Release

1. GitHub → **Releases → Draft a new release**.
2. **Choose a tag** → type `v1.0.0` → *Create new tag on publish*; target `main`.
3. Title `EquiCVD Bench v1.0.0`; paste the `CHANGELOG.md` entry as the description.
4. **Publish release.**
5. Within a few minutes Zenodo shows the new record under **Account menu → GitHub**. It gets two DOIs:
   - **Version DOI**: this exact release (cite it in the paper's reproducibility statement).
   - **Concept DOI**: always resolves to the latest version (cite it in your CV and README).

## After release

- [ ] Add `doi:` (concept DOI) and `date-released:` to `CITATION.cff`.
- [ ] Add the Zenodo DOI badge from the record page to the top of `README.md`.
- [ ] Upload the derived `data/processed/cohort.csv.gz` and `outputs/**/predictions.csv.gz` to the Zenodo record
      as a separate dataset deposit, if you want them archived (they are excluded from git).
- [ ] Replace `[DOI]` in your CV entry with the concept DOI.
- [ ] Commit and push these edits. (Pushing does not create a new release or DOI; only publishing a release does.)
