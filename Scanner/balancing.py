from __future__ import annotations

from collections import defaultdict
from math import floor
from typing import Callable, Iterable, TypeVar

T = TypeVar("T")


def best_row_per_symbol(rows: list[dict]) -> list[dict]:
    """
    Mantém somente 1 estratégia por símbolo (a de maior score_total).
    """
    best: dict[str, dict] = {}
    for r in rows:
        sym = r.get("symbol")
        if not sym:
            continue
        if sym not in best or float(r.get("score_total", 0.0)) > float(best[sym].get("score_total", 0.0)):
            best[sym] = r
    return list(best.values())


def _quota_per_class(classes: list[str], n_total: int) -> dict[str, int]:
    """
    Divide n_total igualmente entre as classes.
    Ex.: n_total=10, classes=3 => base=3 (9) e sobra 1 a ser alocada depois.
    """
    if n_total <= 0 or not classes:
        return {}
    base = floor(n_total / len(classes))
    return {c: base for c in classes}


def pick_top_n_balanced(
    rows: list[dict],
    top_n: int,
    *,
    classes: Iterable[str] | None = None,
) -> list[dict]:
    """
    Seleciona Top N com balanceamento por asset_class:
      1) quotas iguais por classe (base)
      2) vagas restantes (resto) preenchidas pelos melhores scores globais ainda não usados
    """
    if top_n <= 0:
        return []

    rows_sorted = sorted(rows, key=lambda r: float(r.get("score_total", 0.0)), reverse=True)

    if classes is None:
        classes = sorted({r.get("asset_class", "unknown") for r in rows_sorted})

    classes = [c for c in classes if c]  # limpa vazio
    if not classes:
        return rows_sorted[:top_n]

    quotas = _quota_per_class(classes, top_n)

    picked: list[dict] = []
    picked_keys: set[tuple[str, str]] = set()  # (symbol, strategy_id) por segurança
    counts: dict[str, int] = defaultdict(int)

    # 1) preenche quotas base por classe
    for r in rows_sorted:
        if len(picked) >= top_n:
            break
        cls = r.get("asset_class", "unknown")
        sym = r.get("symbol", "")
        sid = r.get("strategy_id", "")
        key = (sym, sid)

        if cls not in quotas:
            continue
        if counts[cls] >= quotas[cls]:
            continue
        if key in picked_keys:
            continue

        picked.append(r)
        picked_keys.add(key)
        counts[cls] += 1

    # 2) resto: melhores scores globais restantes, independente de classe
    if len(picked) < top_n:
        for r in rows_sorted:
            if len(picked) >= top_n:
                break
            sym = r.get("symbol", "")
            sid = r.get("strategy_id", "")
            key = (sym, sid)
            if key in picked_keys:
                continue
            picked.append(r)
            picked_keys.add(key)

    return picked


def select_most_volatile_balanced(
    items: list[T],
    *,
    top_k: int,
    get_class: Callable[[T], str],
    get_vol: Callable[[T], float],
    classes: Iterable[str] | None = None,
) -> list[T]:
    """
    Balanceia o filtro de volatilidade por classe:
      - calcula volatilidade
      - separa por classe
      - pega quota igual por classe
      - preenche resto com melhores vols globais
    """
    if top_k <= 0 or not items:
        return []

    scored = [(it, float(get_vol(it))) for it in items]
    scored.sort(key=lambda x: x[1], reverse=True)

    if classes is None:
        classes = sorted({get_class(it) for it, _ in scored})

    classes = [c for c in classes if c]
    if not classes:
        return [it for it, _ in scored[:top_k]]

    quotas = _quota_per_class(classes, top_k)

    by_class: dict[str, list[tuple[T, float]]] = defaultdict(list)
    for it, v in scored:
        by_class[get_class(it)].append((it, v))

    picked: list[T] = []
    seen: set[T] = set()

    # 1) quotas base por classe
    for c in classes:
        q = quotas.get(c, 0)
        if q <= 0:
            continue
        for it, _v in by_class.get(c, [])[:q]:
            if it in seen:
                continue
            picked.append(it)
            seen.add(it)
            if len(picked) >= top_k:
                return picked

    # 2) resto: maiores vols globais
    for it, _v in scored:
        if len(picked) >= top_k:
            break
        if it in seen:
            continue
        picked.append(it)
        seen.add(it)

    return picked
