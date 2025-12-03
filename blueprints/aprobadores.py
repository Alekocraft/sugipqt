from flask import Blueprint, render_template, request, redirect, session, flash, url_for, current_app
from models.usuarios_model import UsuarioModel
from utils.permissions import can_access
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# 📘 Crear blueprint de aprobadores
aprobadores_bp = Blueprint('aprobadores', __name__, url_prefix='/aprobadores')


# 🧩 Helper: Verifica si el usuario está logueado
def _require_login():
    # Verificar ambas posibles claves de sesión
    return 'usuario_id' in session or 'user_id' in session


# 📄 Ruta principal: listar aprobadores
@aprobadores_bp.route('/')
def listar_aprobadores():
    """Listar todos los aprobadores del sistema"""
    
    # 🔒 Verificación de sesión
    if not _require_login():
        logger.warning("Intento de acceso sin sesión a /aprobadores")
        flash('Debe iniciar sesión para acceder a esta sección', 'warning')
        return redirect(url_for('auth.login'))

    # 🔐 Verificación de permisos
    if not can_access('aprobadores', 'view'):
        logger.warning(f"Usuario {session.get('usuario_id')} sin permisos para ver aprobadores")
        flash('No tiene permisos para acceder a esta sección', 'danger')
        return redirect(url_for('dashboard'))

    try:
        # 📦 Obtener lista de aprobadores desde el modelo
        logger.info(f"Obteniendo aprobadores para usuario {session.get('usuario_id')}")
        aprobadores = UsuarioModel.obtener_aprobadores()
        
        # Log para debugging
        if aprobadores:
            logger.info(f"Se encontraron {len(aprobadores)} aprobadores")
            # Imprimir en consola para debug
            print(f"✅ DATOS DE APROBADORES OBTENIDOS:")
            print(f"✅ Cantidad: {len(aprobadores)}")
            for i, apr in enumerate(aprobadores[:3]):  # Mostrar primeros 3
                print(f"✅ Aprobador {i+1}: ID={apr.get('AprobadorId')}, Nombre={apr.get('NombreAprobador')}, Email={apr.get('Email')}")
        else:
            logger.info("No se encontraron aprobadores")
            print("⚠️ No se encontraron aprobadores en la base de datos")
        
        # ✅ CORREGIDO: Ahora apunta a la plantilla correcta 'aprobadores/listar.html'
        return render_template(
            'aprobadores/listar.html',  # ← CAMBIADO de 'aprobadores.html' a 'aprobadores/listar.html'
            aprobadores=aprobadores or [],
            debug=False  # Cambiar a True para ver datos en pantalla
        )

    except Exception as e:
        # ⚠️ Manejo de errores
        logger.error(f"Error obteniendo aprobadores: {str(e)}", exc_info=True)
        print(f"❌ ERROR en listar_aprobadores: {str(e)}")
        flash('Ocurrió un error al cargar los aprobadores', 'danger')
        return render_template('aprobadores/listar.html', aprobadores=[], debug=False)