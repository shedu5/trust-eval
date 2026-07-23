"""On-disk cache of judge responses — the reproducibility backbone.

Every judge call is keyed by a SHA-256 over ``{provider, model, prompt_version,
prompt}``. A run with a matching cache hit never touches the network, so a
reviewer with no API key reproduces the exact tables from committed cache files;
a live run with a key fills misses and records them. Because the suite and prompt
are deterministic, the same case always maps to the same key.

Records are stored one JSON file per key so they diff cleanly in git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from ..canonical import sha256_hex

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "cache" / "records"


def cache_key(provider: str, model: str, prompt_version: str, prompt: str) -> str:
    return sha256_hex(
        {
            "provider": provider,
            "model": model,
            "prompt_version": prompt_version,
            "prompt": prompt,
        }
    )


class ResponseCache:
    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR):
        self.cache_dir = Path(cache_dir)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        path = self._path(key)
        if path.exists():
            return json.loads(path.read_text())
        return None

    def put(self, key: str, record: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._path(key).write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")


__all__ = ["ResponseCache", "cache_key", "DEFAULT_CACHE_DIR"]
