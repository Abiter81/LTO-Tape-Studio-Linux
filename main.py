"""Entry point for LTO Tape Studio.

Author: Jörg Althaus
"""

from __future__ import annotations

__author__ = "Jörg Althaus"

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.logger import TapeLogger
from ui.main_window import MainWindow


def main() -> int:
    log_dir = Path.home() / ".lto_tape_studio"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger = TapeLogger.instance(log_dir / "audit.log")

    app = QApplication(sys.argv)
    app.setApplicationName("LTO Tape Studio")
    app.setOrganizationName("LTO Tape Studio")

    window = MainWindow()
    window.show()

    code = app.exec()
    return code


if __name__ == "__main__":
    raise SystemExit(main())