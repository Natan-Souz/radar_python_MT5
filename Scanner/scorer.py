from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ScoreWeights:
    # composição final
    w_regime: float = 0.60
    w_strategy: float = 0.40

    # trend regime
    w_adx: float = 0.35
    w_di_spread: float = 0.25
    w_slope: float = 0.25
    w_ema_alignment: float = 0.15

    # range regime
    w_adx_low: float = 0.45
    w_bb_squeeze: float = 0.35
    w_donchian_narrow: float = 0.20

    # breakout regime
    w_breakout_confirm: float = 0.45
    w_atr_expand: float = 0.35
    w_adx_rising: float = 0.20


@dataclass(frozen=True)
class ScoreThresholds:
    # trend
    adx_trend_min: float = 25.0
    adx_trend_max_for_norm: float = 45.0  # saturação
    slope_min_abs: float = 0.05  # %/barra
    slope_max_abs_for_norm: float = 0.25

    # range
    adx_range_max: float = 18.0
    bb_pr_squeeze: float = 20.0  # bb_width percent rank <= 20
    donchian_width_pr_narrow: float = 25.0

    # breakout
    atr_pr_high: float = 80.0
    atr_pr_low: float = 20.0


@dataclass(frozen=True)
class ScoredCandidate:
    symbol: str
    regime: str
    strategy_id: str
    direction: str

    score_total: float
    score_regime: float
    score_strategy: float

    # alguns campos úteis para logging/DB
    adx: Optional[float] = None
    di_plus: Optional[float] = None
    di_minus: Optional[float] = None
    ema50_slope_pct: Optional[float] = None
    atr_pct: Optional[float] = None
    bb_width: Optional[float] = None
    donchian_high: Optional[float] = None
    donchian_low: Optional[float] = None
    close_prank_60: Optional[float] = None


def _clamp01(x: float) -> float:
    if np.isnan(x):
        return 0.0
    return float(max(0.0, min(1.0, x)))


def _norm(x: float, lo: float, hi: float) -> float:
    if np.isnan(x):
        return 0.0
    if hi <= lo:
        return 0.0
    return _clamp01((x - lo) / (hi - lo))


def _percent_rank(series: pd.Series, window: int) -> pd.Series:
    def _rank_last(arr: np.ndarray) -> float:
        if len(arr) == 0 or np.all(np.isnan(arr)):
            return np.nan
        last = arr[-1]
        valid = arr[~np.isnan(arr)]
        if len(valid) == 0:
            return np.nan
        return 100.0 * (np.sum(valid <= last) / len(valid))
    return series.rolling(window).apply(lambda x: _rank_last(np.asarray(x)), raw=False)


def score_regime_trend(last: pd.Series, thr: ScoreThresholds, w: ScoreWeights) -> float:
    # ADX
    s_adx = _norm(float(last["adx"]), thr.adx_trend_min, thr.adx_trend_max_for_norm)

    # DI spread: diferença entre +DI e -DI (quanto maior, melhor)
    di_spread = abs(float(last["di_plus"] - last["di_minus"]))
    s_di = _norm(di_spread, 5.0, 35.0)  # ajustável

    # slope EMA50 (magnitude)
    s_slope = _norm(abs(float(last["ema50_slope_pct"])), thr.slope_min_abs, thr.slope_max_abs_for_norm)

    # alinhamento EMA50/EMA200 (binário)
    s_align = 1.0 if ((last["ema50"] > last["ema200"]) or (last["ema50"] < last["ema200"])) else 0.0

    score = (
        w.w_adx * s_adx +
        w.w_di_spread * s_di +
        w.w_slope * s_slope +
        w.w_ema_alignment * s_align
    )
    return _clamp01(score)


def score_regime_range(df: pd.DataFrame, thr: ScoreThresholds, w: ScoreWeights, pr_window: int) -> float:
    last = df.iloc[-1]

    # ADX baixo (quanto mais baixo, melhor)
    # normaliza invertido: adx 0..thr.adx_range_max
    s_adx_low = 1.0 - _norm(float(last["adx"]), 5.0, thr.adx_range_max)

    # BB squeeze via percent rank do bb_width
    bb_pr = _percent_rank(df["bb_width"], pr_window).iloc[-1]
    s_bb = 1.0 if (pd.notna(bb_pr) and bb_pr <= thr.bb_pr_squeeze) else _clamp01(_norm(thr.bb_pr_squeeze - float(bb_pr), -30.0, 0.0))

    # Donchian narrow: largura do canal em percentil baixo
    dc_width = (df["donchian_high"] - df["donchian_low"]) / df["close"].replace(0, np.nan)
    dc_pr = _percent_rank(dc_width, pr_window).iloc[-1]
    s_dc = 1.0 if (pd.notna(dc_pr) and dc_pr <= thr.donchian_width_pr_narrow) else _clamp01(_norm(thr.donchian_width_pr_narrow - float(dc_pr), -30.0, 0.0))

    score = (
        w.w_adx_low * s_adx_low +
        w.w_bb_squeeze * s_bb +
        w.w_donchian_narrow * s_dc
    )
    return _clamp01(score)


def score_regime_breakout(df: pd.DataFrame, thr: ScoreThresholds, w: ScoreWeights, pr_window: int) -> float:
    last = df.iloc[-1]

    # breakout confirm (close fora do Donchian)
    up = pd.notna(last["donchian_high"]) and (last["close"] > last["donchian_high"])
    dn = pd.notna(last["donchian_low"]) and (last["close"] < last["donchian_low"])
    s_break = 1.0 if (up or dn) else 0.0

    # ATR% high e veio de low recentemente
    atr_pr = _percent_rank(df["atr_pct"], pr_window).iloc[-1]
    is_high = pd.notna(atr_pr) and atr_pr >= thr.atr_pr_high
    atr_pr_series = _percent_rank(df["atr_pct"], pr_window)
    recent_min = atr_pr_series.tail(30).min(skipna=True)
    came_low = pd.notna(recent_min) and recent_min <= thr.atr_pr_low
    s_atr = 1.0 if (is_high and came_low) else 0.0

    # ADX rising bônus (ADX > MA10)
    adx_ma10 = df["adx"].rolling(10).mean().iloc[-1]
    s_adx_rising = 1.0 if (pd.notna(adx_ma10) and last["adx"] > adx_ma10) else 0.0

    score = (
        w.w_breakout_confirm * s_break +
        w.w_atr_expand * s_atr +
        w.w_adx_rising * s_adx_rising
    )
    return _clamp01(score)


def score_strategy(
    strategy_id: str,
    regime: str,
    df: pd.DataFrame,
    direction: str,
) -> float:
    """
    Score "setup now". Heurística inicial baseada nos requisitos dos anexos.
    Retorna 0..1.
    """
    last = df.iloc[-1]

    # Helpers
    close = float(last["close"])
    ema50 = float(last["ema50"])
    atr = float(last["atr"]) if "atr" in df.columns and pd.notna(last["atr"]) else np.nan

    def dist_to_ema50_norm() -> float:
        # quanto mais perto da EMA50, melhor para pullback
        if np.isnan(atr) or atr <= 0:
            return 0.0
        dist = abs(close - ema50)
        # 0 ATR => score 1; 1.5 ATR => score ~0
        return _clamp01(1.0 - (dist / (1.5 * atr)))

    if strategy_id == "trend_pullback_ema50":
        # Critérios: preço próximo da EMA50 e ADX forte já veio do regime
        return dist_to_ema50_norm()

    if strategy_id == "trend_breakout_hh_ll":
        # Critério: close fora do Donchian na direção do regime
        if direction == "buy":
            return 1.0 if close > float(last["donchian_high"]) else 0.0
        if direction == "sell":
            return 1.0 if close < float(last["donchian_low"]) else 0.0
        return 0.0

    if strategy_id == "range_extremes":
        # proximidade dos extremos Donchian (canal)
        dch = float(last["donchian_high"])
        dcl = float(last["donchian_low"])
        if np.isnan(dch) or np.isnan(dcl) or dch == dcl:
            return 0.0
        # normaliza posição no canal [0,1]
        pos = (close - dcl) / (dch - dcl)
        # score alto se perto de 0 ou 1
        return float(max(0.0, 1.0 - min(pos, 1.0 - pos) * 3.0))

    if strategy_id == "range_rsi_scalp":
        # Se RSI existir no df (você pode adicionar depois); por ora, fallback 0.5
        if "rsi" not in df.columns or pd.isna(last["rsi"]):
            return 0.5
        rsi = float(last["rsi"])
        # score alto se perto dos extremos
        if rsi <= 30:
            return _clamp01(_norm(30 - rsi, 0, 15))
        if rsi >= 70:
            return _clamp01(_norm(rsi - 70, 0, 15))
        return 0.0

    if strategy_id == "breakout_directional":
        # basicamente o confirm do breakout
        up = close > float(last["donchian_high"])
        dn = close < float(last["donchian_low"])
        if direction == "buy":
            return 1.0 if up else 0.0
        if direction == "sell":
            return 1.0 if dn else 0.0
        return 0.0

    if strategy_id == "breakout_retest":
        # Reteste: preço volta para perto do nível rompido (±0.5 ATR)
        if np.isnan(atr) or atr <= 0:
            return 0.0
        dch = float(last["donchian_high"])
        dcl = float(last["donchian_low"])
        if direction == "buy":
            # após breakout de alta, espera-se reteste do antigo high (dch)
            return _clamp01(1.0 - (abs(close - dch) / (0.5 * atr)))
        if direction == "sell":
            return _clamp01(1.0 - (abs(close - dcl) / (0.5 * atr)))
        return 0.0

    if strategy_id == "accumulation_early":
        # dentro de range: percent_rank baixo + proximidade do fundo do canal
        prank = float(last["close_prank_60"]) if pd.notna(last["close_prank_60"]) else np.nan
        s_pr = 1.0 if (pd.notna(prank) and prank <= 33.0) else 0.0
        s_pos = score_strategy("range_extremes", "range", df, "buy")
        # mas só a parte de “perto do fundo” importa:
        # range_extremes dá alto nos dois lados; para acum, penaliza topo
        dch = float(last["donchian_high"])
        dcl = float(last["donchian_low"])
        pos = (close - dcl) / (dch - dcl) if dch != dcl else 0.5
        s_bottom = _clamp01(1.0 - _norm(pos, 0.3, 1.0))
        return _clamp01(0.6 * s_pr + 0.4 * s_bottom)

    if strategy_id == "distribution_early":
        prank = float(last["close_prank_60"]) if pd.notna(last["close_prank_60"]) else np.nan
        s_pr = 1.0 if (pd.notna(prank) and prank >= 67.0) else 0.0
        dch = float(last["donchian_high"])
        dcl = float(last["donchian_low"])
        pos = (close - dcl) / (dch - dcl) if dch != dcl else 0.5
        s_top = _clamp01(_norm(pos, 0.0, 0.7))
        return _clamp01(0.6 * s_pr + 0.4 * s_top)

    return 0.0


def score_candidate(
    *,
    symbol: str,
    regime: str,
    strategy_id: str,
    direction: str,
    df_ind: pd.DataFrame,
    weights: ScoreWeights = ScoreWeights(),
    thresholds: ScoreThresholds = ScoreThresholds(),
    percent_rank_window: int = 252,
) -> ScoredCandidate:
    """
    Pontua um (symbol, regime, strategy) usando df_ind com indicadores.
    """
    last = df_ind.iloc[-1]

    # Score do regime
    if regime in ("bull_trend", "bear_trend"):
        s_reg = score_regime_trend(last, thresholds, weights)
    elif regime in ("range", "accumulation", "distribution"):
        s_reg = score_regime_range(df_ind, thresholds, weights, percent_rank_window)
    elif regime == "expansion_breakout":
        s_reg = score_regime_breakout(df_ind, thresholds, weights, percent_rank_window)
    else:
        s_reg = 0.30  # choppy/unknown

    # Score da estratégia
    s_str = score_strategy(strategy_id, regime, df_ind, direction)

    # Composição final
    total = _clamp01(weights.w_regime * s_reg + weights.w_strategy * s_str)

    return ScoredCandidate(
        symbol=symbol,
        regime=regime,
        strategy_id=strategy_id,
        direction=direction,
        score_total=float(total),
        score_regime=float(s_reg),
        score_strategy=float(s_str),
        adx=float(last["adx"]) if pd.notna(last["adx"]) else None,
        di_plus=float(last["di_plus"]) if pd.notna(last["di_plus"]) else None,
        di_minus=float(last["di_minus"]) if pd.notna(last["di_minus"]) else None,
        ema50_slope_pct=float(last["ema50_slope_pct"]) if pd.notna(last["ema50_slope_pct"]) else None,
        atr_pct=float(last["atr_pct"]) if pd.notna(last["atr_pct"]) else None,
        bb_width=float(last["bb_width"]) if pd.notna(last["bb_width"]) else None,
        donchian_high=float(last["donchian_high"]) if pd.notna(last["donchian_high"]) else None,
        donchian_low=float(last["donchian_low"]) if pd.notna(last["donchian_low"]) else None,
        close_prank_60=float(last["close_prank_60"]) if pd.notna(last["close_prank_60"]) else None,
    )
