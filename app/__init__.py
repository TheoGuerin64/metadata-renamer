def main() -> None:
    import logging
    import sys

    from PyQt6.QtWidgets import QApplication

    from app.window import MainWindow

    debug_mode = "--debug" in sys.argv or "-d" in sys.argv

    logging.basicConfig(
        level=logging.DEBUG if debug_mode else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("metadate_renamer.log"),
            logging.StreamHandler(),
        ],
    )

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


__all__ = ["main"]
