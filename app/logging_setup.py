from __future__ import annotations

import logging
from datetime import datetime

from app.paths import LOG_DIR, ensure_runtime_dirs


def setup_logging() -> logging.Logger:
    ensure_runtime_dirs()
    logger = logging.getLogger("shizukuclaw")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_file = LOG_DIR / "app.log"
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    logger.info("logging initialized at %s", datetime.utcnow().isoformat())
    return logger


def read_log_text(limit: int = 20000) -> str:
    log_file = LOG_DIR / "app.log"
    if not log_file.exists():
        return "暂无日志。"
    text = log_file.read_text(encoding="utf-8", errors="replace")
    return text[-limit:]
