import logging
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk
import exifread

if TYPE_CHECKING:
    from exifread.core.ifd_tag import IfdTag

WINDOW_NAME = "MetaDate Renamer"
WINDOW_SIZE = "800x600"
COLOR_THEME = "blue"

IMAGE_EXTENSIONS = (
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
VIDEO_EXTENSIONS = (
    ".mp4",
    ".mov",
)

RENAME_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"


def extract_date_from_image(file_path: Path) -> datetime | None:
    logging.debug("Processing image: %s", file_path.name)
    try:
        with file_path.open("rb") as image_file:
            tags = exifread.process_file(image_file, details=False)

        tag: IfdTag | None = tags.get("EXIF DateTimeOriginal")
        if tag is None:
            logging.info("No 'EXIF DateTimeOriginal' tag in %s", file_path.name)
            return None

        return datetime.strptime(tag.values, "%Y:%m:%d %H:%M:%S")
    except Exception as e:
        logging.error("Could not process image file %s: %s", file_path.name, e)
        return None


def extract_date_from_video(file_path: Path) -> datetime | None:
    logging.warning(
        "Video date extraction not implemented. Skipping %s", file_path.name
    )
    return None


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self._setup_window()
        self._setup_top_frame()
        self._setup_treeview()
        self._setup_bottom_frame()

        self._rename_queue: list[tuple[str, str, str]] = []
        self._date_count: Counter[datetime] = Counter()

    def _setup_window(self) -> None:
        self.title(WINDOW_NAME)
        self.geometry(WINDOW_SIZE)
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme(COLOR_THEME)
        self.grid_columnconfigure(0, weight=1)

    def _setup_top_frame(self) -> None:
        top_frame = ctk.CTkFrame(self, corner_radius=0)
        top_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        top_frame.grid_columnconfigure(1, weight=1)

        media_folder_label = ctk.CTkLabel(top_frame, text="Media Folder:")
        media_folder_label.grid(row=0, column=0, padx=10, pady=10)

        self.folder_path_entry = ctk.CTkEntry(top_frame, state="readonly")
        self.folder_path_entry.grid(row=0, column=1, sticky="ew")

        browse_button = ctk.CTkButton(
            top_frame, text="Browse...", command=self._select_folder
        )
        browse_button.grid(row=0, column=2, padx=10)

    def _setup_treeview(self):
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

        treeview_frame = ctk.CTkFrame(self, corner_radius=0)
        treeview_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=0)
        treeview_frame.grid_rowconfigure(0, weight=1)
        treeview_frame.grid_columnconfigure(0, weight=1)

        self.treeview = ttk.Treeview(
            treeview_frame,
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

        scrollbar = ctk.CTkScrollbar(treeview_frame, command=self.treeview.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.treeview.configure(yscrollcommand=scrollbar.set)

        self.grid_rowconfigure(1, weight=1)

    def _setup_bottom_frame(self):
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.rename_button = ctk.CTkButton(
            bottom_frame, text="Rename Files", command=self._start_rename_process
        )
        self.rename_button.grid(row=0, column=0, columnspan=2, pady=10, padx=10)

        self.progress_bar = ctk.CTkProgressBar(bottom_frame)
        self.progress_bar.set(0)
        self.progress_bar.grid(
            row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 10)
        )

    def _clean_treeview(self) -> None:
        self.treeview.delete(*self.treeview.get_children())

    def _set_folder_path_entry(self, folder_path: str) -> None:
        self.folder_path_entry.configure(state="normal")
        self.folder_path_entry.delete(0, "end")
        self.folder_path_entry.insert(0, folder_path)
        self.folder_path_entry.configure(state="readonly")

    def _add_file_to_treeview(
        self, original_name: str, new_name: str, status: str
    ) -> str:
        item_id = self.treeview.insert(
            "", "end", values=(original_name, new_name, status)
        )
        self.update_idletasks()
        return item_id

    def _select_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            folder_path = Path(folder_selected)
            logging.info("Folder selected: %s", folder_path)
            self._set_folder_path_entry(str(folder_path))
            self._scan_folder(folder_path)

    def _new_filename(self, file_path: Path, date: datetime) -> str:
        formated_date = date.strftime(RENAME_DATE_FORMAT)
        count = self._date_count[date]

        new_filename = f"{formated_date}_{count}{file_path.suffix}"
        self._date_count[date] += 1

        return new_filename

    def _scan_folder(self, folder_path: Path) -> None:
        logging.info("Scanning folder: %s", folder_path)
        self._clean_treeview()
        self.progress_bar.set(0)
        self._rename_queue.clear()
        self._date_count.clear()

        for file_path in sorted(folder_path.iterdir()):
            if not file_path.is_file():
                logging.debug("Skipping non-file item: %s", file_path.name)
                continue

            file_suffix = file_path.suffix.lower()
            if file_suffix in IMAGE_EXTENSIONS:
                date = extract_date_from_image(file_path)
            elif file_suffix in VIDEO_EXTENSIONS:
                date = extract_date_from_video(file_path)
            else:
                logging.debug("Skipping unsupported file type: %s", file_path.name)
                continue

            if date is None:
                self._add_file_to_treeview(file_path.name, "", "No Date Found")
                continue

            new_filename = self._new_filename(file_path, date)
            status = "Ready" if new_filename != file_path.name else "No Change"

            item_id = self._add_file_to_treeview(file_path.name, new_filename, status)
            if status != "Ready":
                continue

            self._rename_queue.append((item_id, file_path.name, new_filename))

        count = len(self._rename_queue)
        logging.info("Scan complete. Found %d files ready for renaming.", count)

    def _start_rename_process(self):
        if not self._rename_queue:
            logging.info("No files to rename.")
            return

        total_items = len(self._rename_queue)
        logging.info("Starting rename process for %d files.", total_items)
        self.progress_bar.set(0)

        folder_path = Path(self.folder_path_entry.get())
        rename_queue = list(self._rename_queue)
        self._rename_queue.clear()

        for index, (item_id, original_filename, new_filename) in enumerate(
            rename_queue
        ):
            original_path = folder_path / original_filename
            new_path = folder_path / new_filename
            status = ""

            try:
                if new_path.exists():
                    status = "Conflict"
                    logging.warning(
                        "Could not rename '%s' because '%s' already exists.",
                        original_filename,
                        new_filename,
                    )
                else:
                    original_path.rename(new_path)
                    status = "Renamed"
                    logging.info(
                        "Renamed '%s' to '%s'", original_filename, new_filename
                    )
            except Exception as e:
                logging.error("Error renaming '%s': %s", original_filename, e)
                status = "Error"

            self.treeview.item(
                item_id, values=(original_filename, new_filename, status)
            )
            self.progress_bar.set((index + 1) / total_items)
            self.update_idletasks()

        logging.info("Rename process finished.")


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

    logging.info("Application started")
    app = App()
    app.mainloop()
    logging.info("Application closed")


if __name__ == "__main__":
    main()
