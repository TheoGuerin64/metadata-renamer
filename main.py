import logging
import re
import sys
from collections import Counter
from concurrent import futures
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING, NamedTuple

import customtkinter as ctk

if TYPE_CHECKING:
    from exifread.core.ifd_tag import IfdTag

WINDOW_TITLE = "MetaDate Renamer"
WINDOW_SIZE = "800x600"
COLOR_THEME = "blue"

IMAGE_FILE_EXTENSIONS = (
    ".tiff",
    ".tif",
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jif",
    ".jfif",
    ".jfi",
    ".png",
    ".webp",
    ".heif",
    ".heifs",
    ".heic",
    ".heics",
    ".avci",
    ".avcs",
    ".hif",
)
VIDEO_FILE_EXTENSIONS = (
    ".avi",
    ".mp4",
    ".mov",
    ".mkv",
    ".flv",
    ".wmv",
    ".mpeg",
    ".webm",
)

EXIF_DATE_TAGS = (
    "EXIF DateTimeOriginal",
    "Image DateTime",
)

TARGET_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"
RENAMED_REGEX = re.compile(
    r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}(_\d+)?(\.\w+)?$", re.IGNORECASE
)


class Status(StrEnum):
    READY = "Ready"
    NO_CHANGE = "No Change"
    NO_DATE_FOUND = "No Date Found"
    CONFLICT = "Conflict"
    RENAMED = "Renamed"
    ERROR = "Error"


class FileEntry(NamedTuple):
    original_name: str
    proposed_name: str
    status: Status


class RenameJob(NamedTuple):
    item_id: str
    original_name: str
    proposed_name: str


def extract_date_from_image(file_path: Path) -> datetime | None:
    from exifread import process_file

    logging.debug("Extracting EXIF date from image: %s", file_path.name)
    try:
        with file_path.open("rb") as image:
            tags = process_file(image, details=False, extract_thumbnail=False)

        for expected_tag in EXIF_DATE_TAGS:
            tag: IfdTag | None = tags.get(expected_tag)
            if tag is not None:
                logging.debug("Found EXIF tag '%s' in %s", expected_tag, file_path.name)
                return datetime.strptime(tag.values, "%Y:%m:%d %H:%M:%S")

        logging.info("No EXIF date tag in %s", file_path.name)
    except Exception as error:
        logging.error("Failed to read EXIF from %s: %s", file_path.name, error)

    return None


def extract_date_from_video(file_path: Path) -> datetime | None:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser

    logging.debug("Extracting metadata date from video: %s", file_path.name)
    try:
        parser = createParser(str(file_path))
        if not parser:
            logging.warning("Cannot parse video file: %s", file_path.name)
            return None

        with parser:
            metadata = extractMetadata(parser)

        if metadata and metadata.has("creation_date"):
            creation_date = metadata.get("creation_date")
            if isinstance(creation_date, str):
                creation_date = datetime.strptime(creation_date, "%Y-%m-%d %H:%M:%S")
            logging.debug(
                "Found metadata date '%s' in %s", creation_date, file_path.name
            )
            return creation_date

        logging.info("No 'creation_date' in metadata for %s", file_path.name)
    except Exception as error:
        logging.error("Failed to extract metadata from %s: %s", file_path.name, error)

    return None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self._init_window()
        self._init_top_controls()
        self._init_treeview()
        self._init_bottom_controls()

        self._executor = futures.ThreadPoolExecutor()
        self._pending_renames: list[RenameJob] = []
        self._date_counter: Counter[datetime] = Counter()

    def __exit__(self, exc: BaseException | None = None) -> None:
        self._executor.shutdown(wait=False)
        logging.debug("ThreadPoolExecutor shutdown complete")

    def _init_window(self) -> None:
        self.title(WINDOW_TITLE)
        self.geometry(WINDOW_SIZE)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme(COLOR_THEME)

        self.grid_columnconfigure(0, weight=1)

        logging.debug("Window set to '%s', size %s", WINDOW_TITLE, WINDOW_SIZE)

    def _init_top_controls(self) -> None:
        top_panel = ctk.CTkFrame(self, corner_radius=0)
        top_panel.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_panel.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(top_panel, text="Media Folder:").grid(
            row=0, column=0, padx=10, pady=10
        )
        self.folder_path_input = ctk.CTkEntry(top_panel, state="readonly")
        self.folder_path_input.grid(row=0, column=1, sticky="ew")

        self.browse_button = ctk.CTkButton(
            top_panel, text="Browse...", command=self._browse_directory
        )
        self.browse_button.grid(row=0, column=2, padx=10)

        logging.debug("Top controls initialized")

    def _init_treeview(self) -> None:
        style = ttk.Style()
        bg_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        )
        fg_color = self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkLabel"]["text_color"]
        )
        style.configure(
            "Treeview",
            highlightthickness=0,
            bd=0,
            font=("Calibri", 11),
            background=bg_color,
            foreground=fg_color,
            fieldbackground=bg_color,
        )
        style.configure("Treeview.Heading", font=("Calibri", 12, "bold"))
        style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

        tree_panel = ctk.CTkFrame(self, corner_radius=0)
        tree_panel.grid(row=1, column=0, sticky="nsew", padx=10)
        tree_panel.grid_rowconfigure(0, weight=1)
        tree_panel.grid_columnconfigure(0, weight=1)

        self.treeview = ttk.Treeview(
            tree_panel,
            columns=("original", "new-name", "status"),
            show="headings",
        )
        self.treeview.grid(row=0, column=0, sticky="nsew")

        self.treeview.heading("original", text="Original Filename")
        self.treeview.heading("new-name", text="Proposed New Name")
        self.treeview.heading("status", text="Status")

        self.treeview.column("original", width=300)
        self.treeview.column("new-name", width=300)
        self.treeview.column("status", width=100, anchor="center")

        scrollbar = ctk.CTkScrollbar(tree_panel, command=self.treeview.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.treeview.configure(yscrollcommand=scrollbar.set)

        self.grid_rowconfigure(1, weight=1)
        logging.debug("Treeview initialized")

    def _init_bottom_controls(self) -> None:
        bottom_panel = ctk.CTkFrame(self)
        bottom_panel.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        bottom_panel.grid_columnconfigure(0, weight=1)

        self.rename_button = ctk.CTkButton(
            bottom_panel, text="Rename Files", command=self._start_renaming
        )
        self.rename_button.grid(row=0, column=0, columnspan=2, pady=10, padx=10)

        self.rename_progress = ctk.CTkProgressBar(bottom_panel)
        self.rename_progress.set(0)
        self.rename_progress.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10)
        )
        logging.debug("Bottom controls initialized")

    def _clear_treeview(self) -> None:
        self.treeview.delete(*self.treeview.get_children())
        logging.debug("Cleared items from treeview")

    def _update_folder_path_input(self, path: str) -> None:
        self.folder_path_input.configure(state="normal")

        self.folder_path_input.delete(0, "end")
        self.folder_path_input.insert(0, path)

        self.folder_path_input.configure(state="readonly")
        logging.debug("Folder path set to: %s", path)

    def _insert_treeview_entry(self, entry: FileEntry) -> str:
        item_id = self.treeview.insert("", "end", values=entry)
        logging.debug("Inserted treeview entry: %s", entry)
        return item_id

    def _lock(self) -> None:
        self.rename_button.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.folder_path_input.configure(state="disabled")
        logging.debug("Input UI locked")

    def _unlock(self) -> None:
        self.rename_button.configure(state="normal")
        self.browse_button.configure(state="normal")
        self.folder_path_input.configure(state="readonly")
        logging.debug("Input UI unlocked")

    def _browse_directory(self) -> None:
        selected = filedialog.askdirectory()
        if selected:
            logging.info("Directory selected: %s", selected)
            self._update_folder_path_input(selected)

            self._lock()
            future = self._executor.submit(self._scan_directory, Path(selected))
            future.add_done_callback(lambda _: self._unlock())
        else:
            logging.info("Directory selection cancelled")

    def _create_renamed_filename(self, file_path: Path, timestamp: datetime) -> str:
        formatted = timestamp.strftime(TARGET_DATE_FORMAT)

        while 1:
            count = self._date_counter[timestamp]
            self._date_counter[timestamp] += 1

            new_name = f"{formatted}_{count}{file_path.suffix}"
            new_path = file_path.parent / new_name
            if not new_path.exists():
                break

        logging.debug("Formatted new filename '%s' from %s", new_name, timestamp)
        return new_name

    def _scan_directory(self, directory: Path) -> None:
        logging.info("Scanning directory: %s", directory)
        self._clear_treeview()
        self.rename_progress.set(0)
        self._pending_renames.clear()
        self._date_counter.clear()

        for path in sorted(directory.iterdir()):
            if not path.is_file():
                logging.debug("Skipping non-file: %s", path.name)
                continue

            if RENAMED_REGEX.match(path.name):
                logging.debug("Skipping already renamed file: %s", path.name)
                continue

            suffix = path.suffix.lower()
            if suffix in IMAGE_FILE_EXTENSIONS:
                date = extract_date_from_image(path)
            elif suffix in VIDEO_FILE_EXTENSIONS:
                date = extract_date_from_video(path)
            else:
                logging.debug("Unsupported type: %s", path.name)
                continue

            if date is None:
                entry = FileEntry(path.name, "", Status.NO_DATE_FOUND)
                self._insert_treeview_entry(entry)
                self.update_idletasks()
                continue

            new_name = self._create_renamed_filename(path, date)
            status = Status.READY if new_name != path.name else Status.NO_CHANGE

            entry = FileEntry(path.name, new_name, status)
            item_id = self._insert_treeview_entry(entry)
            self.update_idletasks()

            if new_name != path.name:
                job = RenameJob(item_id, path.name, new_name)
                self._pending_renames.append(job)

        total_ready = len(self._pending_renames)
        logging.info("Scan complete: %d files ready", total_ready)

    def _start_renaming(self) -> None:
        if not self._pending_renames:
            logging.info("No files scheduled for renaming")
            return

        total = len(self._pending_renames)
        logging.info("Starting rename of %d files", total)
        self._lock()

        self.rename_progress.set(0)
        base_dir = Path(self.folder_path_input.get())

        def _rename_job(job: RenameJob) -> tuple[str, FileEntry]:
            src = base_dir / job.original_name
            dst = base_dir / job.proposed_name

            try:
                if dst.exists():
                    status = Status.CONFLICT
                    logging.warning("Conflict: %s exists", job.proposed_name)
                else:
                    src.rename(dst)
                    status = Status.RENAMED
                    logging.info(
                        "Renamed '%s' to '%s'", job.original_name, job.proposed_name
                    )
            except Exception as error:
                status = Status.ERROR
                logging.error("Error renaming %s: %s", job.original_name, error)

            logging.debug("Job %s result: %s", job.item_id, status)
            return job.item_id, FileEntry(job.original_name, job.proposed_name, status)

        futures_list = [
            self._executor.submit(_rename_job, job) for job in self._pending_renames
        ]

        def _update_results() -> None:
            for index, future in enumerate(futures.as_completed(futures_list), start=1):
                try:
                    item_id, entry = future.result()
                except Exception as error:
                    logging.error("Rename task failed: %s", error)
                    continue

                logging.debug("Updating item %s to %s", item_id, entry.status)
                self.treeview.item(item_id, values=entry)
                self.rename_progress.set(index / total)
                self.update_idletasks()

            self.rename_progress.set(1)
            self._unlock()
            logging.info("Rename process completed (%d files)", total)

        self._executor.submit(_update_results)


def main() -> None:
    debug_mode = "--debug" in sys.argv or "-d" in sys.argv

    logging.basicConfig(
        level=logging.DEBUG if debug_mode else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("metadate_renamer.log"),
            logging.StreamHandler(),
        ],
    )

    logging.info("Application start (debug=%s)", debug_mode)
    app = App()
    app.mainloop()
    logging.info("Application exit")


if __name__ == "__main__":
    main()
