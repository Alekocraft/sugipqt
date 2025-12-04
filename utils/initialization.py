import os
import logging
from datetime import datetime
from database import get_database_connection
from models.oficinas_model import OficinaModel

logger = logging.getLogger(__name__)

def inicializar_oficina_principal():
    """Verifica y crea la oficina COQ principal si no existe en la base de datos"""
    try:
        logger.info("Verificando existencia de la oficina COQ...")
        oficina_principal = OficinaModel.obtener_por_nombre("COQ")

        if not oficina_principal:
            logger.info("Creando oficina COQ...")
            conn = get_database_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO Oficinas (
                    NombreOficina, 
                    DirectorOficina, 
                    Ubicacion, 
                    EsPrincipal, 
                    Activo, 
                    FechaCreacion,
                    Email
                ) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "COQ",
                "Director General",
                "Ubicación Principal",
                1,
                1,
                datetime.now(),
                "coq@empresa.com"
            ))

            conn.commit()
            cursor.close()
            conn.close()
            logger.info("Oficina COQ creada exitosamente")

            oficina_verificada = OficinaModel.obtener_por_nombre("COQ")
            if oficina_verificada:
                logger.info(f"Oficina COQ verificada - ID: {oficina_verificada['id']}")
            else:
                logger.warning("No se pudo verificar la creación de la oficina COQ")
        else:
            logger.info(f"Oficina COQ ya existe - ID: {oficina_principal['id']}")
            
    except Exception as e:
        logger.error(f"Error inicializando oficina principal: {e}", exc_info=True)

def inicializar_directorios():
    """Crea los directorios necesarios para el funcionamiento de la aplicación"""
    from config.config import Config
    
    directorios = [
        Config.UPLOAD_FOLDER,
        os.path.join(Config.UPLOAD_FOLDER, 'productos'),
        os.path.join(Config.UPLOAD_FOLDER, 'documentos'),
        os.path.join(Config.UPLOAD_FOLDER, 'perfiles'),
        os.path.join(Config.UPLOAD_FOLDER, 'temp')
    ]
    
    for directorio in directorios:
        try:
            os.makedirs(directorio, exist_ok=True)
            logger.debug(f"Directorio verificado/creado: {directorio}")
        except Exception as e:
            logger.error(f"Error creando directorio {directorio}: {e}")

def verificar_configuracion():
    """Valida la configuración básica del sistema"""
    from config.config import Config
    
    logger.info("Verificando configuración del sistema...")
    
    directorios_requeridos = [Config.TEMPLATE_FOLDER, Config.STATIC_FOLDER]
    for folder in directorios_requeridos:
        if not os.path.exists(folder):
            logger.error(f"Directorio requerido no encontrado: {folder}")
        else:
            logger.debug(f"Directorio encontrado: {folder}")
    
    if Config.SECRET_KEY == 'dev-secret-key-change-in-production':
        logger.warning("Usando SECRET_KEY por defecto - Cambiar en producción")
    
    logger.info("Verificación de configuración completada")

def inicializar_roles_permisos():
    """Verifica la configuración de roles y permisos del sistema"""
    try:
        from config.config import Config
        roles_configurados = list(Config.ROLES.keys())
        logger.info(f"Roles configurados en el sistema: {len(roles_configurados)} roles")
        logger.debug(f"Roles: {', '.join(roles_configurados)}")
        
    except Exception as e:
        logger.error(f"Error verificando configuración de roles: {e}")

def inicializar_todo():
    """Ejecuta todas las rutinas de inicialización del sistema"""
    logger.info("Iniciando proceso de inicialización del sistema...")
    
    verificar_configuracion()
    inicializar_directorios()
    inicializar_oficina_principal()
    inicializar_roles_permisos()
    
    logger.info("Proceso de inicialización completado exitosamente")