# utils/permissions.py
"""
Sistema de verificación de permisos
"""
from flask import session
from typing import Optional
from config.permissions import ROLE_PERMISSIONS, OFFICE_MAPPING, get_office_key


def normalize_role_key(role_raw: str) -> str:
    """
    Normaliza el string de rol que viene de sesión para que coincida
    con las llaves definidas en ROLE_PERMISSIONS.

    Ejemplos:
    - "Administrador"           -> "administrador"
    - "Líder Inventario"        -> "lider_inventario"
    - "OFICINA COQ"             -> "oficina_coq"
    - "Tesoreria"               -> "tesoreria"  # NUEVO ROL
    """
    if not role_raw:
        return ''

    r = role_raw.strip().lower()

    # Quitar tildes básicas
    reemplazos = {
        'á': 'a',
        'é': 'e',
        'í': 'i',
        'ó': 'o',
        'ú': 'u',
        'ü': 'u',
        'ñ': 'n'
    }
    for k, v in reemplazos.items():
        r = r.replace(k, v)

    # Reemplazar espacios por guiones bajos
    r_norm = r.replace(' ', '_')

    # 1) Intento directo
    if r_norm in ROLE_PERMISSIONS:
        return r_norm

    # 2) Comparar ignorando guiones bajos
    r_flat = r_norm.replace('_', '')
    for key in ROLE_PERMISSIONS.keys():
        k_flat = key.replace('_', '')
        if r_flat == k_flat:
            return key

    # 3) Reglas simples por contenido (por si llega "administrador sistema", etc.)
    if 'admin' in r_norm:
        return 'administrador'
    if 'lider' in r_norm and 'invent' in r_norm:
        return 'lider_inventario'
    if 'tesorer' in r_norm:  # NUEVO: para detectar "tesorería"
        return 'tesoreria'
    if 'coq' in r_norm:
        return 'oficina_coq'

    # Último recurso: devolver lo normalizado (aunque no tenga permisos definidos)
    return r_norm


class PermissionManager:
    @staticmethod
    def get_user_permissions():
        """Obtiene todos los permisos del usuario actual"""
        role_raw = session.get('rol', '')
        role_key = normalize_role_key(role_raw)

        office_name = session.get('oficina_nombre', '')
        office_key = get_office_key(office_name)

        role_perms = ROLE_PERMISSIONS.get(role_key, {})

        return {
            'role_key': role_key,
            'role': role_perms,
            'office_key': office_key,
            'office_filter': role_perms.get('office_filter', 'own'),
        }

    @staticmethod
    def has_module_access(module_name: str) -> bool:
        """Verifica acceso a un módulo completo"""
        perms = PermissionManager.get_user_permissions()
        role_modules = perms['role'].get('modules', [])
        return module_name in role_modules

    @staticmethod
    def has_action_permission(module: str, action: str) -> bool:
        """Verifica permiso para una acción específica en un módulo"""
        perms = PermissionManager.get_user_permissions()
        role_actions = perms['role'].get('actions', {}).get(module, [])
        return action in role_actions

    @staticmethod
    def can_view_actions() -> bool:
        """Verifica si puede ver columnas de acciones en préstamos"""
        role_key = PermissionManager.get_user_permissions().get('role_key', '')
        roles_con_acciones = {'administrador', 'aprobador', 'lider_inventario', 'tesoreria'}  # Añadido tesoreria
        return role_key in roles_con_acciones

    @staticmethod
    def can_manage_inventario_corporativo() -> bool:
        """Verifica si puede gestionar inventario corporativo usando acciones del rol"""
        return (
            PermissionManager.has_action_permission('inventario_corporativo', 'create') or
            PermissionManager.has_action_permission('inventario_corporativo', 'edit') or
            PermissionManager.has_action_permission('inventario_corporativo', 'delete')
        )

    @staticmethod
    def can_view_inventario_actions() -> bool:
        """Verifica si puede ver acciones en inventario corporativo"""
        return PermissionManager.can_manage_inventario_corporativo()

    # ⬇️ MÉTODOS PARA NOVEDADES
    @staticmethod
    def can_create_novedad() -> bool:
        """Verifica si puede crear novedades"""
        return PermissionManager.has_action_permission('novedades', 'create')

    @staticmethod
    def can_manage_novedad() -> bool:
        """Verifica si puede gestionar (aprobar/rechazar) novedades"""
        return (PermissionManager.has_action_permission('novedades', 'approve') or 
                PermissionManager.has_action_permission('novedades', 'reject'))

    @staticmethod
    def get_office_filter():
        """Obtiene el filtro de oficina para consultas"""
        perms = PermissionManager.get_user_permissions()
        office_filter = perms.get('office_filter', 'own')
        office_key = perms.get('office_key')

        if office_filter == 'all':
            return None
        else:
            return office_key

    @staticmethod
    def should_show_materiales_menu() -> bool:
        """Verifica si debe mostrar el menú/opción de materiales en la UI"""
        return PermissionManager.has_action_permission('materiales', 'view')
    
    @staticmethod
    def get_visible_modules() -> list:
        """Obtiene solo los módulos visibles para el usuario actual"""
        perms = PermissionManager.get_user_permissions()
        all_modules = perms['role'].get('modules', [])
        
        # Filtrar módulos según permisos específicos
        visible_modules = []
        
        for module in all_modules:
            if module == 'materiales':
                # Solo mostrar materiales si tiene permiso de view
                if PermissionManager.has_action_permission('materiales', 'view'):
                    visible_modules.append(module)
            elif module == 'inventario_corporativo':
                # Solo mostrar inventario corporativo si tiene permiso de view
                if PermissionManager.has_action_permission('inventario_corporativo', 'view'):
                    visible_modules.append(module)
            else:
                # Para otros módulos, mostrar siempre
                visible_modules.append(module)
        
        return visible_modules


# Funciones de conveniencia
def can_access(module: str, action: Optional[str] = None) -> bool:
    if action:
        return PermissionManager.has_action_permission(module, action)
    return PermissionManager.has_module_access(module)


def can_view_actions() -> bool:
    return PermissionManager.can_view_actions()


def can_manage_inventario_corporativo() -> bool:
    return PermissionManager.can_manage_inventario_corporativo()


def can_view_inventario_actions() -> bool:
    return PermissionManager.can_view_inventario_actions()


# ⬇️ NUEVAS FUNCIONES DE CONVENIENCIA PARA NOVEDADES
def can_create_novedad() -> bool:
    return PermissionManager.can_create_novedad()


def can_manage_novedad() -> bool:
    return PermissionManager.can_manage_novedad()


# ⬇️ FUNCIONES PARA CONTROLAR VISIBILIDAD EN LA UI
def should_show_materiales_menu() -> bool:
    return PermissionManager.should_show_materiales_menu()

def get_visible_modules():
    return PermissionManager.get_visible_modules()


def get_accessible_modules():
    perms = PermissionManager.get_user_permissions()
    return perms['role'].get('modules', [])


def get_office_filter():
    return PermissionManager.get_office_filter()


def user_can_view_all() -> bool:
    perms = PermissionManager.get_user_permissions()
    return perms.get('office_filter') == 'all'


def assign_role_by_office(office_name: str) -> str:
    """Asigna un rol por defecto según la oficina"""
    office_roles = {
        'COQ': 'oficina_coq',
        'CALI': 'oficina_cali',
        'MEDELLÍN': 'oficina_medellin',
        'BUCARAMANGA': 'oficina_bucaramanga',
        'POLO CLUB': 'oficina_polo_club',
        'NOGAL': 'oficina_nogal',
        'TUNJA': 'oficina_tunja',
        'CARTAGENA': 'oficina_cartagena',
        'MORATO': 'oficina_morato',
        'CEDRITOS': 'oficina_cedritos',
        'LOURDES': 'oficina_lourdes',
        'PEREIRA': 'oficina_pereira',
        'NEIVA': 'oficina_neiva',
        'KENNEDY': 'oficina_kennedy',
    }

    office_key = get_office_key(office_name)
    return office_roles.get(office_key, 'oficina_regular')