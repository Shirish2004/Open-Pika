"""Logging setup — the only place logging config lives."""
from __future__ import annotations

import logging


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # Third-party libs shout a lot; keep them quiet unless we're debugging.
    if not verbose:
        for noisy in ("pyrealsense2", "pysurvive", "matplotlib", "h5py"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"open_pika.{name}")
