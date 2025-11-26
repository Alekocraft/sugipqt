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
    def obtener_por_solicitud(solicitud_id):
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
                    EstadoNovedad,
                    UsuarioResuelve,
                    ObservacionesResolucion,
                    FechaResolucion
                FROM NovedadesSolicitudes
                WHERE SolicitudId = ?
                ORDER BY FechaRegistro DESC
            """, (solicitud_id,))

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
                    "usuario_resuelve": r[9],
                    "observaciones_resolucion": r[10],
                    "fecha_resolucion": r[11],
                })
            return resultados

        except Exception as e:
            print("❌ ERROR NovedadModel.obtener_por_solicitud:", str(e))
            return []

        finally:
            cursor.close()
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