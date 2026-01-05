from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

Timeframe = Literal["M5", "M15", "H1", "H4", "D1"]

@dataclass(frozen=True)
class RadarConfig:
    # MT5
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None

    # Universo por path (prefixos). Ex.: "Markets/Forex/" ou "Markets/Stocks/USA/"
    path_prefixes: Sequence[str] = (
        "Markets/Forex/",
        "Markets/Cryptocurrencies/",
        "Markets/Indices/",
        "Markets/Stocks/",
    )

    # Multi-timeframe
    tf_context: Timeframe = "M30"
    tf_entry: Timeframe = "M5"

    # Quantidade de barras para cálculo estável (EMA200 + percent ranks + pivôs)
    bars_context: int = 700
    bars_entry: int = 800

    # Ranking
    top_n: int = 10

    # SQLite
    sqlite_path: str = "radar.sqlite"

    # Percent-rank windows (para ATR%/BBWidth/Donchian width)
    percent_rank_window: int = 252

    # Quando True, remove símbolos não-tradáveis (se o broker marcar)
    require_trade_mode: bool = True

    # Diversificação opcional por classe (ex.: 5 forex, 3 stocks, 2 crypto)
    # deixe vazio para "top N geral"
    cap_per_asset_class: dict[str, int] | None = None