# utils/filters.py
from flask import session
from utils.permissions import PermissionManager, get_office_filter

def filtrar_por_oficina_usuario(datos, campo_oficina_id='oficina_id'):
    """
    Filtra datos según la oficina del usuario actual.
    """
    if 'usuario_id' not in session:
        print("🔍 DEBUG filtrar_por_oficina_usuario: Usuario no autenticado")
        return []
    
    # Usar el sistema de permisos actualizado
    rol_usuario = session.get('rol', '').lower()
    print(f"🔍 DEBUG filtrar_por_oficina_usuario: Rol usuario: {rol_usuario}")
    
    # Administradores y líder de inventario ven todo
    if rol_usuario in ['administrador', 'lider_inventario']:
        print("🔍 DEBUG filtrar_por_oficina_usuario: Usuario con acceso total")
        return datos
    
    # Para otros roles, filtrar por su oficina
    oficina_id_usuario = session.get('oficina_id')
    
    if not oficina_id_usuario:
        print("🔍 DEBUG filtrar_por_oficina_usuario: No hay ID de oficina en sesión")
        return []
    
    print(f"🔍 DEBUG filtrar_por_oficina_usuario: Oficina ID usuario: {oficina_id_usuario}")
    print(f"🔍 DEBUG filtrar_por_oficina_usuario: Total datos a filtrar: {len(datos)}")
    
    datos_filtrados = []
    for i, item in enumerate(datos):
        # Convertir ID a string para comparación segura
        item_oficina_id = str(item.get(campo_oficina_id, ''))
        usuario_oficina_id = str(oficina_id_usuario)
        
        if item_oficina_id == usuario_oficina_id:
            datos_filtrados.append(item)
            print(f"🔍 DEBUG filtrar_por_oficina_usuario: Item {i} coincide - Oficina: {item_oficina_id}")
        else:
            print(f"🔍 DEBUG filtrar_por_oficina_usuario: Item {i} NO coincide - Item Oficina: {item_oficina_id}, Usuario Oficina: {usuario_oficina_id}")
    
    print(f"🔍 DEBUG filtrar_por_oficina_usuario: Filtrados {len(datos_filtrados)} de {len(datos)} items")
    return datos_filtrados

def verificar_acceso_oficina(oficina_id):
    """
    Verifica si el usuario actual tiene acceso a una oficina específica.
    """
    if 'usuario_id' not in session:
        return False
    
    rol_usuario = session.get('rol', '').lower()
    
    # Administradores y líder de inventario acceden a todo
    if rol_usuario in ['administrador', 'lider_inventario']:
        return True
    
    # Para otros roles, verificar si es su oficina
    oficina_id_usuario = session.get('oficina_id')
    
    return str(oficina_id) == str(oficina_id_usuario)