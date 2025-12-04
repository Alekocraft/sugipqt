import os
import logging
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, session, flash,
    jsonify, url_for, send_file
)
from werkzeug.utils import secure_filename

# Configuración de logging
logger = logging.getLogger(__name__)

# Importación de modelos
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.solicitudes_model import SolicitudModel
from models.usuarios_model import UsuarioModel
from models.inventario_corporativo_model import InventarioCorporativoModel

# Importación de utilidades
from utils.filters import filtrar_por_oficina_usuario, verificar_acceso_oficina
from utils.initialization import inicializar_oficina_principal
from utils.permissions import (
    can_access, can_view_actions,
    get_accessible_modules,
    can_create_novedad, can_manage_novedad
)

# Importación de blueprints principales (siempre disponibles)
from blueprints.auth import auth_bp
from blueprints.materiales import materiales_bp
from blueprints.solicitudes import solicitudes_bp
from blueprints.oficinas import oficinas_bp
from blueprints.aprobadores import aprobadores_bp
from blueprints.reportes import reportes_bp
from blueprints.api import api_bp

# Importación condicional de blueprint de préstamos
try:
    from blueprints.prestamos import prestamos_bp
    logger.info("Blueprint de préstamos cargado exitosamente")
except ImportError as e:
    logger.warning(f"Blueprint de préstamos no disponible: {e}")
    from flask import Blueprint
    prestamos_bp = Blueprint('prestamos', __name__)
    
    @prestamos_bp.route('/')
    def prestamos_vacio():
        flash('Módulo de préstamos no disponible', 'warning')
        return redirect('/dashboard')

# Importación condicional de blueprint de inventario corporativo
try:
    from blueprints.inventario_corporativo import inventario_corporativo_bp
    logger.info("Blueprint de inventario corporativo cargado desde blueprints")
except ImportError as e:
    logger.warning(f"Blueprint de inventario corporativo no encontrado en blueprints: {e}")
    try:
        from routes_inventario_corporativo import bp_inv as inventario_corporativo_bp
        logger.info("Blueprint de inventario corporativo cargado desde routes_inventario_corporativo")
    except ImportError as e2:
        logger.warning(f"Blueprint de inventario corporativo no disponible: {e2}")
        from flask import Blueprint
        inventario_corporativo_bp = Blueprint('inventario_corporativo', __name__)
        
        @inventario_corporativo_bp.route('/')
        def inventario_vacio():
            flash('Módulo de inventario corporativo no disponible', 'warning')
            return redirect('/dashboard')

# Conexión a base de datos
from database import get_database_connection

# Configuración de la aplicación Flask
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Configuración de seguridad y aplicación
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Configuración de archivos subidos
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Directorio de uploads configurado en: {os.path.abspath(UPLOAD_FOLDER)}")

# Context processor para funciones de utilidad en templates
@app.context_processor
def utility_processor():
    """Inyecta funciones de permisos en todos los templates"""
    return dict(
        can_create_novedad=can_create_novedad,
        can_manage_novedad=can_manage_novedad,
        can_access=can_access,
        can_view_actions=can_view_actions,
        get_accessible_modules=get_accessible_modules
    )

# Registro de blueprints principales
app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')
app.register_blueprint(auth_bp)
app.register_blueprint(materiales_bp)
app.register_blueprint(oficinas_bp)
app.register_blueprint(aprobadores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(api_bp)

# Registro de blueprints opcionales
app.register_blueprint(prestamos_bp, url_prefix='/prestamos')
logger.info("Blueprint de préstamos registrado")

app.register_blueprint(inventario_corporativo_bp, url_prefix='/inventario-corporativo')
logger.info("Blueprint de inventario corporativo registrado")

# Ruta principal y redirección
@app.route('/')
def index():
    """Redirige usuarios autenticados al dashboard, otros al login"""
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/auth/login')

@app.route('/dashboard')
def dashboard():
    """Página principal del dashboard de la aplicación"""
    if 'user_id' not in session:
        logger.warning("Intento de acceso al dashboard sin autenticación")
        return redirect('/auth/login')
    return render_template('dashboard.html')

# Manejadores de errores
@app.errorhandler(404)
def pagina_no_encontrada(error):
    """Maneja errores 404 - Página no encontrada"""
    logger.warning(f"Página no encontrada: {request.path}")
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def error_interno(error):
    """Maneja errores 500 - Error interno del servidor"""
    logger.error(f"Error interno del servidor: {error}", exc_info=True)
    return render_template('error/500.html'), 500

@app.errorhandler(413)
def archivo_demasiado_grande(error):
    """Maneja errores 413 - Archivo demasiado grande"""
    logger.warning(f"Intento de subir archivo demasiado grande: {request.url}")
    flash('El archivo es demasiado grande. Tamaño máximo: 16MB', 'danger')
    return redirect(request.url)

# Punto de entrada de la aplicación
if __name__ == '__main__':
    logger.info("Iniciando servidor Flask de Sistema de Gestión de Inventarios")
    
    # Inicialización del sistema
    inicializar_oficina_principal()
    
    # Configuración del puerto
    port = int(os.environ.get('PORT', 8000))
    logger.info(f"Servidor iniciado en puerto: {port}")
    
    app.run(
        debug=True,
        host='0.0.0.0',
        port=port
    )