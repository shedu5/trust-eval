"""Canonical serialization and hashing primitives.

Everything that gets hashed in this project goes through :func:`canonical_bytes`
so that hashes are deterministic and reproducible across machines and Python
runs. We use JSON with sorted keys, no insignificant whitespace, and UTF-8
encoding. This is intentionally simple and auditable rather than clever.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

GENESIS_HASH = "0" * 64
"""Sentinel ``prev_hash`` for the first step in a provenance chain."""


def canonical_bytes(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical, deterministic JSON bytes.

    Sorted keys + compact separators means the same logical object always
    produces the same bytes, which is what makes content hashes reproducible.
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(obj: Any) -> str:
    """Return the hex SHA-256 of the canonical serialization of ``obj``."""
    return hashlib.sha256(canonical_bytes(obj)).hexdigest()
