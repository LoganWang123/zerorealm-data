"""Logging utilities with run_id support."""

import logging
import os
from datetime import datetime


def setup_logger(run_id: str, log_dir: str = "logs", level: str = "INFO") -> logging.Logger:
    """Create a logger that writes to both console and file."""
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("zerorealm")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.handlers.clear()

    fmt = logging.Formatter(
        f"[%(asctime)s] [%(levelname)s] [run:{run_id}] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    # File handler
    log_file = os.path.join(log_dir, f"{run_id}.log")
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """Get the zerorealm logger."""
    return logging.getLogger("zerorealm")
