# models/novedades_model.py
from database import get_database_connection
from datetime import datetime

class NovedadModel:

    @staticmethod
    def crear(solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_registra, ruta_imagen):
        conn = get_database_connection()
        if conn is None:
            print("❌ ERROR: Sin conexión a BD en NovedadModel.crear")
            return False

        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO NovedadesSolicitudes (
                    SolicitudId,
                    TipoNovedad,
                    Descripcion,
                    CantidadAfectada,
                    UsuarioRegistra,
                    FechaRegistro,
                    RutaImagen,
                    EstadoNovedad
                )
                VALUES (?, ?, ?, ?, ?, GETDATE(), ?, 'pendiente')
            """, (
                int(solicitud_id),
                tipo_novedad,
                descripcion,
                int(cantidad_afectada),
                usuario_registra,
                ruta_imagen
            ))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print("❌ ERROR SQL EN NovedadModel.crear:", str(e))
            return False

        finally:
            cursor.close()
            conn.close()
             
    @staticmethod
    def obtener_todas(filtro_estado=None):
        """Obtiene todas las novedades con información de oficina, opcionalmente filtradas por estado"""
        conn = get_database_connection()
        if conn is None:
            print("❌ ERROR: No hay conexión a BD en obtener_todas")
            return []

        cursor = None
        try:
            cursor = conn.cursor()
            
            sql = """
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    sm.OficinaSolicitanteId,
                    o.NombreOficina,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.CantidadAfectada,
                    ns.UsuarioRegistra,
                    ns.FechaRegistro,
                    ns.EstadoNovedad,
                    ns.UsuarioResuelve,
                    ns.FechaResolucion,
                    ns.ObservacionesResolucion,
                    ns.RutaImagen,
                    sm.MaterialId,
                    m.NombreElemento as MaterialNombre,
                    sm.CantidadSolicitada,
                    sm.CantidadEntregada
                FROM NovedadesSolicitudes ns
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
            """
            
            params = []
            if filtro_estado:
                sql += " WHERE ns.EstadoNovedad = ?"
                params.append(filtro_estado)
            
            sql += " ORDER BY ns.FechaRegistro DESC"
            cursor.execute(sql, params)

            rows = cursor.fetchall()
            print(f"✅ NovedadModel.obtener_todas: Se obtuvieron {len(rows)} novedades")
            
            resultados = []
            for r in rows:
                # Determinar prioridad basada en tipo
                tipo_novedad = r[4] or ""
                prioridad = "media"
                tipo_lower = tipo_novedad.lower()
                
                if any(palabra in tipo_lower for palabra in ['robo', 'perdida', 'urgente', 'grave', 'emergencia']):
                    prioridad = "alta"
                elif any(palabra in tipo_lower for palabra in ['daño', 'avería', 'averia', 'incidente', 'problema']):
                    prioridad = "media"
                else:
                    prioridad = "baja"
                
                # Determinar estado amigable
                estado_db = r[9] or "pendiente"
                estado = "pendiente"
                estado_lower = estado_db.lower()
                
                if estado_lower == "pendiente":
                    estado = "pendiente"
                elif "proceso" in estado_lower or "en proceso" in estado_lower:
                    estado = "en_proceso"
                elif any(est in estado_lower for est in ["resuelto", "solucionado", "cerrado", "completado", "finalizado"]):
                    estado = "resuelto"
                elif "cancelado" in estado_lower:
                    estado = "cancelado"
                else:
                    estado = estado_lower
                
                # Convertir fecha si es necesario
                fecha_registro = r[8]
                if isinstance(fecha_registro, str):
                    try:
                        fecha_registro = datetime.strptime(fecha_registro, '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        try:
                            fecha_registro = datetime.strptime(fecha_registro, '%Y-%m-%d %H:%M:%S')
                        except:
                            fecha_registro = datetime.now()
                
                resultados.append({
                    "id": r[0],
                    "solicitud_id": r[1],
                    "oficina_id": r[2],
                    "oficina_nombre": r[3],
                    "tipo": r[4],
                    "descripcion": r[5],
                    "cantidad_afectada": r[6],
                    "usuario_registra": r[7],
                    "fecha_reporte": fecha_registro,
                    "estado": estado,
                    "usuario_resuelve": r[10],
                    "fecha_resolucion": r[11],
                    "observaciones_resolucion": r[12],
                    "ruta_imagen": r[13],
                    "prioridad": prioridad,
                    "reportante_nombre": r[7],
                    "asignado_a_nombre": r[10] or "Sin asignar",
                    "color_tipo": "#6f42c1",
                    "material_id": r[14] if r[14] is not None else 0,
                    "material_nombre": r[15] or "No especificado",
                    "cantidad_solicitada": r[16] or 0,
                    "cantidad_entregada": r[17] or 0
                })
            
            return resultados

        except Exception as e:
            print(f"❌ ERROR NovedadModel.obtener_todas: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def obtener_novedades_pendientes():
        conn = get_database_connection()
        if conn is None:
            return []

        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    NovedadId,
                    SolicitudId,
                    TipoNovedad,
                    Descripcion,
                    CantidadAfectada,
                    UsuarioRegistra,
                    FechaRegistro,
                    RutaImagen,
                    EstadoNovedad
                FROM NovedadesSolicitudes
                WHERE EstadoNovedad = 'pendiente'
                ORDER BY FechaRegistro DESC
            """)

            rows = cursor.fetchall()
            resultados = []
            for r in rows:
                resultados.append({
                    "novedad_id": r[0],
                    "solicitud_id": r[1],
                    "tipo_novedad": r[2],
                    "descripcion": r[3],
                    "cantidad_afectada": r[4],
                    "usuario_registra": r[5],
                    "fecha_registro": r[6],
                    "ruta_imagen": r[7],
                    "estado": r[8],
                })
            return resultados

        except Exception as e:
            print("❌ ERROR NovedadModel.obtener_novedades_pendientes:", str(e))
            return []

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def actualizar_estado(novedad_id, estado, usuario_resuelve, observaciones_resolucion):
        conn = get_database_connection()
        if conn is None:
            return False

        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE NovedadesSolicitudes
                SET EstadoNovedad = ?,
                    UsuarioResuelve = ?,
                    ObservacionesResolucion = ?,
                    FechaResolucion = GETDATE()
                WHERE NovedadId = ?
            """, (
                estado,
                usuario_resuelve,
                observaciones_resolucion,
                int(novedad_id)
            ))

            conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            conn.rollback()
            print("❌ ERROR NovedadModel.actualizar_estado:", str(e))
            return False

        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_ultima_por_solicitud(solicitud_id: int):
        """
        Retorna la última novedad registrada para una solicitud
        como dict, o None si no hay.
        """
        conn = get_database_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT TOP 1
                    NovedadId,
                    SolicitudId,
                    TipoNovedad,
                    Descripcion,
                    CantidadAfectada,
                    EstadoNovedad,
                    UsuarioRegistra,
                    FechaRegistro,
                    UsuarioResuelve,
                    FechaResolucion,
                    ObservacionesResolucion,
                    RutaImagen
                FROM NovedadesSolicitudes
                WHERE SolicitudId = ?
                ORDER BY FechaRegistro DESC
            """, (solicitud_id,))
            row = cursor.fetchone()
            if not row:
                return None

            cols = [c[0] for c in cursor.description]
            novedad = dict(zip(cols, row))
            
            # Añadir URL de imagen si existe
            if novedad.get('RutaImagen'):
                novedad['imagen_url'] = f"/static/{novedad['RutaImagen']}"
            
            return novedad
        except Exception as e:
            print(f"❌ ERROR NovedadModel.obtener_ultima_por_solicitud: {str(e)}")
            return None
        finally:
            conn.close()

    @staticmethod
    def obtener_por_id(novedad_id):
        """Obtiene una novedad por su ID"""
        conn = get_database_connection()
        if conn is None:
            return None
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    sm.MaterialId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.EstadoNovedad as Estado,
                    ns.FechaRegistro as FechaReporte,
                    ns.UsuarioRegistra as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    ns.ObservacionesResolucion as ComentarioResolucion,
                    m.NombreElemento as MaterialNombre,
                    sm.CantidadSolicitada,
                    sm.CantidadEntregada,
                    o.NombreOficina,
                    o.OficinaId
                FROM NovedadesSolicitudes ns
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                LEFT JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                WHERE ns.NovedadId = ?
            """, (novedad_id,))
            
            row = cursor.fetchone()
            if row:
                novedad = {
                    "id": row[0],
                    "solicitud_id": row[1],
                    "material_id": row[2] if row[2] is not None else 0,
                    "tipo_novedad": row[3],
                    "descripcion": row[4],
                    "estado": row[5],
                    "fecha_reporte": row[6],
                    "usuario_reporta": row[7],
                    "fecha_resolucion": row[8],
                    "usuario_resuelve": row[9],
                    "comentario_resolucion": row[10],
                    "material_nombre": row[11] or "No especificado",
                    "cantidad_solicitada": row[12] or 0,
                    "cantidad_entregada": row[13] or 0,
                    "oficina_nombre": row[14] or "No especificada",
                    "oficina_id": row[15] or None
                }
                
                return novedad
            return None
            
        except Exception as e:
            print(f"❌ Error obteniendo novedad por ID: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_solicitud(solicitud_id):
        """Obtiene las novedades asociadas a una solicitud"""
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    ns.NovedadId,
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.EstadoNovedad as Estado,
                    ns.FechaRegistro as FechaReporte,
                    ns.UsuarioRegistra as UsuarioReporta,
                    ns.FechaResolucion,
                    ns.UsuarioResuelve,
                    ns.ObservacionesResolucion as ComentarioResolucion,
                    m.NombreElemento as MaterialNombre,
                    ns.RutaImagen,
                    ns.CantidadAfectada
                FROM NovedadesSolicitudes ns
                LEFT JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                WHERE ns.SolicitudId = ?
                ORDER BY ns.FechaRegistro DESC
            """, (solicitud_id,))
            
            novedades = []
            for row in cursor.fetchall():
                novedad = {
                    # Múltiples nombres de clave para compatibilidad
                    'id': row[0],
                    'novedad_id': row[0],
                    'NovedadId': row[0],
                    'tipo_novedad': row[1],
                    'descripcion': row[2],
                    'estado': row[3],
                    'estado_novedad': row[3],
                    'fecha_reporte': row[4],
                    'usuario_reporta': row[5],
                    'usuario_registra': row[5],
                    'fecha_resolucion': row[6],
                    'usuario_resuelve': row[7],
                    'comentario_resolucion': row[8],
                    'observaciones_resolucion': row[8],
                    'material_nombre': row[9] or "No especificado",
                    'ruta_imagen': row[10],
                    'cantidad_afectada': row[11],
                    'CantidadAfectada': row[11]
                }
                
                # Añadir URL de imagen si existe
                if row[10]:
                    novedad['imagen_url'] = f"/static/{row[10]}"
                
                novedades.append(novedad)
            
            return novedades
            
        except Exception as e:
            print(f"❌ Error obteniendo novedades por solicitud: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_estadisticas():
        """Obtiene estadísticas de novedades"""
        conn = get_database_connection()
        if conn is None:
            return {"total": 0, "pendientes": 0, "resueltas": 0}
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN EstadoNovedad = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
                    SUM(CASE WHEN EstadoNovedad = 'resuelta' THEN 1 ELSE 0 END) as resueltas
                FROM NovedadesSolicitudes
            """)
            
            row = cursor.fetchone()
            if row:
                return {
                    "total": row[0] or 0,
                    "pendientes": row[1] or 0,
                    "resueltas": row[2] or 0
                }
            return {"total": 0, "pendientes": 0, "resueltas": 0}
            
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas de novedades: {e}")
            import traceback
            traceback.print_exc()
            return {"total": 0, "pendientes": 0, "resueltas": 0}
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_tipos_disponibles():
        """Obtiene los tipos de novedad únicos que existen"""
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT TipoNovedad 
                FROM NovedadesSolicitudes 
                WHERE TipoNovedad IS NOT NULL
                ORDER BY TipoNovedad
            """)
            
            tipos = []
            for row in cursor.fetchall():
                tipos.append(row[0])
            
            return tipos
            
        except Exception as e:
            print(f"❌ Error obteniendo tipos de novedad: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def crear_nueva(solicitud_id, tipo_novedad, descripcion, usuario_reporta, cantidad_afectada=None):
        """Crea una nueva novedad (versión alternativa sin imagen)"""
        conn = get_database_connection()
        if conn is None:
            return None
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO NovedadesSolicitudes (
                    SolicitudId, TipoNovedad, Descripcion, CantidadAfectada,
                    EstadoNovedad, UsuarioRegistra, FechaRegistro
                )
                VALUES (?, ?, ?, ?, 'pendiente', ?, GETDATE())
            """, (solicitud_id, tipo_novedad, descripcion, cantidad_afectada, usuario_reporta))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error creando novedad: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            cursor.close()
            conn.close()