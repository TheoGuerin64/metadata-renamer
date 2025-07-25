from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pathlib import Path


_IMAGE_FILE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
    ".webp",
    ".tif",
    ".tiff",
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
    from PIL import Image
    from PIL.ExifTags import IFD
    from PIL.ExifTags import Base as ExifBase

    logging.debug("Extracting EXIF date from %s", path.name)

    try:
        image = Image.open(path)
    except OSError as error:
        logging.error("Failed to read %s: %s", path.name, error)
        return None

    try:
        exif = image.getexif()
    except Exception as error:
        logging.error("Failed to extract EXIF data from %s: %s", path.name, error)
        return None
    if not exif:
        logging.info("No EXIF data found in %s", path.name)
        return None

    ifd = exif.get_ifd(IFD.Exif)
    if ifd is None:
        logging.info("No EXIF IFD found in %s", path.name)
        return None

    raw_date: str | None = ifd.get(ExifBase.DateTimeOriginal)
    if raw_date is not None:
        try:
            date = datetime.strptime(raw_date, "%Y:%m:%d %H:%M:%S")
        except ValueError as e:
            logging.error(
                "Failed to parse EXIF date '%s' in %s: %s", raw_date, path.name, e
            )
            return None

        logging.debug("Found EXIF date '%s' in %s", date, path.name)
        return date

    logging.info("No EXIF date tag in %s", path.name)
    return None


def _from_video(path: Path) -> datetime | None:
    from hachoir.metadata import extractMetadata
    from hachoir.parser import createParser

    logging.debug("Extracting metadata date from %s", path.name)

    try:
        parser = createParser(str(path))
    except Exception as error:
        logging.error("Failed to create parser for %s: %s", path.name, error)
        return None
    if not parser:
        logging.error("No parser created for %s", path.name)
        return None

    try:
        with parser:
            metadata = extractMetadata(parser)
    except Exception as error:
        logging.error("Failed to extract metadata from %s: %s", path.name, error)
        return None

    if metadata and metadata.has("creation_date"):
        try:
            creation_date = cast(datetime, metadata.get("creation_date"))
        except ValueError as error:
            logging.error("Failed to parse creation date in %s: %s", path.name, error)
            return None

        logging.debug("Found metadata date '%s' in %s", creation_date, path.name)
        return creation_date

    logging.info("No 'creation_date' in metadata for %s", path.name)
    return None
