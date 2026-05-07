import logging
import os
from logging.handlers import TimedRotatingFileHandler

class DailyRotatingFileHandler(TimedRotatingFileHandler):
    def rotation_filename(self, default_name):
        base_dir, base_name = os.path.split(default_name)
        if ".log." in base_name:
            nombre, fecha = base_name.split(".log.")
            nuevo_nombre = f"{nombre}-{fecha}.log"
            return os.path.join(base_dir, nuevo_nombre)
        return default_name

    def getFilesToDelete(self):
        dirName, baseName = os.path.split(self.baseFilename)
        fileNames = os.listdir(dirName)
        result = []
        prefix = baseName.replace('.log', '-')
        suffix = ".log"
        for fileName in fileNames:
            if fileName.startswith(prefix) and fileName.endswith(suffix):
                date_str = fileName[len(prefix):-len(suffix)]
                if self.extMatch and self.extMatch.match(date_str):
                    result.append(os.path.join(dirName, fileName))
        result.sort()
        if len(result) < self.backupCount:
            result = []
        else:
            result = result[:len(result) - self.backupCount]
        return result

class ColorFormatter(logging.Formatter):
    def format(self, record):
        timestamp = self.formatTime(record, self.datefmt)
        level = record.levelname.ljust(8)
        name = record.name.ljust(15)
        message = record.getMessage()
        return f"{timestamp} | {level} | {name} | {message}"

def setup_logger(name: str, log_file: str, level=logging.INFO):
    if not os.path.isabs(log_file):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_file = os.path.join(base_dir, "Logs", log_file)

    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    formatter = ColorFormatter(datefmt='%Y-%m-%d %H:%M:%S')
    
    handler = DailyRotatingFileHandler(log_file, when="midnight", interval=1, backupCount=30)
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        logger.addHandler(handler)
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger
