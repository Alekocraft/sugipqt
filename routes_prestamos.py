# routes_prestamos.py
from flask import (
    Blueprint, render_template, request, redirect, session, flash, 
    send_file, url_for, jsonify, current_app
)
from datetime import datetime
from decimal import Decimal
from io import BytesIO
import os
from werkzeug.utils import secure_filename

# Import defensivo (para no romper el arranque si no están instalados)
try:
    import pandas as pd
    HAS_PANDAS = True
except Exception:
    pd = None
    HAS_PANDAS = False

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle, SimpleDocTemplate, Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    HAS_REPORTLAB = True
except Exception:
    HAS_REPORTLAB = False

# Tu helper de conexión (pyodbc / SQL Server)
from database import get_database_connection
from utils.permissions import can_view_actions

bp_prestamos = Blueprint('prestamos', __name__, url_prefix='/prestamos')

# ==========================================================
# Helpers de sesión / permisos
# ==========================================================
def _require_login():
    return 'usuario_id' in session

def _has_role(*roles):
    rol = (session.get('rol', '') or '').strip().lower()
    return rol in [r.lower() for r in roles]

# ==========================================================
# Helpers de imágenes (detección de columna y normalización URL)
# ==========================================================
IMG_COLS = ["RutaImagen", "ImagenURL", "ImagenUrl", "Imagen", "FotoURL", "FotoUrl", "Foto"]

def _detect_image_column(cur):
    """Detecta la primera columna de imagen disponible en ElementosPublicitarios."""
    cur.execute("SELECT TOP 1 * FROM dbo.ElementosPublicitarios")
    col_names = [d[0] for d in cur.description]
    for c in IMG_COLS:
        if c in col_names:
            return c
    return None

def _normalize_image_url(path_value: str) -> str:
    """Normaliza valores de imagen a una URL servible por Flask static."""
    if not path_value:
        return ""
    if isinstance(path_value, str) and path_value.startswith('http'):
        return path_value
    # si viene 'static/...' o relativo al static
    if isinstance(path_value, str) and path_value.startswith('static/'):
        rel = path_value.replace('static/', '')
        return url_for('static', filename=rel)
    if isinstance(path_value, str):
        # asumimos que es relativo a static_folder
        return url_for('static', filename=path_value)
    return ""

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ==========================================================
# Consultas (USANDO SOLO dbo.PrestamosElementos + ElementosPublicitarios)
# ==========================================================
def _fetch_estados_distintos():
    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT Estado
            FROM dbo.PrestamosElementos
            WHERE Activo = 1
            ORDER BY Estado
        """)
        return [row[0] for row in cur.fetchall() if row and row[0]]
    except Exception as e:
        print("Error leyendo estados:", e)
        return []
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

def _fetch_prestamos(estado=None, oficina_id=None):
    """Lista préstamos con filtro opcional por estado y oficina."""
    conn = cur = None
    rows_out = []
    try:
        conn = get_database_connection()
        cur = conn.cursor()

        sql = """
            SELECT 
                pe.PrestamoId               AS Id,
                pe.ElementoId               AS ElementoId,
                el.NombreElemento           AS Material,
                el.ValorUnitario            AS ValorUnitario,
                pe.CantidadPrestada         AS Cantidad,
                u.NombreUsuario             AS SolicitanteNombre,
                o.NombreOficina             AS OficinaNombre,
                pe.FechaPrestamo            AS Fecha,
                pe.FechaDevolucionPrevista  AS FechaPrevista,
                pe.Estado                   AS Estado,
                pe.Observaciones            AS Observaciones
            FROM dbo.PrestamosElementos pe
            INNER JOIN dbo.ElementosPublicitarios el
                ON el.ElementoId = pe.ElementoId
            INNER JOIN dbo.Usuarios u
                ON u.UsuarioId = pe.UsuarioSolicitanteId
            INNER JOIN dbo.Oficinas o
                ON o.OficinaId = pe.OficinaId
            WHERE pe.Activo = 1
        """
        params = []
        
        if oficina_id:
            sql += " AND pe.OficinaId = ?"
            params.append(oficina_id)
        
        if estado and estado.strip():
            sql += " AND pe.Estado = ?"
            params.append(estado.strip())

        sql += " ORDER BY pe.FechaPrestamo DESC"

        cur.execute(sql, params)
        rows = cur.fetchall()

        for r in rows:
            id_ = r[0]
            valor_unit = r[3] or 0
            cant = r[4] or 0
            subtotal = Decimal(valor_unit) * Decimal(cant)
            rows_out.append({
                'id': id_,
                'elemento_id': r[1],
                'material': r[2],
                'valor_unitario': Decimal(valor_unit),
                'cantidad': int(cant),
                'subtotal': subtotal,
                'solicitante_nombre': r[5] or 'N/A',
                'oficina_nombre': r[6] or 'N/A',
                'fecha': r[7],
                'fecha_prevista': r[8],
                'estado': r[9] or '',
                'observaciones': r[10] or '',
            })
    except Exception as e:
        print("Error leyendo préstamos:", e)
        flash(f"Error leyendo préstamos: {e}", "danger")
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass
    return rows_out

def _fetch_detalle(prestamo_id: int):
    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                pe.PrestamoId,
                pe.ElementoId,
                el.NombreElemento,
                el.ValorUnitario,
                pe.CantidadPrestada,
                u.NombreUsuario,
                o.NombreOficina,
                pe.FechaPrestamo,
                pe.FechaDevolucionPrevista,
                pe.FechaDevolucionReal,
                pe.Estado,
                pe.Observaciones
            FROM dbo.PrestamosElementos pe
            INNER JOIN dbo.ElementosPublicitarios el
                ON el.ElementoId = pe.ElementoId
            INNER JOIN dbo.Usuarios u
                ON u.UsuarioId = pe.UsuarioSolicitanteId
            INNER JOIN dbo.Oficinas o
                ON o.OficinaId = pe.OficinaId
            WHERE pe.PrestamoId = ? AND pe.Activo = 1
        """, (prestamo_id,))
        row = cur.fetchone()
        if not row:
            return None
        valor_unit = Decimal(row[3] or 0)
        cant = int(row[4] or 0)
        return {
            'id': row[0],
            'elemento_id': row[1],
            'material': row[2],
            'valor_unitario': valor_unit,
            'cantidad': cant,
            'subtotal': valor_unit * cant,
            'solicitante_nombre': row[5] or 'N/A',
            'oficina_nombre': row[6] or 'N/A',
            'fecha': row[7],
            'fecha_prevista': row[8],
            'fecha_real': row[9],
            'estado': row[10] or '',
            'observaciones': row[11] or '',
        }
    except Exception as e:
        print("Error leyendo detalle:", e)
        return None
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

# ==========================================================
# Rutas: Listar + Filtro + Export (Excel/PDF)
# ==========================================================
@bp_prestamos.get('/')
def listar_prestamos():
    if not _require_login():
        return redirect('/login')

    estado = request.args.get('estado', '').strip() or None
    
    # Filtro de oficina según permisos
    from utils.permissions import user_can_view_all
    oficina_id = None if user_can_view_all() else session.get('oficina_id')
    
    prestamos = _fetch_prestamos(estado, oficina_id)
    estados = _fetch_estados_distintos()

    return render_template(
        'prestamos/listar.html',
        prestamos=prestamos,
        filtro_estado=estado or '',
        estados=estados
    )

@bp_prestamos.get('/export')
def exportar():
    if not _require_login():
        return redirect('/login')

    estado = request.args.get('estado', '').strip() or None
    fmt = (request.args.get('fmt', 'xlsx') or 'xlsx').lower()  # 'xlsx' | 'pdf'

    # Respetar filtro de oficina
    from utils.permissions import user_can_view_all
    oficina_id = None if user_can_view_all() else session.get('oficina_id')

    data = _fetch_prestamos(estado, oficina_id)

    rows = [{
        'PrestamoId': d['id'],
        'Material': d['material'],
        'CantidadPrestada': d['cantidad'],
        'ValorUnitario': float(d['valor_unitario']),
        'Subtotal': float(d['subtotal']),
        'Solicitante': d['solicitante_nombre'],
        'Oficina': d['oficina_nombre'],
        'FechaPrestamo': d['fecha'],
        'FechaDevolucionPrevista': d['fecha_prevista'],
        'Estado': d['estado'],
        'Observaciones': d['observaciones'],
    } for d in data]

    if fmt == 'xlsx':
        if not HAS_PANDAS:
            flash('Exportar a Excel requiere pandas y openpyxl. Instálalos o usa PDF.', 'warning')
            return redirect(url_for('prestamos.listar_prestamos', estado=estado or ''))

        df = pd.DataFrame(rows)
        buf = BytesIO()
        # usar openpyxl (menor dependencia que xlsxwriter)
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Prestamos', index=False)
        buf.seek(0)
        fname = 'prestamos.xlsx' if not estado else f'prestamos_{estado}.xlsx'
        return send_file(
            buf,
            as_attachment=True,
            download_name=fname,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    if fmt == 'pdf':
        if not HAS_REPORTLAB:
            flash('Exportar a PDF requiere reportlab.', 'warning')
            return redirect(url_for('prestamos.listar_prestamos', estado=estado or ''))

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=landscape(A4),
            leftMargin=1*cm, rightMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm
        )

        styles = getSampleStyleSheet()
        title = Paragraph("Reporte de Préstamos", styles['Title'])
        subt = Paragraph(
            f"Estado: {estado or 'Todos'} — Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            styles['Normal']
        )

        headers = ['ID', 'Material', 'Cant', 'V.Unit', 'Subtotal', 'Solicitante', 'Oficina', 'Fecha', 'Prevista', 'Estado']
        body = [
            [
                d['PrestamoId'],
                d['Material'],
                d['CantidadPrestada'],
                f"{d['ValorUnitario']:.2f}",
                f"{d['Subtotal']:.2f}",
                d['Solicitante'],
                d['Oficina'],
                d['FechaPrestamo'].strftime('%Y-%m-%d %H:%M') if d['FechaPrestamo'] else '',
                d['FechaDevolucionPrevista'].strftime('%Y-%m-%d %H:%M') if d['FechaDevolucionPrevista'] else '',
                d['Estado']
            ]
            for d in rows
        ]
        table = Table(
            [headers] + body,
            colWidths=[1.2*cm, 6.5*cm, 1.2*cm, 2*cm, 2.4*cm, 2.2*cm, 2.0*cm, 3*cm, 3*cm, 2.5*cm]
        )
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e9ecef')),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('ALIGN', (2,1), (4,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.HexColor('#ced4da')),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8f9fa')]),
        ]))

        doc.build([title, subt, table])
        buf.seek(0)
        fname = 'prestamos.pdf' if not estado else f'prestamos_{estado}.pdf'
        return send_file(buf, as_attachment=True, download_name=fname, mimetype='application/pdf')

    # fallback
    flash('Formato no soportado. Usa fmt=xlsx o fmt=pdf', 'warning')
    return redirect(url_for('prestamos.listar_prestamos', estado=estado or ''))

# ==========================================================
# Rutas: Detalle (solo lectura)
# ==========================================================
@bp_prestamos.get('/<int:prestamo_id>')
def detalle(prestamo_id: int):
    if not _require_login():
        return redirect('/login')
    data = _fetch_detalle(prestamo_id)
    if not data:
        flash('Préstamo no encontrado', 'warning')
        return redirect(url_for('prestamos.listar_prestamos'))
    return render_template('prestamos/detalle.html', p=data)

# ==========================================================
# Rutas: Crear material / Crear préstamo (con sesión y nombres)
# ==========================================================
@bp_prestamos.get('/elementos/crearmaterial')
def crear_elemento_publicitario_get():
    if not _require_login():
        return redirect('/login')
    
    # ✅ VERIFICACIÓN: Restringir para oficinas específicas
    if _has_role('oficina_pereira', 'oficina_neiva', 'oficina_kennedy', 'oficina_bucaramanga', 
                 'oficina_polo_club', 'oficina_nogal', 'oficina_tunja', 'oficina_lourdes',
                 'oficina_cartagena', 'oficina_morato', 'oficina_medellin', 'oficina_cedritos'):
        flash('No tiene permisos para crear materiales publicitarios', 'danger')
        return redirect('/prestamos')
    
    if not _has_role('administrador', 'lider_inventario'):
        flash('No autorizado para crear materiales', 'danger')
        return redirect('/prestamos')

    return render_template('prestamos/elemento_crear.html')

@bp_prestamos.route('/elementos/crearmaterial', methods=['POST'], endpoint='crear_elemento_publicitario_post')
def crear_elemento_publicitario_post():
    if not _require_login():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'No autorizado'}), 401
        return redirect('/login')

    # 🔒 PROTECCIÓN CONTRA DOBLE ENVÍO (5 segundos)
    session_key = f"last_material_submit_{session.get('usuario_id')}"
    last_submit = session.get(session_key)
    current_time = datetime.now().timestamp()
    
    if last_submit and (current_time - last_submit) < 5:
        return jsonify({
            'success': False, 
            'message': '⚠️ Por favor espera unos segundos antes de enviar nuevamente'
        }), 429
    
    session[session_key] = current_time

    # ====== CAMPOS ======
    nombre_elemento = (request.form.get('nombre_elemento') or '').strip()
    valor_unitario_str = request.form.get('valor_unitario', '0')
    cantidad_disp_str = request.form.get('cantidad_disponible', '0')
    cantidad_minima_str = request.form.get('cantidad_minima', '0')
    imagen = request.files.get('imagen')

    # OFICINA FIJA: COQ (ID 1)
    oficina_id = 1
    usuario_nombre = (session.get('usuario_nombre') or 'administrador').strip()

    # ====== VALIDACIONES ======
    if not nombre_elemento:
        return jsonify({'success': False, 'message': 'El nombre es obligatorio'}), 400

    try:
        valor_unitario = float(valor_unitario_str) if valor_unitario_str else 0.0
        cantidad_disp = int(cantidad_disp_str) if cantidad_disp_str else 0
        cantidad_minima = int(cantidad_minima_str) if cantidad_minima_str else 0
    except ValueError:
        return jsonify({'success': False, 'message': 'Valores numéricos inválidos'}), 400

    if valor_unitario <= 0 or cantidad_disp < 0 or cantidad_minima < 0:
        return jsonify({'success': False, 'message': 'Valores deben ser mayores o iguales a 0'}), 400

    # ===========================================================
    # Guardar imagen
    # ===========================================================
    ruta_imagen = None
    if imagen and imagen.filename:
        if not allowed_file(imagen.filename):
            return jsonify({'success': False, 'message': 'Tipo de archivo no permitido. Use PNG, JPG, JPEG, GIF o WEBP.'}), 400
            
        filename = secure_filename(imagen.filename)
        upload_dir = os.path.join(current_app.static_folder, 'uploads', 'elementos')
        os.makedirs(upload_dir, exist_ok=True)
        path_file = os.path.join(upload_dir, filename)
        
        try:
            imagen.save(path_file)
            ruta_imagen = f'uploads/elementos/{filename}'
        except Exception as e:
            return jsonify({'success': False, 'message': f'Error al guardar imagen: {str(e)}'}), 500

    # ===========================================================
    # VERIFICAR SI YA EXISTE EL MATERIAL CON EL MISMO NOMBRE
    # ===========================================================
    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()

        # 🔒 INICIAR TRANSACCIÓN EXPLÍCITA
        conn.autocommit = False

        # =======================================================
        # VERIFICAR SI YA EXISTE UN MATERIAL CON EL MISMO NOMBRE EN LA MISMA OFICINA
        # =======================================================
        cur.execute("""
            SELECT ElementoId, NombreElemento, Activo 
            FROM dbo.ElementosPublicitarios 
            WHERE OficinaCreadoraId = ? AND LOWER(LTRIM(RTRIM(NombreElemento))) = LOWER(LTRIM(RTRIM(?)))
        """, (oficina_id, nombre_elemento))
        
        material_existente = cur.fetchone()

        if material_existente:
            elemento_id, nombre_existente, activo = material_existente
            conn.rollback()  # 🔒 IMPORTANTE: Rollback de la transacción
            
            if activo:
                mensaje = f'❌ Ya existe un material ACTIVO llamado "{nombre_elemento}" en esta oficina. (ID: {elemento_id})'
            else:
                mensaje = f'⚠️ Ya existe un material INACTIVO llamado "{nombre_elemento}" en esta oficina. (ID: {elemento_id})'

            return jsonify({
                'success': False,
                'message': mensaje
            }), 409

        # =======================================================
        # INSERT REAL - SOLO SI NO EXISTE DUPLICADO
        # =======================================================
        columnas = [
            "NombreElemento", "ValorUnitario", "CantidadDisponible", "CantidadMinima",
            "OficinaCreadoraId", "Activo", "FechaCreacion", "UsuarioCreador"
        ]
        valores = [
            nombre_elemento, valor_unitario, cantidad_disp, cantidad_minima,
            oficina_id, 1, datetime.now(), usuario_nombre
        ]

        if ruta_imagen:
            columnas.append("RutaImagen")
            valores.append(ruta_imagen)

        placeholders = ", ".join(["?"] * len(columnas))
        sql = f"INSERT INTO dbo.ElementosPublicitarios ({','.join(columnas)}) VALUES ({placeholders})"

        print("SQL:", sql)
        print("VALORES:", valores)

        cur.execute(sql, valores)
        
        # ✅ CONFIRMAR TRANSACCIÓN
        conn.commit()

        return jsonify({
            'success': True,
            'message': f'✅ Elemento "{nombre_elemento}" creado correctamente'
        })

    except Exception as e:
        # 🔒 ROLLBACK EN CASO DE ERROR
        try:
            if conn:
                conn.rollback()
        except:
            pass

        error_msg = str(e)
        
        # Manejar específicamente el error de duplicado
        if "2601" in error_msg and "UX_ElementosPublicitarios_Oficina_Nombre" in error_msg:
            return jsonify({
                'success': False,
                'message': f'❌ Ya existe un material con el nombre "{nombre_elemento}" en esta oficina.'
            }), 409
        else:
            return jsonify({'success': False, 'message': f'Error al crear material: {error_msg}'}), 500

    finally:
        try:
            # Restaurar autocommit
            if conn:
                conn.autocommit = True
            if cur: 
                cur.close()
            if conn: 
                conn.close()
        except:
            pass

@bp_prestamos.get('/crear')
def crear_prestamo_get():
    if not _require_login():
        return redirect('/login')

    # Datos del usuario/oficina desde la sesión
    solicitante_id = session.get('usuario_id', 0)
    solicitante_nombre = session.get('usuario_nombre', '—')
    oficina_id = session.get('oficina_id', 0)
    oficina_nombre = session.get('oficina_nombre', '—')

    # Fecha mínima para el calendario (hoy)
    fecha_minima = datetime.now().strftime('%Y-%m-%d')
    
    # Cargar elementos activos
    elementos = []
    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        img_col = _detect_image_column(cur)

        if img_col:
            cur.execute(f"""
                SELECT ElementoId, NombreElemento, ValorUnitario, CantidadDisponible, {img_col}
                FROM dbo.ElementosPublicitarios
                WHERE Activo = 1 AND CantidadDisponible > 0
                ORDER BY NombreElemento
            """)
            for (eid, nom, val, disp, img) in cur.fetchall():
                imagen_url = _normalize_image_url(img)
                elementos.append({
                    'id': eid,
                    'nombre': nom,
                    'valor': float(val or 0),
                    'disponible': int(disp or 0),
                    'imagen': imagen_url
                })
        else:
            cur.execute("""
                SELECT ElementoId, NombreElemento, ValorUnitario, CantidadDisponible
                FROM dbo.ElementosPublicitarios
                WHERE Activo = 1 AND CantidadDisponible > 0
                ORDER BY NombreElemento
            """)
            for (eid, nom, val, disp) in cur.fetchall():
                elementos.append({
                    'id': eid,
                    'nombre': nom,
                    'valor': float(val or 0),
                    'disponible': int(disp or 0),
                    'imagen': None
                })
    except Exception as e:
        print("Error cargando elementos:", e)
        flash(f"Error al cargar elementos: {e}", "danger")
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

    return render_template(
        'prestamos/crear.html',
        elementos=elementos,
        solicitante_id=solicitante_id,
        solicitante_nombre=solicitante_nombre,
        oficina_id=oficina_id,
        oficina_nombre=oficina_nombre,
        fecha_minima=fecha_minima
    )

@bp_prestamos.post('/crear')
def crear_prestamo_post():
    if not _require_login():
        return redirect('/login')

    # Tomar IDs desde sesión
    solicitante_id = int(session.get('usuario_id', 0))
    oficina_id = int(session.get('oficina_id', 0))

    elemento_id = request.form.get('elemento_id')
    cantidad = request.form.get('cantidad') or '0'
    fecha_prevista = request.form.get('fecha_prevista')
    evento = (request.form.get('evento') or '').strip()
    observaciones = (request.form.get('observaciones') or '').strip()

    # Validaciones
    if not elemento_id:
        flash('Debes seleccionar un elemento', 'warning')
        return redirect('/prestamos/crear')
    if int(cantidad) <= 0:
        flash('La cantidad debe ser mayor a 0', 'warning')
        return redirect('/prestamos/crear')
    if not fecha_prevista:
        flash('La fecha de devolución prevista es obligatoria', 'warning')
        return redirect('/prestamos/crear')
    if not evento:
        flash('El evento/motivo del préstamo es obligatorio', 'warning')
        return redirect('/prestamos/crear')
    if not observaciones:
        flash('Las observaciones son obligatorias', 'warning')
        return redirect('/prestamos/crear')
    if not solicitante_id or not oficina_id:
        flash('No se encontraron datos de sesión para solicitante/oficina', 'danger')
        return redirect('/prestamos/crear')

    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        # Valida stock
        cur.execute("""
            SELECT CantidadDisponible, NombreElemento
            FROM dbo.ElementosPublicitarios WITH (UPDLOCK, ROWLOCK)
            WHERE ElementoId = ? AND Activo = 1
        """, (int(elemento_id),))
        row = cur.fetchone()
        if not row:
            flash('Elemento no encontrado o inactivo', 'danger')
            return redirect('/prestamos/crear')

        disponible = int(row[0] or 0)
        nombre_elemento = row[1]
        if int(cantidad) > disponible:
            flash(f'Stock insuficiente. Disponible: {disponible}', 'danger')
            return redirect('/prestamos/crear')

        # Obtener usuario prestador de la sesión
        usuario_prestador = session.get('usuario_nombre', 'Sistema')

        # Crea préstamo
        cur.execute("""
            INSERT INTO dbo.PrestamosElementos
                (ElementoId, UsuarioSolicitanteId, OficinaId, CantidadPrestada, 
                 FechaPrestamo, FechaDevolucionPrevista, Estado, Evento, Observaciones, 
                 UsuarioPrestador, Activo)
            VALUES (?, ?, ?, ?, GETDATE(), ?, 'PRESTADO', ?, ?, ?, 1)
        """, (
            int(elemento_id), solicitante_id, oficina_id, int(cantidad),
            fecha_prevista, evento, observaciones, usuario_prestador
        ))

        # Descontar stock
        cur.execute("""
            UPDATE dbo.ElementosPublicitarios
            SET CantidadDisponible = CantidadDisponible - ?
            WHERE ElementoId = ? AND Activo = 1
        """, (int(cantidad), int(elemento_id)))

        conn.commit()
        flash(f'✅ Préstamo de "{nombre_elemento}" registrado correctamente para el evento: {evento}', 'success')
        return redirect('/prestamos')
        
    except Exception as e:
        try:
            if conn: conn.rollback()
        except:
            pass
        flash(f'Error al crear préstamo: {e}', 'danger')
        return redirect('/prestamos/crear')
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except:
            pass

# ==========================================================
# API auxiliar: datos de un elemento
# ==========================================================
@bp_prestamos.get('/api/elemento/<int:elemento_id>')
def api_elemento_info(elemento_id: int):
    """API para obtener información de un elemento publicitario"""
    if not _require_login():
        return jsonify({'ok': False, 'error': 'No autorizado'}), 401
    
    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        img_col = _detect_image_column(cur)
        
        if img_col:
            cur.execute(f"""
                SELECT ElementoId, NombreElemento, ValorUnitario, CantidadDisponible, {img_col}
                FROM dbo.ElementosPublicitarios
                WHERE ElementoId = ? AND Activo = 1
            """, (elemento_id,))
        else:
            cur.execute("""
                SELECT ElementoId, NombreElemento, ValorUnitario, CantidadDisponible
                FROM dbo.ElementosPublicitarios
                WHERE ElementoId = ? AND Activo = 1
            """, (elemento_id,))
        
        row = cur.fetchone()
        if row:
            imagen_url = ""
            if img_col and len(row) >= 5:
                imagen_url = _normalize_image_url(row[4])
            
            return jsonify({
                'ok': True,
                'id': row[0],
                'nombre': row[1],
                'valor_unitario': float(row[2] or 0),
                'disponible': int(row[3] or 0),
                'imagen': imagen_url
            })
        else:
            return jsonify({'ok': False, 'error': 'Elemento no encontrado'}), 404
            
    except Exception as e:
        print(f"Error en api_elemento_info: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except: 
            pass

# ==========================================================
# Rutas: Aprobar, Aprobar Parcial y Rechazar Préstamos
# ==========================================================
@bp_prestamos.post('/<int:prestamo_id>/aprobar')
def aprobar_prestamo(prestamo_id: int):
    if not _require_login():
        return redirect('/login')
    
    # ✅ VERIFICAR ROLES ESPECÍFICOS
    if not _has_role('administrador', 'aprobador'):
        flash('No autorizado para aprobar préstamos', 'danger')
        return redirect(url_for('prestamos.listar_prestamos'))

    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        # Verificar que el préstamo existe y está en estado PRESTADO
        cur.execute("""
            SELECT Estado FROM dbo.PrestamosElementos 
            WHERE PrestamoId = ? AND Activo = 1
        """, (prestamo_id,))
        result = cur.fetchone()
        
        if not result:
            flash('Préstamo no encontrado', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        estado_actual = result[0]
        if estado_actual != 'PRESTADO':
            flash('Solo se pueden aprobar préstamos en estado PRESTADO', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        # Actualizar estado a APROBADO
        cur.execute("""
            UPDATE dbo.PrestamosElementos 
            SET Estado = 'APROBADO'
            WHERE PrestamoId = ?
        """, (prestamo_id,))
        
        conn.commit()
        flash('Préstamo aprobado correctamente', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al aprobar préstamo: {str(e)}', 'danger')
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except: 
            pass
    
    return redirect(url_for('prestamos.listar_prestamos'))

@bp_prestamos.post('/<int:prestamo_id>/aprobar_parcial')
def aprobar_parcial_prestamo(prestamo_id: int):
    if not _require_login():
        return redirect('/login')
    
    # ✅ VERIFICAR ROLES ESPECÍFICOS
    if not _has_role('administrador', 'aprobador'):
        flash('No autorizado para aprobar préstamos', 'danger')
        return redirect(url_for('prestamos.listar_prestamos'))

    cantidad_aprobada = request.form.get('cantidad_aprobada')
    
    if not cantidad_aprobada or int(cantidad_aprobada) <= 0:
        flash('La cantidad aprobada debe ser mayor a 0', 'warning')
        return redirect(url_for('prestamos.listar_prestamos'))

    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        # Verificar que el préstamo existe y está en estado PRESTADO
        cur.execute("""
            SELECT Estado, CantidadPrestada, ElementoId 
            FROM dbo.PrestamosElementos 
            WHERE PrestamoId = ? AND Activo = 1
        """, (prestamo_id,))
        result = cur.fetchone()
        
        if not result:
            flash('Préstamo no encontrado', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        estado_actual, cantidad_prestada, elemento_id = result
        if estado_actual != 'PRESTADO':
            flash('Solo se pueden aprobar préstamos en estado PRESTADO', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        cantidad_aprobada_int = int(cantidad_aprobada)
        if cantidad_aprobada_int > cantidad_prestada:
            flash('La cantidad aprobada no puede ser mayor a la cantidad prestada', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        # Calcular diferencia para devolver al stock
        diferencia = cantidad_prestada - cantidad_aprobada_int
        
        # Actualizar estado a APROBADO_PARCIAL y cantidad
        cur.execute("""
            UPDATE dbo.PrestamosElementos 
            SET Estado = 'APROBADO_PARCIAL', CantidadPrestada = ?
            WHERE PrestamoId = ?
        """, (cantidad_aprobada_int, prestamo_id))
        
        # Devolver diferencia al stock
        if diferencia > 0:
            cur.execute("""
                UPDATE dbo.ElementosPublicitarios
                SET CantidadDisponible = CantidadDisponible + ?
                WHERE ElementoId = ?
            """, (diferencia, elemento_id))
        
        conn.commit()
        flash(f'Préstamo aprobado parcialmente. Se aprobaron {cantidad_aprobada_int} unidades', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al aprobar parcialmente: {str(e)}', 'danger')
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except: 
            pass
    
    return redirect(url_for('prestamos.listar_prestamos'))

@bp_prestamos.post('/<int:prestamo_id>/rechazar')
def rechazar_prestamo(prestamo_id: int):
    if not _require_login():
        return redirect('/login')
    
    # ✅ VERIFICAR ROLES ESPECÍFICOS
    if not _has_role('administrador', 'aprobador'):
        flash('No autorizado para rechazar préstamos', 'danger')
        return redirect(url_for('prestamos.listar_prestamos'))

    observacion = request.form.get('observacion', '').strip()
    
    if not observacion:
        flash('La observación es obligatoria para rechazar un préstamo', 'warning')
        return redirect(url_for('prestamos.listar_prestamos'))

    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        # Verificar que el préstamo existe y está en estado PRESTADO
        cur.execute("""
            SELECT Estado, Observaciones, CantidadPrestada, ElementoId 
            FROM dbo.PrestamosElementos 
            WHERE PrestamoId = ? AND Activo = 1
        """, (prestamo_id,))
        result = cur.fetchone()
        
        if not result:
            flash('Préstamo no encontrado', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        estado_actual, observaciones_actuales, cantidad_prestada, elemento_id = result
        if estado_actual != 'PRESTADO':
            flash('Solo se pueden rechazar préstamos en estado PRESTADO', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        # Construir nuevas observaciones
        nuevas_observaciones = (observaciones_actuales or '')
        if observacion:
            nuevas_observaciones += f" | Rechazo: {observacion}"

        # Actualizar estado a RECHAZADO y agregar observación
        cur.execute("""
            UPDATE dbo.PrestamosElementos 
            SET Estado = 'RECHAZADO', Observaciones = ?
            WHERE PrestamoId = ?
        """, (nuevas_observaciones, prestamo_id))
        
        # Devolver todo el stock
        cur.execute("""
            UPDATE dbo.ElementosPublicitarios
            SET CantidadDisponible = CantidadDisponible + ?
            WHERE ElementoId = ?
        """, (cantidad_prestada, elemento_id))
        
        conn.commit()
        flash('Préstamo rechazado correctamente', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al rechazar préstamo: {str(e)}', 'danger')
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except: 
            pass
    
    return redirect(url_for('prestamos.listar_prestamos'))

# ==========================================================
# Ruta: Registrar Devolución
# ==========================================================
@bp_prestamos.post('/<int:prestamo_id>/devolucion')
def registrar_devolucion(prestamo_id: int):
    if not _require_login():
        return redirect('/login')
    
    # ✅ VERIFICAR ROLES ESPECÍFICOS
    if not _has_role('administrador', 'aprobador'):
        flash('No autorizado para registrar devoluciones', 'danger')
        return redirect(url_for('prestamos.listar_prestamos'))

    observacion = request.form.get('observacion', '').strip()
    usuario_devolucion = session.get('usuario_nombre', 'Sistema')

    conn = cur = None
    try:
        conn = get_database_connection()
        cur = conn.cursor()
        
        # Verificar que el préstamo existe y está en estado APROBADO o APROBADO_PARCIAL
        cur.execute("""
            SELECT Estado, Observaciones, CantidadPrestada, ElementoId
            FROM dbo.PrestamosElementos 
            WHERE PrestamoId = ? AND Activo = 1
        """, (prestamo_id,))
        result = cur.fetchone()
        
        if not result:
            flash('Préstamo no encontrado', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        estado_actual, observaciones_actuales, cantidad_prestada, elemento_id = result
        if estado_actual not in ['APROBADO', 'APROBADO_PARCIAL']:
            flash('Solo se pueden devolver préstamos en estado APROBADO o APROBADO_PARCIAL', 'warning')
            return redirect(url_for('prestamos.listar_prestamos'))
        
        # Construir nuevas observaciones
        nuevas_observaciones = (observaciones_actuales or '')
        if observacion:
            nuevas_observaciones += f" | Devolución [{usuario_devolucion}]: {observacion}"

        # Actualizar el préstamo
        cur.execute("""
            UPDATE dbo.PrestamosElementos 
            SET Estado = 'DEVUELTO', 
                FechaDevolucionReal = GETDATE(),
                Observaciones = ?,
                UsuarioDevolucion = ?
            WHERE PrestamoId = ?
        """, (nuevas_observaciones, usuario_devolucion, prestamo_id))
        
        # Devolver la cantidad prestada al stock
        cur.execute("""
            UPDATE dbo.ElementosPublicitarios
            SET CantidadDisponible = CantidadDisponible + ?
            WHERE ElementoId = ?
        """, (cantidad_prestada, elemento_id))
        
        conn.commit()
        flash('Devolución registrada correctamente', 'success')
        
    except Exception as e:
        if conn:
            conn.rollback()
        flash(f'Error al registrar devolución: {str(e)}', 'danger')
    finally:
        try:
            if cur: cur.close()
            if conn: conn.close()
        except: 
            pass
    
    return redirect(url_for('prestamos.listar_prestamos'))