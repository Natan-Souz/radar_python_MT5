from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import MetaTrader5 as mt5


@dataclass(frozen=True)
class SymbolInfoLite:
    symbol: str
    path: str
    asset_class: str  #forex/crypto/stocks/indices/commodities/etfs/other


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


def list_symbols_by_paths(
    path_prefixes: Sequence[str],
    *,
    require_trade_mode: bool = True,
) -> list[SymbolInfoLite]:
    """
    Busca todos os símbolos e filtra por 'path' do MT5.
    Aceita prefixos com e sem 'Markets/' e funciona com "\" ou "/".
    """
    all_symbols = mt5.symbols_get()
    if all_symbols is None:
        raise RuntimeError("mt5.symbols_get() retornou None. Verifique MT5.initialize().")

    # normaliza prefixos e cria variações (com/sem Markets/)
    prefixes_norm: list[str] = []
    for pref in path_prefixes:
        n = _norm_path(pref)
        if not n:
            continue
        # garante que prefixo termina com "/"
        if not n.endswith("/"):
            n += "/"
        prefixes_norm.append(n)
        # variação sem "markets/"
        if n.startswith("markets/"):
            prefixes_norm.append(n[len("markets/"):])

    # remove duplicatas preservando ordem
    seen = set()
    prefixes_norm = [x for x in prefixes_norm if not (x in seen or seen.add(x))]

    out: list[SymbolInfoLite] = []
    for s in all_symbols:
        raw_path = getattr(s, "path", "") or ""
        npth = _norm_path(raw_path)
        if not npth:
            continue

        ok_path = any(npth.startswith(pref) for pref in prefixes_norm)
        if not ok_path:
            continue

        if require_trade_mode:
            trade_mode = getattr(s, "trade_mode", None)
            if trade_mode is not None and int(trade_mode) == 0:
                continue

        out.append(
            SymbolInfoLite(
                symbol=s.name,
                path=raw_path,  # mantém original (útil para debug)
                asset_class=infer_asset_class(raw_path),
            )
        )

    # dedup por símbolo
    dedup = {}
    for item in out:
        dedup[item.symbol] = item
    return list(dedup.values())


def debug_sample_paths(limit: int = 30) -> list[str]:
    """
    Retorna uma amostra de paths únicos para você enxergar como o seu broker expõe os grupos.
    """
    syms = mt5.symbols_get() or []
    uniq = []
    seen = set()
    for s in syms:
        p = getattr(s, "path", "") or ""
        if not p:
            continue
        if p in seen:
            continue
        seen.add(p)
        uniq.append(p)
        if len(uniq) >= limit:
            break
    return uniq
