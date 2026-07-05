"""Compatibility wrapper around ``orjson`` with a stdlib fallback."""

from __future__ import annotations

import importlib
import importlib.util
import json as _stdlib_json
from typing import Any

_orjson = importlib.import_module("orjson") if importlib.util.find_spec("orjson") else None


class _JsonCompat:
    """Expose the small subset of the json API this project needs."""

    JSONDecodeError = _stdlib_json.JSONDecodeError

    @staticmethod
    def dumps(value: Any) -> bytes:
        if _orjson is not None:
            return _orjson.dumps(value)
        return _stdlib_json.dumps(value).encode("utf-8")

    @staticmethod
    def loads(value: str | bytes | bytearray) -> Any:
        if _orjson is not None:
            return _orjson.loads(value)
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        return _stdlib_json.loads(value)


json = _JsonCompat()
