# SPDX-License-Identifier: GPL-3.0-or-later
"""PyInstaller entry point.

PyInstaller cannot use ``plasma_tint/__main__.py`` directly because that module
relies on relative imports. Importing the installed package here keeps the
module name correct.
"""

from plasma_tint.__main__ import main

if __name__ == "__main__":
    main()
