import os
import shutil
import logging

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, subcarpeta="imagenes"):
        # Definir la ruta base del almacenamiento
        self.base_dir = os.path.abspath(os.path.join(os.getcwd(), "storage", subcarpeta))
        
        # Asegurar que el directorio existe
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir, exist_ok=True)

    def borrar_archivo(self, ruta_o_nombre):
        """
        Borra un archivo. Si se pasa solo el nombre, lo busca en la carpeta configurada.
        Si se pasa la ruta completa, la borra directamente.
        """
        if not ruta_o_nombre:
            return False

        # Si es solo un nombre de archivo (no tiene barras de ruta), construir ruta completa
        if os.sep not in ruta_o_nombre and "/" not in ruta_o_nombre:
            ruta_final = os.path.join(self.base_dir, ruta_o_nombre)
        else:
            ruta_final = os.path.abspath(ruta_o_nombre)

        try:
            if os.path.exists(ruta_final):
                os.remove(ruta_final)
                logger.info(f"   [Storage] Archivo eliminado: {os.path.basename(ruta_final)}")
                return True
            else:
                logger.warning(f"   [Storage] El archivo no existe para borrar: {ruta_final}")
                return False
        except Exception as e:
            logger.error(f"   [Storage] Error al borrar archivo {ruta_o_nombre}: {e}")
            return False

    def borrar_todo(self):
        """
        Limpia completamente el contenido de la carpeta de almacenamiento.
        """
        logger.info(f"   [Storage] Limpiando todo el contenido de: {self.base_dir}")
        exito = True
        try:
            for elemento in os.listdir(self.base_dir):
                ruta_elemento = os.path.join(self.base_dir, elemento)
                try:
                    if os.path.isfile(ruta_elemento) or os.path.islink(ruta_elemento):
                        os.unlink(ruta_elemento)
                    elif os.path.isdir(ruta_elemento):
                        shutil.rmtree(ruta_elemento)
                except Exception as e:
                    logger.error(f"   [Storage] No se pudo borrar {elemento}: {e}")
                    exito = False
            return exito
        except Exception as e:
            logger.error(f"   [Storage] Error crítico al limpiar carpeta: {e}")
            return False

    def obtener_ruta(self, nombre_archivo):
        """Auxiliar para obtener la ruta completa de un nombre en el storage."""
        return os.path.join(self.base_dir, nombre_archivo)
