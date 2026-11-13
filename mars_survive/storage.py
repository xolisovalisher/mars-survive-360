"""SQLite storage for missions, science targets and dataset provenance.

All queries use parameter binding (no string formatting) -> no SQL injection.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config as C

SCHEMA = """
CREATE TABLE IF NOT EXISTS missions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, description TEXT, region TEXT,
  scenario TEXT, duration_h REAL, params TEXT, status TEXT, created TEXT, updated TEXT);
CREATE TABLE IF NOT EXISTS targets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, lat REAL, lon REAL, kind TEXT,
  description TEXT, status TEXT, priority INTEGER, origin TEXT, source TEXT, created TEXT);
CREATE TABLE IF NOT EXISTS datasets(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, data_class TEXT, provider TEXT, url TEXT,
  acquisition_date TEXT, processing_date TEXT, resolution TEXT, crs TEXT, units TEXT, quality TEXT,
  history TEXT, limitations TEXT, size_bytes INTEGER, sha256 TEXT, created TEXT);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextmanager
def connect(path=C.DB_PATH):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        con.executescript(SCHEMA)
        yield con
        con.commit()
    finally:
        con.close()


def rows(sql: str, args=(), path=C.DB_PATH) -> list[dict]:
    with connect(path) as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def execute(sql: str, args=(), path=C.DB_PATH) -> int:
    with connect(path) as con:
        cur = con.execute(sql, args)
        return cur.lastrowid


# ---------------------------------------------------------------- missions (module 1)
def create_mission(name, description, region, scenario, duration_h, params: dict, path=C.DB_PATH) -> int:
    name = (name or "").strip()[:120]
    if not name:
        raise ValueError("empty name")
    return execute("INSERT INTO missions(name,description,region,scenario,duration_h,params,status,created,updated)"
                   " VALUES(?,?,?,?,?,?,?,?,?)",
                   (name, (description or "")[:2000], region, scenario, float(duration_h), json.dumps(params),
                    "planning", now(), now()), path)


def update_mission(mid: int, path=C.DB_PATH, **fields):
    allowed = {"name", "description", "scenario", "duration_h", "params", "status"}
    sets = [(k, json.dumps(v) if k == "params" else v) for k, v in fields.items() if k in allowed]
    if not sets:
        return
    sql = "UPDATE missions SET " + ",".join(f"{k}=?" for k, _ in sets) + ",updated=? WHERE id=?"
    execute(sql, tuple(v for _, v in sets) + (now(), int(mid)), path)


def list_missions(path=C.DB_PATH):
    out = rows("SELECT * FROM missions ORDER BY id DESC", (), path)
    for m in out:
        m["params"] = json.loads(m["params"] or "{}")
    return out


def delete_mission(mid: int, path=C.DB_PATH):
    execute("DELETE FROM missions WHERE id=?", (int(mid),), path)
