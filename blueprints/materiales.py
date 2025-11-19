# blueprints/materiales.py

from __future__ import annotations

# Standard library
import os
from datetime import datetime

# Third-party
from flask import Blueprint, render_template, request, redirect, session, flash, url_for, current_app
from werkzeug.utils import secure_filename

# Local
from models.materiales_model import MaterialModel
from models.oficinas_model import OficinaModel
from utils.permissions import can_access
from utils.filters import verificar_acceso_oficina

materiales_bp = Blueprint('materiales', __name__, url_prefix='/materiales')


def _require_login() -> bool:
    return 'usuario_id' in session


@materiales_bp.route('/', methods=['GET'])
def listar_materiales():
    """Listar todos los materiales (protegido por permisos)."""
    if not can_access('materiales', 'view'):
        flash('❌ No tienes permisos para acceder a materiales', 'danger')
        print(f"🚫 Acceso denegado a /materiales - Usuario: {session.get('usuario_nombre')}")
        return redirect('/dashboard')

    try:
        print("📦 Cargando lista de materiales...")
        materiales = MaterialModel.obtener_todos() or []
        print(f"📦 Se cargaron {len(materiales)} materiales para mostrar")
        return render_template('materials/listar.html', materiales=materiales)
    except Exception as e:
        print(f"❌ Error obteniendo materiales: {e}")
        flash('Error al cargar los materiales', 'danger')
        return render_template('materials/listar.html', materiales=[])


@materiales_bp.route('/crear', methods=['GET', 'POST'])
def crear_material():
    if not _require_login():
        return redirect('/login')

    if not can_access('materiales', 'view'):
        flash('No tiene permisos para acceder a esta sección', 'danger')
        return redirect('/dashboard')

    if request.method == 'GET':
        return render_template('materials/crear.html')

    # PROCESAMIENTO DEL MÉTODO POST
    try:
        # Obtener la oficina del usuario actual
        oficina_id = session.get('oficina_id')
        if not oficina_id:
            flash('No se pudo determinar su oficina', 'danger')
            return render_template('materials/crear.html')

        # Obtener la lista de materiales del formulario
        materiales_creados = 0
        errores = 0

        # Contar cuántos materiales se enviaron
        indices = set()
        for key in request.form:
            if key.startswith('nombre_'):
                indices.add(key.split('_')[1])

        for idx in indices:
            nombre = request.form.get(f'nombre_{idx}')
            valor_unitario = request.form.get(f'valor_unitario_{idx}')
            cantidad = request.form.get(f'cantidad_{idx}')
            imagen = request.files.get(f'imagen_{idx}')

            # Validaciones básicas
            if not nombre or not valor_unitario or not cantidad:
                flash(f'Material {int(idx)+1}: Faltan campos obligatorios', 'danger')
                errores += 1
                continue

            try:
                valor_unitario_float = float(valor_unitario)
                cantidad_int = int(cantidad)
            except ValueError:
                flash(f'Material {int(idx)+1}: Valor unitario o cantidad no válidos', 'danger')
                errores += 1
                continue

            # Procesar la imagen - CORRECCIÓN: Guardar en static/uploads
            ruta_imagen = None
            if imagen and imagen.filename:
                filename = secure_filename(imagen.filename)
                # Guardar con un nombre único para evitar colisiones
                unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                
                # Asegurar que el directorio de uploads existe
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                
                filepath = os.path.join(upload_folder, unique_filename)
                imagen.save(filepath)
                
                # Guardar solo el nombre del archivo, no la ruta completa
                ruta_imagen = unique_filename
                print(f"✅ Imagen guardada en: {filepath}")

            # Crear el material
            material_id = MaterialModel.crear(
                nombre=nombre,
                valor_unitario=valor_unitario_float,
                cantidad=cantidad_int,
                oficina_id=oficina_id,
                ruta_imagen=ruta_imagen,
                usuario_creador=session.get('usuario_nombre', 'Sistema')
            )

            if material_id:
                materiales_creados += 1
                print(f"✅ Material creado con ID: {material_id}")
            else:
                flash(f'Material {int(idx)+1}: Error al guardar en la base de datos', 'danger')
                errores += 1

        if materiales_creados > 0:
            flash(f'✅ Se crearon {materiales_creados} materiales correctamente', 'success')
        if errores > 0:
            flash(f'❌ No se pudieron crear {errores} materiales', 'danger')

        return redirect('/materiales')

    except Exception as e:
        print(f"❌ Error creando materiales: {e}")
        import traceback
        print(traceback.format_exc())
        flash('Error interno al crear los materiales', 'danger')
        return render_template('materials/crear.html')


# NUEVAS RUTAS PARA EDITAR Y ELIMINAR
@materiales_bp.route('/editar/<int:material_id>', methods=['GET', 'POST'])
def editar_material(material_id):
    """Editar un material existente"""
    if not _require_login():
        return redirect('/login')

    if not can_access('materiales', 'edit'):
        flash('No tiene permisos para editar materiales', 'danger')
        return redirect('/materiales')

    if request.method == 'GET':
        # Obtener el material por ID
        material = MaterialModel.obtener_por_id(material_id)
        if not material:
            flash('Material no encontrado', 'danger')
            return redirect('/materiales')
        
        # Verificar que el usuario tiene acceso a la oficina del material
        if not verificar_acceso_oficina(material.get('oficina_id')):
            flash('No tiene permisos para editar este material', 'danger')
            return redirect('/materiales')

        return render_template('materials/editar.html', material=material)

    # Procesar POST para actualizar
    try:
        # Validar que el material existe y el usuario tiene permisos
        material_existente = MaterialModel.obtener_por_id(material_id)
        if not material_existente:
            flash('Material no encontrado', 'danger')
            return redirect('/materiales')

        if not verificar_acceso_oficina(material_existente.get('oficina_id')):
            flash('No tiene permisos para editar este material', 'danger')
            return redirect('/materiales')

        # Obtener datos del formulario
        nombre = request.form.get('nombre')
        valor_unitario = request.form.get('valor_unitario')
        cantidad = request.form.get('cantidad')
        imagen = request.files.get('imagen')

        # Validaciones
        if not nombre or not valor_unitario or not cantidad:
            flash('Todos los campos excepto la imagen son obligatorios', 'danger')
            return render_template('materials/editar.html', material=material_existente)

        try:
            valor_unitario_float = float(valor_unitario)
            cantidad_int = int(cantidad)
        except ValueError:
            flash('Valor unitario o cantidad no válidos', 'danger')
            return render_template('materials/editar.html', material=material_existente)

        # Procesar imagen si se subió una nueva
        ruta_imagen = material_existente.get('ruta_imagen')
        if imagen and imagen.filename:
            filename = secure_filename(imagen.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            
            # Asegurar que el directorio de uploads existe
            upload_folder = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_folder, exist_ok=True)
            
            filepath = os.path.join(upload_folder, unique_filename)
            imagen.save(filepath)
            ruta_imagen = unique_filename
            print(f"✅ Nueva imagen guardada en: {filepath}")

        # Actualizar el material
        actualizado = MaterialModel.actualizar(
            material_id=material_id,
            nombre=nombre,
            valor_unitario=valor_unitario_float,
            cantidad=cantidad_int,
            oficina_id=material_existente.get('oficina_id'),
            ruta_imagen=ruta_imagen
        )

        if actualizado:
            flash('✅ Material actualizado correctamente', 'success')
        else:
            flash('❌ Error al actualizar el material', 'danger')

        return redirect('/materiales')

    except Exception as e:
        print(f"❌ Error editando material: {e}")
        import traceback
        print(traceback.format_exc())
        flash('Error interno al actualizar el material', 'danger')
        return redirect('/materiales')


@materiales_bp.route('/eliminar/<int:material_id>', methods=['POST'])
def eliminar_material(material_id):
    """Eliminar (desactivar) un material"""
    if not _require_login():
        return redirect('/login')

    if not can_access('materiales', 'delete'):
        flash('No tiene permisos para eliminar materiales', 'danger')
        return redirect('/materiales')

    try:
        # Validar que el material existe y el usuario tiene permisos
        material = MaterialModel.obtener_por_id(material_id)
        if not material:
            flash('Material no encontrado', 'danger')
            return redirect('/materiales')

        if not verificar_acceso_oficina(material.get('oficina_id')):
            flash('No tiene permisos para eliminar este material', 'danger')
            return redirect('/materiales')

        # Eliminar (desactivar) el material
        eliminado = MaterialModel.eliminar(material_id)
        if eliminado:
            flash('✅ Material eliminado correctamente', 'success')
        else:
            flash('❌ Error al eliminar el material', 'danger')

        return redirect('/materiales')

    except Exception as e:
        print(f"❌ Error eliminando material: {e}")
        flash('Error interno al eliminar el material', 'danger')
        return redirect('/materiales')