from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Any

_TMP_SUFFIX: str = ".tmp"


def _tmp_path_for(dest_path: Path) -> Path:
    return dest_path.with_suffix(dest_path.suffix + _TMP_SUFFIX)


def replace_atomic(tmp_path: Path, dest_path: Path) -> None:
    """Rename tmp_path onto dest_path. The caller is responsible for having
    written tmp_path. On any failure, tmp_path is removed if it still exists.
    """
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(tmp_path, dest_path)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def write_text_atomic(dest_path: Path, content: str, encoding: str = "utf-8") -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path = _tmp_path_for(dest_path)
    try:
        tmp_path.write_text(content, encoding=encoding)
        os.replace(tmp_path, dest_path)
    except OSError:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

# NOTE : might need to stream later if file size becomes an issue
def write_json_atomic(dest_path: Path, payload: Any) -> None:
    content: str = json.dumps(payload, separators=(",", ":"))
    write_text_atomic(dest_path, content)
