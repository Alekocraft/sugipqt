"""
BLUEPRINT DE REPORTES - Versión mejorada con filtros avanzados
Integra la funcionalidad original con la estructura actual del sistema
"""

from flask import Blueprint, render_template, request, redirect, session, flash, url_for, jsonify, send_file
from io import BytesIO
import pandas as pd
from datetime import datetime, timedelta
from models.solicitudes_model import SolicitudModel
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from models.prestamos_model import PrestamosModel
from models.novedades_model import NovedadModel
from utils.permissions import can_access, get_office_filter
from utils.filters import filtrar_por_oficina_usuario

# Crear blueprint de reportes
reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

# Helpers de autenticación locales
def _require_login():
    return 'usuario_id' in session

# Helper para aplicar filtros según permisos
def aplicar_filtro_permisos(datos, campo_oficina='oficina_id'):
    """
    Aplica filtro de oficina según permisos del usuario
    """
    if not datos:
        return []
    
    # Si puede ver todo (administrador/lider_inventario), no filtra
    if can_access('materiales', 'view') and can_access('solicitudes', 'view'):
        return datos
    
    # Para otros roles, filtrar por su oficina
    oficina_usuario = session.get('oficina_id')
    if not oficina_usuario:
        return []
    
    # Filtrar datos por oficina
    datos_filtrados = []
    for item in datos:
        if isinstance(item, dict):
            if item.get(campo_oficina) == oficina_usuario:
                datos_filtrados.append(item)
        else:
            # Si es objeto, verificar atributo
            if hasattr(item, campo_oficina):
                if getattr(item, campo_oficina) == oficina_usuario:
                    datos_filtrados.append(item)
    
    return datos_filtrados

# ============================================================================
# RUTAS DE REPORTES
# ============================================================================

# Página principal de reportes
@reportes_bp.route('/')
def reportes_index():
    """Página principal de reportes"""
    if not _require_login():
        return redirect('/login')
    
    return render_template('reportes/index.html')

# ----------------------------------------------------------------------------
# REPORTE DE SOLICITUDES MEJORADO
# ----------------------------------------------------------------------------
@reportes_bp.route('/solicitudes')
def reporte_solicitudes():
    """Reporte de solicitudes con filtros avanzados"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('solicitudes', 'view'):
        flash('No tiene permisos para ver reportes de solicitudes', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener parámetros de filtro
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '').strip()
        filtro_solicitante = request.args.get('solicitante', '').strip()
        filtro_fecha_inicio = request.args.get('fecha_inicio', '')
        filtro_fecha_fin = request.args.get('fecha_fin', '')
        
        # Obtener todas las solicitudes con detalle
        solicitudes = SolicitudModel.obtener_todas_con_detalle() or []
        
        # Aplicar filtro según permisos del usuario
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            solicitudes = filtrar_por_oficina_usuario(solicitudes, 'oficina_id')
        
        # Aplicar filtros adicionales
        solicitudes_filtradas = []
        for solicitud in solicitudes:
            # Filtro por estado
            if filtro_estado != 'todos':
                estado_solicitud = solicitud.get('estado', '').lower()
                estado_filtro = filtro_estado.lower()
                if estado_filtro not in estado_solicitud:
                    continue
            
            # Filtro por oficina
            if filtro_oficina != 'todas':
                oficina_solicitud = solicitud.get('oficina_nombre', '')
                if oficina_solicitud != filtro_oficina:
                    continue
            
            # Filtro por material (búsqueda por nombre)
            if filtro_material:
                material_nombre = solicitud.get('material_nombre', '').lower()
                if filtro_material.lower() not in material_nombre:
                    continue
            
            # Filtro por solicitante
            if filtro_solicitante:
                solicitante = solicitud.get('usuario_solicitante', '').lower()
                if filtro_solicitante.lower() not in solicitante:
                    continue
            
            # Filtro por fecha
            if filtro_fecha_inicio:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        fecha_inicio = datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d').date()
                        if fecha_solicitud < fecha_inicio:
                            continue
                except:
                    continue
            
            if filtro_fecha_fin:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        fecha_fin = datetime.strptime(filtro_fecha_fin, '%Y-%m-%d').date()
                        if fecha_solicitud > fecha_fin:
                            continue
                except:
                    continue
            
            solicitudes_filtradas.append(solicitud)
        
        # Calcular estadísticas
        estados = {
            'pendiente': 0, 
            'aprobada': 0, 
            'rechazada': 0, 
            'parcial': 0, 
            'completada': 0, 
            'devuelta': 0
        }
        
        total_cantidad_solicitada = 0
        total_cantidad_entregada = 0
        
        for solicitud in solicitudes_filtradas:
            estado = solicitud.get('estado', 'pendiente').lower()
            if 'pendiente' in estado:
                estados['pendiente'] += 1
            elif 'aprobada' in estado or 'aprobado' in estado:
                estados['aprobada'] += 1
            elif 'rechazada' in estado or 'rechazado' in estado:
                estados['rechazada'] += 1
            elif 'parcial' in estado:
                estados['parcial'] += 1
            elif 'completada' in estado or 'completado' in estado:
                estados['completada'] += 1
            elif 'devuelta' in estado or 'devuelto' in estado:
                estados['devuelta'] += 1
            
            total_cantidad_solicitada += solicitud.get('cantidad_solicitada', 0)
            total_cantidad_entregada += solicitud.get('cantidad_entregada', 0)
        
        # Obtener listas para filtros
        oficinas = OficinaModel.obtener_todas() or []
        materiales = MaterialModel.obtener_todos() or []
        nombres_materiales = list(set([m.get('nombre', '') for m in materiales]))
        
        # Calcular tasa de aprobación
        total_solicitudes = len(solicitudes_filtradas)
        tasa_aprobacion = 0
        if total_solicitudes > 0:
            aprobadas_totales = estados['aprobada'] + estados['completada'] + estados['parcial']
            tasa_aprobacion = round((aprobadas_totales / total_solicitudes) * 100, 1)
        
        return render_template('reportes/solicitudes.html',
                             solicitudes=solicitudes_filtradas,
                             filtro_estado=filtro_estado,
                             filtro_oficina=filtro_oficina,
                             filtro_material=filtro_material,
                             filtro_solicitante=filtro_solicitante,
                             filtro_fecha_inicio=filtro_fecha_inicio,
                             filtro_fecha_fin=filtro_fecha_fin,
                             oficinas=oficinas,
                             nombres_materiales=nombres_materiales,
                             total_solicitudes=total_solicitudes,
                             pendientes=estados['pendiente'],
                             aprobadas=estados['aprobada'],
                             rechazadas=estados['rechazada'],
                             parciales=estados['parcial'],
                             completadas=estados['completada'],
                             devueltas=estados['devuelta'],
                             total_cantidad_solicitada=total_cantidad_solicitada,
                             total_cantidad_entregada=total_cantidad_entregada,
                             tasa_aprobacion=tasa_aprobacion)
                             
    except Exception as e:
        print(f"❌ Error generando reporte de solicitudes: {e}")
        flash('Error al generar el reporte de solicitudes', 'danger')
        return render_template('reportes/solicitudes.html',
                             solicitudes=[],
                             oficinas=[],
                             nombres_materiales=[],
                             total_solicitudes=0,
                             pendientes=0,
                             aprobadas=0,
                             rechazadas=0,
                             parciales=0,
                             completadas=0,
                             devueltas=0)

# ----------------------------------------------------------------------------
# EXPORTACIÓN DE SOLICITUDES A EXCEL
# ----------------------------------------------------------------------------
@reportes_bp.route('/solicitudes/exportar/excel')
def exportar_solicitudes_excel():
    """Exporta las solicitudes filtradas a Excel"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('solicitudes', 'view'):
        flash('No tiene permisos para exportar reportes de solicitudes', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener mismos filtros que en la vista
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        filtro_material = request.args.get('material', '').strip()
        filtro_solicitante = request.args.get('solicitante', '').strip()
        filtro_fecha_inicio = request.args.get('fecha_inicio', '')
        filtro_fecha_fin = request.args.get('fecha_fin', '')
        
        # Obtener datos
        solicitudes = SolicitudModel.obtener_todas_con_detalle() or []
        
        # Aplicar filtro según permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            solicitudes = filtrar_por_oficina_usuario(solicitudes, 'oficina_id')
        
        # Aplicar filtros adicionales
        solicitudes_filtradas = []
        for solicitud in solicitudes:
            # Filtro por estado
            if filtro_estado != 'todos':
                estado_solicitud = solicitud.get('estado', '').lower()
                estado_filtro = filtro_estado.lower()
                if estado_filtro not in estado_solicitud:
                    continue
            
            # Filtro por oficina
            if filtro_oficina != 'todas':
                oficina_solicitud = solicitud.get('oficina_nombre', '')
                if oficina_solicitud != filtro_oficina:
                    continue
            
            # Filtro por material
            if filtro_material:
                material_nombre = solicitud.get('material_nombre', '').lower()
                if filtro_material.lower() not in material_nombre:
                    continue
            
            # Filtro por solicitante
            if filtro_solicitante:
                solicitante = solicitud.get('usuario_solicitante', '').lower()
                if filtro_solicitante.lower() not in solicitante:
                    continue
            
            # Filtro por fecha
            if filtro_fecha_inicio:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        fecha_inicio = datetime.strptime(filtro_fecha_inicio, '%Y-%m-%d').date()
                        if fecha_solicitud < fecha_inicio:
                            continue
                except:
                    continue
            
            if filtro_fecha_fin:
                try:
                    fecha_solicitud_str = solicitud.get('fecha_solicitud', '')
                    if fecha_solicitud_str:
                        fecha_solicitud = datetime.strptime(str(fecha_solicitud_str).split()[0], '%Y-%m-%d').date()
                        fecha_fin = datetime.strptime(filtro_fecha_fin, '%Y-%m-%d').date()
                        if fecha_solicitud > fecha_fin:
                            continue
                except:
                    continue
            
            solicitudes_filtradas.append(solicitud)
        
        # Preparar datos para Excel
        data = []
        for sol in solicitudes_filtradas:
            data.append({
                'ID': sol.get('id', ''),
                'Material': sol.get('material_nombre', ''),
                'Cantidad Solicitada': sol.get('cantidad_solicitada', 0),
                'Cantidad Entregada': sol.get('cantidad_entregada', 0),
                'Solicitante': sol.get('usuario_solicitante', ''),
                'Oficina': sol.get('oficina_nombre', ''),
                'Estado': sol.get('estado', ''),
                'Fecha Solicitud': sol.get('fecha_solicitud', ''),
                'Fecha Aprobación': sol.get('fecha_aprobacion', ''),
                'Observaciones': sol.get('observacion', ''),
                'Usuario Aprobador': sol.get('usuario_aprobador', ''),
                'Stock Actual Material': sol.get('cantidad_disponible', '')
            })

        df = pd.DataFrame(data)
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Solicitudes', index=False)
            
            # Ajustar ancho de columnas
            worksheet = writer.sheets['Solicitudes']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
            
            # Agregar hoja de resumen
            summary_data = {
                'Resumen': [
                    f'Total Solicitudes: {len(solicitudes_filtradas)}',
                    f'Filtro Estado: {filtro_estado if filtro_estado != "todos" else "Todos"}',
                    f'Filtro Oficina: {filtro_oficina if filtro_oficina != "todas" else "Todas"}',
                    f'Filtro Material: {filtro_material if filtro_material else "Ninguno"}',
                    f'Fecha Generación: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, sheet_name='Resumen', index=False)
        
        output.seek(0)

        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'reporte_solicitudes_{fecha_actual}.xlsx'

        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=filename)
                         
    except Exception as e:
        print(f"❌ Error exportando solicitudes a Excel: {e}")
        flash('Error al exportar el reporte de solicitudes a Excel', 'danger')
        return redirect(url_for('reportes.reporte_solicitudes'))

# ============================================================================
# OTROS REPORTES
# ============================================================================

@reportes_bp.route('/materiales')
def reporte_materiales():
    """Reporte de materiales"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver reportes de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro según permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')
        
        # Calcular estadísticas
        valor_total_inventario = sum(m.get('valor_total', 0) or 0 for m in materiales)
        
        # Obtener estadísticas de solicitudes
        stats_dict = {}
        for mat in materiales:
            stats = SolicitudModel.obtener_estadisticas_por_material(mat['id'])
            stats_dict[mat['id']] = stats
        
        # Calcular totales
        total_solicitudes = sum(stats[0] for stats in stats_dict.values() if stats)
        total_entregado = sum(stats[3] for stats in stats_dict.values() if stats)
        
        return render_template('reportes/materiales.html',
                             materiales=materiales,
                             valor_total_inventario=valor_total_inventario,
                             stats_dict=stats_dict,
                             total_solicitudes=total_solicitudes,
                             total_entregado=total_entregado)
    except Exception as e:
        print(f"❌ Error generando reporte de materiales: {e}")
        flash('Error al generar el reporte de materiales', 'danger')
        return render_template('reportes/materiales.html',
                             materiales=[],
                             valor_total_inventario=0,
                             stats_dict={},
                             total_solicitudes=0,
                             total_entregado=0)

@reportes_bp.route('/inventario')
def reporte_inventario():
    """Reporte de inventario corporativo"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para ver reportes de inventario', 'warning')
        return redirect('/reportes')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro según permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')
        
        # Calcular estadísticas
        valor_total = 0
        for material in materiales:
            valor_total_material = material.get('valor_total', 0)
            try:
                valor_total += float(valor_total_material)
            except:
                valor_total += 0
        
        valor_promedio = valor_total / len(materiales) if materiales else 0
        
        # Agrupar por oficina
        ubicaciones_dict = {}
        for material in materiales:
            ubicacion = material.get('oficina_nombre', 'Sin oficina')
            if ubicacion not in ubicaciones_dict:
                ubicaciones_dict[ubicacion] = {'cantidad': 0, 'nombre': ubicacion}
            ubicaciones_dict[ubicacion]['cantidad'] += 1
        
        categorias = []
        ubicaciones = list(ubicaciones_dict.values())
        
        # Formatear productos
        productos = []
        for material in materiales:
            productos.append({
                'id': material.get('id'),
                'nombre': material.get('nombre', 'Sin nombre'),
                'valor_unitario': float(material.get('valor_unitario', 0)),
                'cantidad': int(material.get('cantidad', 0)),
                'valor_total': float(material.get('valor_total', 0)),
                'oficina_nombre': material.get('oficina_nombre', 'Sin oficina'),
                'fecha_creacion': material.get('fecha_creacion')
            })
        
        return render_template('reportes/inventario.html',
                            productos=productos,
                            total_productos=len(materiales),
                            valor_total_inventario=valor_total,
                            valor_promedio=valor_promedio,
                            categorias=categorias,
                            ubicaciones=ubicaciones)
        
    except Exception as e:
        print(f"❌ Error en reporte_inventario: {e}")
        flash('Error al generar el reporte de inventario', 'danger')
        return render_template('reportes/inventario.html',
                            productos=[],
                            total_productos=0,
                            valor_total_inventario=0,
                            valor_promedio=0,
                            categorias=[],
                            ubicaciones=[])

@reportes_bp.route('/novedades')
def reporte_novedades():
    """Reporte de novedades"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('novedades', 'view'):
        flash('No tiene permisos para ver reportes de novedades', 'warning')
        return redirect('/reportes')
    
    try:
        novedades = NovedadModel.obtener_todas() or []
        
        # Aplicar filtro según permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            oficina_usuario = session.get('oficina_id')
            novedades = [n for n in novedades if n.get('oficina_id') == oficina_usuario]
        
        # Calcular estadísticas
        total_novedades = len(novedades)
        
        # Contar por estado
        estados = {'pendiente': 0, 'en_proceso': 0, 'resuelto': 0}
        for novedad in novedades:
            estado = novedad.get('estado', 'pendiente')
            if estado == 'pendiente':
                estados['pendiente'] += 1
            elif estado == 'en_proceso':
                estados['en_proceso'] += 1
            elif estado == 'resuelto':
                estados['resuelto'] += 1
        
        # Contar por prioridad
        prioridades = {'alta': 0, 'media': 0, 'baja': 0}
        for novedad in novedades:
            prioridad = novedad.get('prioridad', 'media')
            if prioridad == 'alta':
                prioridades['alta'] += 1
            elif prioridad == 'media':
                prioridades['media'] += 1
            elif prioridad == 'baja':
                prioridades['baja'] += 1
        
        # Tipos de novedad únicos
        tipos_novedad = list(set([n.get('tipo', 'General') for n in novedades]))
        
        # Reportantes únicos
        reportantes = list(set([n.get('usuario_registra', 'Desconocido') for n in novedades]))
        
        # Novedades recientes
        novedades_recientes = sorted(novedades, 
                                   key=lambda x: x.get('fecha_reporte', datetime.now()), 
                                   reverse=True)[:6]
        
        return render_template('reportes/novedades.html',
                             novedades=novedades,
                             total_novedades=total_novedades,
                             pendientes=estados['pendiente'],
                             en_proceso=estados['en_proceso'],
                             resueltas=estados['resuelto'],
                             prioridad_alta=prioridades['alta'],
                             prioridad_media=prioridades['media'],
                             prioridad_baja=prioridades['baja'],
                             tipos_novedad=tipos_novedad,
                             reportantes=reportantes,
                             novedades_recientes=novedades_recientes)
    except Exception as e:
        print(f"❌ Error en reporte_novedades: {e}")
        flash('Error al generar el reporte de novedades', 'danger')
        return render_template('reportes/novedades.html',
                             novedades=[],
                             total_novedades=0,
                             pendientes=0,
                             en_proceso=0,
                             resueltas=0,
                             prioridad_alta=0,
                             prioridad_media=0,
                             prioridad_baja=0,
                             tipos_novedad=[],
                             reportantes=[],
                             novedades_recientes=[])

@reportes_bp.route('/oficinas')
def reporte_oficinas():
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('oficinas', 'view'):
        flash('No tiene permisos para ver reportes de oficinas', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener todas las oficinas
        oficinas = OficinaModel.obtener_todas() or []
        
        print(f"🔍 DEBUG reporte_oficinas: Total oficinas obtenidas: {len(oficinas)}")
        
        # FILTRO DE PERMISOS CORREGIDO
        rol_usuario = session.get('rol', '').lower()
        oficina_id_usuario = session.get('oficina_id')
        
        print(f"🔍 Permisos usuario - Rol: {rol_usuario}, Oficina ID: {oficina_id_usuario}")
        
        # SOLO filtrar si es rol específico de oficina
        if rol_usuario.startswith('oficina_'):
            print(f"🔍 Filtrando solo oficina del usuario: ID {oficina_id_usuario}")
            oficinas_filtradas = []
            for o in oficinas:
                if o.get('id') == oficina_id_usuario:
                    oficinas_filtradas.append(o)
            oficinas = oficinas_filtradas
        
        print(f"🔍 Oficinas después de filtrar: {len(oficinas)}")
        
        # Obtener información de inventario corporativo para cada oficina
        from database import get_database_connection
        
        conn = None
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            for oficina in oficinas:
                oficina_id = oficina.get('id')
                oficina_nombre = oficina.get('nombre', '')
                
                print(f"🔍 Procesando oficina: {oficina_nombre} (ID: {oficina_id})")
                
                # --- INVENTARIO CORPORATIVO: Productos corporativos asignados a esta oficina ---
                try:
                    # CONSULTA ACTUALIZADA: Productos corporativos desde AsignacionesCorporativasHistorial con CodigoUnico
                    cursor.execute("""
                        SELECT DISTINCT
                            pc.ProductoId,
                            pc.CodigoUnico,  -- NUEVO: Código único del producto
                            pc.NombreProducto,
                            pc.Descripcion,
                            pc.ValorUnitario,
                            pc.CantidadMinima,
                            pc.Activo,
                            pc.FechaCreacion,
                            pc.UsuarioCreador,
                            c.NombreCategoria,
                            -- Obtener cantidad total asignada a esta oficina
                            (
                                SELECT SUM(ach.Cantidad) 
                                FROM AsignacionesCorporativasHistorial ach 
                                WHERE ach.ProductoId = pc.ProductoId 
                                AND ach.OficinaId = ?
                                AND ach.Accion LIKE '%ASIGNAR%'
                            ) as CantidadAsignada
                        FROM ProductosCorporativos pc
                        LEFT JOIN CategoriasProductos c ON pc.CategoriaId = c.CategoriaId
                        WHERE EXISTS (
                            SELECT 1 
                            FROM AsignacionesCorporativasHistorial ach 
                            WHERE ach.ProductoId = pc.ProductoId 
                            AND ach.OficinaId = ?
                        )
                        AND pc.Activo = 1
                        ORDER BY pc.NombreProducto
                    """, (oficina_id, oficina_id))
                    
                    productos_oficina = []
                    for row in cursor.fetchall():
                        producto_id = row[0]
                        codigo_unico = row[1]  # NUEVO: Obtener código único
                        cantidad_asignada = row[10] or 0  # Cambió de índice por agregar CodigoUnico
                        valor_unitario = float(row[4] or 0)
                        valor_total = cantidad_asignada * valor_unitario
                        
                        producto = {
                            'id': producto_id,
                            'codigo_unico': codigo_unico,  # NUEVO: Incluir código único
                            'nombre': row[2],
                            'descripcion': row[3] or '',
                            'cantidad': cantidad_asignada,
                            'valor_unitario': valor_unitario,
                            'valor_total': valor_total,
                            'stock_minimo': row[5] or 0,
                            'categoria': row[9] or 'General',  # Cambió de índice
                            'activo': bool(row[6]),
                            'usuario_creador': row[8] if row[8] else '',  # Cambió de índice
                            'fecha_creacion': row[7] if row[7] else None,  # Cambió de índice
                            'tipo': 'corporativo'
                        }
                        productos_oficina.append(producto)
                    
                    oficina['materiales'] = productos_oficina
                    oficina['cantidad_materiales'] = len(productos_oficina)
                    
                    # Calcular valor total del inventario corporativo para esta oficina
                    valor_total_oficina = sum(p.get('valor_total', 0) for p in productos_oficina)
                    oficina['valor_total_inventario'] = valor_total_oficina
                    
                    print(f"✅ Inventario corporativo para {oficina_nombre}: {len(productos_oficina)} productos")
                    
                except Exception as mat_error:
                    print(f"⚠️ Error obteniendo inventario corporativo para oficina {oficina_id}: {mat_error}")
                    oficina['materiales'] = []
                    oficina['cantidad_materiales'] = 0
                    oficina['valor_total_inventario'] = 0
                
                # --- Solicitudes de esta oficina (últimas 5) ---
                try:
                    cursor.execute("""
                        SELECT TOP 5
                            sm.SolicitudId,
                            sm.CantidadSolicitada,
                            sm.CantidadEntregada,
                            sm.FechaSolicitud,
                            es.NombreEstado as Estado,
                            m.NombreElemento as MaterialNombre,
                            sm.UsuarioSolicitante,
                            sm.Observacion
                        FROM SolicitudesMaterial sm
                        INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                        INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                        WHERE sm.OficinaSolicitanteId = ?
                        ORDER BY sm.FechaSolicitud DESC
                    """, (oficina_id,))
                    
                    solicitudes_oficina = []
                    for row in cursor.fetchall():
                        solicitud = {
                            'id': row[0],
                            'cantidad_solicitada': row[1],
                            'cantidad_entregada': row[2],
                            'fecha_solicitud': row[3],
                            'estado': row[4],
                            'material_nombre': row[5],
                            'usuario_solicitante': row[6],
                            'observacion': row[7] or ''
                        }
                        solicitudes_oficina.append(solicitud)
                    
                    oficina['solicitudes'] = solicitudes_oficina
                    oficina['cantidad_solicitudes'] = len(solicitudes_oficina)
                    
                except Exception as sol_error:
                    print(f"⚠️ Error obteniendo solicitudes para oficina {oficina_id}: {sol_error}")
                    oficina['solicitudes'] = []
                    oficina['cantidad_solicitudes'] = 0
                
                # --- Préstamos de esta oficina ---
                try:
                    cursor.execute("""
                        SELECT COUNT(*) 
                        FROM PrestamosMaterial 
                        WHERE OficinaId = ? AND Activo = 1
                    """, (oficina_id,))
                    
                    result = cursor.fetchone()
                    oficina['cantidad_prestamos'] = result[0] if result else 0
                    
                except Exception as prestamo_error:
                    print(f"⚠️ Error obteniendo préstamos para oficina {oficina_id}: {prestamo_error}")
                    oficina['cantidad_prestamos'] = 0
                
                # --- HISTORIAL DE ASIGNACIONES CORPORATIVAS - TABLA CORRECTA ---
                try:
                    # CONSULTA PRINCIPAL: Obtener historial de asignaciones corporativas
                    cursor.execute("""
                        SELECT TOP 15
                            ach.HistorialId,
                            ach.Fecha,
                            ach.Accion,
                            ach.Cantidad,
                            ach.UsuarioAccion,
                            ach.Observaciones,
                            pc.NombreProducto as MaterialNombre,
                            o2.NombreOficina as OficinaNombre
                        FROM AsignacionesCorporativasHistorial ach
                        LEFT JOIN ProductosCorporativos pc ON ach.ProductoId = pc.ProductoId
                        LEFT JOIN Oficinas o2 ON ach.OficinaId = o2.OficinaId
                        WHERE ach.OficinaId = ?
                        ORDER BY ach.Fecha DESC
                    """, (oficina_id,))
                    
                    historial_oficina = []
                    for row in cursor.fetchall():
                        movimiento = {
                            'fecha': row[1],
                            'accion': row[2] if row[2] else 'Asignación',
                            'material_nombre': row[6] if row[6] else f"Producto ID: {row[0]}",
                            'cantidad': row[3] if row[3] else 1,
                            'oficina_destino_nombre': row[7] if row[7] else oficina_nombre,
                            'usuario_nombre': row[4] if row[4] else 'Sistema',
                            'observaciones': row[5] if row[5] else ''
                        }
                        historial_oficina.append(movimiento)
                    
                    # También buscar asignaciones regulares
                    cursor.execute("""
                        SELECT TOP 5
                            a.FechaAsignacion,
                            'Asignación a Usuario' as Accion,
                            a.UsuarioAsignador,
                            a.Observaciones,
                            pc.NombreProducto as MaterialNombre
                        FROM Asignaciones a
                        LEFT JOIN ProductosCorporativos pc ON a.ProductoId = pc.ProductoId
                        WHERE a.OficinaId = ? AND a.Activo = 1
                        ORDER BY a.FechaAsignacion DESC
                    """, (oficina_id,))
                    
                    asignaciones_regulares = []
                    for row in cursor.fetchall():
                        movimiento = {
                            'fecha': row[0],
                            'accion': row[1],
                            'material_nombre': row[4] if row[4] else 'Producto asignado',
                            'cantidad': 1,
                            'oficina_destino_nombre': oficina_nombre,
                            'usuario_nombre': row[2] if row[2] else 'Sistema',
                            'observaciones': row[3] if row[3] else ''
                        }
                        asignaciones_regulares.append(movimiento)
                    
                    # Combinar todos los movimientos
                    todos_movimientos = historial_oficina + asignaciones_regulares
                    
                    # Ordenar por fecha (más reciente primero)
                    todos_movimientos_ordenados = sorted(
                        todos_movimientos, 
                        key=lambda x: x['fecha'] if x['fecha'] else datetime.min, 
                        reverse=True
                    )[:15]  # Limitar a 15 movimientos
                    
                    oficina['movimientos'] = todos_movimientos_ordenados
                    oficina['cantidad_movimientos'] = len(todos_movimientos_ordenados)
                    
                    print(f"✅ Movimientos para oficina {oficina_nombre}: {len(todos_movimientos_ordenados)} registros")
                    
                    # Debug: Mostrar los primeros 3 movimientos
                    for i, mov in enumerate(todos_movimientos_ordenados[:3]):
                        print(f"   {i+1}. {mov.get('fecha')} - {mov.get('accion')}: {mov.get('material_nombre')}")
                    
                except Exception as mov_error:
                    print(f"⚠️ Error obteniendo movimientos para oficina {oficina_id}: {mov_error}")
                    import traceback
                    traceback.print_exc()
                    oficina['movimientos'] = []
                    oficina['cantidad_movimientos'] = 0
        
        except Exception as e:
            print(f"⚠️ Error general obteniendo datos: {e}")
            import traceback
            traceback.print_exc()
            
            for oficina in oficinas:
                oficina['materiales'] = []
                oficina['solicitudes'] = []
                oficina['movimientos'] = []
                oficina['cantidad_materiales'] = 0
                oficina['cantidad_solicitudes'] = 0
                oficina['cantidad_prestamos'] = 0
                oficina['cantidad_movimientos'] = 0
                oficina['valor_total_inventario'] = 0
        
        finally:
            if conn:
                conn.close()
        
        # Calcular totales generales
        total_materiales_oficinas = sum(o.get('cantidad_materiales', 0) for o in oficinas)
        total_solicitudes_oficinas = sum(o.get('cantidad_solicitudes', 0) for o in oficinas)
        total_valor_inventario = sum(o.get('valor_total_inventario', 0) for o in oficinas)
        total_movimientos_oficinas = sum(o.get('cantidad_movimientos', 0) for o in oficinas)
        oficinas_activas_count = len([o for o in oficinas if o.get('estado') == 'activo'])
        
        print(f"✅ REPORTE OFICINAS GENERADO:")
        print(f"   - Total oficinas: {len(oficinas)}")
        print(f"   - Total materiales: {total_materiales_oficinas}")
        print(f"   - Valor total inventario: ${total_valor_inventario:,.2f}")
        print(f"   - Total movimientos: {total_movimientos_oficinas}")
        
        return render_template('reportes/oficinas.html',
                             oficinas=oficinas,
                             total_oficinas=len(oficinas),
                             oficinas_activas=oficinas_activas_count,
                             total_materiales_oficinas=total_materiales_oficinas,
                             total_solicitudes_oficinas=total_solicitudes_oficinas,
                             total_movimientos_oficinas=total_movimientos_oficinas,
                             total_valor_inventario=total_valor_inventario)
        
    except Exception as e:
        print(f"❌ Error generando reporte de oficinas: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al generar el reporte de oficinas', 'danger')
        return render_template('reportes/oficinas.html',
                             oficinas=[],
                             total_oficinas=0,
                             oficinas_activas=0,
                             total_materiales_oficinas=0,
                             total_solicitudes_oficinas=0,
                             total_movimientos_oficinas=0,
                             total_valor_inventario=0)

@reportes_bp.route('/prestamos')
def reporte_prestamos():
    """Reporte de préstamos"""
    if not _require_login():
        return redirect('/login')
    
    if not (can_access('prestamos', 'view') or can_access('prestamos', 'view_own')):
        flash('No tiene permisos para ver reportes de préstamos', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener préstamos de la base de datos
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                pe.PrestamoId,
                pe.ElementoId,
                ep.NombreElemento as MaterialNombre,
                pe.UsuarioSolicitanteId,
                u.NombreUsuario as SolicitanteNombre,
                pe.OficinaId,
                o.NombreOficina as OficinaNombre,
                pe.CantidadPrestada,
                pe.FechaPrestamo,
                pe.FechaDevolucionPrevista,
                pe.FechaDevolucionReal,
                pe.Estado,
                pe.Evento,
                pe.Observaciones,
                pe.UsuarioPrestador
            FROM PrestamosElementos pe
            INNER JOIN ElementosPublicitarios ep ON pe.ElementoId = ep.ElementoId
            INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
            INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
            WHERE pe.Activo = 1
            ORDER BY pe.FechaPrestamo DESC
        """)
        
        prestamos = []
        for row in cursor.fetchall():
            prestamo = {
                'id': row[0],
                'elemento_id': row[1],
                'material_nombre': row[2],
                'usuario_id': row[3],
                'solicitante_nombre': row[4],
                'oficina_id': row[5],
                'oficina_nombre': row[6],
                'cantidad': row[7],
                'fecha_prestamo': row[8],
                'fecha_devolucion_prevista': row[9],
                'fecha_devolucion_real': row[10],
                'estado': row[11],
                'evento': row[12],
                'observaciones': row[13],
                'usuario_prestador': row[14]
            }
            prestamos.append(prestamo)
        
        conn.close()
        
        # Aplicar filtro según permisos
        rol_usuario = session.get('rol', '').lower()
        oficina_id_usuario = session.get('oficina_id')
        
        if rol_usuario.startswith('oficina_'):
            prestamos = [p for p in prestamos if p.get('oficina_id') == oficina_id_usuario]
        
        # Estadísticas
        total_prestamos = len(prestamos)
        prestamos_activos = len([p for p in prestamos if p.get('estado', '').upper() == 'PRESTADO'])
        devueltos = len([p for p in prestamos if p.get('estado', '').upper() == 'DEVUELTO'])
        
        return render_template('reportes/prestamos.html',
                             prestamos=prestamos,
                             total_prestamos=total_prestamos,
                             prestamos_activos=prestamos_activos,
                             devueltos=devueltos)
    except Exception as e:
        print(f"❌ Error generando reporte de préstamos: {e}")
        flash('Error al generar el reporte de préstamos', 'danger')
        return render_template('reportes/prestamos.html',
                             prestamos=[],
                             total_prestamos=0,
                             prestamos_activos=0,
                             devueltos=0)

# ============================================================================
# RUTAS DE EXPORTACIÓN
# ============================================================================

@reportes_bp.route('/materiales/exportar/excel')
def exportar_materiales_excel():
    """Exporta materiales a Excel"""
    if not _require_login():
        return redirect('/login')
    
    try:
        materiales = MaterialModel.obtener_todos() or []
        
        # Aplicar filtro según permisos
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            materiales = filtrar_por_oficina_usuario(materiales, 'oficina_id')

        data = []
        for mat in materiales:
            data.append({
                'ID': mat.get('id', ''),
                'Nombre': mat.get('nombre', ''),
                'Valor Unitario': mat.get('valor_unitario', 0),
                'Stock Actual': mat.get('cantidad', 0),
                'Stock Mínimo': mat.get('stock_minimo', 0) if mat.get('stock_minimo') else 0,
                'Valor Total': mat.get('valor_total', 0),
                'Oficina': mat.get('oficina_nombre', ''),
                'Creado por': mat.get('usuario_creador', ''),
                'Fecha Creación': mat.get('fecha_creacion', '')
            })

        df = pd.DataFrame(data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Materiales', index=False)
        
        output.seek(0)
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        filename = f'reporte_materiales_{fecha_actual}.xlsx'

        return send_file(output,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True,
                         download_name=filename)
    except Exception as e:
        print(f"❌ Error exportando materiales a Excel: {e}")
        flash('Error al exportar el reporte de materiales a Excel', 'danger')
        return redirect(url_for('reportes.reporte_materiales'))

@reportes_bp.route('/material/<int:material_id>')
def material_detalle(material_id):
    """Detalle de material específico"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver detalles de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        # Obtener el material
        material = MaterialModel.obtener_por_id(material_id)
        if not material:
            flash('Material no encontrado', 'danger')
            return redirect('/reportes/materiales')
        
        # Verificar permisos de oficina
        if not (session.get('rol') in ['administrador', 'lider_inventario']):
            if material.get('oficina_id') != session.get('oficina_id'):
                flash('No tiene permisos para ver este material', 'danger')
                return redirect('/reportes/materiales')
        
        return render_template('reportes/material_detalle.html',
                             material=material)
        
    except Exception as e:
        print(f"❌ Error obteniendo detalle del material: {e}")
        flash('Error al obtener el detalle del material', 'danger')
        return redirect('/reportes/materiales')

@reportes_bp.route('/exportar/inventario-corporativo/excel')
def exportar_inventario_corporativo_excel():
    """Exporta TODO el inventario corporativo a Excel"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        
        # CONSULTA COMPLETA DEL INVENTARIO CORPORATIVO
        query = """
        SELECT 
            o.NombreOficina,
            o.Ubicacion,
            o.Region,
            m.NombreElemento as Material,
            m.Descripcion,
            m.CantidadDisponible as Stock,
            m.ValorUnitario,
            m.CantidadDisponible * m.ValorUnitario as ValorTotal,
            m.StockMinimo,
            m.Categoria,
            CASE WHEN m.Activo = 1 THEN 'Activo' ELSE 'Inactivo' END as Estado,
            u.NombreUsuario as Responsable,
            m.FechaCreacion,
            m.FechaUltimaActualizacion
        FROM Materiales m
        INNER JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
        INNER JOIN Usuarios u ON m.UsuarioCreadorId = u.UsuarioId
        WHERE m.Activo = 1
        ORDER BY o.NombreOficina, m.NombreElemento
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        print(f"✅ EXPORTANDO INVENTARIO CORPORATIVO: {len(df)} registros")
        print(f"   - Fuente: Tabla Materiales (INVENTARIO CORPORATIVO)")
        print(f"   - Oficinas incluidas: {df['NombreOficina'].nunique()}")
        print(f"   - Valor total exportado: ${df['ValorTotal'].sum():,.2f}")
        
        # Crear archivo Excel en memoria
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Hoja 1: Inventario completo
            df.to_excel(writer, sheet_name='Inventario Corporativo', index=False)
            
            # Hoja 2: Resumen por oficina
            resumen_df = df.groupby(['NombreOficina', 'Ubicacion', 'Region']).agg({
                'Material': 'count',
                'Stock': 'sum',
                'ValorTotal': 'sum'
            }).reset_index()
            resumen_df.columns = ['Oficina', 'Ubicación', 'Región', 'Cantidad Materiales', 'Stock Total', 'Valor Total Inventario']
            resumen_df['Valor Total Inventario'] = resumen_df['Valor Total Inventario'].round(2)
            resumen_df.to_excel(writer, sheet_name='Resumen por Oficina', index=False)
            
            # Hoja 3: Totales generales
            totales_data = {
                'Métrica': [
                    'Total Oficinas con Inventario',
                    'Total Materiales',
                    'Stock Total',
                    'Valor Total Inventario',
                    'Valor Promedio por Material',
                    'Fecha de Exportación'
                ],
                'Valor': [
                    resumen_df['Oficina'].nunique(),
                    df['Material'].count(),
                    int(df['Stock'].sum()),
                    f"${df['ValorTotal'].sum():,.2f}",
                    f"${df['ValorTotal'].mean():,.2f}",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }
            totales_df = pd.DataFrame(totales_data)
            totales_df.to_excel(writer, sheet_name='Totales Generales', index=False)
        
        output.seek(0)
        
        # Crear nombre de archivo
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_corporativo_completo_{fecha_actual}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error exportando inventario corporativo: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al exportar el inventario corporativo', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

@reportes_bp.route('/exportar/inventario-corporativo/pdf')
def exportar_inventario_corporativo_pdf():
    """Exporta el inventario corporativo a PDF"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        # Esta función generaría un PDF (requiere bibliotecas adicionales)
        # Por ahora, redirige al Excel o muestra mensaje
        flash('La exportación a PDF está en desarrollo. Use la exportación Excel por ahora.', 'info')
        return redirect(url_for('reportes.exportar_inventario_corporativo_excel'))
        
    except Exception as e:
        print(f"❌ Error exportando a PDF: {e}")
        flash('Error al generar el PDF', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

# ============================================================================
# EXPORTACIÓN POR OFICINA
# ============================================================================

@reportes_bp.route('/exportar/oficina/<int:oficina_id>/<string:formato>')
def exportar_oficina_inventario(oficina_id, formato):
    """Exporta el inventario de una oficina específica"""
    if not _require_login():
        return redirect('/login')
    
    # Verificar permisos
    if not can_access('inventario_corporativo', 'view'):
        flash('No tiene permisos para exportar inventario corporativo', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        # Obtener parámetros
        incluir_materiales = request.args.get('materiales', '1') == '1'
        incluir_solicitudes = request.args.get('solicitudes', '1') == '1'
        incluir_totales = request.args.get('totales', '1') == '1'
        incluir_movimientos = request.args.get('movimientos', '1') == '1'
        
        conn = get_database_connection()
        
        # Obtener información de la oficina
        cursor = conn.cursor()
        cursor.execute("""
            SELECT OficinaId, NombreOficina, Ubicacion, Region 
            FROM Oficinas 
            WHERE OficinaId = ?
        """, (oficina_id,))
        
        oficina_data = cursor.fetchone()
        if not oficina_data:
            flash('Oficina no encontrada', 'danger')
            return redirect(url_for('reportes.reporte_oficinas'))
        
        oficina = {
            'id': oficina_data[0],
            'nombre': oficina_data[1],
            'ubicacion': oficina_data[2],
            'region': oficina_data[3]
        }
        
        # Obtener materiales del inventario corporativo de esta oficina
        materiales = []
        if incluir_materiales:
            cursor.execute("""
                SELECT 
                    MaterialId,
                    NombreElemento,
                    Descripcion,
                    CantidadDisponible,
                    ValorUnitario,
                    StockMinimo,
                    Categoria,
                    Activo,
                    FechaCreacion
                FROM Materiales 
                WHERE OficinaCreadoraId = ? AND Activo = 1
                ORDER BY NombreElemento
            """, (oficina_id,))
            
            for row in cursor.fetchall():
                valor_total = row[3] * row[4]
                material = {
                    'id': row[0],
                    'nombre': row[1],
                    'descripcion': row[2] or '',
                    'cantidad': row[3],
                    'valor_unitario': float(row[4]),
                    'valor_total': float(valor_total),
                    'stock_minimo': row[5] or 0,
                    'categoria': row[6] or 'General',
                    'activo': bool(row[7]),
                    'fecha_creacion': row[8]
                }
                materiales.append(material)
        
        # Obtener solicitudes recientes
        solicitudes = []
        if incluir_solicitudes:
            cursor.execute("""
                SELECT TOP 10
                    sm.SolicitudId,
                    sm.CantidadSolicitada,
                    sm.CantidadEntregada,
                    sm.FechaSolicitud,
                    es.NombreEstado as Estado,
                    m.NombreElemento as MaterialNombre,
                    sm.UsuarioSolicitante,
                    sm.Observacion
                FROM SolicitudesMaterial sm
                INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                WHERE sm.OficinaSolicitanteId = ?
                ORDER BY sm.FechaSolicitud DESC
            """, (oficina_id,))
            
            for row in cursor.fetchall():
                solicitud = {
                    'id': row[0],
                    'cantidad_solicitada': row[1],
                    'cantidad_entregada': row[2],
                    'fecha_solicitud': row[3],
                    'estado': row[4],
                    'material_nombre': row[5],
                    'usuario_solicitante': row[6],
                    'observacion': row[7] or ''
                }
                solicitudes.append(solicitud)
        
        # Obtener movimientos/historial
        movimientos = []
        if incluir_movimientos:
            try:
                # Buscar tabla de movimientos
                cursor.execute("""
                    SELECT TABLE_NAME 
                    FROM INFORMATION_SCHEMA.TABLES 
                    WHERE TABLE_TYPE = 'BASE TABLE'
                    AND (TABLE_NAME LIKE '%movimiento%' OR TABLE_NAME LIKE '%asignacion%')
                """)
                
                tablas_mov = cursor.fetchall()
                if tablas_mov:
                    tabla_mov = tablas_mov[0][0]
                    
                    # Intentar obtener movimientos
                    cursor.execute(f"""
                        SELECT TOP 20
                            m.*,
                            mat.NombreElemento as MaterialNombre,
                            o.NombreOficina as OficinaDestinoNombre,
                            u.NombreUsuario as UsuarioNombre
                        FROM {tabla_mov} m
                        LEFT JOIN Materiales mat ON m.MaterialId = mat.MaterialId
                        LEFT JOIN Oficinas o ON m.OficinaDestinoId = o.OficinaId
                        LEFT JOIN Usuarios u ON m.UsuarioId = u.UsuarioId
                        WHERE m.OficinaCreadoraId = ? OR m.OficinaDestinoId = ? OR m.OficinaOrigenId = ?
                        ORDER BY m.FechaMovimiento DESC, m.FechaCreacion DESC
                    """, (oficina_id, oficina_id, oficina_id))
                    
                    columns = [column[0] for column in cursor.description]
                    for row in cursor.fetchall():
                        row_dict = dict(zip(columns, row))
                        movimiento = {
                            'fecha': row_dict.get('FechaMovimiento', row_dict.get('FechaCreacion', row_dict.get('Fecha', None))),
                            'accion': row_dict.get('TipoMovimiento', row_dict.get('Accion', row_dict.get('Tipo', 'Asignación'))),
                            'material_nombre': row_dict.get('MaterialNombre', 'Material no especificado'),
                            'cantidad': row_dict.get('Cantidad', 1),
                            'oficina_destino_nombre': row_dict.get('OficinaDestinoNombre', 'Oficina no especificada'),
                            'usuario_nombre': row_dict.get('UsuarioNombre', 'Usuario no especificado'),
                            'observaciones': row_dict.get('Observaciones', '')
                        }
                        movimientos.append(movimiento)
            except Exception as mov_error:
                print(f"⚠️ Error obteniendo movimientos para exportación: {mov_error}")
        
        conn.close()
        
        # Calcular totales
        total_materiales = len(materiales)
        valor_total_inventario = sum(m.get('valor_total', 0) for m in materiales)
        total_solicitudes = len(solicitudes)
        total_movimientos = len(movimientos)
        
        # Exportar según formato
        if formato.lower() == 'excel':
            return _exportar_oficina_excel(oficina, materiales, solicitudes, movimientos,
                                          total_materiales, valor_total_inventario, 
                                          total_solicitudes, total_movimientos, incluir_totales)
        elif formato.lower() == 'pdf':
            return _exportar_oficina_pdf(oficina, materiales, solicitudes, movimientos,
                                        total_materiales, valor_total_inventario,
                                        total_solicitudes, total_movimientos, incluir_totales)
        elif formato.lower() == 'csv':
            return _exportar_oficina_csv(oficina, materiales, solicitudes, movimientos,
                                        total_materiales, valor_total_inventario,
                                        total_solicitudes, total_movimientos, incluir_totales)
        else:
            flash('Formato de exportación no válido', 'danger')
            return redirect(url_for('reportes.reporte_oficinas'))
            
    except Exception as e:
        print(f"❌ Error exportando inventario de oficina: {e}")
        import traceback
        traceback.print_exc()
        flash('Error al exportar el inventario de la oficina', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

def _exportar_oficina_excel(oficina, materiales, solicitudes, movimientos, total_materiales, 
                           valor_total_inventario, total_solicitudes, total_movimientos, incluir_totales):
    """Exporta a Excel el inventario de una oficina"""
    try:
        import pandas as pd
        from io import BytesIO
        
        # Crear DataFrames
        data_frames = []
        sheet_names = []
        
        # Hoja 1: Información de la oficina
        oficina_info = {
            'Campo': ['Nombre', 'Ubicación', 'Región', 'ID Oficina', 
                     'Total Materiales', 'Valor Inventario', 'Total Solicitudes',
                     'Total Movimientos', 'Fecha Exportación'],
            'Valor': [oficina['nombre'], oficina['ubicacion'], oficina['region'], 
                     oficina['id'], total_materiales, 
                     f"${valor_total_inventario:,.2f}", total_solicitudes,
                     total_movimientos,
                     datetime.now().strftime('%Y-%m-%d %H:%M:%S')]
        }
        df_oficina = pd.DataFrame(oficina_info)
        data_frames.append(df_oficina)
        sheet_names.append('Información Oficina')
        
        # Hoja 2: Materiales del inventario
        if materiales:
            materiales_data = []
            for mat in materiales:
                materiales_data.append({
                    'ID': mat['id'],
                    'Nombre': mat['nombre'],
                    'Descripción': mat['descripcion'],
                    'Cantidad': mat['cantidad'],
                    'Valor Unitario': f"${mat['valor_unitario']:,.2f}",
                    'Valor Total': f"${mat['valor_total']:,.2f}",
                    'Stock Mínimo': mat['stock_minimo'],
                    'Categoría': mat['categoria'],
                    'Estado': 'Activo' if mat['activo'] else 'Inactivo',
                    'Fecha Creación': mat['fecha_creacion'].strftime('%Y-%m-%d') 
                    if hasattr(mat['fecha_creacion'], 'strftime') 
                    else str(mat['fecha_creacion'])
                })
            
            df_materiales = pd.DataFrame(materiales_data)
            data_frames.append(df_materiales)
            sheet_names.append('Materiales Inventario')
        
        # Hoja 3: Solicitudes recientes
        if solicitudes:
            solicitudes_data = []
            for sol in solicitudes:
                solicitudes_data.append({
                    'ID': sol['id'],
                    'Material': sol['material_nombre'],
                    'Cantidad Solicitada': sol['cantidad_solicitada'],
                    'Cantidad Entregada': sol['cantidad_entregada'],
                    'Estado': sol['estado'],
                    'Fecha Solicitud': sol['fecha_solicitud'].strftime('%Y-%m-%d') 
                    if hasattr(sol['fecha_solicitud'], 'strftime') 
                    else str(sol['fecha_solicitud']),
                    'Solicitante': sol['usuario_solicitante'],
                    'Observaciones': sol['observacion']
                })
            
            df_solicitudes = pd.DataFrame(solicitudes_data)
            data_frames.append(df_solicitudes)
            sheet_names.append('Solicitudes')
        
        # Hoja 4: Historial de movimientos
        if movimientos:
            movimientos_data = []
            for mov in movimientos:
                movimientos_data.append({
                    'Fecha': mov['fecha'].strftime('%Y-%m-%d %H:%M') 
                    if hasattr(mov['fecha'], 'strftime') 
                    else str(mov['fecha']),
                    'Acción': mov['accion'],
                    'Material': mov['material_nombre'],
                    'Cantidad': mov['cantidad'],
                    'Oficina Destino': mov['oficina_destino_nombre'],
                    'Usuario': mov['usuario_nombre'],
                    'Observaciones': mov['observaciones']
                })
            
            df_movimientos = pd.DataFrame(movimientos_data)
            data_frames.append(df_movimientos)
            sheet_names.append('Historial Movimientos')
        
        # Crear archivo Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            for i, df in enumerate(data_frames):
                df.to_excel(writer, sheet_name=sheet_names[i], index=False)
        
        output.seek(0)
        
        # Nombre del archivo
        nombre_oficina_safe = oficina['nombre'].replace(' ', '_').replace('/', '_')
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_{nombre_oficina_safe}_{fecha}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error generando Excel de oficina: {e}")
        flash('Error al generar el archivo Excel', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

def _exportar_oficina_pdf(oficina, materiales, solicitudes, movimientos, total_materiales,
                         valor_total_inventario, total_solicitudes, total_movimientos, incluir_totales):
    """Exporta a PDF el inventario de una oficina"""
    try:
        # Por ahora, redirigir a Excel hasta que implementemos PDF
        flash('La exportación a PDF estará disponible próximamente. Usando Excel por ahora.', 'info')
        
        # Crear parámetros para redirección a Excel
        from urllib.parse import urlencode
        params = {
            'materiales': '1' if materiales else '0',
            'solicitudes': '1' if solicitudes else '0',
            'movimientos': '1' if movimientos else '0',
            'totales': '1' if incluir_totales else '0'
        }
        
        return redirect(url_for('reportes.exportar_oficina_inventario', 
                              oficina_id=oficina['id'], 
                              formato='excel') + '?' + urlencode(params))
        
    except Exception as e:
        print(f"❌ Error generando PDF de oficina: {e}")
        flash('Error al generar el PDF', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

def _exportar_oficina_csv(oficina, materiales, solicitudes, movimientos, total_materiales,
                         valor_total_inventario, total_solicitudes, total_movimientos, incluir_totales):
    """Exporta a CSV el inventario de una oficina"""
    try:
        import pandas as pd
        from io import StringIO
        
        # Crear contenido CSV
        output = StringIO()
        
        # Encabezado con información de la oficina
        output.write(f"Inventario Corporativo - {oficina['nombre']}\n")
        output.write(f"Ubicación: {oficina['ubicacion']}\n")
        output.write(f"Región: {oficina['region']}\n")
        output.write(f"Fecha Exportación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        output.write(f"Total Materiales: {total_materiales}\n")
        output.write(f"Valor Total Inventario: ${valor_total_inventario:,.2f}\n")
        output.write(f"Total Solicitudes: {total_solicitudes}\n")
        output.write(f"Total Movimientos: {total_movimientos}\n")
        output.write("\n")
        
        # Sección de materiales
        if materiales:
            output.write("=== MATERIALES DEL INVENTARIO ===\n")
            df_materiales = pd.DataFrame(materiales)
            df_materiales = df_materiales[['nombre', 'cantidad', 'valor_unitario', 'valor_total', 'categoria']]
            df_materiales.columns = ['Material', 'Cantidad', 'Valor_Unitario', 'Valor_Total', 'Categoría']
            df_materiales.to_csv(output, index=False)
            output.write("\n")
        
        # Sección de movimientos
        if movimientos:
            output.write("=== HISTORIAL DE MOVIMIENTOS ===\n")
            df_movimientos = pd.DataFrame(movimientos)
            df_movimientos = df_movimientos[['fecha', 'accion', 'material_nombre', 'cantidad', 'usuario_nombre']]
            df_movimientos.columns = ['Fecha', 'Acción', 'Material', 'Cantidad', 'Usuario']
            df_movimientos.to_csv(output, index=False)
        
        # Convertir a bytes
        output_str = output.getvalue()
        output_bytes = BytesIO(output_str.encode('utf-8'))
        output_bytes.seek(0)
        
        # Nombre del archivo
        nombre_oficina_safe = oficina['nombre'].replace(' ', '_').replace('/', '_')
        fecha = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'inventario_{nombre_oficina_safe}_{fecha}.csv'
        
        return send_file(
            output_bytes,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        print(f"❌ Error generando CSV de oficina: {e}")
        flash('Error al generar el archivo CSV', 'danger')
        return redirect(url_for('reportes.reporte_oficinas'))

# ============================================================================
# FUNCIÓN ADICIONAL PARA DEPURAR DATOS DE OFICINA
# ============================================================================

@reportes_bp.route('/debug/oficina/<int:oficina_id>')
def debug_oficina_data(oficina_id):
    """Endpoint para depurar datos de una oficina específica"""
    if not _require_login():
        return redirect('/login')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Obtener información básica de la oficina
        cursor.execute("""
            SELECT OficinaId, NombreOficina, Ubicacion, Region, Estado 
            FROM Oficinas 
            WHERE OficinaId = ?
        """, (oficina_id,))
        
        oficina = cursor.fetchone()
        
        # Obtener materiales de esta oficina
        cursor.execute("""
            SELECT COUNT(*) as total_materiales, 
                   SUM(CantidadDisponible) as total_stock,
                   SUM(CantidadDisponible * ValorUnitario) as valor_total
            FROM Materiales 
            WHERE OficinaCreadoraId = ? AND Activo = 1
        """, (oficina_id,))
        
        materiales_stats = cursor.fetchone()
        
        # Obtener algunos materiales como muestra
        cursor.execute("""
            SELECT TOP 5 MaterialId, NombreElemento, CantidadDisponible, ValorUnitario
            FROM Materiales 
            WHERE OficinaCreadoraId = ? AND Activo = 1
        """, (oficina_id,))
        
        materiales_sample = cursor.fetchall()
        
        conn.close()
        
        # Preparar respuesta JSON para depuración
        debug_info = {
            'oficina': {
                'id': oficina[0] if oficina else None,
                'nombre': oficina[1] if oficina else None,
                'ubicacion': oficina[2] if oficina else None,
                'region': oficina[3] if oficina else None,
                'estado': oficina[4] if oficina else None
            },
            'materiales_stats': {
                'total_materiales': materiales_stats[0] if materiales_stats else 0,
                'total_stock': materiales_stats[1] if materiales_stats else 0,
                'valor_total': materiales_stats[2] if materiales_stats else 0
            },
            'materiales_sample': [
                {
                    'id': row[0],
                    'nombre': row[1],
                    'cantidad': row[2],
                    'valor_unitario': row[3]
                } for row in materiales_sample
            ]
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({'error': str(e)})

@reportes_bp.route('/material/<int:material_id>/historial')
def material_historial(material_id):
    """Obtiene el historial completo de un material"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('materiales', 'view'):
        flash('No tiene permisos para ver historial de materiales', 'warning')
        return redirect('/reportes')
    
    try:
        from database import get_database_connection
        
        conn = get_database_connection()
        cursor = conn.cursor()
        
        # Primero obtener información básica del material
        cursor.execute("""
            SELECT m.MaterialId, m.NombreElemento, m.Descripcion, m.Categoria,
                   m.ValorUnitario, m.CantidadDisponible, m.StockMinimo,
                   o.NombreOficina as Ubicacion, m.Asignable
            FROM Materiales m
            LEFT JOIN Oficinas o ON m.OficinaCreadoraId = o.OficinaId
            WHERE m.MaterialId = ?
        """, (material_id,))
        
        material_data = cursor.fetchone()
        if not material_data:
            return jsonify({'error': 'Material no encontrado'})
        
        material = {
            'id': material_data[0],
            'nombre': material_data[1],
            'descripcion': material_data[2],
            'categoria': material_data[3],
            'valor_unitario': float(material_data[4] or 0),
            'cantidad': material_data[5],
            'stock_minimo': material_data[6],
            'ubicacion': material_data[7],
            'asignable': bool(material_data[8]) if material_data[8] is not None else False
        }
        
        # Buscar historial de movimientos para este material
        historial = []
        
        # Buscar en tabla de solicitudes
        cursor.execute("""
            SELECT sm.FechaSolicitud as Fecha, 'Solicitud' as Accion,
                   sm.CantidadSolicitada as Cantidad, 
                   o.NombreOficina as Oficina,
                   sm.UsuarioSolicitante as Usuario,
                   sm.Observacion as Observaciones
            FROM SolicitudesMaterial sm
            INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            WHERE sm.MaterialId = ?
            ORDER BY sm.FechaSolicitud DESC
        """, (material_id,))
        
        for row in cursor.fetchall():
            historial.append({
                'fecha': row[0],
                'accion': row[1],
                'cantidad': row[2],
                'oficina': row[3],
                'usuario': row[4],
                'observaciones': row[5]
            })
        
        # Buscar en tabla de préstamos
        cursor.execute("""
            SELECT pe.FechaPrestamo as Fecha, 'Préstamo' as Accion,
                   pe.CantidadPrestada as Cantidad,
                   o.NombreOficina as Oficina,
                   u.NombreUsuario as Usuario,
                   pe.Observaciones
            FROM PrestamosElementos pe
            INNER JOIN Oficinas o ON pe.OficinaId = o.OficinaId
            INNER JOIN Usuarios u ON pe.UsuarioSolicitanteId = u.UsuarioId
            WHERE pe.ElementoId = ? AND pe.Activo = 1
            ORDER BY pe.FechaPrestamo DESC
        """, (material_id,))
        
        for row in cursor.fetchall():
            historial.append({
                'fecha': row[0],
                'accion': row[1],
                'cantidad': row[2],
                'oficina': row[3],
                'usuario': row[4],
                'observaciones': row[5]
            })
        
        conn.close()
        
        # Ordenar historial por fecha
        historial_ordenado = sorted(historial, key=lambda x: x['fecha'], reverse=True)
        
        return jsonify({
            'material': material,
            'historial': historial_ordenado[:50]  # Limitar a 50 registros
        })
        
    except Exception as e:
        print(f"❌ Error obteniendo historial del material: {e}")
        return jsonify({'error': str(e)})