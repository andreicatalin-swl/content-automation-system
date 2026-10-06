import logging
import tempfile
from pathlib import Path
from typing import Final

from content_automation_system.__about__ import __application__

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

    # Determine if the logger has already been configured
    is_configured = bool(logger.handlers)
    # If the logger has already been configured, return it as is
    if is_configured:
        return logger

    # Set the logger level to DEBUG to capture all log messages
    logger.setLevel(logging.DEBUG)

    # Keep records on this logger so the handlers of its ancestors do not emit them again
    logger.propagate = False

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
