"""Safe JSON fetching for NASA web services."""
from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import config as C
from mars_survive.common import ModuleError, get_logger

log = get_logger("nasa_live")
CACHE_DIR = C.DATA / "cache"
MAX_JSON_BYTES = 25 * 1024 * 1024
USER_AGENT = f"MARS-SURVIVE-360/{C.VERSION} (NASA Space Apps prototype)"


def _redact(text: str) -> str:
    return re.sub(r"(api_key=)[^&\s]+", r"\1***", str(text))


def get_json(url: str, params: dict | None = None, timeout: float = 30.0):
    """GET → parsed JSON. Raises ModuleError with a translation key (network / http / too_big / json)."""
    import requests
    try:
        r = requests.get(url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT}, stream=True)
    except requests.exceptions.Timeout as e:
        raise ModuleError("err.network", "timeout") from e
    except requests.exceptions.RequestException as e:
        log.warning("network error %s for %s", e.__class__.__name__, _redact(url))
        raise ModuleError("err.network", e.__class__.__name__) from e
    with r:
        if r.status_code != 200:
            raise ModuleError("err.http", f"HTTP {r.status_code}")
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > MAX_JSON_BYTES:
                raise ModuleError("err.too_big", f"> {MAX_JSON_BYTES // 2**20} MB")
    try:
        return json.loads(bytes(buf).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ModuleError("err.bad_json", str(e)[:120]) from e


def parse_json_bytes(data: bytes):
    if len(data) > MAX_JSON_BYTES:
        raise ModuleError("err.too_big", f"> {MAX_JSON_BYTES // 2**20} MB")
    try:
        return json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise ModuleError("err.bad_json", str(e)[:120]) from e


def cache_path(kind: str, key: str) -> Path:
    h = hashlib.sha256(key.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{kind}_{h}.json"


def cache_save(kind: str, key: str, payload, data_class: str, source: str) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    p = cache_path(kind, key)
    p.write_text(json.dumps({"fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "data_class": data_class, "source": _redact(source), "payload": payload}),
                 encoding="utf-8")
    return p


def cache_load(kind: str, key: str, max_age_h: float | None = None):
    p = cache_path(kind, key)
    if not p.is_file():
        return None
    if max_age_h is not None and (time.time() - p.stat().st_mtime) > max_age_h * 3600:
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
