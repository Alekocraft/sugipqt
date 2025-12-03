from typing import Any, Dict, List, Optional
from database import get_database_connection
import bcrypt


class UsuarioModel:
    """
    Acceso a datos de usuarios.

    Este modelo encapsula operaciones comunes sobre la tabla `Usuarios`, tales como:
    - Verificar credenciales con hash bcrypt.
    - Obtener un usuario por ID.
    - Listar usuarios con rol aprobador.

    Seguridad:
    - Nunca se expone el hash almacenado en BD.
    - La verificación se realiza con bcrypt.checkpw(plaintext, hash_almacenado).
    """

    @classmethod
    def verificar_credenciales(cls, usuario: str, contraseña: str) -> Optional[Dict[str, Any]]:
        """
        Verifica las credenciales de un usuario activo.

        Parámetros
        ----------
        usuario : str
            Nombre de usuario (u.NombreUsuario).
        contraseña : str
            Contraseña en texto plano ingresada por el usuario.

        Retorna
        -------
        dict | None
            Diccionario con datos del usuario si la verificación es correcta,
            o None si el usuario no existe, está inactivo o la contraseña es incorrecta.
        """
        conn = get_database_connection()
        if conn is None:
            return None

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT
                    u.UsuarioId           AS id,
                    u.NombreUsuario       AS nombre,
                    u.NombreUsuario       AS usuario,
                    u.Rol                 AS rol,
                    u.OficinaId           AS oficina_id,
                    o.NombreOficina       AS oficina_nombre,
                    u.ContraseñaHash      AS contrasena_hash
                FROM Usuarios u
                LEFT JOIN Oficinas o ON u.OficinaId = o.OficinaId
                WHERE u.NombreUsuario = ? AND u.Activo = 1
                """,
                (usuario,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            # Convertimos la fila a dict usando los alias de la consulta
            columns = [col[0] for col in cursor.description]
            usuario_data = dict(zip(columns, row))

            hash_guardado = usuario_data.get("contrasena_hash")

            # Normalizamos el tipo del hash a bytes (sqlite/pyodbc a veces devuelve memoryview/str)
            if isinstance(hash_guardado, memoryview):
                hash_guardado = hash_guardado.tobytes()
            elif isinstance(hash_guardado, str):
                hash_guardado = hash_guardado.encode("utf-8")

            if not isinstance(hash_guardado, (bytes, bytearray)):
                # Hash inválido o inexistente en BD
                return None

            if bcrypt.checkpw(contraseña.encode("utf-8"), hash_guardado):
                # Eliminamos el hash antes de retornar (defensa en profundidad)
                usuario_data.pop("contrasena_hash", None)

                # Normalizamos valores por conveniencia
                if usuario_data.get("oficina_id") is None:
                    usuario_data["oficina_id"] = 1

                return usuario_data

            # Contraseña incorrecta
            return None

        finally:
            try:
                cursor.close()
            finally:
                conn.close()

    @staticmethod
    def obtener_por_id(usuario_id: int) -> Optional[Dict[str, Any]]:
        """
        Obtiene un usuario activo por su ID.

        Parámetros
        ----------
        usuario_id : int
            Identificador del usuario.

        Retorna
        -------
        dict | None
            Diccionario con {id, nombre, usuario, rol, oficina_id} o None si no existe/está inactivo.
        """
        conn = get_database_connection()
        if conn is None:
            return None

        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                SELECT UsuarioId, NombreUsuario, Rol, OficinaId
                FROM Usuarios
                WHERE UsuarioId = ? AND Activo = 1
                """,
                (usuario_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            return {
                "id": row[0],
                "nombre": row[1],
                "usuario": row[1],
                "rol": row[2],
                "oficina_id": row[3] if row[3] is not None else 1,
            }

        finally:
            try:
                cursor.close()
            finally:
                conn.close()
    
    @staticmethod
    def obtener_aprobadores():
        """Obtener todos los aprobadores desde la tabla Aprobadores"""
        try:
            conn = get_database_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    AprobadorId,
                    NombreAprobador,
                    Email,
                    Activo,
                    FechaCreacion
                FROM Aprobadores
                ORDER BY NombreAprobador
            """)
            
            # Convertir resultados a lista de diccionarios
            columns = [column[0] for column in cursor.description]
            aprobadores = []
            for row in cursor.fetchall():
                aprobador_dict = {}
                for i, column in enumerate(columns):
                    aprobador_dict[column] = row[i]
                aprobadores.append(aprobador_dict)
            
            cursor.close()
            conn.close()
            
            print(f"✅ Aprobadores obtenidos: {len(aprobadores)} registros")
            if aprobadores:
                print(f"✅ Primer aprobador: {aprobadores[0]}")
            
            return aprobadores
            
        except Exception as e:
            print(f"❌ Error en obtener_aprobadores: {str(e)}")
            return []
