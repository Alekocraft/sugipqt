# -*- coding: utf-8 -*- AAP.PY
import os
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect, session, flash,
    jsonify, url_for, send_file
)
from werkzeug.utils import secure_filename

# ===============================
# 📦 Importación de Modelos
# ===============================
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.solicitudes_model import SolicitudModel
from models.usuarios_model import UsuarioModel
from models.inventario_corporativo_model import InventarioCorporativoModel

# ===============================
# ⚙️ Importación de Utilidades
# ===============================
from utils.filters import filtrar_por_oficina_usuario, verificar_acceso_oficina
from utils.initialization import inicializar_oficina_principal
from utils.permissions import can_access, can_view_actions, get_accessible_modules

# ===============================
# 🧩 Importación de Blueprints
# ===============================
from blueprints.auth import auth_bp
from blueprints.materiales import materiales_bp
from blueprints.solicitudes import solicitudes_bp
from blueprints.oficinas import oficinas_bp
from blueprints.aprobadores import aprobadores_bp
from blueprints.reportes import reportes_bp
from blueprints.aprobacion import aprobacion_bp
from blueprints.api import api_bp


# SOLUCIÓN: Solo importar UN blueprint de inventario corporativo
try:
    from blueprints.inventario_corporativo import inventario_corporativo_bp
    HAS_INVENTARIO_BP = True
except ImportError:
    HAS_INVENTARIO_BP = False
    print("⚠️  Blueprint de inventario corporativo no encontrado en blueprints/")

# Importar solo si no existe el blueprint en blueprints/
if not HAS_INVENTARIO_BP:
    try:
        from routes_inventario_corporativo import bp_inv as inventario_corporativo_bp
        print("✅ Usando blueprint de inventario desde routes_inventario_corporativo")
    except ImportError:
        print("❌ No se pudo importar ningún blueprint de inventario corporativo")

# Importación adicional de rutas
from routes_prestamos import bp_prestamos

# ===============================
# 💾 Conexión a Base de Datos
# ===============================
from database import get_database_connection


# ===============================
# 🚀 Configuración de la Aplicación
# ===============================
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static')
)

# Configuración básica
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ===============================
# 📂 Configuración de Uploads
# ===============================
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

# Crear directorio de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Directorio de uploads: {os.path.abspath(UPLOAD_FOLDER)}")


# ===============================
# 🧠 Context Processor (Permisos)
# ===============================
@app.context_processor
def inject_permissions():
    return {
        'can_access': can_access,
        'can_view_actions': can_view_actions,
        'get_accessible_modules': get_accessible_modules
    }


# ===============================
# 🔗 Registro de Blueprints - CORREGIDO
# ===============================
# Rutas adicionales
app.register_blueprint(bp_prestamos)
app.register_blueprint(auth_bp)
app.register_blueprint(materiales_bp)
app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')  # CORREGIDO: agregado url_prefix
app.register_blueprint(oficinas_bp)
app.register_blueprint(aprobadores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(aprobacion_bp)
app.register_blueprint(api_bp)

# ===============================
# 🔄 ACTUALIZACIÓN: Registro de inventario_corporativo_bp
# ===============================
# Registro directo del blueprint sin url_prefix (como en el primer código)
app.register_blueprint(inventario_corporativo_bp)   # No usar url_prefix, ya viene en las rutas

# ===============================
# ✅ Verificación de Registro
# ===============================
print("✅ Blueprints registrados:")
for name, blueprint in app.blueprints.items():
    print(f"   - {name}: {blueprint.url_prefix}")

# ===============================
# 🏠 Ruta Principal
# ===============================
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect('/dashboard')
    return redirect('/auth/login')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/auth/login')
    return render_template('dashboard.html')

# ============================================================================
# 🔥 ERROR HANDLERS
# ============================================================================
@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template('error/404.html'), 404

@app.errorhandler(500)
def error_interno(error):
    # Puedes loggear el error aquí si lo deseas
    return render_template('error/500.html'), 500

@app.errorhandler(413)
def archivo_demasiado_grande(error):
    flash('El archivo es demasiado grande. Tamaño máximo: 16MB', 'danger')
    return redirect(request.url)


# ============================================================================
# 🏁 INICIALIZACIÓN
# ============================================================================
 
if __name__ == '__main__':
    print("🚀 Iniciando servidor Flask...")
    print(f"📁 Directorio de trabajo: {os.getcwd()}")
    
    # Inicializar Sede Principal
    inicializar_oficina_principal()
    
    # Puerto configurable por entorno
    port = int(os.environ.get('PORT', 8000))
    
    print(f"🌐 Servidor ejecutándose en: http://0.0.0.0:{port}")
    print("📍 Presiona Ctrl+C para detener el servidor")
    
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true',
        host='0.0.0.0', 
        port=port
    )