"""Entry point for Madany's PDF Batcher."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from ui import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("fusion")
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())
