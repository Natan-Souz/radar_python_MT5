# python_radar/strategy_mapper.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Regime = Literal[
    "expansion_breakout",
    "bull_trend",
    "bear_trend",
    "range",
    "accumulation",
    "distribution",
    "choppy",
    "unknown",
]

StrategyId = Literal[
    # Trend
    "trend_pullback_ema50",
    "trend_breakout_hh_ll",
    # Range
    "range_extremes",
    "range_rsi_scalp",
    # Breakout/Expansion
    "breakout_directional",
    "breakout_retest",
    # Acc/Dist
    "accumulation_early",
    "distribution_early",
]


@dataclass(frozen=True)
class StrategySpec:
    id: StrategyId
    direction_hint: Literal["buy", "sell", "two_sided", "neutral"]
    # qual EA/preset deverá ser aplicado no MT5 no futuro
    mt5_profile: str
    # opcional: observação/descrição curta
    note: str = ""


def map_strategies(regime: Regime) -> list[StrategySpec]:
    """
    Mapeia regimes -> estratégias conforme seus anexos.
    Aqui apenas lista; não valida setup, não calcula score.
    """
    if regime == "bull_trend":
        return [
            StrategySpec(
                id="trend_pullback_ema50",
                direction_hint="buy",
                mt5_profile="EA_TrendPullback_Buy",
                note="Pullback na EMA50 em tendência de alta",
            ),
            StrategySpec(
                id="trend_breakout_hh_ll",
                direction_hint="buy",
                mt5_profile="EA_TrendBreakout_Buy",
                note="Rompimento de HH em tendência de alta",
            ),
        ]

    if regime == "bear_trend":
        return [
            StrategySpec(
                id="trend_pullback_ema50",
                direction_hint="sell",
                mt5_profile="EA_TrendPullback_Sell",
                note="Retração à EMA50 em tendência de baixa",
            ),
            StrategySpec(
                id="trend_breakout_hh_ll",
                direction_hint="sell",
                mt5_profile="EA_TrendBreakout_Sell",
                note="Rompimento de LL em tendência de baixa",
            ),
        ]

    if regime == "range":
        return [
            StrategySpec(
                id="range_extremes",
                direction_hint="two_sided",
                mt5_profile="EA_RangeExtremes",
                note="Operar extremos do range (Donchian High/Low)",
            ),
            StrategySpec(
                id="range_rsi_scalp",
                direction_hint="two_sided",
                mt5_profile="EA_RSI_Scalp",
                note="Scalping RSI em range (ADX baixo)",
            ),
        ]

    if regime == "expansion_breakout":
        return [
            StrategySpec(
                id="breakout_directional",
                direction_hint="buy",  # direction final vem do detector, aqui é um placeholder
                mt5_profile="EA_BreakoutDirectional",
                note="Breakout direcional com expansão de vol",
            ),
            StrategySpec(
                id="breakout_retest",
                direction_hint="buy",
                mt5_profile="EA_BreakoutRetest",
                note="Reteste do nível rompido após breakout",
            ),
        ]

    if regime == "accumulation":
        return [
            StrategySpec(
                id="accumulation_early",
                direction_hint="buy",
                mt5_profile="EA_AccumulationEarly",
                note="Compra antecipada em acumulação dentro do range",
            ),
            # Em acumulação você ainda pode permitir range_extremes, se quiser:
            StrategySpec(
                id="range_extremes",
                direction_hint="two_sided",
                mt5_profile="EA_RangeExtremes",
                note="Fallback: extremos do range",
            ),
        ]

    if regime == "distribution":
        return [
            StrategySpec(
                id="distribution_early",
                direction_hint="sell",
                mt5_profile="EA_DistributionEarly",
                note="Venda antecipada em distribuição dentro do range",
            ),
            StrategySpec(
                id="range_extremes",
                direction_hint="two_sided",
                mt5_profile="EA_RangeExtremes",
                note="Fallback: extremos do range",
            ),
        ]

    # choppy/unknown: sem estratégia
    return []
