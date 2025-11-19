# blueprints/oficinas.py

from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from models.oficinas_model import OficinaModel
from utils.permissions import can_access

oficinas_bp = Blueprint('oficinas', __name__, url_prefix='/oficinas')

def _require_login():
    return 'usuario_id' in session

@oficinas_bp.route('/')
def listar_oficinas():
    """Listar todas las oficinas"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('oficinas', 'view'):
        flash('No tienes permisos para acceder a esta sección', 'danger')
        return redirect('/dashboard')
    
    try:
        oficinas = OficinaModel.obtener_todas()
        return render_template('oficinas/listar.html', oficinas=oficinas)
    except Exception as e:
        print(f"Error al obtener oficinas: {e}")
        flash('Error al cargar las oficinas', 'danger')
        return render_template('oficinas/listar.html', oficinas=[])

@oficinas_bp.route('/crear', methods=['GET', 'POST'])
def crear_oficina():
    """Crear una nueva oficina"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('oficinas', 'create'):
        flash('No tienes permisos para crear oficinas', 'danger')
        return redirect('/oficinas')
    
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            director = request.form.get('director')
            ubicacion = request.form.get('ubicacion')
            email = request.form.get('email')
            es_principal = bool(request.form.get('es_principal'))
            
            if not nombre or not director or not ubicacion:
                flash('Todos los campos obligatorios deben ser completados', 'danger')
                return render_template('oficinas/crear.html')
            
            oficina_id = OficinaModel.crear(
                nombre=nombre,
                director=director,
                ubicacion=ubicacion,
                email=email,
                es_principal=es_principal
            )
            
            if oficina_id:
                flash('Oficina creada exitosamente', 'success')
                return redirect('/oficinas')
            else:
                flash('Error al crear la oficina', 'danger')
                return render_template('oficinas/crear.html')
                
        except Exception as e:
            print(f"Error al crear oficina: {e}")
            flash('Error interno al crear la oficina', 'danger')
            return render_template('oficinas/crear.html')
    
    return render_template('oficinas/crear.html')

@oficinas_bp.route('/editar/<int:oficina_id>', methods=['GET', 'POST'])
def editar_oficina(oficina_id):
    """Editar una oficina existente"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('oficinas', 'edit'):
        flash('No tienes permisos para editar oficinas', 'danger')
        return redirect('/oficinas')
    
    if request.method == 'POST':
        try:
            nombre = request.form.get('nombre')
            director = request.form.get('director')
            ubicacion = request.form.get('ubicacion')
            email = request.form.get('email')
            es_principal = bool(request.form.get('es_principal'))
            
            if not nombre or not director or not ubicacion:
                flash('Todos los campos obligatorios deben ser completados', 'danger')
                return redirect(f'/oficinas/editar/{oficina_id}')
            
            actualizado = OficinaModel.actualizar(
                oficina_id=oficina_id,
                nombre=nombre,
                director=director,
                ubicacion=ubicacion,
                email=email,
                es_principal=es_principal
            )
            
            if actualizado:
                flash('Oficina actualizada exitosamente', 'success')
            else:
                flash('Error al actualizar la oficina', 'danger')
                
            return redirect('/oficinas')
            
        except Exception as e:
            print(f"Error al actualizar oficina: {e}")
            flash('Error interno al actualizar la oficina', 'danger')
            return redirect(f'/oficinas/editar/{oficina_id}')
    
    try:
        oficina = OficinaModel.obtener_por_id(oficina_id)
        if not oficina:
            flash('Oficina no encontrada', 'danger')
            return redirect('/oficinas')
        
        return render_template('oficinas/editar.html', oficina=oficina)
    except Exception as e:
        print(f"Error al obtener oficina: {e}")
        flash('Error al cargar la oficina', 'danger')
        return redirect('/oficinas')

@oficinas_bp.route('/eliminar/<int:oficina_id>', methods=['POST'])
def eliminar_oficina(oficina_id):
    """Eliminar una oficina"""
    if not _require_login():
        return redirect('/login')
    
    if not can_access('oficinas', 'delete'):
        flash('No tienes permisos para eliminar oficinas', 'danger')
        return redirect('/oficinas')
    
    try:
        eliminado = OficinaModel.eliminar(oficina_id)
        if eliminado:
            flash('Oficina eliminada exitosamente', 'success')
        else:
            flash('Error al eliminar la oficina', 'danger')
    except Exception as e:
        print(f"Error al eliminar oficina: {e}")
        flash('Error interno al eliminar la oficina', 'danger')
    
    return redirect('/oficinas')

@oficinas_bp.route('/api/oficinas')
def api_oficinas():
    """API para obtener todas las oficinas (para selectores)"""
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        oficinas = OficinaModel.obtener_todas()
        oficinas_data = [{
            'id': oficina['id'],
            'nombre': oficina['nombre'],
            'director': oficina['director'],
            'ubicacion': oficina['ubicacion']
        } for oficina in oficinas]
        
        return jsonify(oficinas_data)
    except Exception as e:
        print(f"Error en API oficinas: {e}")
        return jsonify({'error': 'Error interno del servidor'}), 500