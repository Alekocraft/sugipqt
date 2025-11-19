# utils/permissions.py
"""
Sistema de verificación de permisos
"""
from flask import session
from typing import Optional
from config.permissions import ROLE_PERMISSIONS, OFFICE_MAPPING, get_office_key


class PermissionManager:
    @staticmethod
    def get_user_permissions():
        """Obtiene todos los permisos del usuario actual"""
        role = session.get('rol', '').lower()
        office_name = session.get('oficina_nombre', '')
        office_key = get_office_key(office_name)

        # Permisos base del rol
        role_perms = ROLE_PERMISSIONS.get(role, {})

        return {
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
        role = session.get('rol', '').lower()
        roles_con_acciones = {'administrador', 'aprobador'}
        return role in roles_con_acciones

    # ⬇️ ESTA ES LA PARTE QUE QUERÍAS CAMBIAR (NUEVA LÓGICA)
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
