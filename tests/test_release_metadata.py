"""Release metadata must be consistent before a GitHub release triggers the Zenodo DOI."""
import json
import re
from pathlib import Path

import equicvd

ROOT = Path(__file__).resolve().parents[1]


def _field(path, pattern):
    m = re.search(pattern, (ROOT / path).read_text(encoding="utf-8"), re.M)
    assert m, f"{pattern} not found in {path}"
    return m.group(1)


def test_versions_agree():
    pyproject = _field("pyproject.toml", r'^version\s*=\s*"([^"]+)"')
    citation = _field("CITATION.cff", r"^version:\s*(\S+)")
    assert pyproject == equicvd.__version__ == citation


def test_zenodo_metadata_complete():
    z = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    assert z["upload_type"] == "software" and z["license"] == "MIT" and z["access_right"] == "open"
    for c in z["creators"]:
        assert re.fullmatch(r"[^,]+, [^,]+", c["name"]), "creator name must be 'Family, Given'"
        assert re.fullmatch(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]", c.get("orcid", "")), "bare ORCID iD expected"
    assert "TODO" not in json.dumps(z)
