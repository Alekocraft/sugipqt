# models/solicitudes_model.py
from database import get_database_connection


class SolicitudModel:
    # ==========================
    # CREAR / APROBAR / RECHAZAR
    # ==========================

    @staticmethod
    def crear(oficina_id, material_id, cantidad_solicitada, porcentaje_oficina, usuario_nombre, observacion=""):
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
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def aprobar(solicitud_id, usuario_aprobador_id):
        conn = get_database_connection()
        if conn is None:
            return False, "❌ Error de conexión a la base de datos"
        cursor = conn.cursor()
        try:
            # PRIMERO: Obtener información de la solicitud
            cursor.execute("""
                SELECT sm.MaterialId, sm.CantidadSolicitada, sm.EstadoId,
                       m.ValorUnitario, m.CantidadDisponible, sm.PorcentajeOficina
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                WHERE sm.SolicitudId = ? AND sm.EstadoId = 1
            """, (solicitud_id,))
            
            solicitud_info = cursor.fetchone()
            
            if not solicitud_info:
                return False, "❌ Solicitud no encontrada o no está pendiente"
            
            material_id, cantidad_solicitada, estado_id, valor_unitario, stock_disponible, porcentaje_oficina = solicitud_info
            
            # VERIFICAR STOCK DISPONIBLE
            if cantidad_solicitada > stock_disponible:
                return False, f"❌ Stock insuficiente. Disponible: {stock_disponible}, Solicitado: {cantidad_solicitada}"
            
            # OBTENER APROBADOR ID
            aprobador_id = SolicitudModel._obtener_aprobador_id(usuario_aprobador_id)
            
            # CALCULAR VALORES FINANCIEROS
            valor_total_solicitado = valor_unitario * cantidad_solicitada
            valor_oficina = valor_total_solicitado * (porcentaje_oficina / 100)
            valor_sede_principal = valor_total_solicitado - valor_oficina
            
            # EJECUTAR APROBACIÓN COMPLETA
            cursor.execute("""
                BEGIN TRANSACTION;
                
                -- 1. APROBAR LA SOLICITUD
                UPDATE dbo.SolicitudesMaterial 
                SET EstadoId = 2, -- Aprobada
                    AprobadorId = ?,
                    FechaAprobacion = GETDATE(),
                    CantidadEntregada = ?,
                    ValorTotalSolicitado = ?,
                    ValorOficina = ?,
                    ValorSedePrincipal = ?,
                    FechaUltimaEntrega = GETDATE()
                WHERE SolicitudId = ? AND EstadoId = 1;
                
                -- 2. ACTUALIZAR STOCK (restar cantidad solicitada)
                UPDATE dbo.Materiales 
                SET CantidadDisponible = CantidadDisponible - ?
                WHERE MaterialId = ?;
                
                -- 3. REGISTRAR EN HISTORIAL DE ENTREGAS
                INSERT INTO dbo.HistorialEntregas (
                    SolicitudId, CantidadEntregada, UsuarioEntrega, Observaciones
                ) VALUES (?, ?, 'Sistema', 'Aprobación completa');
                
                COMMIT TRANSACTION;
            """, (
                aprobador_id, cantidad_solicitada, valor_total_solicitado, 
                valor_oficina, valor_sede_principal, solicitud_id,
                cantidad_solicitada, material_id,
                solicitud_id, cantidad_solicitada
            ))
            
            conn.commit()
            return True, f"✅ Solicitud aprobada exitosamente. Stock actualizado: -{cantidad_solicitada} unidades"
            
        except Exception as e:
            conn.rollback()
            err = str(e)
            if "Límite mensual" in err:
                return False, "❌ Límite mensual excedido"
            if "Stock insuficiente" in err or "excede el inventario" in err:
                return False, "❌ Stock insuficiente"
            if "Solicitud no encontrada" in err:
                return False, "❌ Solicitud no encontrada"
            return False, f"❌ Error al aprobar: {err}"
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def aprobar_parcial(solicitud_id, usuario_aprobador_id, cantidad_aprobada):
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
            err = str(e)
            if "Cantidad aprobada inválida" in err:
                return False, "❌ Cantidad aprobada inválida"
            if "solicitudes pendientes" in err:
                return False, "❌ Solo solicitudes pendientes"
            if "Solicitud no encontrada" in err:
                return False, "❌ Solicitud no encontrada"
            return False, f"❌ Error al aprobar parcialmente: {err}"
        finally:
            cursor.close()
            conn.close()
            
    @staticmethod
    def rechazar(solicitud_id, usuario_aprobador_id, observacion=""):
        conn = get_database_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        try:
            aprobador_id = SolicitudModel._obtener_aprobador_id(usuario_aprobador_id)
            cursor.execute(
                "{CALL sp_RechazarSolicitud (?, ?, ?)}",
                (solicitud_id, aprobador_id, observacion)
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def actualizar_estado_solicitud(solicitud_id, nuevo_estado_id):
        conn = get_database_connection()
        if conn is None:
            return False
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE SolicitudesMaterial SET EstadoId = ? WHERE SolicitudId = ?",
                (nuevo_estado_id, solicitud_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    # ==========================
    # DEVOLUCIONES
    # ==========================

    @staticmethod
    def obtener_info_devolucion(solicitud_id):
        """
        - 1er SELECT: info de la solicitud, material, oficina, estado
        - 2do SELECT: suma de devoluciones
        - Se convierten TODAS las cantidades a int para que jsonify no explote.
        """
        conn = get_database_connection()
        if conn is None:
            return None

        cursor = conn.cursor()
        try:
            # 1) Info base de la solicitud
            cursor.execute("""
                SELECT 
                    sm.SolicitudId,
                    sm.EstadoId,
                    es.NombreEstado,
                    sm.CantidadSolicitada,
                    ISNULL(sm.CantidadEntregada, 0) AS CantidadEntregada,
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
            if not row:
                return None

            solicitud_id_db = int(row[0])
            estado_id = int(row[1]) if row[1] is not None else 0
            estado = row[2]
            # convertir a int para evitar Decimal en JSON
            cantidad_solicitada = int(row[3]) if row[3] is not None else 0
            cantidad_entregada = int(row[4]) if row[4] is not None else 0
            material_nombre = row[5]
            oficina_nombre = row[6]
            solicitante_nombre = row[7]

            # 2) Total devuelto hasta ahora
            cursor.execute("""
                SELECT ISNULL(SUM(CantidadDevuelta), 0)
                FROM dbo.Devoluciones
                WHERE SolicitudId = ?
            """, (solicitud_id_db,))
            row_dev = cursor.fetchone()
            cantidad_ya_devuelta = int(row_dev[0]) if row_dev and row_dev[0] is not None else 0

            cantidad_puede_devolver = cantidad_entregada - cantidad_ya_devuelta
            if cantidad_puede_devolver < 0:
                cantidad_puede_devolver = 0

            return {
                "solicitud_id": solicitud_id_db,
                "estado_id": estado_id,
                "estado": estado,
                "cantidad_solicitada": cantidad_solicitada,
                "cantidad_entregada": cantidad_entregada,
                "cantidad_ya_devuelta": cantidad_ya_devuelta,
                "cantidad_puede_devolver": cantidad_puede_devolver,
                "material_nombre": material_nombre,
                "oficina_nombre": oficina_nombre,
                "solicitante_nombre": solicitante_nombre,
            }
        except Exception as e:
            print("❌ ERROR en obtener_info_devolucion:", str(e))
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def registrar_devolucion(solicitud_id, cantidad_devuelta, usuario_nombre, observacion=""):
        conn = get_database_connection()
        if conn is None:
            return False, "❌ Error de conexión"
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    sm.MaterialId,
                    sm.CantidadSolicitada,
                    sm.CantidadEntregada,
                    sm.EstadoId,
                    ISNULL(sm.CantidadEntregada,0) 
                      - ISNULL((SELECT SUM(d.CantidadDevuelta) FROM Devoluciones d WHERE d.SolicitudId = sm.SolicitudId), 0) AS CantidadPuedeDevolver
                FROM dbo.SolicitudesMaterial sm
                WHERE sm.SolicitudId = ?
            """, (solicitud_id,))
            row = cursor.fetchone()
            if not row:
                return False, "❌ Solicitud no encontrada"

            material_id = row[0]
            estado_id = row[3]
            cantidad_puede_devolver = row[4] or 0

            if estado_id not in (2, 4):
                return False, "❌ Solo se pueden devolver solicitudes aprobadas o entregadas"

            if cantidad_devuelta <= 0:
                return False, "❌ La cantidad a devolver debe ser mayor a 0"

            if cantidad_devuelta > cantidad_puede_devolver:
                return False, f"❌ No puede devolver más de {cantidad_puede_devolver} unidades"

            nueva_pendiente = cantidad_puede_devolver - cantidad_devuelta

            cursor.execute("""
                INSERT INTO Devoluciones (
                    SolicitudId, MaterialId, CantidadDevuelta, FechaDevolucion,
                    UsuarioDevolucion, Observaciones, EstadoDevolucion, CondicionMaterial
                )
                VALUES (?, ?, ?, GETDATE(), ?, ?, 'COMPLETADA', 'BUENO')
            """, (solicitud_id, material_id, cantidad_devuelta, usuario_nombre, observacion))

            cursor.execute("""
                UPDATE Materiales
                SET CantidadDisponible = CantidadDisponible + ?
                WHERE MaterialId = ?
            """, (cantidad_devuelta, material_id))

            if nueva_pendiente <= 0:
                cursor.execute("""
                    UPDATE SolicitudesMaterial
                    SET EstadoId = 5,
                        FechaUltimaEntrega = GETDATE()
                    WHERE SolicitudId = ?
                """, (solicitud_id,))
            else:
                cursor.execute("""
                    UPDATE SolicitudesMaterial
                    SET FechaUltimaEntrega = GETDATE()
                    WHERE SolicitudId = ?
                """, (solicitud_id,))

            conn.commit()
            return True, "✅ Devolución registrada exitosamente"
        except Exception as e:
            conn.rollback()
            return False, f"❌ Error en devolución: {str(e)}"
        finally:
            cursor.close()
            conn.close()

    # ==========================
    # CONSULTAS LISTADO
    # ==========================

    @staticmethod
    def obtener_todas(oficina_id=None):
        return SolicitudModel.obtener_todas_ordenadas(oficina_id)

    @staticmethod
    def obtener_todas_ordenadas(oficina_id=None):
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
                    sm.CantidadEntregada
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
            """
            params = ()
            if oficina_id:
                sql += " WHERE sm.OficinaSolicitanteId = ?"
                params = (oficina_id,)
            sql += " ORDER BY sm.FechaSolicitud DESC"
            cursor.execute(sql, params)
            return SolicitudModel._mapear_solicitudes(cursor.fetchall())
        except Exception:
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_id(solicitud_id):
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
                    sm.CantidadEntregada
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
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_para_aprobador(oficina_id=None):
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
                    sm.CantidadEntregada
                FROM dbo.SolicitudesMaterial sm
                INNER JOIN dbo.Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN dbo.Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN dbo.EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                WHERE sm.EstadoId = 1
            """
            params = ()
            if oficina_id:
                sql += " AND sm.OficinaSolicitanteId = ?"
                params = (oficina_id,)
            cursor.execute(sql, params)
            return SolicitudModel._mapear_solicitudes(cursor.fetchall())
        except Exception:
            return []
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_devoluciones(solicitud_id):
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
                FROM Devoluciones d
                WHERE d.SolicitudId = ?
                ORDER BY d.FechaDevolucion DESC
            """, (solicitud_id,))
            devoluciones = []
            for row in cursor.fetchall():
                devoluciones.append({
                    "devolucion_id": row[0],
                    "solicitud_id": row[1],
                    "usuario_nombre": row[2],
                    "cantidad_devuelta": row[3],
                    "fecha_devolucion": row[4],
                    "observacion": row[5] or ""
                })
            return devoluciones
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def puede_devolver(solicitud_id):
        info = SolicitudModel.obtener_info_devolucion(solicitud_id)
        if not info:
            return False, "Solicitud no encontrada", None
        if info["estado_id"] not in (2, 4):
            return False, "Solo se pueden devolver solicitudes aprobadas o entregadas", info
        if info["cantidad_puede_devolver"] <= 0:
            return False, "No hay cantidad disponible para devolver", info
        return True, "Puede devolver", info

    # ==========================
    # PRIVADOS
    # ==========================

    @staticmethod
    def _obtener_aprobador_id(usuario_id):
        conn = get_database_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT AprobadorId FROM Usuarios WHERE UsuarioId = ?", (usuario_id,))
            row = cursor.fetchone()
            return row[0] if row else 1
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def _mapear_solicitudes(rows):
        solicitudes = []
        for row in rows:
            solicitudes.append({
                "id": row[0],
                "material_nombre": row[1],
                "usuario_solicitante": row[2],
                "oficina_nombre": row[3],
                "oficina_id": row[4],
                "cantidad_solicitada": row[5],
                "estado": row[6],
                "fecha_solicitud": row[7],
                "observacion": row[8] or "",
                "material_id": row[9],
                "porcentaje_oficina": float(row[10]) if row[10] is not None else 0.0,
                "valor_total_solicitado": float(row[11]) if row[11] is not None else 0.0,
                "valor_oficina": float(row[12]) if row[12] is not None else 0.0,
                "valor_sede": float(row[13]) if row[13] is not None else 0.0,
                "valor_unitario": float(row[14]) if row[14] is not None else 0.0,
                "stock_disponible": row[15] or 0,
                "fecha_aprobacion": row[16],
                "cantidad_entregada": row[17] or 0,
            })
        return solicitudes

    # ==========================
    # MÉTODOS ADICIONALES
    # ==========================

    @staticmethod
    def obtener_estadisticas_por_material(material_id):
        """Obtiene estadísticas de solicitudes para un material específico"""
        conn = get_database_connection()
        if conn is None:
            return [0, 0, 0, 0, 0, 0, 0]
        
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_solicitudes,
                    SUM(CASE WHEN EstadoId = 2 THEN 1 ELSE 0 END) as aprobadas,
                    SUM(CASE WHEN EstadoId = 1 THEN 1 ELSE 0 END) as pendientes,
                    SUM(ISNULL(CantidadEntregada, 0)) as total_entregado,
                    SUM(CASE WHEN EstadoId = 5 THEN 1 ELSE 0 END) as devueltas,
                    SUM(CASE WHEN EstadoId = 3 THEN 1 ELSE 0 END) as rechazadas,
                    SUM(CASE WHEN TieneNovedad = 1 THEN 1 ELSE 0 END) as con_novedad
                FROM SolicitudesMaterial
                WHERE MaterialId = ?
            """, (material_id,))
            
            row = cursor.fetchone()
            if row:
                return [
                    int(row[0] or 0),
                    int(row[1] or 0),
                    int(row[2] or 0),
                    int(row[3] or 0),
                    int(row[4] or 0),
                    int(row[5] or 0),
                    int(row[6] or 0)
                ]
            return [0, 0, 0, 0, 0, 0, 0]
            
        except Exception as e:
            print(f"Error obteniendo estadísticas para material {material_id}: {e}")
            return [0, 0, 0, 0, 0, 0, 0]
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_por_nombre(nombre):
        conn = get_database_connection()
        if conn is None:
            return None
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT OficinaId, NombreOficina, DirectorOficina, Ubicacion, 
                       EsPrincipal, Activo, FechaCreacion, Email
                FROM Oficinas
                WHERE UPPER(NombreOficina) = UPPER(?)
            """, (nombre,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'nombre': row[1],
                    'director': row[2],
                    'ubicacion': row[3],
                    'es_principal': bool(row[4]) if row[4] is not None else False,
                    'activo': bool(row[5]) if row[5] is not None else True,
                    'fecha_creacion': row[6],
                    'email': row[7]
                }
            return None
        except Exception as e:
            print(f"Error obteniendo oficina por nombre: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def obtener_todas_con_detalle():
        """Obtiene todas las solicitudes con detalles completos"""
        conn = get_database_connection()
        if not conn:
            return []
        try:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    sm.SolicitudId,
                    sm.OficinaSolicitanteId,
                    o.NombreOficina,
                    sm.MaterialId,
                    m.NombreElemento,
                    sm.CantidadSolicitada,
                    sm.CantidadEntregada,
                    sm.FechaSolicitud,
                    sm.EstadoId,
                    es.NombreEstado,
                    sm.AprobadorId,
                    a.NombreAprobador,
                    sm.FechaAprobacion,
                    sm.PorcentajeOficina,
                    sm.UsuarioSolicitante,
                    sm.Observacion,
                    sm.ValorTotalSolicitado,
                    sm.ValorOficina,
                    sm.ValorSedePrincipal
                FROM SolicitudesMaterial sm
                INNER JOIN Oficinas o ON sm.OficinaSolicitanteId = o.OficinaId
                INNER JOIN Materiales m ON sm.MaterialId = m.MaterialId
                INNER JOIN EstadosSolicitud es ON sm.EstadoId = es.EstadoId
                LEFT JOIN Aprobadores a ON sm.AprobadorId = a.AprobadorId
                ORDER BY sm.FechaSolicitud DESC
            """)
            
            columns = [column[0] for column in cursor.description]
            solicitudes = []
            for row in cursor.fetchall():
                solicitud = dict(zip(columns, row))
                # Renombrar campos para consistencia
                solicitud['id'] = solicitud.pop('SolicitudId')
                solicitud['oficina_id'] = solicitud.pop('OficinaSolicitanteId')
                solicitud['oficina_nombre'] = solicitud.pop('NombreOficina')
                solicitud['material_id'] = solicitud.pop('MaterialId')
                solicitud['material_nombre'] = solicitud.pop('NombreElemento')
                solicitud['cantidad_solicitada'] = solicitud.pop('CantidadSolicitada')
                solicitud['cantidad_entregada'] = solicitud.pop('CantidadEntregada')
                solicitud['fecha_solicitud'] = solicitud.pop('FechaSolicitud')
                solicitud['estado_id'] = solicitud.pop('EstadoId')
                solicitud['estado'] = solicitud.pop('NombreEstado')
                solicitud['aprobador_id'] = solicitud.pop('AprobadorId')
                solicitud['aprobador_nombre'] = solicitud.pop('NombreAprobador')
                solicitud['fecha_aprobacion'] = solicitud.pop('FechaAprobacion')
                solicitud['porcentaje_oficina'] = solicitud.pop('PorcentajeOficina')
                solicitud['usuario_solicitante'] = solicitud.pop('UsuarioSolicitante')
                solicitud['observacion'] = solicitud.pop('Observacion')
                solicitudes.append(solicitud)
            
            return solicitudes
            
        except Exception as e:
            print(f"Error obteniendo solicitudes con detalle: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()