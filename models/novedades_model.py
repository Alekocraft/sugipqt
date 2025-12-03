# models/novedades_model.py
from database import get_database_connection

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
    def obtener_todas():
        """Obtiene todas las novedades con información de oficina"""
        conn = get_database_connection()
        if conn is None:
            print("❌ ERROR: No hay conexión a BD en obtener_todas")
            return []

        cursor = None
        try:
            cursor = conn.cursor()
            
            # CORRECCIÓN: Usar el nombre correcto de la tabla NovedadesSolicitudes
            cursor.execute("""
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
                    ns.RutaImagen
                FROM NovedadesSolicitudes ns
                INNER JOIN SolicitudesMaterial sm ON ns.SolicitudId = sm.SolicitudId
                INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                ORDER BY ns.FechaRegistro DESC
            """)

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
                    "fecha_reporte": fecha_registro,  # Cambiado de fecha_registro a fecha_reporte
                    "estado": estado,
                    "usuario_resuelve": r[10],
                    "fecha_resolucion": r[11],
                    "observaciones_resolucion": r[12],
                    "ruta_imagen": r[13],
                    "prioridad": prioridad,
                    "reportante_nombre": r[7],  # Usuario que registra
                    "asignado_a_nombre": r[10] or "Sin asignar",  # Usuario que resuelve
                    "color_tipo": "#6f42c1"  # Color fijo para simplificar
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
            return dict(zip(cols, row))
        finally:
            conn.close()