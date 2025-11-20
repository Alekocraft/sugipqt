# models/solicitudes_model.py
from database import get_database_connection

class SolicitudModel:
    
    @staticmethod
    def crear(oficina_id, material_id, cantidad_solicitada, porcentaje_oficina, usuario_nombre, observacion=""):
        """Crea una nueva solicitud"""
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute(
                "{CALL sp_CrearSolicitud (?, ?, ?, ?, ?, ?)}",
                (oficina_id, material_id, cantidad_solicitada, porcentaje_oficina, usuario_nombre, observacion)
            )
            result = cursor.fetchone()
            conn.commit()
            return result[0] if result else None
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def aprobar(solicitud_id, usuario_aprobador_id):
        """Aprueba una solicitud completamente"""
        conn = get_database_connection()
        if conn is None:
            return False, "Error de conexión"
        cursor = conn.cursor()
        try:
            aprobador_id = SolicitudModel._obtener_aprobador_id(usuario_aprobador_id)
            cursor.execute(
                "{CALL sp_AprobarSolicitud (?, ?)}",
                (solicitud_id, aprobador_id)
            )
            conn.commit()
            return True, "✅ Solicitud aprobada exitosamente"
        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            if "Límite mensual" in error_msg:
                return False, "❌ Límite mensual excedido"
            elif "Stock insuficiente" in error_msg or "excede el inventario" in error_msg:
                return False, "❌ Stock insuficiente"
            else:
                return False, f"❌ Error: {error_msg}"
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def aprobar_parcial(solicitud_id, usuario_aprobador_id, cantidad_aprobada):
        """Aprobar parcialmente una solicitud"""
        conn = get_database_connection()
        if conn is None:
            return False, "Error de conexión"
        
        cursor = conn.cursor()
        try:
            aprobador_id = SolicitudModel._obtener_aprobador_id(usuario_aprobador_id)
            
            cursor.execute(
                "{CALL sp_AprobarParcialSolicitud (?, ?, ?)}",
                (solicitud_id, aprobador_id, cantidad_aprobada)
            )
            conn.commit()
            return True, f"✅ {cantidad_aprobada} unidades aprobadas y entregadas"
        
        except Exception as e:
            conn.rollback()
            error_msg = str(e)
            if "Cantidad aprobada inválida" in error_msg:
                return False, "❌ Cantidad aprobada inválida"
            elif "solicitudes pendientes" in error_msg:
                return False, "❌ Solo se pueden aprobar parcialmente solicitudes pendientes"
            elif "Solicitud no encontrada" in error_msg:
                return False, "❌ Solicitud no encontrada"
            else:
                return False, f"❌ Error al aprobar parcialmente: {error_msg}"
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def rechazar(solicitud_id, usuario_aprobador_id, observacion=""):
        """Rechaza una solicitud"""
        conn = get_database_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        try:
            aprobador_id = SolicitudModel._obtener_aprobador_id(usuario_aprobador_id)
            cursor.execute("""
                UPDATE SolicitudesMaterial 
                SET EstadoId = 3, 
                    FechaAprobacion = GETDATE(), 
                    AprobadorId = ?, 
                    Observacion = ?
                WHERE SolicitudId = ? AND EstadoId = 1
            """, (aprobador_id, observacion, solicitud_id))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    # Método registrar_devolucion - VERSIÓN CORREGIDA
    @staticmethod
    def registrar_devolucion(solicitud_id, cantidad_devuelta, usuario_nombre, observacion):
        """Registrar devolución - VERSIÓN CORREGIDA"""
        conn = get_database_connection()
        if conn is None:
            return False, "Error de conexión a la base de datos"

        cursor = conn.cursor()
        try:
            # Primero obtener información actualizada de la solicitud
            cursor.execute("""
                SELECT 
                    sm.MaterialId,
                    sm.CantidadSolicitada,
                    ISNULL(sm.CantidadEntregada, 0) as CantidadAprobada,
                    sm.EstadoId,
                    (ISNULL(sm.CantidadEntregada, 0) - ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0)) as CantidadPuedeDevolver
                FROM SolicitudesMaterial sm
                WHERE sm.SolicitudId = ?
            """, (solicitud_id,))
        
            row = cursor.fetchone()
            if not row:
                conn.rollback()
                return False, "❌ Solicitud no encontrada"
        
            material_id = row[0]
            cantidad_solicitada = row[1]
            cantidad_aprobada = row[2]  # Esto es lo que realmente se aprobó/entregó
            estado_id = row[3]
            cantidad_puede_devolver = row[4] or 0
        
            # Validar estado - permitir devoluciones en estados Aprobada (2) y Entregada (4)
            if estado_id not in [2, 4]:
                conn.rollback()
                return False, "❌ Solo se pueden devolver solicitudes aprobadas o entregadas"
        
            # Validar cantidad usando la cantidad APROBADA, no la solicitada
            if cantidad_devuelta <= 0:
                conn.rollback()
                return False, "❌ La cantidad a devolver debe ser mayor a 0"
        
            if cantidad_devuelta > cantidad_puede_devolver:
                conn.rollback()
                return False, f"❌ No puede devolver más de {cantidad_puede_devolver} unidades (cantidad aprobada pendiente)"
        
            # Calcular nueva cantidad pendiente después de esta devolución
            nueva_cantidad_pendiente = cantidad_puede_devolver - cantidad_devuelta
        
            # 1. REGISTRAR LA DEVOLUCIÓN
            cursor.execute("""
                INSERT INTO Devoluciones (
                    SolicitudId, MaterialId, CantidadDevuelta, FechaDevolucion,
                    UsuarioDevolucion, Observaciones, EstadoDevolucion, CondicionMaterial
                )
                VALUES (?, ?, ?, GETDATE(), ?, ?, 'COMPLETADA', 'BUENO')
            """, (solicitud_id, material_id, cantidad_devuelta, usuario_nombre, observacion or ''))
        
            # 2. ACTUALIZAR STOCK (devolver al inventario)
            cursor.execute("""
                UPDATE Materiales 
                SET CantidadDisponible = CantidadDisponible + ?
                WHERE MaterialId = ?
            """, (cantidad_devuelta, material_id))
        
            # 3. ACTUALIZAR ESTADO DE LA SOLICITUD
            if nueva_cantidad_pendiente <= 0:
                # Si no queda nada por devolver, cambiar estado a "Devuelta" (5)
                cursor.execute("""
                    UPDATE SolicitudesMaterial 
                    SET EstadoId = 5,  -- Estado Devuelta
                        FechaUltimaEntrega = GETDATE()
                    WHERE SolicitudId = ?
                """, (solicitud_id,))
                estado_final = "Devuelta"
            else:
                # Si aún queda por devolver, mantener estado "Aprobada" (2) o "Entregada" (4)
                cursor.execute("""
                    UPDATE SolicitudesMaterial 
                    SET FechaUltimaEntrega = GETDATE()
                    WHERE SolicitudId = ?
                """, (solicitud_id,))
                estado_final = "Parcialmente Devuelta"
        
            conn.commit()
            return True, f"✅ Devolución registrada exitosamente. Estado: {estado_final}"
    
        except Exception as e:
            conn.rollback()
            return False, f"❌ Error al procesar devolución: {str(e)}"
        finally:
            cursor.close()
            conn.close()

    # ========== MÉTODOS DE CONSULTA ==========

    @staticmethod
    def obtener_todas(oficina_id=None):
        """Obtiene todas las solicitudes (alias para mantener compatibilidad)"""
        return SolicitudModel.obtener_todas_ordenadas(oficina_id)

    @staticmethod
    def obtener_todas_ordenadas(oficina_id=None):
        """Obtiene todas las solicitudes ordenadas por estado y fecha"""
        conn = get_database_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    sm.SolicitudId,
                    m.NombreElemento,
                    sm.UsuarioSolicitante,
                    o.NombreOficina,
                    sm.OficinaSolicitanteId,
                    sm.CantidadSolicitada,
                    es.NombreEstado,
                    sm.FechaSolicitud,
                    sm.Observacion,
                    sm.MaterialId,
                    sm.PorcentajeOficina,
                    sm.ValorTotalSolicitado,
                    sm.ValorOficina,
                    sm.ValorSedePrincipal,
                    m.ValorUnitario,
                    m.CantidadDisponible,
                    sm.FechaAprobacion,
                    sm.CantidadEntregada  -- AGREGAR ESTA COLUMNA
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
            """
            if oficina_id:
                sql += " WHERE sm.OficinaSolicitanteId = ?"
            sql += """
                ORDER BY 
                    CASE es.NombreEstado 
                        WHEN 'Pendiente' THEN 1
                        WHEN 'Aprobada' THEN 2
                        WHEN 'Rechazada' THEN 3
                        WHEN 'Devuelta' THEN 4
                        ELSE 5
                    END,
                    sm.FechaSolicitud DESC
            """
            if oficina_id:
                cursor.execute(sql, (oficina_id,))
            else:
                cursor.execute(sql)
            return SolicitudModel._mapear_solicitudes(cursor.fetchall())
        except Exception as e:
            print(f"Error en obtener_todas_ordenadas: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_para_aprobador(oficina_id=None):
        """Obtiene solicitudes pendientes para aprobación"""
        conn = get_database_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        try:
            sql = """
                SELECT 
                    sm.SolicitudId,
                    m.NombreElemento,
                    sm.UsuarioSolicitante,
                    o.NombreOficina,
                    sm.OficinaSolicitanteId,
                    sm.CantidadSolicitada,
                    es.NombreEstado,
                    sm.FechaSolicitud,
                    sm.Observacion,
                    sm.MaterialId,
                    sm.PorcentajeOficina,
                    sm.ValorTotalSolicitado,
                    sm.ValorOficina,
                    sm.ValorSedePrincipal,
                    m.ValorUnitario,
                    m.CantidadDisponible,
                    sm.FechaAprobacion,
                    sm.CantidadEntregada  -- AGREGAR ESTA COLUMNA
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                WHERE sm.EstadoId = 1
            """
            if oficina_id:
                sql += " AND sm.OficinaSolicitanteId = ?"
                cursor.execute(sql, (oficina_id,))
            else:
                cursor.execute(sql)
            return SolicitudModel._mapear_solicitudes(cursor.fetchall())
        except Exception as e:
            print(f"Error en obtener_para_aprobador: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_id(solicitud_id):
        """Obtiene una solicitud específica por ID"""
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    sm.SolicitudId,
                    m.NombreElemento,
                    sm.UsuarioSolicitante,
                    o.NombreOficina,
                    sm.OficinaSolicitanteId,
                    sm.CantidadSolicitada,
                    es.NombreEstado,
                    sm.FechaSolicitud,
                    sm.Observacion,
                    sm.MaterialId,
                    sm.PorcentajeOficina,
                    sm.ValorTotalSolicitado,
                    sm.ValorOficina,
                    sm.ValorSedePrincipal,
                    m.ValorUnitario,
                    m.CantidadDisponible,
                    sm.FechaAprobacion,
                    sm.CantidadEntregada  -- AGREGAR ESTA COLUMNA
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                WHERE sm.SolicitudId = ?
            """, (solicitud_id,))
            rows = cursor.fetchall()
            if rows:
                return SolicitudModel._mapear_solicitudes(rows)[0]
            return None
        except Exception as e:
            print(f"Error en obtener_por_id: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    # ========== MÉTODOS DE DEVOLUCIÓN ==========

    @staticmethod
    def obtener_info_devolucion(solicitud_id):
        """Obtiene información actualizada para devoluciones"""
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    sm.SolicitudId,
                    sm.EstadoId,
                    es.NombreEstado as Estado,
                    sm.CantidadSolicitada,
                    ISNULL(sm.CantidadEntregada, 0) as CantidadEntregada,
                    ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0) as CantidadYaDevuelta,
                    (ISNULL(sm.CantidadEntregada, 0) - ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0)) as CantidadPuedeDevolver,
                    m.NombreElemento,
                    o.NombreOficina
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                WHERE sm.SolicitudId = ?
            """, (solicitud_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'solicitud_id': row[0],
                    'estado_id': row[1],
                    'estado': row[2],
                    'cantidad_solicitada': row[3],
                    'cantidad_entregada': row[4],
                    'cantidad_ya_devuelta': row[5],
                    'cantidad_puede_devolver': row[6],
                    'material_nombre': row[7],
                    'oficina_nombre': row[8]
                }
            return None
        except Exception as e:
            print(f"Error en obtener_info_devolucion: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_info_devolucion_actualizada(solicitud_id):
        """Obtiene información actualizada para devoluciones incluyendo cantidad aprobada"""
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    sm.SolicitudId,
                    sm.EstadoId,
                    es.NombreEstado as Estado,
                    sm.CantidadSolicitada,
                    ISNULL(sm.CantidadEntregada, 0) as CantidadAprobada,
                    ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0) as CantidadYaDevuelta,
                    (ISNULL(sm.CantidadEntregada, 0) - ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0)) as CantidadPuedeDevolver,
                    m.NombreElemento,
                    o.NombreOficina,
                    sm.UsuarioSolicitante
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                WHERE sm.SolicitudId = ?
            """, (solicitud_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'solicitud_id': row[0],
                    'estado_id': row[1],
                    'estado': row[2],
                    'cantidad_solicitada': row[3],
                    'cantidad_aprobada': row[4],
                    'cantidad_ya_devuelta': row[5],
                    'cantidad_puede_devolver': row[6],
                    'material_nombre': row[7],
                    'oficina_nombre': row[8],
                    'solicitante_nombre': row[9]
                }
            return None
        except Exception as e:
            print(f"Error en obtener_info_devolucion_actualizada: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_devoluciones(solicitud_id):
        """Obtiene el historial de devoluciones para una solicitud específica"""
        conn = get_database_connection()
        if conn is None:
            return []
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    d.DevolucionId,
                    d.SolicitudId,
                    d.UsuarioDevolucion,
                    d.CantidadDevuelta,
                    d.FechaDevolucion,
                    d.Observaciones
                FROM dbo.Devoluciones d
                WHERE d.SolicitudId = ?
                ORDER BY d.FechaDevolucion DESC
            """, (solicitud_id,))
            
            devoluciones = []
            for row in cursor.fetchall():
                devolucion = {
                    'devolucion_id': row[0],
                    'solicitud_id': row[1],
                    'usuario_nombre': row[2],
                    'cantidad_devuelta': row[3],
                    'fecha_devolucion': row[4],
                    'observacion': row[5] or ''
                }
                devoluciones.append(devolucion)
            return devoluciones
        except Exception as e:
            print(f"Error en obtener_devoluciones: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def puede_devolver(solicitud_id):
        """Verifica si una solicitud puede ser devuelta"""
        info = SolicitudModel.obtener_info_devolucion(solicitud_id)
        if not info:
            return False, "Solicitud no encontrada", None
        
        # Permitir devoluciones en estados Aprobada (2) y Entregada (4)
        if info['estado_id'] not in [2, 4]:
            return False, "Solo se pueden devolver solicitudes aprobadas o entregadas", info
        
        if info['cantidad_puede_devolver'] <= 0:
            return False, "No hay cantidad disponible para devolver", info
        
        return True, "Puede devolver", info

    # ========== MÉTODOS PRIVADOS ==========

    @staticmethod
    def _obtener_aprobador_id(usuario_id):
        """Obtiene el ID del aprobador para un usuario"""
        conn = get_database_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT AprobadorId FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
            row = cursor.fetchone()
            return row[0] if row and row[0] else 1
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _mapear_solicitudes(rows):
        """Mapea los resultados de la base de datos a diccionarios"""
        solicitudes = []
        for row in rows:
            solicitud = {
                'id': row[0],
                'material_nombre': row[1],
                'usuario_solicitante': row[2],
                'oficina_nombre': row[3],
                'oficina_id': row[4],
                'cantidad_solicitada': row[5],
                'estado': row[6],
                'fecha_solicitud': row[7],
                'observacion': row[8] or '',
                'material_id': row[9],
                'porcentaje_oficina': float(row[10]) if row[10] else 0,
                'valor_total_solicitado': float(row[11]) if row[11] else 0,
                'valor_oficina': float(row[12]) if row[12] else 0,
                'valor_sede': float(row[13]) if row[13] else 0,
                'valor_unitario': float(row[14]) if row[14] else 0,
                'stock_disponible': row[15] if row[15] else 0,
                'fecha_aprobacion': row[16],
                'cantidad_entregada': row[17] if row[17] else 0  # AGREGAR ESTA LÍNEA
            }
            solicitudes.append(solicitud)
        return solicitudes