# models/novedades_model.py
from database import get_database_connection

class NovedadModel:
    
    @staticmethod
    def obtener_todas(filtro_estado=None):
        """Obtiene todas las novedades, opcionalmente filtradas por estado"""
        conn = get_database_connection()
        if conn is None:
            return []
        
        cursor = conn.cursor()
        try:
            # ¡IMPORTANTE! Usa la tabla que SÍ existe: NovedadesSolicitudes
            sql = """
                SELECT 
                    ns.NovedadId,
                    ns.SolicitudId,
                    sm.MaterialId,  -- Obtener MaterialId desde SolicitudesMaterial
                    ns.TipoNovedad,
                    ns.Descripcion,
                    ns.EstadoNovedad as Estado,  -- ¡Corregir nombre del campo!
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
                FROM NovedadesSolicitudes ns  -- ¡Tabla correcta!
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                LEFT JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
            """
            
            params = []
            if filtro_estado:
                sql += " WHERE ns.EstadoNovedad = ?"  # ¡Campo correcto!
                params.append(filtro_estado)
            
            sql += " ORDER BY ns.FechaRegistro DESC"  # ¡Campo correcto!
            
            cursor.execute(sql, params)
            
            novedades = []
            for row in cursor.fetchall():
                novedades.append({
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
                })
            
            return novedades
            
        except Exception as e:
            print(f"❌ Error obteniendo novedades: {e}")
            import traceback
            traceback.print_exc()
            return []
        finally:
            cursor.close()
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
                return {
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
    def crear(solicitud_id, tipo_novedad, descripcion, usuario_reporta, cantidad_afectada=None):
        """Crea una nueva novedad"""
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
                VALUES (?, ?, ?, ?, 'registrada', ?, GETDATE())
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
    
    @staticmethod
    def actualizar_estado(novedad_id, nuevo_estado, usuario_resuelve, comentario=""):
        """Actualiza el estado de una novedad"""
        conn = get_database_connection()
        if conn is None:
            return False
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                UPDATE NovedadesSolicitudes 
                SET EstadoNovedad = ?,
                    FechaResolucion = GETDATE(),
                    UsuarioResuelve = ?,
                    ObservacionesResolucion = ?
                WHERE NovedadId = ?
            """, (nuevo_estado, usuario_resuelve, comentario, novedad_id))
            
            conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Error actualizando novedad: {e}")
            import traceback
            traceback.print_exc()
            return False
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
                    SUM(CASE WHEN EstadoNovedad = 'registrada' THEN 1 ELSE 0 END) as pendientes,
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
                    m.NombreElemento as MaterialNombre
                FROM NovedadesSolicitudes ns
                LEFT JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                LEFT JOIN Materiales m ON sm.MaterialId = m.MaterialId
                WHERE ns.SolicitudId = ?
                ORDER BY ns.FechaRegistro DESC
            """, (solicitud_id,))
            
            novedades = []
            for row in cursor.fetchall():
                novedades.append({
                    "id": row[0],
                    "tipo_novedad": row[1],
                    "descripcion": row[2],
                    "estado": row[3],
                    "fecha_reporte": row[4],
                    "usuario_reporta": row[5],
                    "fecha_resolucion": row[6],
                    "usuario_resuelve": row[7],
                    "comentario_resolucion": row[8],
                    "material_nombre": row[9] or "No especificado"
                })
            
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