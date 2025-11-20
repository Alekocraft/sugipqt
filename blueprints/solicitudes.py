# blueprints/solicitudes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from models.solicitudes_model import SolicitudModel
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from utils.auth import login_required, role_required

solicitudes_bp = Blueprint('solicitudes', __name__)

@solicitudes_bp.route('/')
@login_required
def listar_solicitudes():
    try:
        # Obtener filtros
        filtro_estado = request.args.get('estado', 'todos')
        filtro_oficina = request.args.get('oficina', 'todas')
        
        # Obtener solicitudes según permisos
        user_rol = session.get('rol', 'usuario')
        oficina_id = session.get('oficina_id')
        
        if user_rol in ['administrador', 'aprobador']:
            # Admin y aprobadores ven todas las solicitudes o filtran por oficina
            if filtro_oficina != 'todas' and filtro_oficina.isdigit():
                solicitudes = SolicitudModel.obtener_todas_ordenadas(int(filtro_oficina))
            else:
                solicitudes = SolicitudModel.obtener_todas_ordenadas()
        else:
            # Usuarios normales solo ven las de su oficina
            solicitudes = SolicitudModel.obtener_todas_ordenadas(oficina_id)
        
        # Aplicar filtro de estado
        if filtro_estado != 'todos':
            estado_map = {
                'pendiente': 'Pendiente',
                'aprobada': 'Aprobada', 
                'rechazada': 'Rechazada',
                'devuelta': 'Devuelta'
            }
            estado_filtro = estado_map.get(filtro_estado, '')
            if estado_filtro:
                solicitudes = [s for s in solicitudes if s['estado'] == estado_filtro]
        
        # Obtener materiales para el diccionario - CORREGIDO
        materiales = MaterialModel.obtener_todos()
        materiales_dict = {}
        for m in materiales:
            materiales_dict[m['id']] = {
                'cantidad_disponible': m.get('cantidad_disponible', 0),
                'ruta_imagen': m.get('ruta_imagen', '')  # Asegurar que existe
            }
        
        # Obtener oficinas únicas para el filtro
        oficinas_unique = list(set([s['oficina_nombre'] for s in solicitudes]))
        
        # Calcular resumen
        total_solicitudes = len(solicitudes)
        solicitudes_pendientes = len([s for s in solicitudes if s['estado'] == 'Pendiente'])
        solicitudes_aprobadas = len([s for s in solicitudes if s['estado'] == 'Aprobada'])
        solicitudes_rechazadas = len([s for s in solicitudes if s['estado'] == 'Rechazada'])
        solicitudes_devueltas = len([s for s in solicitudes if s['estado'] == 'Devuelta'])
        
        return render_template('solicitudes/solicitudes.html',
                            solicitudes=solicitudes,
                            materiales_dict=materiales_dict,
                            oficinas_unique=oficinas_unique,
                            total_solicitudes=total_solicitudes,
                            solicitudes_pendientes=solicitudes_pendientes,
                            solicitudes_aprobadas=solicitudes_aprobadas,
                            solicitudes_rechazadas=solicitudes_rechazadas,
                            solicitudes_devueltas=solicitudes_devueltas,
                            filtro_estado=filtro_estado,
                            filtro_oficina=filtro_oficina)
    
    except Exception as e:
        flash(f'Error al cargar solicitudes: {str(e)}', 'error')
        return render_template('solicitudes/solicitudes.html', 
                             solicitudes=[], 
                             materiales_dict={})

@solicitudes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear_solicitud():
    if request.method == 'GET':
        materiales = MaterialModel.obtener_todos()
        oficinas = OficinaModel.obtener_todas()
        return render_template('solicitudes/crear.html',
                             materiales=materiales, 
                             oficinas=oficinas)
    
    try:
        oficina_id = int(request.form['oficina_id'])
        material_id = int(request.form['material_id'])
        cantidad_solicitada = int(request.form['cantidad_solicitada'])
        porcentaje_oficina = float(request.form['porcentaje_oficina'])
        usuario_nombre = session.get('user_name') or session.get('usuario_nombre', 'Usuario')
        observacion = request.form.get('observacion', '')
        
        # Validaciones básicas
        if cantidad_solicitada <= 0:
            flash('La cantidad debe ser mayor a 0', 'error')
            return redirect(url_for('solicitudes.crear_solicitud'))
        
        if porcentaje_oficina < 0 or porcentaje_oficina > 100:
            flash('El porcentaje debe estar entre 0 y 100', 'error')
            return redirect(url_for('solicitudes.crear_solicitud'))
        
        # Crear solicitud
        solicitud_id = SolicitudModel.crear(
            oficina_id, material_id, cantidad_solicitada, 
            porcentaje_oficina, usuario_nombre, observacion
        )
        
        if solicitud_id:
            flash('✅ Solicitud creada exitosamente', 'success')
        else:
            flash('❌ Error al crear la solicitud', 'error')
            
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))

@solicitudes_bp.route('/aprobar/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador')
def aprobar_solicitud(solicitud_id):
    try:
        usuario_id = session.get('user_id') or session.get('usuario_id')
        success, message = SolicitudModel.aprobar(solicitud_id, usuario_id)
        
        flash(message, 'success' if success else 'error')
        
    except Exception as e:
        flash(f'❌ Error al aprobar solicitud: {str(e)}', 'error')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))

@solicitudes_bp.route('/aprobar_parcial/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador')
def aprobar_parcial_solicitud(solicitud_id):
    try:
        cantidad_aprobada = int(request.form['cantidad_aprobada'])
        usuario_id = session.get('user_id') or session.get('usuario_id')
        
        success, message = SolicitudModel.aprobar_parcial(
            solicitud_id, usuario_id, cantidad_aprobada
        )
        
        flash(message, 'success' if success else 'error')
        
    except ValueError:
        flash('❌ Cantidad inválida', 'error')
    except Exception as e:
        flash(f'❌ Error al aprobar parcialmente: {str(e)}', 'error')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))

@solicitudes_bp.route('/rechazar/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador')
def rechazar_solicitud(solicitud_id):
    try:
        observacion = request.form.get('observacion', '')
        usuario_id = session.get('user_id') or session.get('usuario_id')
        
        success = SolicitudModel.rechazar(solicitud_id, usuario_id, observacion)
        
        if success:
            flash('✅ Solicitud rechazada exitosamente', 'success')
        else:
            flash('❌ Error al rechazar la solicitud', 'error')
            
    except Exception as e:
        flash(f'❌ Error: {str(e)}', 'error')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))

# Ruta de devolución
@solicitudes_bp.route('/devolucion/<int:solicitud_id>', methods=['POST'])
@login_required
@role_required('administrador', 'aprobador')
def registrar_devolucion(solicitud_id):
    try:
        cantidad_devuelta = int(request.form.get('cantidad_devuelta'))
        observacion = request.form.get('observacion_devolucion', '')
        usuario_nombre = session.get('user_name') or session.get('usuario_nombre', 'Usuario')
        
        # Validar que la cantidad sea positiva
        if cantidad_devuelta <= 0:
            flash('❌ La cantidad a devolver debe ser mayor a 0', 'error')
            return redirect(url_for('solicitudes.listar_solicitudes'))
        
        # Registrar la devolución
        success, message = SolicitudModel.registrar_devolucion(
            solicitud_id, 
            cantidad_devuelta,
            usuario_nombre,
            observacion
        )
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
            
    except ValueError:
        flash('❌ Cantidad inválida', 'error')
    except Exception as e:
        flash(f'❌ Error al procesar la devolución: {str(e)}', 'error')
    
    return redirect(url_for('solicitudes.listar_solicitudes'))

# API endpoints para datos en tiempo real
@solicitudes_bp.route('/api/pendientes')
@login_required
def api_solicitudes_pendientes():
    try:
        user_rol = session.get('rol', 'usuario')
        oficina_id = session.get('oficina_id')
        
        if user_rol in ['administrador', 'aprobador']:
            solicitudes = SolicitudModel.obtener_para_aprobador()
        else:
            solicitudes = SolicitudModel.obtener_para_aprobador(oficina_id)
        
        return jsonify(solicitudes)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# En blueprints/solicitudes.py - ACTUALIZAR ESTA RUTA
@solicitudes_bp.route('/api/<int:solicitud_id>/info-devolucion')
@login_required
def api_info_devolucion(solicitud_id):
    try:
        # Usar el nuevo método que incluye cantidad_aprobada
        info = SolicitudModel.obtener_info_devolucion_actualizada(solicitud_id)
        if info:
            return jsonify(info)
        else:
            return jsonify({'error': 'Solicitud no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500