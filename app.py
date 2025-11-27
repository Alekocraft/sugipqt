# -*- coding: utf-8 -*-
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
from utils.permissions import (
    can_access, can_view_actions,
    get_accessible_modules,
    can_create_novedad, can_manage_novedad
)

# ===============================
# 🧩 Importación de Blueprints (CORRECTOS)
# ===============================
from blueprints.auth import auth_bp
from blueprints.materiales import materiales_bp
from blueprints.solicitudes import solicitudes_bp
from blueprints.oficinas import oficinas_bp
from blueprints.aprobadores import aprobadores_bp
from blueprints.reportes import reportes_bp
from blueprints.aprobacion import aprobacion_bp
from blueprints.api import api_bp

# ===============================
# 🔧 SOLO UN BLUEPRINT DE PRÉSTAMOS
# ===============================
try:
    from blueprints.prestamos import prestamos_bp
    print("✅ Blueprint de préstamos encontrado")
except ImportError as e:
    print(f"❌ Error importando blueprint de préstamos: {e}")
    # Crear blueprint vacío como fallback
    from flask import Blueprint
    prestamos_bp = Blueprint('prestamos', __name__)
    
    @prestamos_bp.route('/')
    def prestamos_vacio():
        flash('Módulo de préstamos no disponible', 'warning')
        return redirect('/dashboard')

# ===============================
# 🔧 Configuración robusta para Inventario Corporativo
# ===============================
try:
    from blueprints.inventario_corporativo import inventario_corporativo_bp
    print("✅ Blueprint de inventario corporativo encontrado en blueprints")
except ImportError as e:
    print(f"⚠️ No se encontró en blueprints: {e}")
    try:
        from routes_inventario_corporativo import bp_inv as inventario_corporativo_bp
        print("✅ Blueprint de inventario encontrado en routes_inventario_corporativo")
    except ImportError as e2:
        print(f"⚠️ No se encontró en routes_inventario_corporativo: {e2}")
        print("🔧 Creando blueprint vacío para inventario...")
        from flask import Blueprint
        inventario_corporativo_bp = Blueprint('inventario_corporativo', __name__)
        
        # Añadir ruta básica al blueprint vacío para evitar errores
        @inventario_corporativo_bp.route('/')
        def inventario_vacio():
            flash('Módulo de inventario corporativo no disponible', 'warning')
            return redirect('/dashboard')

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

app.secret_key = os.environ.get('SECRET_KEY', os.urandom(32))
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ===============================
# 📂 Configuración de Uploads
# ===============================
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"✅ Directorio de uploads: {os.path.abspath(UPLOAD_FOLDER)}")

# =======================================
# 🧠 Context Processor
# =======================================
@app.context_processor
def utility_processor():
    return dict(
        can_create_novedad=can_create_novedad,
        can_manage_novedad=can_manage_novedad,
        can_access=can_access,
        can_view_actions=can_view_actions,
        get_accessible_modules=get_accessible_modules
    )

# ===============================
# 🔗 Registro de Blueprints (FINAL)
# ===============================
app.register_blueprint(solicitudes_bp, url_prefix='/solicitudes')
app.register_blueprint(auth_bp)
app.register_blueprint(materiales_bp)
app.register_blueprint(oficinas_bp)
app.register_blueprint(aprobadores_bp)
app.register_blueprint(reportes_bp)
app.register_blueprint(aprobacion_bp)
app.register_blueprint(api_bp)

# ===============================
# 📌 SOLO UN BLUEPRINT DE PRÉSTAMOS REGISTRADO
# ===============================
app.register_blueprint(prestamos_bp, url_prefix='/prestamos')
print("✅ Blueprint de préstamos registrado exitosamente")

# Registrar inventario de forma incondicional con prefijo
app.register_blueprint(inventario_corporativo_bp, url_prefix='/inventario-corporativo')
print("✅ Blueprint de inventario corporativo registrado exitosamente")

# ===============================
# 📌 Verificación de Blueprints
# ===============================
print("✅ Blueprints registrados:")
for name, blueprint in app.blueprints.items():
    print(f"   - {name}: {blueprint}")

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

# ===============================
# 🔥 Error Handlers
# ===============================
@app.errorhandler(404)
def pagina_no_encontrada(error):
    return render_template('error/404.html'), 404


@app.errorhandler(500)
def error_interno(error):
    return render_template('error/500.html'), 500


@app.errorhandler(413)
def archivo_demasiado_grande(error):
    flash('El archivo es demasiado grande. Tamaño máximo: 16MB', 'danger')
    return redirect(request.url)

# ===============================
# 🏁 Inicialización
# ===============================
if __name__ == '__main__':
    print("🚀 Iniciando servidor Flask...")
    inicializar_oficina_principal()

    port = int(os.environ.get('PORT', 8000))
    print(f"🌐 Servidor en: http://0.0.0.0:{port}")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=port
    )