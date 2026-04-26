from __future__ import annotations
from pathlib import Path
from typing import Any


def _key_check(
    obj: dict[str, Any], name: str, missing_message: str, error_cls: type[Exception]
):
    if name not in obj:
        raise error_cls(missing_message)


def require_section(
    raw: dict[str, Any], name: str, path: Path, error_cls: type[Exception]
) -> dict[str, Any]:
    _key_check(raw, name, f"missing [{name}] section in {path}", error_cls)
    section = raw[name]
    if not isinstance(section, dict):
        raise error_cls(f"[{name}] must be a table in {path}")
    return section


def require_string(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> str:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if not isinstance(value, str) or not value:
        raise error_cls(f"{section_name}.{key} must be a non-empty string in {path}")
    return value


def require_string_list(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> list[str]:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise error_cls(
            f"{section_name}.{key} must be a list of non-empty strings in {path}"
        )
    return list(value)


def require_int(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> int:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise error_cls(f"{section_name}.{key} must be an integer in {path}")
    return value


def require_int_list(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> list[int]:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if not isinstance(value, list) or not all(
        isinstance(v, int) and not isinstance(v, bool) for v in value
    ):
        raise error_cls(f"{section_name}.{key} must be a list of integers in {path}")
    return list(value)


def require_float(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> float:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error_cls(f"{section_name}.{key} must be a number in {path}")
    return float(value)


def require_float_list(
    section: dict[str, Any],
    key: str,
    section_name: str,
    path: Path,
    error_cls: type[Exception],
) -> list[float]:
    _key_check(section, key, f"missing {section_name}.{key} in {path}", error_cls)
    value = section[key]
    if not isinstance(value, list) or not all(
        isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
    ):
        raise error_cls(f"{section_name}.{key} must be a list of numbers in {path}")
    return list(value)


def require_supported_schema_version(
    raw: dict[str, Any],
    supported_versions: frozenset[int],
    path: Path,
    error_cls: type[Exception],
) -> int:
    schema_version = raw.get("schema_version")
    if schema_version not in supported_versions:
        supported: str = ", ".join(str(v) for v in sorted(supported_versions))
        raise error_cls(
            f"schema_version {schema_version!r} in {path} is not supported "
            f"(this version of the pipeline supports: {supported}). "
            f"Upgrade the pipeline or adjust the config."
        )
    return int(schema_version)
