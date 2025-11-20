from flask import session, flash, redirect, url_for, request
from functools import wraps

def require_login():
    """Verifica si el usuario está logueado"""
    # CORREGIDO: Verificar ambas posibles variables de sesión
    return 'user_id' in session or 'usuario_id' in session

def has_role(*roles):
    """Verifica si el usuario tiene alguno de los roles especificados"""
    user_role = (session.get('rol', '') or '').strip().lower()
    return user_role in [r.lower() for r in roles]

def login_required(f):
    """Decorator para requerir autenticación"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not require_login():
            flash('Por favor inicie sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth_bp.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*roles):
    """Decorator para requerir roles específicos"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not require_login():
                flash('Por favor inicie sesión.', 'warning')
                return redirect(url_for('auth_bp.login', next=request.url))
            
            if not has_role(*roles):
                flash('No tiene permisos para acceder a esta sección.', 'danger')
                return redirect(url_for('auth_bp.dashboard'))
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def get_current_user():
    """Obtener información del usuario actual"""
    if require_login():
        return {
            'id': session.get('user_id') or session.get('usuario_id'),  # CORREGIDO: ambas opciones
            'nombre': session.get('user_name') or session.get('usuario_nombre'),
            'rol': session.get('rol'),
            'oficina_id': session.get('oficina_id'),
            'oficina_nombre': session.get('oficina_nombre')
        }
    return None

def can_access_module(module_name):
    """Verificar si el usuario puede acceder a un módulo específico"""
    from config.config import Config
    user_role = (session.get('rol', '') or '').strip().lower()
    allowed_modules = Config.ROLES.get(user_role, [])
    return module_name in allowed_modules