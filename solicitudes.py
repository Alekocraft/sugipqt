import os
from werkzeug.utils import secure_filename
from models.novedades_model import NovedadModel

# Configuración para carga de imágenes
UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Crear directorio si no existe
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)

@solicitudes_bp.route('/registrar-novedad', methods=['POST'])
@login_required
def registrar_novedad():
    try:
        # USAR request.form para formularios con archivos
        solicitud_id = request.form.get('solicitud_id')
        tipo_novedad = request.form.get('tipo_novedad')
        descripcion = request.form.get('descripcion')
        cantidad_afectada = request.form.get('cantidad_afectada')
        usuario_id = session.get('user_id')
        
        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id]):
            return jsonify({'success': False, 'error': 'Faltan datos requeridos'}), 400
        
        # Procesar imagen
        imagen = request.files.get('imagen_novedad')
        ruta_imagen = None
        
        if imagen and imagen.filename:
            if allowed_file(imagen.filename):
                filename = secure_filename(imagen.filename)
                name, ext = os.path.splitext(filename)
                filename = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                filepath = os.path.join(UPLOAD_FOLDER_NOVEDADES, filename)
                imagen.save(filepath)
                ruta_imagen = f"images/novedades/{filename}"
        
        # Lógica de base de datos (mantener tu código existente)
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO NovedadesSolicitudes 
            (SolicitudId, TipoNovedad, Descripcion, CantidadAfectada, UsuarioRegistra, FechaRegistro, EstadoNovedad, RutaImagen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id, datetime.now(), 'Registrada', ruta_imagen))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Novedad registrada correctamente'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error interno: {str(e)}'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@solicitudes_bp.route('/gestionar-novedad', methods=['POST'])
@login_required
def gestionar_novedad():
    try:
        # CAMBIAR: Usar request.form
        data = request.form
        solicitud_id = data.get('solicitud_id')
        accion = data.get('accion')
        observaciones = data.get('observaciones', '')
        
       
        if not all([solicitud_id, accion]):
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        # Obtener la novedad más reciente de la solicitud
        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        if not novedades:
            return jsonify({'success': False, 'message': 'No se encontró novedad para esta solicitud'}), 404

        novedad = novedades[0]  # Tomar la más reciente

        # Determinar nuevo estado según la acción
        if accion == 'aceptar':
            nuevo_estado_novedad = 'aceptada'
            nuevo_estado_solicitud = 9  # novedad_aceptada
        else:
            nuevo_estado_novedad = 'rechazada'
            nuevo_estado_solicitud = 10  # novedad_rechazada

        # Actualizar estado de la novedad
        success_novedad = NovedadModel.actualizar_estado(
            novedad_id=novedad['novedad_id'],
            estado=nuevo_estado_novedad,
            usuario_resuelve=session.get('usuario_nombre'),
            observaciones_resolucion=observaciones
        )

        # Actualizar estado de la solicitud
        success_solicitud = SolicitudModel.actualizar_estado_solicitud(
            int(solicitud_id), 
            nuevo_estado_solicitud
        )

        if success_novedad and success_solicitud:
            return jsonify({
                'success': True, 
                'message': f'Novedad {nuevo_estado_novedad} exitosamente'
            })
        else:
            return jsonify({'success': False, 'message': 'Error al procesar la novedad'}), 500

    except Exception as e:
        print(f"Error en gestionar_novedad: {e}")
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@solicitudes_bp.route('/api/novedades/pendientes')
def obtener_novedades_pendientes():
    """Obtiene novedades pendientes para usuarios con permisos"""
    if 'usuario_id' not in session:
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    # Verificar permisos usando la lógica del sistema de permisos
    rol_usuario = session.get('rol', '').lower()
    puede_gestionar_novedad = rol_usuario in ['administrador', 'lider_inventario', 'aprobador']
    
    if not puede_gestionar_novedad:
        return jsonify({'success': False, 'message': 'No tiene permisos'}), 403

    try:
        novedades = NovedadModel.obtener_novedades_pendientes()
        return jsonify({'success': True, 'novedades': novedades})
    except Exception as e:
        print(f"Error en obtener_novedades_pendientes: {e}")
        return jsonify({'success': False, 'message': 'Error interno'}), 500