from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from metadate_renamer import extract_date

if TYPE_CHECKING:
    from pathlib import Path


class RenameWorker(QObject):
    finished = Signal()
    progress = Signal(int)

    def __init__(self, directory: Path, files: list[Path], target_format: str) -> None:
        super().__init__()
        self._directory = directory
        self._files = files
        self._target_format = target_format

    def _is_renamed(self, path: Path) -> bool:
        name = path.stem

        last_underscore_index = name.rfind("_")
        if last_underscore_index != -1 and name[last_underscore_index + 1 :].isdigit():
            name = name[:last_underscore_index]

        try:
            datetime.strptime(name, self._target_format)
        except ValueError:
            return False

        return True

    def run(self) -> None:
        date_counter: Counter[tuple[datetime, str]] = Counter()

        for index, path in enumerate(sorted(self._files), start=1):
            if not path.is_file():
                logging.debug("Skipping non-file path: %s", path)
                self.progress.emit(index)
                continue

            if self._is_renamed(path):
                logging.debug("Skipping already renamed file: %s", path.name)
                self.progress.emit(index)
                continue

            try:
                date = extract_date.from_file(path)
            except Exception as error:
                logging.error(
                    "Unexpected error extracting date from %s: %s", path, error
                )
                date = None
            if not date:
                self.progress.emit(index)
                continue

            while True:
                count = date_counter[(date, path.suffix)]
                date_counter[(date, path.suffix)] += 1

                new_name = date.strftime(self._target_format)
                if count > 0:
                    new_name += f"_{count}"
                new_name += path.suffix

                new_path = self._directory / new_name
                if not new_path.exists():
                    break

            logging.info("Renaming %s to %s", path.name, new_path.name)
            path.rename(new_path)

            self.progress.emit(index)

        self.finished.emit()
