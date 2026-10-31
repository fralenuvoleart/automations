"""Differential test: seo/report/schema_lite.py vs the reference `jsonschema` (Draft 7).

`jsonschema` is a *development* oracle only — the toolkit ships stdlib-only (see seo/requirements.txt).
Where it is not installed the test prints SKIP and passes, so `bash seo/check.sh` stays hermetic;
on a workstation with `seo/requirements-dev.txt` (or any venv) it proves equivalence on the real
schema and a mutation corpus. Verdict **and** the failing path must agree; message wording is ours.
"""
import copy
import json
import random
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import schema_lite  # noqa: E402
from _runner import main  # noqa: E402

SCHEMA = json.loads((SEO / "references" / "findings-schema.json").read_text())
BASE = json.loads((SEO / "tests" / "fixtures" / "findings_example.json").read_text())


def _oracle():
    try:
        import jsonschema
    except ImportError:
        return None
    return jsonschema.Draft7Validator(SCHEMA)


def _rich() -> dict:
    """A valid document exercising every optional branch of the schema."""
    doc = copy.deepcopy(BASE)
    doc["window"].update({"source": "ga4", "compareStartDate": "2026-08-01", "compareEndDate": "2026-08-28",
                          "compareMode": "previous", "days": 28})
    doc["sections"] = [
        {"heading": "Overview", "body": "b", "estimate": True,
         "window": {"startDate": "2026-09-01", "endDate": "2026-09-28", "note": "snapshot"},
         "table": [{"q": "a", "n": 1, "b": True, "z": None}]},
        {"heading": "Second", "body": "b", "window": {"note": "no dates"}},
        {"heading": "Third", "body": "b", "window": {"startDate": "2026-09-01", "endDate": "2026-09-28"}},
    ]
    doc["actions"] = [{"action": "do x", "impact": "high", "effort": "low", "page": "https://x.ge/a",
                       "why": "w", "est_clicks": 12, "keyword": "k", "category": "c"}, "plain string"]
    doc["unavailable"] = [{"source": "dataforseo (dfs.anchors)", "affects": "anchor mix"}]
    doc["coverage"] = {"basis": "gsc_impressions", "priority_keywords": ["a"], "priority_pages": ["https://x.ge/"],
                       "covered": ["a"], "missing": [], "by_language": {"ru": {"total": 3, "covered": 2,
                                                                                "missing": 1}}}
    return doc


REMOVE = object()
WRONG = [None, True, False, 0, -1, 1.5, "", "x", "2026-13-45", [], {}, [1, 2], {"a": 1}, "  "]


def _walk_nodes(o, path=()):
    yield path, o
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _walk_nodes(v, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_nodes(v, path + (i,))


def _set(doc, path, value):
    out = copy.deepcopy(doc)
    cur = out
    for k in path[:-1]:
        cur = cur[k]
    if value is REMOVE:
        del cur[path[-1]]
    else:
        cur[path[-1]] = value
    return out


def _mutations(doc):
    for path, node in list(_walk_nodes(doc)):
        if not path:
            continue
        yield _set(doc, path, REMOVE)
        for wrong in WRONG:
            if type(wrong) is type(node) and wrong == node:
                continue
            yield _set(doc, path, wrong)
        if isinstance(node, list):
            yield _set(doc, path, [])


def _paths(errors):
    return sorted(tuple(str(p) for p in e.absolute_path) for e in errors)


def test_schema_lite_agrees_with_jsonschema_on_every_mutation():
    validator = _oracle()
    if validator is None:
        print("SKIP test_schema_lite_agrees_with_jsonschema_on_every_mutation "
              "(jsonschema not installed — pip install -r seo/requirements-dev.txt to run the oracle)")
        return
    bases = [BASE, _rich()]
    cases = []
    for base in bases:
        assert _paths(validator.iter_errors(base)) == [], "base document must be schema-valid"
        assert _paths(schema_lite.iter_errors(base, SCHEMA)) == [], "base document must be schema-valid"
        cases += list(_mutations(base))
    rnd = random.Random(11)
    for _ in range(400):
        doc = copy.deepcopy(rnd.choice(bases))
        for _ in range(rnd.randint(1, 3)):
            paths = [p for p, _ in _walk_nodes(doc) if p]
            if not paths:
                break
            doc = _set(doc, rnd.choice(paths), rnd.choice(WRONG + [REMOVE]))
        cases.append(doc)

    bad = []
    for doc in cases:
        mine, theirs = _paths(schema_lite.iter_errors(doc, SCHEMA)), _paths(validator.iter_errors(doc))
        if mine != theirs:
            bad.append((mine, theirs))
    assert not bad, f"{len(bad)} divergences of {len(cases)} cases, first: {bad[0]}"
    print(f"     oracle: {len(cases)} cases, 0 divergences")


if __name__ == "__main__":
    main(globals())
