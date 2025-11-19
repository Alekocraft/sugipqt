from flask import Blueprint, render_template, request, redirect, session, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from models.inventario_corporativo_model import InventarioCorporativoModel
from utils.permissions import can_access, can_manage_inventario_corporativo, can_view_inventario_actions
import os
import pandas as pd
from io import BytesIO
from datetime import datetime

# =====================================================
# BLUEPRINT — FIX PROFESIONAL PARA PLANTILLAS
# =====================================================
inventario_corporativo_bp = Blueprint(
    'inventario_corporativo',
    __name__,
    template_folder='templates'  # 🔥 CLAVE PARA CARGAR /inventario_corporativo/crear.html
)


# =========================
#  HELPERS DE AUTENTICACIÓN
# =========================
def _require_login():
    return 'usuario_id' in session


# ==========================================================
# LISTAR INVENTARIO CORPORATIVO CON ESTADÍSTICAS COMPLETAS
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo')
def listar_inventario_corporativo():
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_todos() or []

    valor_total = sum(p.get('valor_unitario', 0) * p.get('cantidad', 0) for p in productos)
    productos_bajo_stock = len([p for p in productos if p.get('cantidad', 0) <= p.get('cantidad_minima', 5)])
    productos_asignables = len([p for p in productos if p.get('es_asignable')])

    return render_template(
        'inventario_corporativo/listar.html',
        productos=productos,
        total_productos=len(productos),
        valor_total_inventario=valor_total,
        productos_bajo_stock=productos_bajo_stock,
        productos_asignables=productos_asignables,
        puede_gestionar_inventario=can_manage_inventario_corporativo(),
        puede_ver_acciones_inventario=can_view_inventario_actions()
    )


# ==========================================================
#  DETALLE DE PRODUCTO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/<int:producto_id>')
def ver_detalle_producto(producto_id):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'view'):
        flash('No autorizado para ver productos', 'danger')
        return redirect('/inventario-corporativo')

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect('/inventario-corporativo')

    historial = InventarioCorporativoModel.historial_asignaciones(producto_id) or []

    return render_template(
        'inventario_corporativo/detalle.html',
        producto=producto,
        historial=historial,
        puede_gestionar_inventario=can_manage_inventario_corporativo()
    )


# ==========================================================
#  CREAR PRODUCTO CORPORATIVO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/crear', methods=['GET', 'POST'])
def crear_inventario_corporativo():
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'create'):
        flash('No autorizado para crear productos', 'danger')
        return redirect('/inventario-corporativo')

    categorias = InventarioCorporativoModel.obtener_categorias() or []
    proveedores = InventarioCorporativoModel.obtener_proveedores() or []

    if request.method == 'POST':
        try:
            # Validar que hay categorías y proveedores disponibles
            if not categorias or not proveedores:
                flash('Error: No hay categorías o proveedores disponibles. Contacte al administrador.', 'danger')
                return render_template('inventario_corporativo/crear.html', 
                                    categorias=categorias, 
                                    proveedores=proveedores)

            nombre = request.form.get('nombre', '').strip()
            categoria_id = int(request.form.get('categoria_id') or 0)
            proveedor_id = int(request.form.get('proveedor_id') or 0)
            valor_unitario = float(request.form.get('valor_unitario') or 0)
            cantidad = int(request.form.get('cantidad') or 0)
            cantidad_minima = int(request.form.get('cantidad_minima') or 5)
            ubicacion = request.form.get('ubicacion', 'COQ').strip()
            descripcion = request.form.get('descripcion', '').strip()
            es_asignable = 1
            usuario_creador = session.get('usuario', 'Sistema')

            # Validaciones básicas
            if not nombre:
                flash('El nombre del producto es requerido', 'danger')
                return render_template('inventario_corporativo/crear.html', 
                                    categorias=categorias, 
                                    proveedores=proveedores)
            
            if categoria_id == 0:
                flash('Debe seleccionar una categoría', 'danger')
                return render_template('inventario_corporativo/crear.html', 
                                    categorias=categorias, 
                                    proveedores=proveedores)
            
            if proveedor_id == 0:
                flash('Debe seleccionar un proveedor', 'danger')
                return render_template('inventario_corporativo/crear.html', 
                                    categorias=categorias, 
                                    proveedores=proveedores)

            # Generar código automático
            codigo_unico = InventarioCorporativoModel.generar_codigo_unico()

            ruta_imagen = None
            archivo = request.files.get('imagen')
            if archivo and archivo.filename:
                filename = secure_filename(archivo.filename)
                upload_dir = os.path.join('static', 'uploads', 'productos')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                archivo.save(filepath)
                ruta_imagen = '/' + filepath.replace('\\', '/')

            nuevo_id = InventarioCorporativoModel.crear(
                codigo_unico=codigo_unico,
                nombre=nombre,
                descripcion=descripcion,
                categoria_id=categoria_id,
                proveedor_id=proveedor_id,
                valor_unitario=valor_unitario,
                cantidad=cantidad,
                cantidad_minima=cantidad_minima,
                ubicacion=ubicacion,
                es_asignable=es_asignable,
                usuario_creador=usuario_creador,
                ruta_imagen=ruta_imagen
            )

            if nuevo_id:
                flash('Producto creado correctamente.', 'success')
                return redirect('/inventario-corporativo')
            else:
                flash('No fue posible crear el producto. Verifique los datos.', 'danger')

        except ValueError as e:
            print(f"[ERROR VALOR] {e}")
            flash('Error en los datos numéricos. Verifique los valores.', 'danger')
        except Exception as e:
            print(f"[ERROR CREAR] {e}")
            flash('Ocurrió un error al guardar el producto.', 'danger')

    return render_template(
        'inventario_corporativo/crear.html',
        categorias=categorias,
        proveedores=proveedores
    )


# ==========================================================
# EDITAR PRODUCTO CORPORATIVO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/editar/<int:producto_id>', methods=['GET', 'POST'])
def editar_producto_corporativo(producto_id):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'edit'):
        flash('No autorizado', 'danger')
        return redirect('/inventario-corporativo')

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect('/inventario-corporativo')

    categorias = InventarioCorporativoModel.obtener_categorias() or []
    proveedores = InventarioCorporativoModel.obtener_proveedores() or []

    if request.method == 'POST':
        try:
            codigo_unico = request.form.get('codigo_unico', '').strip()
            nombre = request.form.get('nombre', '').strip()
            categoria_id = int(request.form.get('categoria_id') or 0)
            proveedor_id = int(request.form.get('proveedor_id') or 0)
            valor_unitario = float(request.form.get('valor_unitario') or 0)
            cantidad = int(request.form.get('cantidad') or 0)
            cantidad_minima = int(request.form.get('cantidad_minima') or 5)
            ubicacion = request.form.get('ubicacion', '').strip()
            descripcion = request.form.get('descripcion', '').strip()
            es_asignable = 1 if request.form.get('es_asignable') == 'on' else 0

            ruta_imagen = producto.get('ruta_imagen')
            archivo = request.files.get('imagen')

            if archivo and archivo.filename:
                filename = secure_filename(archivo.filename)
                upload_dir = os.path.join('static', 'uploads', 'productos')
                os.makedirs(upload_dir, exist_ok=True)
                filepath = os.path.join(upload_dir, filename)
                archivo.save(filepath)
                ruta_imagen = '/' + filepath.replace('\\', '/')

            actualizado = InventarioCorporativoModel.actualizar(
                producto_id=producto_id,
                codigo_unico=codigo_unico,
                nombre=nombre,
                descripcion=descripcion,
                categoria_id=categoria_id,
                proveedor_id=proveedor_id,
                valor_unitario=valor_unitario,
                cantidad=cantidad,
                cantidad_minima=cantidad_minima,
                ubicacion=ubicacion,
                es_asignable=es_asignable,
                ruta_imagen=ruta_imagen
            )

            if actualizado:
                flash('Producto actualizado correctamente.', 'success')
                return redirect(f'/inventario-corporativo/{producto_id}')

            flash('No fue posible actualizar el producto.', 'danger')

        except Exception as e:
            print(f"[ERROR EDITAR] {e}")
            flash('Error al actualizar el producto.', 'danger')

    return render_template(
        'inventario_corporativo/editar.html',
        producto=producto,
        categorias=categorias,
        proveedores=proveedores
    )


# ==========================================================
# ASIGNAR PRODUCTO CORPORATIVO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/asignar/<int:producto_id>', methods=['GET', 'POST'])
def asignar_producto_corporativo(producto_id):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'assign'):
        flash('No autorizado', 'danger')
        return redirect('/inventario-corporativo')

    producto = InventarioCorporativoModel.obtener_por_id(producto_id)
    if not producto:
        flash('Producto no encontrado', 'danger')
        return redirect('/inventario-corporativo')

    if not producto.get('es_asignable'):
        flash('Este producto no es asignable.', 'warning')
        return redirect(f'/inventario-corporativo/{producto_id}')

    oficinas = InventarioCorporativoModel.obtener_oficinas() or []
    historial = InventarioCorporativoModel.historial_asignaciones(producto_id) or []

    if request.method == 'POST':
        try:
            oficina_id = int(request.form.get('oficina_id') or 0)
            cantidad_asignar = int(request.form.get('cantidad') or 0)

            if cantidad_asignar > producto.get('cantidad', 0):
                flash('No hay suficiente stock.', 'danger')
                return redirect(request.url)

            asignado = InventarioCorporativoModel.asignar_a_oficina(
                producto_id=producto_id,
                oficina_id=oficina_id,
                cantidad=cantidad_asignar,
                usuario_accion=session.get('usuario', 'Sistema')
            )

            if asignado:
                flash('Producto asignado correctamente.', 'success')
                return redirect(f'/inventario-corporativo/{producto_id}')

            flash('No se pudo asignar el producto.', 'danger')

        except Exception as e:
            print(f"[ERROR ASIGNAR] {e}")
            flash('Error al asignar producto.', 'danger')

    return render_template(
        'inventario_corporativo/asignar.html',
        producto=producto,
        oficinas=oficinas,
        historial=historial
    )


# ==========================================================
# ELIMINAR PRODUCTO CORPORATIVO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/eliminar/<int:producto_id>', methods=['POST'])
def eliminar_producto_corporativo(producto_id):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'delete'):
        flash('No autorizado', 'danger')
        return redirect('/inventario-corporativo')

    try:
        eliminado = InventarioCorporativoModel.eliminar(
            producto_id=producto_id,
            usuario_accion=session.get('usuario', 'Sistema')
        )

        flash('Producto eliminado correctamente.' if eliminado else 'No fue posible eliminar el producto.',
              'success' if eliminado else 'danger')

    except Exception as e:
        print(f"[ERROR ELIMINAR] {e}")
        flash('Error al eliminar producto.', 'danger')

    return redirect('/inventario-corporativo')


# ==========================================================
# FILTROS
# ==========================================================
def aplicar_filtros(productos, oficina, categoria, stock):
    filtrados = productos

    if oficina:
        filtrados = [p for p in filtrados if p.get('oficina') == oficina]

    if categoria:
        filtrados = [p for p in filtrados if p.get('categoria') == categoria]

    if stock == 'bajo':
        filtrados = [p for p in filtrados if p.get('cantidad') <= p.get('cantidad_minima')]
    elif stock == 'sin':
        filtrados = [p for p in filtrados if p.get('cantidad') == 0]
    elif stock == 'normal':
        filtrados = [p for p in filtrados if p.get('cantidad') > p.get('cantidad_minima')]

    return filtrados


# ==========================================================
# LISTADO CON FILTROS
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/filtrado/<tipo>')
def listar_inventario_corporativo_filtrado(tipo):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'view'):
        flash('No autorizado', 'danger')
        return redirect('/dashboard')

    oficina = request.args.get('oficina', '').strip()
    categoria = request.args.get('categoria', '').strip()
    stock = request.args.get('stock', '').strip()

    productos = InventarioCorporativoModel.obtener_todos_con_oficina() or []

    if tipo == 'sede':
        productos = [p for p in productos if p.get('oficina') == 'Sede Principal']
    elif tipo == 'oficinas':
        productos = [p for p in productos if p.get('oficina') != 'Sede Principal']

    productos = aplicar_filtros(productos, oficina, categoria, stock)

    oficinas = InventarioCorporativoModel.obtener_oficinas() or []
    categorias = InventarioCorporativoModel.obtener_categorias() or []

    return render_template(
        'inventario_corporativo/listar_con_filtros.html',
        productos=productos,
        oficinas_filtradas=oficinas,
        categorias=categorias,
        filtro_oficina=oficina,
        filtro_categoria=categoria,
        filtro_stock=stock,
        titulo=tipo,
        subtitulo="Inventario filtrado",
        total_productos=len(productos)
    )


# ==========================================================
# EXPORTAR A EXCEL
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/exportar/excel/<tipo>')
def exportar_inventario_corporativo_excel(tipo):
    if not _require_login():
        return redirect('/login')

    if not can_access('inventario_corporativo', 'view'):
        flash('No autorizado', 'danger')
        return redirect('/inventario-corporativo')

    productos = InventarioCorporativoModel.obtener_todos_con_oficina() or []

    df = pd.DataFrame(productos)

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return send_file(output, download_name='inventario_corporativo.xlsx', as_attachment=True)


# ==========================================================
# API ESTADISTICAS COMPLETAS
# ==========================================================
@inventario_corporativo_bp.route('/api/inventario-corporativo/estadisticas')
def api_estadisticas_inventario():
    if not _require_login():
        return jsonify({'error': 'No autorizado'}), 401

    try:
        productos = InventarioCorporativoModel.obtener_todos() or []
        
        total_productos = len(productos)
        valor_total = sum(p.get('valor_unitario', 0) * p.get('cantidad', 0) for p in productos)
        stock_bajo = len([p for p in productos if p.get('cantidad', 0) <= p.get('cantidad_minima', 5)])
        
        return jsonify({
            "total_productos": total_productos,
            "valor_total": valor_total,
            "stock_bajo": stock_bajo
        })
        
    except Exception as e:
        print(f"Error en API estadísticas: {e}")
        return jsonify({
            "total_productos": 0,
            "valor_total": 0,
            "stock_bajo": 0
        })


# ==========================================================
# VISTAS ESPECÍFICAS POR TIPO
# ==========================================================
@inventario_corporativo_bp.route('/inventario-corporativo/sede-principal')
def listar_sede_principal():
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_por_sede_principal() or []
    
    valor_total = sum(p.get('valor_unitario', 0) * p.get('cantidad', 0) for p in productos)
    productos_bajo_stock = len([p for p in productos if p.get('cantidad', 0) <= p.get('cantidad_minima', 5)])
    total_oficinas = len(set(p.get('oficina') for p in productos if p.get('oficina')))

    return render_template(
        'inventario_corporativo/listar_con_filtros.html',
        productos=productos,
        oficinas_filtradas=InventarioCorporativoModel.obtener_oficinas() or [],
        categorias=InventarioCorporativoModel.obtener_categorias() or [],
        filtro_oficina='',
        filtro_categoria='',
        filtro_stock='',
        titulo='Sede Principal',
        subtitulo='Productos de la sede principal',
        total_productos=len(productos),
        valor_total=valor_total,
        productos_bajo_stock=productos_bajo_stock,
        total_oficinas=total_oficinas,
        tipo='sede',
        puede_gestionar_inventario=can_manage_inventario_corporativo(),
        puede_ver_acciones_inventario=can_view_inventario_actions()
    )


@inventario_corporativo_bp.route('/inventario-corporativo/oficinas-servicio')
def listar_oficinas_servicio():
    if not _require_login():
        return redirect('/login')

    productos = InventarioCorporativoModel.obtener_por_oficinas_servicio() or []
    
    valor_total = sum(p.get('valor_unitario', 0) * p.get('cantidad', 0) for p in productos)
    productos_bajo_stock = len([p for p in productos if p.get('cantidad', 0) <= p.get('cantidad_minima', 5)])
    total_oficinas = len(set(p.get('oficina') for p in productos if p.get('oficina')))

    return render_template(
        'inventario_corporativo/listar_con_filtros.html',
        productos=productos,
        oficinas_filtradas=InventarioCorporativoModel.obtener_oficinas() or [],
        categorias=InventarioCorporativoModel.obtener_categorias() or [],
        filtro_oficina='',
        filtro_categoria='',
        filtro_stock='',
        titulo='Oficinas de Servicio',
        subtitulo='Productos en oficinas de servicio',
        total_productos=len(productos),
        valor_total=valor_total,
        productos_bajo_stock=productos_bajo_stock,
        total_oficinas=total_oficinas,
        tipo='oficinas',
        puede_gestionar_inventario=can_manage_inventario_corporativo(),
        puede_ver_acciones_inventario=can_view_inventario_actions()
    )