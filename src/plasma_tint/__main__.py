# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point for the plasma_tint GUI."""

from __future__ import annotations

import sys


def main() -> None:
    from PySide6.QtWidgets import QApplication

    from .gui.window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("plasma-tint")
    app.setApplicationDisplayName("plasma-tint")
    window = MainWindow()
    window.resize(940, 560)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
