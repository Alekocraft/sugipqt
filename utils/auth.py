import logging
from flask import session, flash, redirect, url_for, request
from functools import wraps

logger = logging.getLogger(__name__)

def require_login():
    """
    Verifica si el usuario está autenticado en el sistema
    
    Returns:
        bool: True si el usuario tiene sesión activa
    """
    is_authenticated = 'user_id' in session or 'usuario_id' in session
    logger.debug(f"Verificación de autenticación: {is_authenticated}")
    return is_authenticated

def has_role(*roles):
    """
    Verifica si el usuario tiene alguno de los roles especificados
    
    Args:
        *roles: Roles a verificar
        
    Returns:
        bool: True si el usuario tiene al menos uno de los roles
    """
    user_role = (session.get('rol', '') or '').strip().lower()
    target_roles = [r.lower() for r in roles]
    has_valid_role = user_role in target_roles
    
    logger.debug(f"Usuario rol '{user_role}' tiene alguno de {roles}: {has_valid_role}")
    return has_valid_role

def login_required(f):
    """
    Decorador para proteger rutas que requieren autenticación
    
    Args:
        f: Función a decorar
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not require_login():
            logger.warning(f"Intento de acceso no autenticado a {request.endpoint}")
            flash('Por favor inicie sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth_bp.login', next=request.url))
        
        logger.debug(f"Acceso autorizado a {request.endpoint}")
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """
    Decorador para proteger rutas que requieren roles específicos
    
    Args:
        *roles: Roles requeridos para acceder
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not require_login():
                logger.warning(f"Intento de acceso no autenticado a ruta con roles {roles}")
                flash('Por favor inicie sesión.', 'warning')
                return redirect(url_for('auth_bp.login', next=request.url))
            
            if not has_role(*roles):
                user_role = session.get('rol', 'No definido')
                logger.warning(f"Usuario rol '{user_role}' intentó acceder a ruta que requiere roles {roles}")
                flash('No tiene permisos para acceder a esta sección.', 'danger')
                return redirect(url_for('auth_bp.dashboard'))
            
            logger.debug(f"Acceso autorizado con rol a {request.endpoint}")
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """
    Obtiene la información del usuario actualmente autenticado
    
    Returns:
        dict: Información del usuario o None si no está autenticado
    """
    if not require_login():
        return None
    
    user_data = {
        'id': session.get('user_id') or session.get('usuario_id'),
        'nombre': session.get('user_name') or session.get('usuario_nombre'),
        'rol': session.get('rol'),
        'oficina_id': session.get('oficina_id'),
        'oficina_nombre': session.get('oficina_nombre')
    }
    
    logger.debug(f"Datos de usuario obtenidos: {user_data['nombre']} ({user_data['rol']})")
    return user_data

def can_access_module(module_name):
    """
    Verifica si el usuario puede acceder a un módulo específico según su rol
    
    Args:
        module_name: Nombre del módulo a verificar
        
    Returns:
        bool: True si el usuario tiene acceso al módulo
    """
    from config.config import Config
    user_role = (session.get('rol', '') or '').strip().lower()
    allowed_modules = Config.ROLES.get(user_role, [])
    
    has_access = module_name in allowed_modules
    logger.debug(f"Acceso a módulo '{module_name}' para rol '{user_role}': {has_access}")
    return has_access