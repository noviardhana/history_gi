"""
logsetup.py
===========
One logging setup for all scripts in pipeline/ (standard library only).

    from logsetup import get_logger
    log = get_logger("preprocess_gi")
    log.warning("3 rows have no rarity mapping")

* Output goes to stdout, so it stays in order with the normal prints.
* Level: env GACHA_LOG_LEVEL (DEBUG / INFO / WARNING / ERROR), default INFO.
* In GitHub Actions, warnings and errors are written as ::warning:: / ::error::
  annotations, so they show up on the workflow summary page, not only in the raw log.
"""

import logging
import os
import sys

_configured = False


class _ConsoleHandler(logging.StreamHandler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if os.environ.get("GITHUB_ACTIONS") and record.levelno >= logging.WARNING:
                tag = "error" if record.levelno >= logging.ERROR else "warning"
                self.stream.write(f"::{tag}::{msg.replace(chr(10), '%0A')}\n")
            else:
                label = {"WARNING": "[WARN]", "ERROR": "[ERROR]", "INFO": "", "DEBUG": "[DEBUG]"}.get(record.levelname, "")
                self.stream.write(f"{label} {msg}\n" if label else f"{msg}\n")
            self.flush()
        except Exception:  # noqa: BLE001 - logging must never crash a script
            self.handleError(record)


def get_logger(name: str) -> logging.Logger:
    global _configured
    root = logging.getLogger("gacha")
    if not _configured:
        handler = _ConsoleHandler(sys.stdout)
        root.addHandler(handler)
        root.setLevel(os.environ.get("GACHA_LOG_LEVEL", "INFO").upper())
        root.propagate = False
        _configured = True
    return root.getChild(name)
