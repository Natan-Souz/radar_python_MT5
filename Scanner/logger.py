from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass(frozen=True)
class LogConfig:
    name: str = "python_radar"
    level: int = logging.INFO

    # Arquivo (rotativo)
    log_dir: str = "logs"
    log_file: str = "radar.log"
    max_bytes: int = 5 * 1024 * 1024  # 5 MB
    backup_count: int = 5

    # Console
    console: bool = True

    # Formato
    # Inclui "extras" como symbol/regime/strategy quando presentes
    fmt: str = (
        "%(asctime)s | %(levelname)s | %(name)s | "
        "symbol=%(symbol)s regime=%(regime)s strategy=%(strategy)s | %(message)s"
    )
    datefmt: str = "%Y-%m-%d %H:%M:%S"


class _ContextFilter(logging.Filter):
    """
    Garante que campos extras existam no record, para o formatter não quebrar.
    """
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "symbol"):
            record.symbol = "-"
        if not hasattr(record, "regime"):
            record.regime = "-"
        if not hasattr(record, "strategy"):
            record.strategy = "-"
        return True


def setup_logger(cfg: LogConfig = LogConfig()) -> logging.Logger:
    logger = logging.getLogger(cfg.name)
    logger.setLevel(cfg.level)
    logger.propagate = False  # evita logs duplicados

    # Evita adicionar handlers repetidos em re-import/reload
    if logger.handlers:
        return logger

    formatter = logging.Formatter(cfg.fmt, datefmt=cfg.datefmt)
    logger.addFilter(_ContextFilter())

    # Console handler
    if cfg.console:
        ch = logging.StreamHandler()
        ch.setLevel(cfg.level)
        ch.setFormatter(formatter)
        logger.addHandler(ch)

    # File handler rotativo
    log_dir = Path(cfg.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = RotatingFileHandler(
        log_dir / cfg.log_file,
        maxBytes=cfg.max_bytes,
        backupCount=cfg.backup_count,
        encoding="utf-8",
    )
    fh.setLevel(cfg.level)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


def log_ctx(
    logger: logging.Logger,
    *,
    symbol: Optional[str] = None,
    regime: Optional[str] = None,
    strategy: Optional[str] = None,
) -> dict[str, Any]:
    """
    Helper para gerar dict de contexto (extras) de forma consistente.
    Uso:
      logger.info("mensagem", extra=log_ctx(logger, symbol="EURUSD", regime="bull_trend"))
    """
    return {
        "symbol": symbol or "-",
        "regime": regime or "-",
        "strategy": strategy or "-",
    }