from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

@dataclass(frozen=True)
class RegimeThresholds:
    #Tendencia
    adx_trend_min: float = 25.0
    ema_slope_trend_min_abs: float = 0.05

    #Range
    adx_range_max: float = 18

    #Breackout/Expanção
    atr_pct_prank_high: float = 80.0
    atr_pct_prank_low: float = 20.0
    donchian_breakout_confirm_close: bool = True

    #Acumulação/Distribuição
    acc_prank_max: float = 33.0
    dist_prank_min: float = 67.0

def _percent_rank(series: pd.Series, window: int) -> pd.Series:
    #ATR% e BBWidth
    def _rank_last(x: np.ndarray) -> float:
        if len(x) == 0 or np.all(np.isnan(x)):
            return np.nan
        last = x[-1]
        valid = x[~np.isnan(x)]

        if len(valid) == 0:
            return np.nan
        return 100.0 * (np.sum(valid <= last) / len(valid))
    return series.rolling(window).apply(lambda x: _rank_last(np.asarray(x)), raw=False)

def _last_valid(row: pd.Series, cols: list[str]) -> bool:
    return all(pd.notna(row[c]) for c in cols)

def _structure_from_pivots(df: pd.DataFrame, lookback_pivots: int = 6) -> tuple[bool, bool]:
    """
    Retorna (bull_structure, bear_structure) usando pivôs recentes.
    - bull: últimos 2 pivot_high ascendentes (HH) e últimos 2 pivot_low ascendentes (HL)
    - bear: últimos 2 pivot_high descendentes (LH) e últimos 2 pivot_low descendentes (LL)
    Se não houver pivôs suficientes, retorna (False, False).
    """
    piv_h = df[df["pivot_high"] == 1.0][["high"]].tail(lookback_pivots)
    piv_l = df[df["pivot_low"] == 1.0][["low"]].tail(lookback_pivots)

    if len(piv_h) < 2 or len(piv_l) < 2:
        return False, False
    
    #Ultimos 2 pivos
    h1, h2 = piv_h["high"].iloc[-2], piv_h["high"].iloc[-1]
    l1, l2 = piv_l["low"].iloc[-2], piv_l["low"].iloc[-1]

    bull = (h2 > h1) and (l2 > l1)
    bear = (h2 < h1) and (l2 < l1)
    return bull, bear

def detect_regime(
    df: pd.DataFrame,
    thresholds: RegimeThresholds = RegimeThresholds(),
    *,
    percent_rank_window: int = 252,
    use_structure_filter: bool = True,
) -> dict:
    """
    Espera df já com indicadores:
      'ema50','ema200','ema50_slope_pct','adx','di_plus','di_minus',
      'atr_pct','donchian_high','donchian_low','bb_width',
      'close_prank_60','pivot_high','pivot_low'

    Retorna dict com:
      regime, direction, confidence, tags, debug
    """

    required_cols = [
        "close", "ema50", "ema200", "ema50_slope_pct",
        "adx", "di_plus", "di_minus",
        "atr_pct", "donchian_high", "donchian_low",
        "bb_width", "close_prank_60",
        "pivot_high", "pivot_low",
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"df sem colunas necessárias para regime: {missing}")

    if len(df) < max(200, percent_rank_window, 60) + 5:
        # para EMA200 e percentis fazerem sentido
        return {
            "regime": "unknown",
            "direction": "neutral",
            "confidence": 0.0,
            "tags": ["insufficient_data"],
            "debug": {"len": int(len(df))}
        }

    last = df.iloc[-1].copy()

    # Percent ranks para detectar squeeze/expansão
    atrpct_pr = _percent_rank(df["atr_pct"], percent_rank_window).iloc[-1]
    bb_pr = _percent_rank(df["bb_width"], percent_rank_window).iloc[-1]

    debug = {
        "adx": float(last["adx"]),
        "di_plus": float(last["di_plus"]) if pd.notna(last["di_plus"]) else None,
        "di_minus": float(last["di_minus"]) if pd.notna(last["di_minus"]) else None,
        "ema50_gt_ema200": bool(last["ema50"] > last["ema200"]),
        "ema50_slope_pct": float(last["ema50_slope_pct"]) if pd.notna(last["ema50_slope_pct"]) else None,
        "atr_pct": float(last["atr_pct"]) if pd.notna(last["atr_pct"]) else None,
        "atr_pct_pr": float(atrpct_pr) if pd.notna(atrpct_pr) else None,
        "bb_width": float(last["bb_width"]) if pd.notna(last["bb_width"]) else None,
        "bb_width_pr": float(bb_pr) if pd.notna(bb_pr) else None,
        "close_prank_60": float(last["close_prank_60"]) if pd.notna(last["close_prank_60"]) else None,
        "donchian_high": float(last["donchian_high"]) if pd.notna(last["donchian_high"]) else None,
        "donchian_low": float(last["donchian_low"]) if pd.notna(last["donchian_low"]) else None,
    }

    # ---------- 1) Breakout / Expansion (prioridade máxima) ----------
    # Condição de rompimento Donchian (close fora do canal)
    breakout_up = pd.notna(last["donchian_high"]) and (last["close"] > last["donchian_high"])
    breakout_dn = pd.notna(last["donchian_low"]) and (last["close"] < last["donchian_low"])

    # Expansão de vol (ATR% percentil alto) e, idealmente, vindo de low antes (squeeze)
    is_atr_high = pd.notna(atrpct_pr) and (atrpct_pr >= thresholds.atr_pct_prank_high)

    # Heurística simples de “vinha comprimido”: mínimo do percentil ATR% nos últimos 30 candles
    atrpct_pr_series = _percent_rank(df["atr_pct"], percent_rank_window)
    recent_min = atrpct_pr_series.tail(30).min(skipna=True)
    came_from_low = pd.notna(recent_min) and (recent_min <= thresholds.atr_pct_prank_low)

    if (breakout_up or breakout_dn) and is_atr_high and came_from_low:
        direction = "buy" if breakout_up else "sell"
        conf = 0.75
        tags = ["expansion_breakout"]
        if pd.notna(last["adx"]):
            # ADX subindo é bônus de confiança
            adx_ma10 = df["adx"].rolling(10).mean().iloc[-1]
            if pd.notna(adx_ma10) and last["adx"] > adx_ma10:
                conf += 0.10
                tags.append("adx_rising")
        return {
            "regime": "expansion_breakout",
            "direction": direction,
            "confidence": min(conf, 0.95),
            "tags": tags,
            "debug": debug,
        }

    # ---------- 2) Trend (bull/bear) ----------
    trend_ready = _last_valid(last, ["adx", "ema50", "ema200", "ema50_slope_pct", "di_plus", "di_minus"])
    if trend_ready:
        adx_ok = last["adx"] >= thresholds.adx_trend_min
        slope = last["ema50_slope_pct"]
        slope_ok = pd.notna(slope) and (abs(slope) >= thresholds.ema_slope_trend_min_abs)

        bull_bias = (last["ema50"] > last["ema200"]) and (last["di_plus"] > last["di_minus"]) and (slope > 0)
        bear_bias = (last["ema50"] < last["ema200"]) and (last["di_minus"] > last["di_plus"]) and (slope < 0)

        bull_struct, bear_struct = _structure_from_pivots(df) if use_structure_filter else (True, True)

        if adx_ok and slope_ok and bull_bias and (bull_struct or not use_structure_filter):
            conf = 0.70
            # bônus de “força”: diferença DI
            conf += min(abs(last["di_plus"] - last["di_minus"]) / 100.0, 0.15)
            return {
                "regime": "bull_trend",
                "direction": "buy",
                "confidence": float(min(conf, 0.95)),
                "tags": ["trend", "bull"],
                "debug": debug,
            }

        if adx_ok and slope_ok and bear_bias and (bear_struct or not use_structure_filter):
            conf = 0.70
            conf += min(abs(last["di_plus"] - last["di_minus"]) / 100.0, 0.15)
            return {
                "regime": "bear_trend",
                "direction": "sell",
                "confidence": float(min(conf, 0.95)),
                "tags": ["trend", "bear"],
                "debug": debug,
            }

    # ---------- 3) Range / Consolidação ----------
    range_ready = _last_valid(last, ["adx", "bb_width", "close_prank_60"])
    if range_ready and (last["adx"] <= thresholds.adx_range_max):
        # “compressão” como tag (bb_width percentil baixo)
        tags = ["range"]
        conf = 0.60
        if pd.notna(bb_pr) and bb_pr <= 20:
            tags.append("bb_squeeze")
            conf += 0.10

        # ---------- 4) Accumulation / Distribution dentro do range ----------
        prank = last["close_prank_60"]
        if pd.notna(prank) and prank <= thresholds.acc_prank_max:
            return {
                "regime": "accumulation",
                "direction": "buy",
                "confidence": float(min(conf + 0.05, 0.85)),
                "tags": tags + ["accumulation"],
                "debug": debug,
            }

        if pd.notna(prank) and prank >= thresholds.dist_prank_min:
            return {
                "regime": "distribution",
                "direction": "sell",
                "confidence": float(min(conf + 0.05, 0.85)),
                "tags": tags + ["distribution"],
                "debug": debug,
            }

        # Range neutro
        return {
            "regime": "range",
            "direction": "two_sided",
            "confidence": float(min(conf, 0.80)),
            "tags": tags,
            "debug": debug,
        }

    # Se não encaixou em nada, classifica como "choppy" (ou unknown)
    return {
        "regime": "choppy",
        "direction": "neutral",
        "confidence": 0.40,
        "tags": ["no_clear_regime"],
        "debug": debug,
    }