#config/permissions.py

"""
Sistema centralizado de permisos basado en roles y oficinas config/permissions.py
"""

ROLE_PERMISSIONS = {
    'administrador': {
        'modules': ['dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material', 'reportes'],  
        'actions': {
            'materiales': ['view', 'create', 'edit', 'delete'],
            'solicitudes': ['view', 'create', 'approve', 'reject', 'partial_approve'],
            'oficinas': ['view', 'manage'],
            'aprobadores': ['view', 'manage'],
            'reportes': ['view_all'],  
            'inventario_corporativo': ['view', 'create', 'edit', 'delete', 'assign', 'manage_sedes', 'manage_oficinas'],
            'prestamos': ['view', 'create', 'approve', 'reject', 'return', 'manage_materials'],
            'novedades': ['create', 'view', 'approve', 'reject']
        },
        'office_filter': 'all'
    },

    'lider_inventario': {
        'modules': ['dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material', 'reportes'],  
        'actions': {
            'materiales': ['view', 'create', 'edit', 'delete'],
            'solicitudes': ['view', 'create', 'approve', 'reject', 'partial_approve'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],  
            'inventario_corporativo': ['view', 'create', 'edit', 'delete', 'assign', 'manage_sedes', 'manage_oficinas'],
            'prestamos': ['view', 'create', 'approve', 'reject', 'return', 'manage_materials'],         
            'novedades': ['create', 'view', 'approve', 'reject']
        },
        'office_filter': 'all'
    },
    
    'aprobador': {
        'modules': ['dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material', 'reportes'],
        'actions': {
            'materiales': ['view'],
            'solicitudes': ['view', 'approve', 'reject', 'partial_approve'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],
            'inventario_corporativo': ['view'],
            'prestamos': ['view', 'create', 'approve', 'reject', 'return'],
            'novedades': ['create', 'view', 'approve', 'reject']
        },
        'office_filter': 'all'
    },

     
    'tesoreria': {
        'modules': ['dashboard', 'material_pop', 'inventario_corporativo', 'prestamo_material', 'reportes'],
        'actions': {
            'materiales': [],  
            'solicitudes': ['view'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'reportes': ['view_all'],  
            'inventario_corporativo': ['view'],  
            'prestamos': ['view'],  
            'novedades': ['view']  
        },
        'office_filter': 'all'  
    },

    'oficina_coq': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [], 
            'solicitudes': ['view', 'create'],   
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'COQ' 
    },

    'oficina_cali': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],   
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'CALI'
    },

    'oficina_pereira': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'PEREIRA'
    },

    'oficina_neiva': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'NEIVA'
    },

    'oficina_kennedy': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'KENNEDY'
    },

    'oficina_bucaramanga': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'BUCARAMANGA'
    },

    'oficina_polo_club': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'POLO CLUB'
    },

    'oficina_nogal': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'NOGAL'
    },

    'oficina_tunja': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'TUNJA'
    },

    'oficina_cartagena': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'CARTAGENA'
    },

    'oficina_morato': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'MORATO'
    },

    'oficina_medellin': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'MEDELLÍN'
    },

    'oficina_cedritos': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],   
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'CEDRITOS'
    },

    'oficina_lourdes': {
        'modules': ['dashboard', 'material_pop', 'prestamo_material', 'reportes', 'oficinas', 'solicitudes'],
        'actions': {
            'materiales': [],
            'solicitudes': ['view', 'create'],  
            'oficinas': ['view'],
            'aprobadores': ['view'],
            'prestamos': ['view_own', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'LOURDES'
    },

    'oficina_regular': {
        'modules': ['dashboard', 'reportes', 'solicitudes'],   
        'actions': {
            'solicitudes': ['view', 'create'],
            'reportes': ['view_own'],
            'novedades': ['create']
        },
        'office_filter': 'own'
    }
}

OFFICE_MAPPING = {
    'COQ': 'COQ',
    'POLO CLUB': 'POLO CLUB',
    'NOGAL': 'NOGAL',
    'TUNJA': 'TUNJA',
    'CARTAGENA': 'CARTAGENA',
    'MORATO': 'MORATO',
    'MEDELLÍN': 'MEDELLÍN',
    'CEDRITOS': 'CEDRITOS',
    'LOURDES': 'LOURDES',
    'CALI': 'CALI',
    'PEREIRA': 'PEREIRA',
    'NEIVA': 'NEIVA',
    'KENNEDY': 'KENNEDY',
    'BUCARAMANGA': 'BUCARAMANGA'
}

def get_office_key(office_name: str) -> str:
    """
    Normaliza el nombre de oficina y lo mapea si existe en OFFICE_MAPPING.
    """
    key = office_name.upper().strip()
    return OFFICE_MAPPING.get(key, key)