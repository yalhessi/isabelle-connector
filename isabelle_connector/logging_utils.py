from __future__ import annotations

import logging
import sys
from pathlib import Path

from loguru import logger

DEFAULT_CONSOLE_FORMAT = "{level} {name}: {message}"
DEFAULT_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{function}:{line} - {message}"
)

# If tqdm is installed, configure loguru with tqdm.write
# https://github.com/Delgan/loguru/issues/135
try:
    from tqdm import tqdm

    logger.remove(0)
    logger.add(lambda msg: tqdm.write(msg, end=""), colorize=True)
except ModuleNotFoundError:
    pass
except ValueError:
    pass

class InterceptHandler(logging.Handler):
    """Route stdlib logging records into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame = logging.currentframe()
        depth = 2
        while frame is not None and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def intercept_stdlib_logging() -> None:
    """Send stdlib logging through loguru."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


def configure_logging(
    level: str | int = "INFO",
    *,
    file_path: str | Path | None = None,
    enable_package_logs: bool = True,
) -> None:
    """Configure loguru for scripts and examples."""
    logger.remove()
    logger.add(sys.stderr, level=level, format=DEFAULT_CONSOLE_FORMAT)
    if file_path is not None:
        logger.add(file_path, level="DEBUG", format=DEFAULT_FILE_FORMAT, enqueue=True)
    if enable_package_logs:
        logger.enable("isabelle_connector")
    intercept_stdlib_logging()
