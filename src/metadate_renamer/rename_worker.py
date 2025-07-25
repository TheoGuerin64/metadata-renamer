from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from metadate_renamer import extract_date

if TYPE_CHECKING:
    from datetime import datetime
    from pathlib import Path

_TARGET_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"
_RENAMED_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(?:_\d+)?\.\w+$", re.IGNORECASE
)


class RenameWorker(QObject):
    finished = Signal()
    progress = Signal(int)

    def __init__(self, directory: Path, files: list[Path]) -> None:
        super().__init__()
        self._directory = directory
        self._files = files

    def run(self) -> None:
        date_counter: Counter[tuple[datetime, str]] = Counter()

        for index, path in enumerate(sorted(self._files), start=1):
            if not path.is_file():
                logging.debug("Skipping non-file path: %s", path)
                self.progress.emit(index)
                continue

            if _RENAMED_REGEX.match(path.name):
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

                new_name = date.strftime(_TARGET_DATE_FORMAT)
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
