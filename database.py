import pyodbc
import logging

# Configuración de logging
logger = logging.getLogger(__name__)

class Database:
    """
    Clase para manejar la conexión a la base de datos SQL Server
    Utiliza autenticación integrada de Windows (Trusted_Connection)
    """
    def __init__(self):
        self.server = 'localhost'
        self.database = 'SistemaGestionInventarios'
        self.driver = '{ODBC Driver 17 for SQL Server}'
    
    def get_connection(self):
        """
        Establece una conexión con la base de datos
        
        Returns:
            pyodbc.Connection: Objeto de conexión a la base de datos
            None: Si la conexión falla
        """
        try:
            conn_str = f"""
                DRIVER={self.driver};
                SERVER={self.server};
                DATABASE={self.database};
                Trusted_Connection=yes;
            """
            conn = pyodbc.connect(conn_str)
            logger.info("Conexión a la base de datos establecida exitosamente")
            return conn
        except pyodbc.InterfaceError as e:
            logger.error(f"Error de interfaz ODBC al conectar a la base de datos: {e}")
            return None
        except pyodbc.OperationalError as e:
            logger.error(f"Error operacional al conectar a la base de datos: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al conectar a la base de datos: {e}", exc_info=True)
            return None

# Instancia global de la base de datos para uso en toda la aplicación
db = Database()

def get_database_connection():
    """
    Proporciona una conexión a la base de datos
    Mantiene compatibilidad con imports existentes en la aplicación
    
    Returns:
        pyodbc.Connection: Conexión a la base de datos configurada
    """
    return db.get_connection()