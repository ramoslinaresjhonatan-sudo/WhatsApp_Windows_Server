import logging
import sys
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler

_BASE_DIR = Path(__file__).resolve().parent.parent.parent


class _DailyRotatingHandler(TimedRotatingFileHandler):

    def rotation_filename(self, default_name: str) -> str:
        p = Path(default_name)
        stem = p.stem          
        suffix = p.suffix      
        if stem.endswith(".log"):
            base = stem[: -len(".log")]
            date = suffix.lstrip(".")
            return str(p.parent / f"{base}-{date}.log")
        return default_name


class _PlainFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname.ljust(8)
        name = record.name.ljust(15)
        return f"{timestamp} | {level} | {name} | {record.getMessage()}"


def setup_logger(
    name: str,
    log_file: str,
    level: int = logging.INFO,
    backup_days: int = 30,
) -> logging.Logger:
    log_path = Path(log_file) if Path(log_file).is_absolute() else _BASE_DIR / "Logs" / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = _PlainFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    file_handler = _DailyRotatingHandler(
        str(log_path), when="midnight", interval=1, backupCount=backup_days, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger
