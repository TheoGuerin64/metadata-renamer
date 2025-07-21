def main() -> None:
    import sys

    from PyQt6.QtWidgets import QApplication

    from app.window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["main"]
