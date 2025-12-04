"""
Sistema de gestión de permisos para el Sistema de Gestión de Inventarios
Maneja autorización basada en roles y oficinas del usuario
"""
import logging
from flask import session
from typing import Optional
from config.permissions import ROLE_PERMISSIONS, OFFICE_MAPPING, get_office_key

logger = logging.getLogger(__name__)

def normalize_role_key(role_raw: str) -> str:
    """
    Normaliza el rol obtenido de sesión para que coincida con las claves definidas
    
    Args:
        role_raw: Rol en formato crudo desde la sesión
        
    Returns:
        str: Clave normalizada del rol para búsqueda en ROLE_PERMISSIONS
    """
    if not role_raw:
        logger.debug("Rol vacío recibido para normalización")
        return ''

    role = role_raw.strip().lower()
    
    # Normalización de caracteres especiales
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ü': 'u', 'ñ': 'n'
    }
    
    for old, new in replacements.items():
        role = role.replace(old, new)
    
    role_normalized = role.replace(' ', '_')
    
    # Búsqueda directa en permisos definidos
    if role_normalized in ROLE_PERMISSIONS:
        logger.debug(f"Rol encontrado directamente: {role_normalized}")
        return role_normalized
    
    # Búsqueda ignorando guiones bajos
    role_flat = role_normalized.replace('_', '')
    for key in ROLE_PERMISSIONS.keys():
        key_flat = key.replace('_', '')
        if role_flat == key_flat:
            logger.debug(f"Rol encontrado por comparación plana: {key}")
            return key
    
    # Detección por contenido específico
    if 'admin' in role_normalized:
        logger.debug(f"Rol detectado como administrador: {role_raw}")
        return 'administrador'
    if 'lider' in role_normalized and 'invent' in role_normalized:
        logger.debug(f"Rol detectado como líder de inventario: {role_raw}")
        return 'lider_inventario'
    if 'tesorer' in role_normalized:
        logger.debug(f"Rol detectado como tesorería: {role_raw}")
        return 'tesoreria'
    if 'coq' in role_normalized:
        logger.debug(f"Rol detectado como oficina COQ: {role_raw}")
        return 'oficina_coq'
    
    logger.warning(f"Rol no reconocido: {role_raw}. Usando versión normalizada: {role_normalized}")
    return role_normalized

class PermissionManager:
    """Gestor centralizado de permisos de usuario"""
    
    @staticmethod
    def get_user_permissions() -> dict:
        """
        Obtiene todos los permisos del usuario actual basados en rol y oficina
        
        Returns:
            dict: Permisos del usuario incluyendo rol, oficina y filtros
        """
        role_raw = session.get('rol', '')
        role_key = normalize_role_key(role_raw)
        
        office_name = session.get('oficina_nombre', '')
        office_key = get_office_key(office_name)
        
        role_perms = ROLE_PERMISSIONS.get(role_key, {})
        
        permissions = {
            'role_key': role_key,
            'role': role_perms,
            'office_key': office_key,
            'office_filter': role_perms.get('office_filter', 'own'),
        }
        
        logger.debug(f"Permisos obtenidos para usuario: {permissions}")
        return permissions
    
    @staticmethod
    def has_module_access(module_name: str) -> bool:
        """Verifica si el usuario tiene acceso a un módulo completo"""
        perms = PermissionManager.get_user_permissions()
        role_modules = perms['role'].get('modules', [])
        has_access = module_name in role_modules
        logger.debug(f"Acceso a módulo '{module_name}': {has_access}")
        return has_access
    
    @staticmethod
    def has_action_permission(module: str, action: str) -> bool:
        """Verifica permiso para acción específica en módulo"""
        perms = PermissionManager.get_user_permissions()
        role_actions = perms['role'].get('actions', {}).get(module, [])
        has_permission = action in role_actions
        logger.debug(f"Permiso para acción '{action}' en módulo '{module}': {has_permission}")
        return has_permission
    
    @staticmethod
    def can_view_actions() -> bool:
        """Determina si el usuario puede ver columnas de acciones en interfaces"""
        role_key = PermissionManager.get_user_permissions().get('role_key', '')
        roles_with_actions = {'administrador', 'aprobador', 'lider_inventario', 'tesoreria'}
        can_view = role_key in roles_with_actions
        logger.debug(f"Usuario puede ver acciones: {can_view}")
        return can_view
    
    @staticmethod
    def can_manage_inventario_corporativo() -> bool:
        """Verifica permisos de gestión en inventario corporativo"""
        has_create = PermissionManager.has_action_permission('inventario_corporativo', 'create')
        has_edit = PermissionManager.has_action_permission('inventario_corporativo', 'edit')
        has_delete = PermissionManager.has_action_permission('inventario_corporativo', 'delete')
        can_manage = has_create or has_edit or has_delete
        logger.debug(f"Usuario puede gestionar inventario corporativo: {can_manage}")
        return can_manage
    
    @staticmethod
    def can_view_inventario_actions() -> bool:
        """Verifica si puede ver acciones en inventario corporativo"""
        return PermissionManager.can_manage_inventario_corporativo()
    
    @staticmethod
    def can_create_novedad() -> bool:
        """Verifica permiso para crear novedades"""
        can_create = PermissionManager.has_action_permission('novedades', 'create')
        logger.debug(f"Usuario puede crear novedades: {can_create}")
        return can_create
    
    @staticmethod
    def can_manage_novedad() -> bool:
        """Verifica permiso para gestionar (aprobar/rechazar) novedades"""
        can_approve = PermissionManager.has_action_permission('novedades', 'approve')
        can_reject = PermissionManager.has_action_permission('novedades', 'reject')
        can_manage = can_approve or can_reject
        logger.debug(f"Usuario puede gestionar novedades: {can_manage}")
        return can_manage
    
    @staticmethod
    def get_office_filter():
        """Obtiene filtro de oficina para consultas de base de datos"""
        perms = PermissionManager.get_user_permissions()
        office_filter = perms.get('office_filter', 'own')
        office_key = perms.get('office_key')
        
        if office_filter == 'all':
            logger.debug("Filtro de oficina: todas (sin filtro)")
            return None
        else:
            logger.debug(f"Filtro de oficina: {office_key}")
            return office_key
    
    @staticmethod
    def should_show_materiales_menu() -> bool:
        """Determina si debe mostrar el menú de materiales en la interfaz"""
        should_show = PermissionManager.has_action_permission('materiales', 'view')
        logger.debug(f"Mostrar menú de materiales: {should_show}")
        return should_show
    
    @staticmethod
    def get_visible_modules() -> list:
        """Obtiene lista de módulos visibles para el usuario actual"""
        perms = PermissionManager.get_user_permissions()
        all_modules = perms['role'].get('modules', [])
        
        visible_modules = []
        
        for module in all_modules:
            if module == 'materiales':
                if PermissionManager.has_action_permission('materiales', 'view'):
                    visible_modules.append(module)
            elif module == 'inventario_corporativo':
                if PermissionManager.has_action_permission('inventario_corporativo', 'view'):
                    visible_modules.append(module)
            else:
                visible_modules.append(module)
        
        logger.debug(f"Módulos visibles para usuario: {visible_modules}")
        return visible_modules

# Funciones de conveniencia para uso en templates y rutas
def can_access(module: str, action: Optional[str] = None) -> bool:
    """Verifica acceso a módulo o acción específica"""
    if action:
        return PermissionManager.has_action_permission(module, action)
    return PermissionManager.has_module_access(module)

def can_view_actions() -> bool:
    """Wrapper para verificación de visibilidad de acciones"""
    return PermissionManager.can_view_actions()

def can_manage_inventario_corporativo() -> bool:
    """Wrapper para gestión de inventario corporativo"""
    return PermissionManager.can_manage_inventario_corporativo()

def can_view_inventario_actions() -> bool:
    """Wrapper para visibilidad de acciones en inventario"""
    return PermissionManager.can_view_inventario_actions()

def can_create_novedad() -> bool:
    """Wrapper para creación de novedades"""
    return PermissionManager.can_create_novedad()

def can_manage_novedad() -> bool:
    """Wrapper para gestión de novedades"""
    return PermissionManager.can_manage_novedad()

def should_show_materiales_menu() -> bool:
    """Wrapper para visibilidad de menú de materiales"""
    return PermissionManager.should_show_materiales_menu()

def get_visible_modules():
    """Wrapper para obtención de módulos visibles"""
    return PermissionManager.get_visible_modules()

def get_accessible_modules():
    """Obtiene todos los módulos accesibles para el usuario"""
    perms = PermissionManager.get_user_permissions()
    modules = perms['role'].get('modules', [])
    logger.debug(f"Módulos accesibles para usuario: {modules}")
    return modules

def get_office_filter():
    """Wrapper para obtención de filtro de oficina"""
    return PermissionManager.get_office_filter()

def user_can_view_all() -> bool:
    """Verifica si el usuario puede ver registros de todas las oficinas"""
    perms = PermissionManager.get_user_permissions()
    can_view_all = perms.get('office_filter') == 'all'
    logger.debug(f"Usuario puede ver todas las oficinas: {can_view_all}")
    return can_view_all

def assign_role_by_office(office_name: str) -> str:
    """
    Asigna rol por defecto según la oficina del usuario
    
    Args:
        office_name: Nombre de la oficina
        
    Returns:
        str: Clave del rol asignado
    """
    office_roles = {
        'COQ': 'oficina_coq', 'CALI': 'oficina_cali',
        'MEDELLÍN': 'oficina_medellin', 'BUCARAMANGA': 'oficina_bucaramanga',
        'POLO CLUB': 'oficina_polo_club', 'NOGAL': 'oficina_nogal',
        'TUNJA': 'oficina_tunja', 'CARTAGENA': 'oficina_cartagena',
        'MORATO': 'oficina_morato', 'CEDRITOS': 'oficina_cedritos',
        'LOURDES': 'oficina_lourdes', 'PEREIRA': 'oficina_pereira',
        'NEIVA': 'oficina_neiva', 'KENNEDY': 'oficina_kennedy',
    }
    
    office_key = get_office_key(office_name)
    role = office_roles.get(office_key, 'oficina_regular')
    
    logger.debug(f"Rol asignado por oficina '{office_name}': {role}")
    return role