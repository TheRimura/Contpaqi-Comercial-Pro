import json
from functools import cache
from platform import node

from cayal.comandos_base_datos import ComandosBaseDatos


class BaseDatos(ComandosBaseDatos):
    def __init__(self):
        super().__init__(servidor=node())

    def buscar_productos_por_nombre(self, termino):
        configuracion = self.buscar_configuracion_transformaciones()

        return self.fetchall(
            """
            SELECT P.ProductID
            FROM dbo.orgProduct AS P
            WHERE P.DeletedOn IS NULL
              AND P.AvailableForSale = 1
              AND P.ProductName LIKE ?
              AND (
                    EXISTS (
                        SELECT 1
                        FROM dbo.CategoriasTransformacion AS C
                        WHERE C.activa = 1
                          AND UPPER(LTRIM(RTRIM(C.categoria))) =
                              UPPER(LTRIM(RTRIM(P.Category1)))
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM dbo.zvwFormulasListasPCocinar AS F
                        INNER JOIN dbo.orgProduct AS CP
                            ON CP.ProductID = F.ComponenteID
                           AND CP.DeletedOn IS NULL
                        INNER JOIN dbo.CategoriasTransformacion AS C
                            ON C.activa = 1
                           AND UPPER(LTRIM(RTRIM(C.categoria))) =
                               UPPER(LTRIM(RTRIM(CP.Category1)))
                        WHERE F.ProductID = P.ProductID
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM dbo.zvwEquivalenciasTransKoben AS E
                        INNER JOIN dbo.orgProduct AS OP
                            ON OP.ProductID = CASE
                                WHEN E.ProductID1 = P.ProductID
                                THEN E.ProductID2
                                ELSE E.ProductID1
                            END
                           AND OP.DeletedOn IS NULL
                        INNER JOIN dbo.CategoriasTransformacion AS C
                            ON C.activa = 1
                           AND UPPER(LTRIM(RTRIM(C.categoria))) =
                               UPPER(LTRIM(RTRIM(OP.Category1)))
                        WHERE E.Status = ?
                          AND P.ProductID IN (
                              E.ProductID1,
                              E.ProductID2
                          )
                    )
              )
            ORDER BY P.ProductName
            """,
            (
                f"%{termino}%",
                configuracion["estatus_equivalencia"],
            ),
        )

    def buscar_configuracion_transformaciones(self):
        filas = self.fetchall(
            """
            SELECT TOP 1
                C.id_configuracion,
                C.almacen_id,
                A.DepotName AS almacen,
                C.movimiento_salida,
                C.movimiento_entrada,
                C.movimiento_salida_formula,
                C.movimiento_entrada_formula,
                C.modulo_entrada,
                C.modulo_salida,
                C.estatus_equivalencia,
                C.catalogo_salida,
                C.catalogo_entrada
            FROM dbo.ConfiguracionTransformaciones AS C
            INNER JOIN dbo.orgDepot AS A
                ON A.DepotID = C.almacen_id
               AND A.DeletedOn IS NULL
            WHERE C.activa = 1
            ORDER BY C.id_configuracion
            """,
        )

        if not filas:
            raise RuntimeError(
                "No existe una configuracion activa para transformaciones"
            )

        return filas[0]

    def buscar_configuracion_seguridad(self):
        filas = self.fetchall(
            """
            SELECT TOP 1
                grupo_llave_maestra,
                nombre_cookie,
                duracion_sesion_segundos,
                clave_firma
            FROM dbo.ConfiguracionSeguridad
            WHERE activa = 1
            ORDER BY id_configuracion
            """
        )

        if not filas:
            raise RuntimeError(
                "No existe una configuracion activa de seguridad"
            )

        return filas[0]

    def buscar_usuario_login(self, nombre_usuario):
        filas = self.fetchall(
            """
            SELECT
                U.UserID,
                U.UserName,
                U.UserGroupID,
                G.GroupName,
                CU.UserPassword AS HashUsuario
            FROM dbo.engUser AS U
            LEFT JOIN dbo.engUserGroup AS G
                ON G.UserGroupID = U.UserGroupID
            LEFT JOIN dbo.engUserCayal AS CU
                ON CU.UserID = U.UserID
            WHERE U.UserName = ?
              AND U.DeletedOn IS NULL
            """,
            (nombre_usuario.strip(),),
        )
        return filas[0] if filas else None

    def buscar_hashes_grupo_maestro(self):
        configuracion = self.buscar_configuracion_seguridad()

        return self.fetchall(
            """
            SELECT UC.UserPassword
            FROM dbo.engUser AS U
            INNER JOIN dbo.engUserGroup AS G
                ON G.UserGroupID = U.UserGroupID
            INNER JOIN dbo.engUserCayal AS UC
                ON UC.UserID = U.UserID
            WHERE U.DeletedOn IS NULL
              AND UC.UserPassword IS NOT NULL
              AND G.GroupName = ?
            ORDER BY U.UserID
            """,
            (configuracion["grupo_llave_maestra"],),
        )

    def buscar_porcentajes_merma(self):
        return {
            str(fila["categoria"]).strip().upper(): (
                float(fila["porcentaje_merma"])
                if fila["porcentaje_merma"] is not None
                else 0
            )
            for fila in self.fetchall(
                """
                SELECT categoria, porcentaje_merma
                FROM dbo.CategoriasTransformacion
                WHERE activa = 1
                """
            )
        }

    def buscar_info_productos(
        self,
        ids_productos,
        almacen_id=None,
        **kwargs,
    ):
        ids_limpios = list(dict.fromkeys(
            int(producto_id)
            for producto_id in ids_productos
            if producto_id
        ))

        if not ids_limpios:
            return []

        configuracion = self.buscar_configuracion_transformaciones()
        almacen_id = almacen_id or configuracion["almacen_id"]

        parametros = ", ".join("?" for _ in ids_limpios)
        return self.fetchall(
            f"""
            SELECT
                P.ProductID,
                P.ProductKey,
                P.ProductName,
                COALESCE(
                    CM.categoria,
                    CFM.categoria,
                    CEM.categoria,
                    P.Category1
                ) AS Category1,
                P.Category1 AS CategoryOriginal,
                P.Unit,
                P.CostPrice,
                ISNULL(I.QtyPresent, 0) AS QtyPresent,
                P.ProductTypeIDCayal
            FROM dbo.orgProduct AS P
            OUTER APPLY (
                SELECT SUM(Q.QtyPresent) AS QtyPresent
                FROM dbo.vwLBSProductQuantityList AS Q
                WHERE Q.ProductID = P.ProductID
                  AND Q.DepotID = ?
            ) AS I
            OUTER APPLY (
                SELECT TOP 1 C.categoria
                FROM dbo.CategoriasTransformacion AS C
                WHERE C.activa = 1
                  AND UPPER(LTRIM(RTRIM(C.categoria))) =
                      UPPER(LTRIM(RTRIM(P.Category1)))
            ) AS CM
            OUTER APPLY (
                SELECT TOP 1 C.categoria
                FROM dbo.zvwFormulasListasPCocinar AS F
                INNER JOIN dbo.orgProduct AS CP
                    ON CP.ProductID = F.ComponenteID
                   AND CP.DeletedOn IS NULL
                INNER JOIN dbo.CategoriasTransformacion AS C
                    ON C.activa = 1
                   AND UPPER(LTRIM(RTRIM(C.categoria))) =
                       UPPER(LTRIM(RTRIM(CP.Category1)))
                WHERE F.ProductID = P.ProductID
                ORDER BY F.IDComp
            ) AS CFM
            OUTER APPLY (
                SELECT TOP 1 C.categoria
                FROM dbo.zvwEquivalenciasTransKoben AS E
                INNER JOIN dbo.orgProduct AS OP
                    ON OP.ProductID = CASE
                        WHEN E.ProductID1 = P.ProductID
                        THEN E.ProductID2
                        ELSE E.ProductID1
                    END
                   AND OP.DeletedOn IS NULL
                INNER JOIN dbo.CategoriasTransformacion AS C
                    ON C.activa = 1
                   AND UPPER(LTRIM(RTRIM(C.categoria))) =
                       UPPER(LTRIM(RTRIM(OP.Category1)))
                WHERE E.Status = ?
                  AND P.ProductID IN (
                      E.ProductID1,
                      E.ProductID2
                  )
                ORDER BY E.ID
            ) AS CEM
            WHERE P.ProductID IN ({parametros})
              AND P.DeletedOn IS NULL
            ORDER BY P.ProductName
            """,
            (
                almacen_id,
                configuracion["estatus_equivalencia"],
                *ids_limpios,
            ),
        )

    def buscar_ids_productos_modulo(self, ids_productos):
        productos = self.buscar_info_productos(ids_productos)
        categorias_activas = {
            str(fila["categoria"]).strip().upper()
            for fila in self.fetchall(
                """
                SELECT categoria
                FROM dbo.CategoriasTransformacion
                WHERE activa = 1
                """
            )
        }
        return {
            producto["ProductID"]
            for producto in productos
            if str(producto["Category1"]).strip().upper()
            in categorias_activas
        }

    def buscar_resultantes_transformacion(self, producto_origen_id):
        configuracion = self.buscar_configuracion_transformaciones()

        return self.fetchall(
            """
            SELECT ProductID2, Cant1, Cant2
            FROM dbo.zvwEquivalenciasTransKoben
            WHERE ProductID1 = ?
              AND Status = ?
            ORDER BY ID
            """,
            (
                producto_origen_id,
                configuracion["estatus_equivalencia"],
            ),
        )

    def buscar_componentes_formula(self, producto_id):
        return self.fetchall(
            """
            SELECT ComponenteID, CantidadComp
            FROM dbo.zvwFormulasListasPCocinar
            WHERE ProductID = ?
            ORDER BY IDComp
            """,
            (producto_id,),
        )

    def buscar_tipo_movimiento(self, tipo, nombre):
        configuracion = self.buscar_configuracion_transformaciones()
        tipo_normalizado = str(tipo).strip().lower()
        grupo = configuracion.get(f"catalogo_{tipo_normalizado}")

        if not grupo:
            raise ValueError("Tipo de movimiento no valido")

        filas = self.fetchall(
            """
            SELECT TOP 1 ItemData, ItemValue
            FROM dbo.engRefCombo
            WHERE CboGroupName = ?
              AND UPPER(LTRIM(RTRIM(ItemValue))) =
                  UPPER(LTRIM(RTRIM(?)))
            """,
            (grupo, nombre),
        )

        if not filas:
            raise RuntimeError(
                f"No existe el movimiento {nombre!r} para {tipo}"
            )

        return {
            "id": int(filas[0]["ItemData"]),
            "nombre": filas[0]["ItemValue"],
        }

    def buscar_transformacion_por_operacion(self, id_operacion):
        filas = self.fetchall(
            """
            SELECT TOP 1
                id_transformacion,
                documento_salida,
                documento_entrada,
                almacen_id,
                estado_erp,
                error_erp
            FROM dbo.Transformaciones
            WHERE id_operacion = ?
            """,
            (str(id_operacion),),
        )
        return filas[0] if filas else None

    def actualizar_integracion_erp(
        self,
        transformacion_id,
        documento_salida=None,
        documento_entrada=None,
        estado=None,
        error=None,
    ):
        self.command(
            """
            UPDATE dbo.Transformaciones
            SET documento_salida =
                    COALESCE(?, documento_salida),
                documento_entrada =
                    COALESCE(?, documento_entrada),
                estado_erp =
                    COALESCE(?, estado_erp),
                error_erp = ?
            WHERE id_transformacion = ?
            """,
            (
                documento_salida,
                documento_entrada,
                estado,
                error,
                transformacion_id,
            ),
        )

    def configurar_almacen_documento(self, documento_id, almacen_id):
        self.command(
            """
            UPDATE dbo.docDocument
            SET DepotID = ?,
                DepotIDFrom = ?
            WHERE DocumentID = ?
            """,
            (almacen_id, almacen_id, documento_id),
        )

    def buscar_productos_partidas_documento(self, documento_id):
        filas = self.fetchall(
            """
            SELECT ProductID
            FROM dbo.docDocumentItem
            WHERE DocumentID = ?
              AND DeletedOn IS NULL
            """,
            (documento_id,),
        )
        return {
            fila["ProductID"]
            for fila in filas
        }

    def insertar_partida_movimiento(
        self,
        documento_id,
        producto_id,
        almacen_id,
        cantidad,
        modulo_id,
        comentario,
    ):
        costo_producto = self.buscar_ultimo_costo_producto(producto_id)
        costo = float(costo_producto.get("CostPrice") or 0)
        cantidad_numero = float(cantidad)
        total = costo * cantidad_numero

        partida_id = self.insertar_partida_documento_cayal((
            documento_id,
            producto_id,
            almacen_id,
            cantidad_numero,
            0,
            costo,
            total,
            0,
            modulo_id,
            comentario,
        ))

        if not partida_id:
            raise RuntimeError(
                f"No fue posible insertar el producto {producto_id}"
            )

        self.command(
            """
            UPDATE dbo.docDocumentItem
            SET DepotID = ?,
                CostPrice = ?,
                UnitPrice = ?,
                Total = ?
            WHERE DocumentItemID = ?
            """,
            (
                almacen_id,
                costo,
                costo,
                total,
                partida_id,
            ),
        )

        return partida_id

    def registrar_recalculo_si_pendiente(
        self,
        documento_id,
        id_operacion,
    ):
        filas = self.fetchall(
            """
            SELECT TOP 1 ID
            FROM dbo.zvwDocumentosRecalculadosCayal
            WHERE DocumentID = ?
              AND UUID = ?
            """,
            (documento_id, str(id_operacion)),
        )

        if filas:
            return

        self.registrar_documento_a_recalcular(
            documento_id,
            0,
            str(id_operacion),
        )

    def buscar_folio_documento(self, documento_id):
        filas = self.fetchall(
            """
            SELECT
                ISNULL(FolioPrefix, '') + ISNULL(Folio, '') AS Folio
            FROM dbo.docDocument
            WHERE DocumentID = ?
            """,
            (documento_id,),
        )
        return filas[0]["Folio"] if filas else None

    def registrar_transformacion(
        self,
        producto_origen_id,
        producto_seleccionado_id,
        cantidad_origen,
        usuario,
        usuario_id,
        tipo_transformacion,
        productos_resultantes,
        componentes_formula,
        peso_merma,
        almacen_id,
        porcentaje_merma_esperado=None,
        observaciones_merma=None,
        id_operacion=None,
    ):
        productos_json = json.dumps([
            {
                "producto_id": producto.producto_id,
                "cantidad": float(producto.cantidad),
                "unidad": producto.unidad,
            }
            for producto in productos_resultantes
        ])
        componentes_json = json.dumps([
            {
                "producto_id": componente.producto_id,
                "cantidad": float(componente.cantidad),
                "unidad": componente.unidad,
                "es_producto_base": componente.es_producto_base,
            }
            for componente in componentes_formula
        ])

        return int(self.exec_stored_procedure(
            "zvwRegistrarTransformacionCayal",
            (
                str(id_operacion),
                producto_origen_id,
                producto_seleccionado_id,
                float(cantidad_origen),
                usuario,
                usuario_id,
                tipo_transformacion,
                (
                    float(porcentaje_merma_esperado)
                    if porcentaje_merma_esperado is not None
                    else None
                ),
                almacen_id,
                float(peso_merma),
                observaciones_merma,
                productos_json,
                componentes_json or None,
            ),
        ))

    def buscar_historial_transformaciones(self, transformacion_id=None):
        filtro = ""
        parametros = ()

        if transformacion_id is not None:
            filtro = "WHERE T.id_transformacion = ?"
            parametros = (transformacion_id,)

        return self.fetchall(
            f"""
            SELECT
                T.id_transformacion,
                T.producto_origen,
                T.producto_seleccionado,
                T.cantidad_origen,
                T.usuario_responsable,
                T.usuario_id,
                T.tipo_transformacion,
                T.porcentaje_merma_esperado,
                T.id_operacion,
                T.fecha_creacion,
                T.documento_salida,
                T.documento_entrada,
                T.almacen_id,
                A.DepotName AS almacen,
                CASE
                    WHEN T.documento_salida IS NOT NULL
                     AND T.documento_entrada IS NOT NULL
                     AND (
                        SELECT COUNT(DISTINCT R.DocumentID)
                        FROM dbo.zvwDocumentosRecalculadosCayal AS R
                        WHERE R.DocumentID IN (
                            T.documento_salida,
                            T.documento_entrada
                        )
                     ) = 2
                     AND NOT EXISTS (
                        SELECT 1
                        FROM dbo.zvwDocumentosRecalculadosCayal AS R
                        WHERE R.DocumentID IN (
                            T.documento_salida,
                            T.documento_entrada
                        )
                          AND R.Status = 0
                     )
                    THEN 'completada'
                    ELSE T.estado_erp
                END AS estado_erp,
                T.error_erp,
                ISNULL(DS.FolioPrefix, '') +
                    ISNULL(DS.Folio, '') AS folio_salida,
                ISNULL(DE.FolioPrefix, '') +
                    ISNULL(DE.Folio, '') AS folio_entrada,
                P.ProductKey AS origen_clave,
                P.ProductName AS origen_nombre,
                P.Category1 AS origen_categoria,
                P.Unit AS origen_unidad,
                M.peso_merma,
                M.motivo
            FROM dbo.Transformaciones AS T
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = T.producto_origen
            LEFT JOIN dbo.orgDepot AS A
                ON A.DepotID = T.almacen_id
            LEFT JOIN dbo.docDocument AS DS
                ON DS.DocumentID = T.documento_salida
            LEFT JOIN dbo.docDocument AS DE
                ON DE.DocumentID = T.documento_entrada
            OUTER APPLY (
                SELECT TOP 1
                    merma.peso_merma,
                    merma.motivo
                FROM dbo.Mermas AS merma
                WHERE merma.id_transformacion = T.id_transformacion
                ORDER BY merma.id_merma DESC
            ) AS M
            {filtro}
            ORDER BY T.id_transformacion DESC
            """,
            parametros,
        )

    def buscar_detalles_transformaciones(self, ids_transformaciones):
        ids_limpios = list(dict.fromkeys(
            int(transformacion_id)
            for transformacion_id in ids_transformaciones
            if transformacion_id
        ))

        if not ids_limpios:
            return []

        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            SELECT
                D.id_transformacion,
                D.id_detalle,
                D.producto_resultado,
                D.cantidad_resultado,
                D.unidad_resultado,
                P.ProductKey,
                P.ProductName,
                P.Category1,
                P.Unit
            FROM dbo.DetalleTransformaciones AS D
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = D.producto_resultado
            WHERE D.id_transformacion IN ({parametros})
            ORDER BY D.id_transformacion DESC, D.id_detalle
            """,
            tuple(ids_limpios),
        )

    def buscar_componentes_transformaciones(self, ids_transformaciones):
        ids_limpios = list(dict.fromkeys(
            int(transformacion_id)
            for transformacion_id in ids_transformaciones
            if transformacion_id
        ))

        if not ids_limpios:
            return []

        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            SELECT
                C.id_transformacion,
                C.producto_componente,
                C.cantidad,
                C.unidad,
                C.es_producto_base,
                P.ProductKey,
                P.ProductName,
                P.Category1,
                P.Unit
            FROM dbo.ComponentesTransformacion AS C
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = C.producto_componente
            WHERE C.id_transformacion IN ({parametros})
            ORDER BY C.id_transformacion DESC, C.id_componente
            """,
            tuple(ids_limpios),
        )

    def buscar_ids_productos_existentes(self, ids_productos):
        ids_limpios = list(dict.fromkeys(
            int(producto_id)
            for producto_id in ids_productos
            if producto_id
        ))

        if not ids_limpios:
            return set()

        parametros = ", ".join("?" for _ in ids_limpios)
        filas = self.fetchall(
            f"""
            SELECT ProductID
            FROM dbo.orgProduct
            WHERE ProductID IN ({parametros})
              AND DeletedOn IS NULL
            """,
            tuple(ids_limpios),
        )
        return {
            fila["ProductID"]
            for fila in filas
        }

    def buscar_bases_formulas(self, ids_productos):
        ids_limpios = list(dict.fromkeys(
            int(producto_id)
            for producto_id in ids_productos
            if producto_id
        ))

        if not ids_limpios:
            return []

        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            WITH Componentes AS (
                SELECT
                    F.ProductID,
                    F.ComponenteID,
                    ROW_NUMBER() OVER (
                        PARTITION BY F.ProductID
                        ORDER BY
                            CASE
                                WHEN UPPER(LTRIM(RTRIM(P.Category1)))
                                     <> 'INSUMOS'
                                THEN 0
                                ELSE 1
                            END,
                            F.IDComp
                    ) AS posicion
                FROM dbo.zvwFormulasListasPCocinar AS F
                INNER JOIN dbo.orgProduct AS P
                    ON P.ProductID = F.ComponenteID
                WHERE F.ProductID IN ({parametros})
                  AND UPPER(LTRIM(RTRIM(P.Unit))) = 'KILO'
            )
            SELECT ProductID, ComponenteID
            FROM Componentes
            WHERE posicion = 1
            """,
            tuple(ids_limpios),
        )


@cache
def obtener_base_datos():
    return BaseDatos()
