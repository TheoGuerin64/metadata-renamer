import logging
import sys

from app import main

debug_mode = "--debug" in sys.argv or "-d" in sys.argv

logging.basicConfig(
    level=logging.DEBUG if debug_mode else logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("metadate_renamer.log"),
        logging.StreamHandler(),
    ],
)

main()
