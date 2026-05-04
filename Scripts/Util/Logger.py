import os
import logging
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

def setup_logger(name: str, log_file: str, level=logging.INFO):
    if not os.path.isabs(log_file):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        log_file = os.path.join(base_dir, "Logs", log_file)

    log_dir = os.path.dirname(log_file)
    os.makedirs(log_dir, exist_ok=True)

    handler = DailyRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )

    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(name)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)

    logging.basicConfig(
        level=level,
        handlers=[handler, logging.StreamHandler()]
    )

    return logging.getLogger(name)
