# python_radar/storage.py
from __future__ import annotations

import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable

from Scanner.scorer import ScoredCandidate


DDL = """
CREATE TABLE IF NOT EXISTS radar_top (
  ts TEXT NOT NULL,
  symbol TEXT NOT NULL,
  asset_class TEXT NOT NULL,
  path TEXT NOT NULL,

  tf_context TEXT NOT NULL,
  tf_entry TEXT NOT NULL,

  regime TEXT NOT NULL,
  strategy_id TEXT NOT NULL,
  direction TEXT NOT NULL,

  score_total REAL NOT NULL,
  score_regime REAL NOT NULL,
  score_strategy REAL NOT NULL,

  adx REAL,
  di_plus REAL,
  di_minus REAL,
  ema50_slope_pct REAL,
  atr_pct REAL,
  bb_width REAL,
  donchian_high REAL,
  donchian_low REAL,
  close_prank_60 REAL,

  mt5_profile TEXT NOT NULL,

  PRIMARY KEY (ts, symbol, strategy_id)
);
"""

INSERT_SQL = """
INSERT OR REPLACE INTO radar_top (
  ts, symbol, asset_class, path,
  tf_context, tf_entry,
  regime, strategy_id, direction,
  score_total, score_regime, score_strategy,
  adx, di_plus, di_minus, ema50_slope_pct, atr_pct, bb_width, donchian_high, donchian_low, close_prank_60,
  mt5_profile
) VALUES (
  :ts, :symbol, :asset_class, :path,
  :tf_context, :tf_entry,
  :regime, :strategy_id, :direction,
  :score_total, :score_regime, :score_strategy,
  :adx, :di_plus, :di_minus, :ema50_slope_pct, :atr_pct, :bb_width, :donchian_high, :donchian_low, :close_prank_60,
  :mt5_profile
);
"""


def init_db(sqlite_path: str) -> None:
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(DDL)
        conn.commit()


def write_top(
    sqlite_path: str,
    *,
    tf_context: str,
    tf_entry: str,
    rows: Iterable[dict],
) -> None:
    with sqlite3.connect(sqlite_path) as conn:
        conn.execute(DDL)
        conn.executemany(INSERT_SQL, rows)
        conn.commit()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
