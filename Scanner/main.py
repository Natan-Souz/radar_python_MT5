from __future__ import annotations

import logging
import time

import MetaTrader5 as mt5

from .config import RadarConfig
from .universe import list_symbols_by_paths
from .radar import mt5_connect, run_radar_for_symbol, persist_top 
from .balancing import (
    best_row_per_symbol,
    pick_top_n_balanced,
    select_most_volatile_balanced,
) 
from .logger import setup_logger, LogConfig, log_ctx

from .data_feed import get_rates
from .indicators import add_indicators, IndicatorParams


# =========================
# CONFIGURAÇÃO DE PAUSA
# =========================
SCAN_INTERVAL_SECONDS = 60  # <-- edite aqui (ex.: 30, 60, 120)
# Tipos permitidos no scan (edite facilmente)
ALLOWED_ASSET_CLASSES = {"stocks", "crypto", "forex"}  # {"forex"}, {"commodities"}, {"etfs"}, {forwards} ,{"stocks"}, {"etfs"}, {"forex","stocks","crypto"}

# Volatilidade intraday (TF de entrada)
VOL_TF = "M1"           # geralmente o mesmo cfg.tf_entry
VOL_LOOKBACK = 5       # últimos 10 candles
VOL_TOP_K = 50          # só roda o radar completo nos top K mais voláteis
VOL_METHOD = "atr_pct"  # "atr_pct" ou "range_pct"

#HELPERS
def compute_recent_volatility(symbol: str, tf: str, lookback: int, method: str = "atr_pct") -> float:
    """
    Retorna uma métrica simples de volatilidade usando apenas os últimos N candles.
    method:
      - "atr_pct": ATR% (mais robusto)
      - "range_pct": média (high-low)/close em %
    """
    df = get_rates(symbol, tf, max(lookback + 50, 80))  # pega um pouco mais para ATR estabilizar
    df_last = df.tail(lookback)

    if method == "range_pct":
        # Normalização mais estável: usa mid-price (high+low)/2
        high = df_last["high"]
        low = df_last["low"]
        close = df_last["close"]

        mid = (high + low) / 2.0
        rng = (high - low).abs()

        # Limpeza: remove barras inválidas
        valid = (
            high.notna() & low.notna() & close.notna() &
            (high >= low) &
            (mid > 0)
        )

        if valid.sum() < max(3, lookback // 2):
            return 0.0

        rng_pct = 100.0 * (rng[valid] / mid[valid])

        # Winsorize (corta cauda superior) para evitar que 1 candle "domine"
        p95 = float(rng_pct.quantile(0.95))
        if p95 > 0:
            rng_pct = rng_pct.clip(upper=p95)

        # Agregação robusta: mediana
        return float(rng_pct.median())

    # default: atr_pct
    df_ind = add_indicators(df, IndicatorParams())
    # usa ATR% médio dos últimos N candles
    atr_pct = df_ind["atr_pct"].tail(lookback).mean()
    return float(atr_pct) if atr_pct == atr_pct else 0.0


def run_once(cfg: RadarConfig, logger: logging.Logger, scan_id: int) -> None:
    t0 = time.time()

    symbols = list_symbols_by_paths(cfg.path_prefixes, require_trade_mode=cfg.require_trade_mode)
    logger.info(
        "Scan %d iniciado | universo=%d símbolos | tf_context=%s tf_entry=%s",
        scan_id, len(symbols), cfg.tf_context, cfg.tf_entry
    )

    symbols = [s for s in symbols if s.asset_class in ALLOWED_ASSET_CLASSES]
    logger.info("Universo após filtro por classe=%s: %d símbolos", sorted(ALLOWED_ASSET_CLASSES), len(symbols))
    
    # 1) calcula volatilidade rápida
    def _vol_of(syminfo):
        return compute_recent_volatility(syminfo.symbol, cfg.tf_entry, VOL_LOOKBACK, VOL_METHOD)

    selected = select_most_volatile_balanced(
        symbols,
        top_k=VOL_TOP_K,
        get_class=lambda s: s.asset_class,
        get_vol=_vol_of,
        classes=sorted(ALLOWED_ASSET_CLASSES),
    )

    logger.info(
        "Filtro de volatilidade (BAL): lookback=%d tf=%s method=%s | selecionados=%d de %d | classes=%s",
        VOL_LOOKBACK, cfg.tf_entry, VOL_METHOD, len(selected), len(symbols), sorted(ALLOWED_ASSET_CLASSES),
    )

    symbols = selected

    if not symbols:
        logger.error("Scan %d: universo vazio para os path_prefixes informados.", scan_id)
        return

    all_rows: list[dict] = []
    skipped = 0

    for s in symbols:
        try:
            rows = run_radar_for_symbol(
                symbol=s.symbol,
                tf_context=cfg.tf_context,
                tf_entry=cfg.tf_entry,
                bars_context=cfg.bars_context,
                bars_entry=cfg.bars_entry,
                percent_rank_window=cfg.percent_rank_window,
            )

            if not rows:
                # útil para monitoramento, mas pode gerar muito log.
                # se ficar verboso demais, troque para logger.debug
                logger.info("Sem estratégias elegíveis.", extra=log_ctx(logger, symbol=s.symbol))
                continue

            for r in rows:
                r["asset_class"] = s.asset_class
                r["path"] = s.path
                r["scan_id"] = scan_id  # opcional (não está na tabela ainda)

                logger.info(
                    "Candidato: strategy=%s score_total=%.3f regime=%s dir=%s",
                    r["strategy_id"], r["score_total"], r["regime"], r["direction"],
                    extra=log_ctx(logger, symbol=s.symbol, regime=r["regime"], strategy=r["strategy_id"]),
                )

            all_rows.extend(rows)

        except Exception as e:
            skipped += 1
            logger.exception(
                "Falha ao processar símbolo: %s", str(e),
                extra=log_ctx(logger, symbol=s.symbol)
            )
            continue

     # (1) Mantém apenas 1 estratégia por símbolo (maior score_total)
    rows_1per_symbol = best_row_per_symbol(all_rows)

    # (2) Top N balanceado por asset_class (quotas iguais + resto por melhores scores)
    top = pick_top_n_balanced(
        rows_1per_symbol,
        cfg.top_n,
        classes=sorted(ALLOWED_ASSET_CLASSES),
    )

    #Distribuição por classe
    dist = {}
    for r in top:
        dist[r["asset_class"]] = dist.get(r["asset_class"], 0) + 1
    logger.info("Top N (BAL) distribuição por classe: %s", dist)

    persist_top(cfg, top)

    elapsed = time.time() - t0
    logger.info(
        "Scan %d concluído | candidatos=%d | top=%d | falhas=%d | duração=%.2fs | sqlite=%s",
        scan_id, len(all_rows), len(top), skipped, elapsed, cfg.sqlite_path
    )


def main() -> None:
    logger = setup_logger(LogConfig(level=logging.INFO, log_dir="logs", log_file="radar.log"))

    cfg = RadarConfig(
        path_prefixes=(
            "Markets/Forex/",
            "Markets/cryptocurrencies/",
            "Markets/Stocks/",
            "Markets/Indices/",
            "Markets/Commodities/",
            "Markets/ETFs/",
            "Markets/Forwards/",
        ),
        tf_context="H1",
        tf_entry="M1",
        bars_context=700,
        bars_entry=800,
        top_n=20,
        sqlite_path="radar.sqlite",
        percent_rank_window=252,
        require_trade_mode=True,
        cap_per_asset_class=None,
    )

    logger.info("Inicializando conexão MT5...")
    mt5_connect(cfg)

    scan_id = 1

    try:
        while True:
            # roda 1 scan
            run_once(cfg, logger, scan_id)

            scan_id += 1

            # pausa configurável
            logger.info("Aguardando %ds para o próximo ciclo...", SCAN_INTERVAL_SECONDS)
            time.sleep(SCAN_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        logger.info("Interrompido pelo usuário (Ctrl+C). Encerrando...")

    finally:
        mt5.shutdown()
        logger.info("MT5 encerrado. Processo finalizado.")


if __name__ == "__main__":
    main()
