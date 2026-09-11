import logging
import tempfile
from pathlib import Path
from typing import Final

from content_automation_pipeline.__about__ import __application__

_DEFAULT_LOG_FILE_PATH: Final[Path] = Path(tempfile.gettempdir()) / __application__ / 'logs' / 'log.log'
_DEFAULT_CONSOLE_LEVEL: Final[int] = logging.DEBUG
_DEFAULT_FILE_LEVEL: Final[int] = logging.DEBUG

def create_logger(
    name: str,
    log_file: Path = _DEFAULT_LOG_FILE_PATH,
    console_level: int = _DEFAULT_CONSOLE_LEVEL,
    file_level: int = _DEFAULT_FILE_LEVEL,
) -> logging.Logger:
    logger: logging.Logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # If the logger has already been configured (e.g., handlers have been added), return it as is
    if logger.handlers:
        return logger

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Set up console handler
    console_handler: logging.Handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)

    # Set up file handler
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler: logging.Handler = logging.FileHandler(log_file)
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
