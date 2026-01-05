from __future__ import annotations

from dataclasses import asdict
import MetaTrader5 as mt5

from Scanner.config import RadarConfig
from Scanner.data_feed import get_rates
from Scanner.indicators import add_indicators, IndicatorParams
from Scanner.regime_detector import detect_regime, RegimeThresholds
from Scanner.strategy_mapper import map_strategies
from Scanner.scorer import score_candidate
from Scanner.storage import init_db, write_top, now_iso


def mt5_connect(cfg: RadarConfig) -> None:
    """
    Inicializa MT5. Se cfg tiver credenciais, tenta login; se não, usa sessão do terminal.
    """
    if not mt5.initialize():
        raise RuntimeError("Falha no mt5.initialize(). Verifique se o terminal MT5 está aberto e autorizado.")

    # login opcional (muitos casos não precisam)
    if cfg.mt5_login and cfg.mt5_password and cfg.mt5_server:
        ok = mt5.login(cfg.mt5_login, password=cfg.mt5_password, server=cfg.mt5_server)
        if not ok:
            raise RuntimeError("Falha no mt5.login(). Verifique credenciais/servidor.")


def run_radar_for_symbol(
    *,
    symbol: str,
    tf_context: str,
    tf_entry: str,
    bars_context: int,
    bars_entry: int,
    percent_rank_window: int,
) -> list[dict]:
    """
    Retorna lista de candidatos (dict) para persistência.
    """
    # Contexto
    df_ctx = get_rates(symbol, tf_context, bars_context)
    df_ctx_ind = add_indicators(df_ctx, IndicatorParams())
    reg = detect_regime(df_ctx_ind, RegimeThresholds(), percent_rank_window=percent_rank_window)

    regime = reg["regime"]
    direction = reg["direction"]

    # Se não há regime operável, não retorna candidatos
    specs = map_strategies(regime)
    if not specs:
        return []

    # Entry TF: usado como fator de "operável agora" em Partes futuras.
    # Por ora, garantimos que existe (para compatibilidade de pipeline).
    _ = get_rates(symbol, tf_entry, bars_entry)

    candidates: list[dict] = []
    for spec in specs:
        cand = score_candidate(
            symbol=symbol,
            regime=regime,
            strategy_id=spec.id,
            direction=("buy" if direction == "buy" else "sell" if direction == "sell" else spec.direction_hint),
            df_ind=df_ctx_ind,
            percent_rank_window=percent_rank_window,
        )
        row = {
            "ts": now_iso(),
            "symbol": cand.symbol,
            "asset_class": "unknown",  # preenchido no main (temos o path lá)
            "path": "",

            "tf_context": tf_context,
            "tf_entry": tf_entry,

            "regime": cand.regime,
            "strategy_id": cand.strategy_id,
            "direction": cand.direction,

            "score_total": cand.score_total,
            "score_regime": cand.score_regime,
            "score_strategy": cand.score_strategy,

            "adx": cand.adx,
            "di_plus": cand.di_plus,
            "di_minus": cand.di_minus,
            "ema50_slope_pct": cand.ema50_slope_pct,
            "atr_pct": cand.atr_pct,
            "bb_width": cand.bb_width,
            "donchian_high": cand.donchian_high,
            "donchian_low": cand.donchian_low,
            "close_prank_60": cand.close_prank_60,

            "mt5_profile": spec.mt5_profile,
        }
        candidates.append(row)

    return candidates


def pick_top_n(rows: list[dict], top_n: int, cap_per_asset_class: dict[str, int] | None = None) -> list[dict]:
    rows_sorted = sorted(rows, key=lambda r: r["score_total"], reverse=True)

    if not cap_per_asset_class:
        return rows_sorted[:top_n]

    # Diversificação por classe
    picked: list[dict] = []
    counts: dict[str, int] = {}
    for r in rows_sorted:
        cls = r["asset_class"]
        cap = cap_per_asset_class.get(cls, 0)
        if cap <= 0:
            continue
        if counts.get(cls, 0) >= cap:
            continue
        picked.append(r)
        counts[cls] = counts.get(cls, 0) + 1
        if len(picked) >= top_n:
            break
    return picked


def persist_top(cfg: RadarConfig, rows: list[dict]) -> None:
    init_db(cfg.sqlite_path)
    write_top(cfg.sqlite_path, tf_context=cfg.tf_context, tf_entry=cfg.tf_entry, rows=rows)
