import os
import logging
from werkzeug.utils import secure_filename
from models.novedades_model import NovedadModel

# Configuración de logging
logger = logging.getLogger(__name__)

# Configuración para carga de imágenes
UPLOAD_FOLDER_NOVEDADES = 'static/images/novedades'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Valida si la extensión del archivo está permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Crear directorio si no existe
os.makedirs(UPLOAD_FOLDER_NOVEDADES, exist_ok=True)

@solicitudes_bp.route('/registrar-novedad', methods=['POST'])
@login_required
def registrar_novedad():
    """
    Registra una nueva novedad asociada a una solicitud
    Permite adjuntar una imagen como evidencia
    """
    try:
        solicitud_id = request.form.get('solicitud_id')
        tipo_novedad = request.form.get('tipo_novedad')
        descripcion = request.form.get('descripcion')
        cantidad_afectada = request.form.get('cantidad_afectada')
        usuario_id = session.get('user_id')
        
        # Validación de campos obligatorios
        if not all([solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id]):
            logger.warning(f'Intento de registro de novedad con datos incompletos. Usuario: {usuario_id}')
            return jsonify({'success': False, 'error': 'Faltan datos requeridos'}), 400
        
        # Procesamiento de imagen adjunta
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
                logger.info(f'Imagen guardada para novedad: {filename}')
        
        # Inserción en base de datos
        conn = get_database_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO NovedadesSolicitudes 
            (SolicitudId, TipoNovedad, Descripcion, CantidadAfectada, UsuarioRegistra, FechaRegistro, EstadoNovedad, RutaImagen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_id, datetime.now(), 'Registrada', ruta_imagen))
        
        conn.commit()
        
        logger.info(f'Novedad registrada exitosamente. Solicitud ID: {solicitud_id}, Usuario: {usuario_id}')
        return jsonify({
            'success': True, 
            'message': 'Novedad registrada correctamente'
        })
        
    except Exception as e:
        logger.error(f'Error al registrar novedad: {str(e)}', exc_info=True)
        return jsonify({'success': False, 'error': 'Error interno del servidor'}), 500
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

@solicitudes_bp.route('/gestionar-novedad', methods=['POST'])
@login_required
def gestionar_novedad():
    """
    Gestiona una novedad existente (aceptar/rechazar)
    Actualiza el estado tanto de la novedad como de la solicitud asociada
    """
    try:
        solicitud_id = request.form.get('solicitud_id')
        accion = request.form.get('accion')
        observaciones = request.form.get('observaciones', '')
        
        if not all([solicitud_id, accion]):
            logger.warning(f'Intento de gestión de novedad con datos incompletos')
            return jsonify({'success': False, 'message': 'Datos incompletos'}), 400

        # Obtener la novedad más reciente de la solicitud
        novedades = NovedadModel.obtener_por_solicitud(int(solicitud_id))
        if not novedades:
            logger.warning(f'No se encontraron novedades para la solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'No se encontró novedad para esta solicitud'}), 404

        novedad = novedades[0]
        usuario_gestion = session.get('usuario_nombre')

        # Determinar estados según la acción
        if accion == 'aceptar':
            nuevo_estado_novedad = 'aceptada'
            nuevo_estado_solicitud = 9  # novedad_aceptada
            log_action = 'aceptada'
        else:
            nuevo_estado_novedad = 'rechazada'
            nuevo_estado_solicitud = 10  # novedad_rechazada
            log_action = 'rechazada'

        # Actualizar estado de la novedad
        success_novedad = NovedadModel.actualizar_estado(
            novedad_id=novedad['novedad_id'],
            estado=nuevo_estado_novedad,
            usuario_resuelve=usuario_gestion,
            observaciones_resolucion=observaciones
        )

        # Actualizar estado de la solicitud
        success_solicitud = SolicitudModel.actualizar_estado_solicitud(
            int(solicitud_id), 
            nuevo_estado_solicitud
        )

        if success_novedad and success_solicitud:
            logger.info(f'Novedad {log_action}. Solicitud ID: {solicitud_id}, Usuario: {usuario_gestion}')
            return jsonify({
                'success': True, 
                'message': f'Novedad {nuevo_estado_novedad} exitosamente'
            })
        else:
            logger.error(f'Error al procesar novedad. Solicitud ID: {solicitud_id}')
            return jsonify({'success': False, 'message': 'Error al procesar la novedad'}), 500

    except Exception as e:
        logger.error(f'Error en gestión de novedad: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500

@solicitudes_bp.route('/api/novedades/pendientes')
def obtener_novedades_pendientes():
    """
    Obtiene todas las novedades en estado pendiente
    Requiere permisos específicos de gestión
    """
    if 'usuario_id' not in session:
        logger.warning('Intento de acceso no autorizado a novedades pendientes')
        return jsonify({'success': False, 'message': 'No autorizado'}), 401

    # Verificación de permisos
    rol_usuario = session.get('rol', '').lower()
    roles_permitidos = ['administrador', 'lider_inventario', 'aprobador']
    puede_gestionar_novedad = rol_usuario in roles_permitidos
    
    if not puede_gestionar_novedad:
        logger.warning(f'Usuario sin permisos intentó acceder a novedades. Rol: {rol_usuario}')
        return jsonify({'success': False, 'message': 'No tiene permisos'}), 403

    try:
        novedades = NovedadModel.obtener_novedades_pendientes()
        logger.info(f'Consulta de novedades pendientes. Usuario: {session.get("usuario_id")}')
        return jsonify({'success': True, 'novedades': novedades})
    except Exception as e:
        logger.error(f'Error al obtener novedades pendientes: {e}', exc_info=True)
        return jsonify({'success': False, 'message': 'Error interno del servidor'}), 500