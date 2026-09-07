"""Small strict JSON boundary shared by events and local IPC."""
from __future__ import annotations

import json
import math
from collections.abc import Mapping
from types import MappingProxyType

MAX_BYTES = 65536


def freeze(value: object, depth: int = 0) -> object:
    if depth > 16:
        raise ValueError("JSON nesting exceeds 16")
    if value is None or type(value) in (bool, int):
        if type(value) is int and abs(value) > 2**63 - 1:
            raise ValueError("integer outside signed 64-bit range")
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("non-finite number")
        return value
    if type(value) is str:
        if len(value) > 32768:
            raise ValueError("string too long")
        return value
    if isinstance(value, Mapping):
        if len(value) > 1024 or any(type(k) is not str for k in value):
            raise ValueError("invalid object keys/size")
        return MappingProxyType({k: freeze(v, depth + 1) for k, v in value.items()})
    if type(value) in (list, tuple):
        if len(value) > 1024:
            raise ValueError("array too long")
        return tuple(freeze(v, depth + 1) for v in value)
    raise ValueError("value is not JSON")


def thaw(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: thaw(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw(v) for v in value]
    return value


def encode(value: object) -> bytes:
    result = json.dumps(thaw(freeze(value)), ensure_ascii=False, allow_nan=False,
                        separators=(",", ":")).encode("utf-8")
    if len(result) > MAX_BYTES:
        raise ValueError("message exceeds 64 KiB")
    return result


def decode(data: bytes | str) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    if len(data) > MAX_BYTES:
        raise ValueError("message exceeds 64 KiB")
    value = json.loads(data, object_pairs_hook=pairs)
    encode(value)
    return value


def number(value: object, minimum: float, maximum: float) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum
