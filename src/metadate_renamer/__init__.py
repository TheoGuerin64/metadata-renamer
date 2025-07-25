def main() -> None:
    import logging
    import sys

    from PySide6.QtWidgets import QApplication

    from metadate_renamer.window import MainWindow

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("metadate_renamer.log"),
        ],
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["main"]
