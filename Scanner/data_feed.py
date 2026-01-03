from __future__ import annotations

from typing import Literal
import pandas as pd
import MetaTrader5 as mt5

Timeframe = Literal["M1","M5", "M15", "M30","H1", "H4", "D1"]

_TF_MAP = {
    "M1": mt5.TIMEFRAME_M1,
    "M5": mt5.TIMEFRAME_M5,
    "M15": mt5.TIMEFRAME_M15,
    "M30": mt5.TIMEFRAME_M30,
    "H1": mt5.TIMEFRAME_H1,
    "H4": mt5.TIMEFRAME_H4,
    "D1": mt5.TIMEFRAME_D1,
}

def ensure_symbol(symbol: str) -> None:
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Falha ao selecionar símbolo no MT5: {symbol}")

def get_rates(symbol: str, timeframe: Timeframe, n: int) -> pd.DataFrame:
    """
    Retorna DataFrame com colunas:
    time (datetime), open, high, low, close, tick_volume, spread, real_volume
    e adiciona 'volume' como alias de tick_volume.
    """
    ensure_symbol(symbol)

    tf = _TF_MAP[timeframe]
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, n)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Sem candles para {symbol} no timeframe {timeframe} (n={n}).")

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "volume"})
    # padroniza lower-case (as Partes 1/2 esperam open/high/low/close)
    df.columns = [c.lower() for c in df.columns]
    df = df.set_index("time")

    # garante colunas mínimas
    needed = ["open", "high", "low", "close", "volume"]
    for c in needed:
        if c not in df.columns:
            df[c] = pd.NA

    return df[["open", "high", "low", "close", "volume"]]