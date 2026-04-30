from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any


def write_json_atomic(dest_path: Path, payload: Any) -> None:
    tmp_path: Path = dest_path.with_suffix(dest_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
    os.replace(tmp_path, dest_path)
