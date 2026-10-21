"""Recompute a REA Evidence semantic identifier.

REA authenticates an Evidence record by hashing the record's *semantic
projection* (everything except the display-only subject fields and the id
itself) with RFC 8785-style canonical JSON, then prefixing ``ev_``.

This is a read-only helper: it never mutates a record on disk. It exists so a
record produced by ``rea analyze`` can be re-stamped after an environment
binding is added, without hand-waving about the id.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical(value: Any) -> str:
    """Canonical JSON matching JSON.stringify + RFC 8785 key ordering."""
    return json.dumps(
        _normalise(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _normalise(value: Any) -> Any:
    """Collapse integral floats to ints so 1.0 and 1 hash identically."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalise(v) for v in value]
    return value


def semantic_projection(record: dict) -> dict:
    """The exact field set REA hashes (mirrors rea-agents dist/domain/evidence.js)."""
    subject = record.get("subject")
    projection = {
        "subject": None
        if subject is None
        else {
            "digest": subject.get("digest"),
            "format": subject.get("format"),
            "architecture": subject.get("architecture"),
        },
        "provider": record.get("provider"),
        "analysis_profile": record.get("analysis_profile"),
        "predicate_type": record.get("predicate_type"),
        "operation": record.get("operation"),
        "parameters": record.get("parameters"),
        "raw_result": record.get("raw_result"),
        "normalized_result": record.get("normalized_result"),
        "confidence": record.get("confidence"),
        "authority": record.get("authority"),
        "environment": record.get("environment"),
        "limitations": record.get("limitations"),
        "locations": record.get("locations"),
        "evidence_links": record.get("evidence_links"),
    }
    coverage = record.get("relationship_coverage")
    if coverage is not None:
        projection["relationship_coverage"] = coverage
    return projection


def evidence_id(record: dict) -> str:
    """The ``ev_``-prefixed digest REA would assign to this record."""
    digest = hashlib.sha256(_canonical(semantic_projection(record)).encode("utf-8")).hexdigest()
    return f"ev_{digest}"


def authenticate(record: dict) -> dict:
    """Return a copy of ``record`` whose evidence_id matches its content."""
    stamped = dict(record)
    stamped["evidence_id"] = evidence_id(stamped)
    return stamped


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    with open(path, encoding="utf-8") as handle:
        rec = json.load(handle)
    computed = evidence_id(rec)
    print(f"stored:   {rec.get('evidence_id')}")
    print(f"computed: {computed}")
    print("MATCH" if computed == rec.get("evidence_id") else "MISMATCH")
