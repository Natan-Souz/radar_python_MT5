from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

@dataclass(frozen=True)
class IndicatorParams:
    ema_fast: int =50
    ema_slow: int = 200

    adx_period: int = 14
    atr_period: int = 14

    donchian_period: int = 20

    bb_period: int = 20
    bb_k: float = 2.0

    pivot_left: int = 3
    pivot_right: int = 3

    percent_rank_window: int = 6

def _ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()

def _true_range(df: pd.DataFrame) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr1 = (high - low).abs()
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def _atr(df: pd.DataFrame, period: int) -> pd.Series:
    tr = _true_range(df)
    # Wilder smoothing: ATR_t = (ATR_{t-1}*(n-1) + TR_t)/n
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return atr

def _adx(df: pd.DataFrame, period: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Retorna: (ADX, +DI, -DI) usando Wilder smoothing.
    Necessita colunas: high, low, close.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = _true_range(df)

    # Wilder smoothing via EMA(alpha=1/n)
    tr_smooth = pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=1 / period, adjust=False).mean()

    plus_di = 100 * (plus_dm_smooth / tr_smooth.replace(0, np.nan))
    minus_di = 100 * (minus_dm_smooth / tr_smooth.replace(0, np.nan))

    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return adx, plus_di, minus_di

def _bollinger_width(close: pd.Series, period: int, k: float) -> pd.Series:
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)
    upper = mid + k * std
    lower = mid - k * std
    # width relativo: (upper-lower)/mid
    width = (upper - lower) / mid.replace(0, np.nan)
    return width

def _donchian(df: pd.DataFrame, period: int) -> tuple[pd.Series, pd.Series]:
    high = df["high"].rolling(period).max()
    low = df["low"].rolling(period).min()
    return high, low

def percent_rank(series: pd.Series, window: int) -> pd.Series:
    """
    Percent rank do último valor dentro da janela [0, 100].
    Implementação robusta e determinística: rank do último ponto na janela.
    """
    def _rank_last(x: np.ndarray) -> float:
        if len(x) == 0 or np.all(np.isnan(x)):
            return np.nan
        last = x[-1]
        valid = x[~np.isnan(x)]
        if len(valid) == 0:
            return np.nan
        return 100.0 * (np.sum(valid <= last) / len(valid))

    return series.rolling(window).apply(lambda x: _rank_last(np.asarray(x)), raw=False)

def slope_pct_per_bar(series: pd.Series, lookback: int = 20) -> pd.Series:
    """
    Inclinação percentual por barra, aproximada:
    slope ≈ (series_t / series_{t-lookback} - 1) / lookback
    Retorna em percentual (%).
    """
    prev = series.shift(lookback)
    slope = (series / prev.replace(0, np.nan) - 1.0) / lookback
    return 100.0 * slope

def detect_pivots(df: pd.DataFrame, left: int, right: int) -> tuple[pd.Series, pd.Series]:
    """
    Detecta pivôs locais simples:
    pivot_high = 1 quando high[i] é maior que highs nos [i-left, i+right]
    pivot_low  = 1 quando low[i]  é menor que lows  nos [i-left, i+right]
    """
    high = df["high"].values
    low = df["low"].values
    n = len(df)

    ph = np.zeros(n, dtype=float)
    pl = np.zeros(n, dtype=float)

    for i in range(left, n - right):
        window_high = high[i - left : i + right + 1]
        window_low = low[i - left : i + right + 1]
        if np.isfinite(high[i]) and high[i] == np.nanmax(window_high) and np.sum(window_high == high[i]) == 1:
            ph[i] = 1.0
        if np.isfinite(low[i]) and low[i] == np.nanmin(window_low) and np.sum(window_low == low[i]) == 1:
            pl[i] = 1.0

    return pd.Series(ph, index=df.index), pd.Series(pl, index=df.index)

def add_indicators(df: pd.DataFrame, params: IndicatorParams = IndicatorParams()) -> pd.DataFrame:
    """
    Entrada: df com colunas ['open','high','low','close'] (e opcional 'volume')
    Saída: df cópia com colunas adicionais.
    """
    required = {"open", "high", "low", "close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DataFrame sem colunas obrigatórias: {missing}")

    out = df.copy()

    # EMAs
    out["ema50"] = _ema(out["close"], params.ema_fast)
    out["ema200"] = _ema(out["close"], params.ema_slow)

    # Slope EMA50 (% por barra)
    out["ema50_slope_pct"] = slope_pct_per_bar(out["ema50"], lookback=20)

    # ATR e ATR%
    out["atr"] = _atr(out, params.atr_period)
    out["atr_pct"] = 100.0 * (out["atr"] / out["close"].replace(0, np.nan))

    # ADX, +DI, -DI
    adx, di_plus, di_minus = _adx(out, params.adx_period)
    out["adx"] = adx
    out["di_plus"] = di_plus
    out["di_minus"] = di_minus

    # Bollinger width
    out["bb_width"] = _bollinger_width(out["close"], params.bb_period, params.bb_k)

    # Donchian
    d_high, d_low = _donchian(out, params.donchian_period)
    out["donchian_high"] = d_high
    out["donchian_low"] = d_low

    # Percent rank do close (para acc/dist dentro do range)
    out["close_prank_60"] = percent_rank(out["close"], params.percent_rank_window)

    # Pivôs (auxilia estrutura HH/HL e LL/LH)
    ph, pl = detect_pivots(out, params.pivot_left, params.pivot_right)
    out["pivot_high"] = ph
    out["pivot_low"] = pl

    return out