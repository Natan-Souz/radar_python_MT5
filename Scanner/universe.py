from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import MetaTrader5 as mt5

@dataclass(frozen=True)
class SymbolInfoLite:
    symbol: str
    path: str
    asset_class: str #forex/crypto/stocks/indices/commodities/etfs

def _norm_path(p: str) -> str:
    """
    Normaliza path do MT5 para comparação:
    - converte "\" -> "/"
    - remove barras repetidas
    - remove espaços em volta
    - força lower-case
    """
    if not p:
        return ""
    p = p.strip().replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    return p.lower()

def infer_asset_class(path: str) -> str:
    p = _norm_path(path)
    if "/forex/" in p or p.startswith("forex/"):
        return "forex"
    if "cryptocurr" in p or p.startswith("cryptocurrencies/") or "/cryptocurrencies/" in p:
        return "crypto"
    if "/stocks/" in p or p.startswith("stocks/"):
        return "stocks"
    if "/indices/" in p or p.startswith("indices/"):
        return "indices"
    if "/commodities/" in p or p.startswith("commodities/"):
        return "commodities"
    if "/etfs/" in p or p.startswith("etfs/"):
        return "etfs"
    if "/Forwards/" in p or p.startswith("forwards/"):
        return "forwards"
    return "other"