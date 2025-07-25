from pathlib import Path

from PySide6.QtCore import Qt, QThread, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from metadate_renamer.rename_worker import RenameWorker

WINDOW_TITLE = "MetaDate Renamer"
WINDOW_SIZE = (500, 74)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(*WINDOW_SIZE)

        main_widget = MainWidget(self)
        self.setCentralWidget(main_widget)


class MainWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_path: Path | None = None
        self._thread: QThread | None = None
        self._worker: RenameWorker | None = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        self._create_path_selector(main_layout)
        self._create_rename_controls(main_layout)

    def _create_path_selector(self, main_layout: QVBoxLayout) -> None:
        layout = QHBoxLayout()
        main_layout.addLayout(layout)

        self.directory_line_edit = QLineEdit()
        self.directory_line_edit.setReadOnly(True)
        self.directory_line_edit.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.directory_line_edit.setPlaceholderText(
            "Select a directory to rename files"
        )
        self.directory_line_edit.setToolTip("Displays the path of the chosen directory")
        layout.addWidget(self.directory_line_edit)

        browse_button = QPushButton("Browse…")
        browse_button.setToolTip("Open a dialog to choose a directory")
        browse_button.clicked.connect(self._browse_directory)
        layout.addWidget(browse_button)

    def _create_rename_controls(self, main_layout: QVBoxLayout) -> None:
        layout = QHBoxLayout()
        main_layout.addLayout(layout)

        self.rename_button = QPushButton("Rename Files")
        self.rename_button.setToolTip(
            "Rename all files in the selected directory based on metadata"
        )
        self.rename_button.setEnabled(False)
        self.rename_button.clicked.connect(self.start_rename_process)
        layout.addWidget(self.rename_button)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setToolTip("Shows progress of the renaming process")
        layout.addWidget(self.progress_bar)

    def _browse_directory(self) -> None:
        dialog = QFileDialog(self, "Select Directory")
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setViewMode(QFileDialog.ViewMode.List)
        if dialog.exec():
            selected = dialog.selectedFiles()[0]
            self._selected_path = Path(selected)
            self.directory_line_edit.setText(selected)
            self.rename_button.setEnabled(True)

    @Slot()
    def start_rename_process(self) -> None:
        assert self._selected_path is not None
        files = list(self._selected_path.iterdir())
        if not files:
            self.progress_bar.setFormat("No files to rename in the selected directory")
            return

        self.progress_bar.setValue(0)
        self.progress_bar.setMaximum(len(files))
        self.progress_bar.setFormat("Renaming files...")
        self.rename_button.setEnabled(False)

        self._thread = QThread()
        self._worker = RenameWorker(self._selected_path, files)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)

        self._worker.progress.connect(self.set_progress)
        self._worker.finished.connect(self.rename_completed)

        self._thread.start()

    @Slot(int)
    def set_progress(self, index: int) -> None:
        self.progress_bar.setValue(index)
        self.progress_bar.setFormat(f"Renaming file {index}...")

    @Slot()
    def rename_completed(self) -> None:
        self.rename_button.setEnabled(True)
        self.progress_bar.setFormat("Renaming completed")
