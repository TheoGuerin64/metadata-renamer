from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path

    from exifread.core.ifd_tag import IfdTag


_IMAGE_FILE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".heif",
    ".heic",
    ".webp",
)
_VIDEO_FILE_EXTENSIONS = (
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
)


def from_file(file: Path) -> datetime | None:
    suffix = file.suffix.lower()
    if suffix in _IMAGE_FILE_EXTENSIONS:
        return _from_image(file)
    elif suffix in _VIDEO_FILE_EXTENSIONS:
        return _from_video(file)
    else:
        logging.warning("Unsupported file type: %s", file.name)
        return None


def _from_image(path: Path) -> datetime | None:
    from exifread import process_file

    logging.debug("Extracting EXIF date from %s", path.name)

    try:
        with path.open("rb") as file:
            tags = process_file(file, details=False, extract_thumbnail=False)
    except OSError as error:
        logging.error("Failed to read %s: %s", path.name, error)
        return None

    tag: IfdTag | None = tags.get("EXIF DateTimeOriginal")
    if tag is not None:
        logging.debug("Found EXIF date '%s' in %s", tag.values, path.name)
        return datetime.strptime(tag.values, "%Y:%m:%d %H:%M:%S")

    logging.info("No EXIF date tag in %s", path.name)
    return None


def _from_video(path: Path) -> datetime | None:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser

    logging.debug("Extracting metadata date from %s", path.name)

    parser = createParser(str(path))
    if not parser:
        logging.error("No parser created for %s", path.name)
        return None

    with parser:
        metadata = extractMetadata(parser)

    if metadata and metadata.has("creation_date"):
        creation_date = cast(datetime, metadata.get("creation_date"))
        logging.debug("Found metadata date '%s' in %s", creation_date, path.name)
        return creation_date

    logging.info("No 'creation_date' in metadata for %s", path.name)
    return None
