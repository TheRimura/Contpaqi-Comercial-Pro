import json
from functools import cache
from platform import node
from typing import Optional, List

from cayal.comandos_base_datos import ComandosBaseDatos
from sentry_sdk.client import module_not_found_error


class BaseDatos(ComandosBaseDatos):
    def __init__(self):
        super().__init__(servidor=node())
        self.base_de_datos = None

    @staticmethod
    def valor_escalar(fila, campo):
        if fila is None:
            return None

        if isinstance(fila, dict):
            return fila.get(campo)

        if isinstance(fila, (list, tuple)):
            return fila[0] if fila else None

        return fila

    def buscar_productos_por_nombre(self, termino):
        configuracion = self.buscar_configuracion_transformaciones()

        return self.fetchall(
            """
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
                configuracion["almacen_id"],
                configuracion["estatus_equivalencia"],
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

    def buscar_ids_productos_modulo(self, ids_productos):
        ids_limpios = list(dict.fromkeys(
            int(producto_id)
            for producto_id in ids_productos
            if producto_id
        ))

        if not ids_limpios:
            return set()

        configuracion = self.buscar_configuracion_transformaciones()
        parametros = ", ".join("?" for _ in ids_limpios)

        return {
            fila["ProductID"]
            for fila in self.fetchall(
                f"""
                SELECT P.ProductID
                FROM dbo.orgProduct AS P
                WHERE P.ProductID IN ({parametros})
                  AND P.DeletedOn IS NULL
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
                """,
                (
                    *ids_limpios,
                    configuracion["estatus_equivalencia"],
                ),
            )
        }

    def buscar_resultantes_transformacion(self, producto_origen_id):
        configuracion = self.buscar_configuracion_transformaciones()

        return self.fetchall(
            """
            SELECT
                E.ProductID2,
                E.Cant1,
                E.Cant2,
                P.ProductID,
                P.ProductKey,
                P.ProductName,
                COALESCE(CP.categoria, CO.categoria, P.Category1)
                    AS Category1,
                P.Unit,
                P.CostPrice,
                ISNULL(I.QtyPresent, 0) AS QtyPresent,
                P.ProductTypeIDCayal
            FROM dbo.zvwEquivalenciasTransKoben AS E
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = E.ProductID2
               AND P.DeletedOn IS NULL
            INNER JOIN dbo.orgProduct AS O
                ON O.ProductID = E.ProductID1
               AND O.DeletedOn IS NULL
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
            ) AS CP
            OUTER APPLY (
                SELECT TOP 1 C.categoria
                FROM dbo.CategoriasTransformacion AS C
                WHERE C.activa = 1
                  AND UPPER(LTRIM(RTRIM(C.categoria))) =
                      UPPER(LTRIM(RTRIM(O.Category1)))
            ) AS CO
            WHERE E.ProductID1 = ?
              AND E.Status = ?
            ORDER BY E.ID
            """,
            (
                configuracion["almacen_id"],
                producto_origen_id,
                configuracion["estatus_equivalencia"],
            ),
        )

    def buscar_productos_por_ids(self, ids_productos):
        ids_limpios = list(dict.fromkeys(
            int(producto_id)
            for producto_id in ids_productos
            if producto_id
        ))

        if not ids_limpios:
            return []

        configuracion = self.buscar_configuracion_transformaciones()
        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            SELECT
                P.ProductID,
                P.ProductKey,
                P.ProductName,
                P.Category1,
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
            WHERE P.ProductID IN ({parametros})
              AND P.DeletedOn IS NULL
            """,
            (
                configuracion["almacen_id"],
                *ids_limpios,
            ),
        )

    def buscar_configuracion_usuario_para_producto(self, producto_id):
        configuracion = self.buscar_configuracion_transformaciones()
        filas = self.fetchall(
            """
            SELECT TOP 1
                TU.id_transformacion_usuario,
                TU.nombre_transformacion,
                TU.producto_origen,
                TU.producto_formula,
                TU.cantidad_base,
                TU.porcentaje_merma,
                PO.ProductID AS origen_id,
                PO.ProductKey AS origen_clave,
                PO.ProductName AS origen_nombre,
                PO.Category1 AS origen_categoria,
                PO.Unit AS origen_unidad,
                PO.CostPrice AS origen_costo,
                ISNULL(IO.QtyPresent, 0) AS origen_existencia,
                PF.ProductID AS formula_id,
                PF.ProductKey AS formula_clave,
                PF.ProductName AS formula_nombre,
                PF.Category1 AS formula_categoria,
                PF.Unit AS formula_unidad,
                PF.CostPrice AS formula_costo,
                ISNULL(IFM.QtyPresent, 0) AS formula_existencia
            FROM dbo.TransformacionesUsuario AS TU
            INNER JOIN dbo.orgProduct AS PO
                ON PO.ProductID = TU.producto_origen
               AND PO.DeletedOn IS NULL
            LEFT JOIN dbo.orgProduct AS PF
                ON PF.ProductID = TU.producto_formula
               AND PF.DeletedOn IS NULL
            OUTER APPLY (
                SELECT SUM(Q.QtyPresent) AS QtyPresent
                FROM dbo.vwLBSProductQuantityList AS Q
                WHERE Q.ProductID = PO.ProductID
                  AND Q.DepotID = ?
            ) AS IO
            OUTER APPLY (
                SELECT SUM(Q.QtyPresent) AS QtyPresent
                FROM dbo.vwLBSProductQuantityList AS Q
                WHERE Q.ProductID = PF.ProductID
                  AND Q.DepotID = ?
            ) AS IFM
            WHERE TU.activa = 1
              AND (
                    TU.producto_formula = ?
                    OR TU.producto_origen = ?
              )
            ORDER BY
                CASE
                    WHEN TU.producto_formula = ? THEN 0
                    ELSE 1
                END,
                TU.id_transformacion_usuario DESC
            """,
            (
                configuracion["almacen_id"],
                configuracion["almacen_id"],
                producto_id,
                producto_id,
                producto_id,
            ),
        )
        return filas[0] if filas else None

    def contar_configuraciones_usuario(self):
        fila = self.fetchone(
            """
            SELECT COUNT(*) AS total
            FROM dbo.TransformacionesUsuario
            WHERE activa = 1
            """
        )

        if fila is None:
            return 0

        if isinstance(fila, dict):
            return int(fila["total"] or 0)

        return int(fila)

    def buscar_configuraciones_usuario(self, pagina=1, limite=10):
        inicio = (int(pagina) - 1) * int(limite)

        return self.fetchall(
            """
            SELECT
                TU.id_transformacion_usuario,
                TU.nombre_transformacion,
                TU.producto_origen,
                PO.ProductKey AS origen_clave,
                PO.ProductName AS origen_nombre,
                PO.Category1 AS origen_categoria,
                PO.Unit AS origen_unidad,
                TU.producto_formula,
                PF.ProductKey AS formula_clave,
                PF.ProductName AS formula_nombre,
                PF.Category1 AS formula_categoria,
                PF.Unit AS formula_unidad,
                TU.cantidad_base,
                TU.porcentaje_merma,
                TU.usuario_creacion,
                U.UserName AS usuario_creacion_nombre,
                TU.fecha_creacion,
                TU.usuario_actualizacion,
                UA.UserName AS usuario_actualizacion_nombre,
                TU.fecha_actualizacion,
                TU.activa,
                TU.observaciones
            FROM dbo.TransformacionesUsuario AS TU
            INNER JOIN dbo.orgProduct AS PO
                ON PO.ProductID = TU.producto_origen
            LEFT JOIN dbo.orgProduct AS PF
                ON PF.ProductID = TU.producto_formula
            INNER JOIN dbo.engUser AS U
                ON U.UserID = TU.usuario_creacion
            LEFT JOIN dbo.engUser AS UA
                ON UA.UserID = TU.usuario_actualizacion
            WHERE TU.activa = 1
            ORDER BY TU.id_transformacion_usuario DESC
            OFFSET ? ROWS
            FETCH NEXT ? ROWS ONLY
            """,
            (inicio, int(limite)),
        )

    def buscar_detalles_configuraciones_usuario(self, ids_configuraciones):
        ids_limpios = list(dict.fromkeys(
            int(configuracion_id)
            for configuracion_id in ids_configuraciones
            if configuracion_id
        ))

        if not ids_limpios:
            return []

        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            SELECT
                D.id_transformacion_usuario,
                D.id_detalle_usuario,
                D.producto_resultante,
                P.ProductID,
                D.cantidad_resultante,
                D.unidad,
                D.participa_balance,
                D.orden,
                D.activa,
                P.ProductKey,
                P.ProductName,
                P.Category1,
                P.Unit,
                P.CostPrice,
                ISNULL(I.QtyPresent, 0) AS QtyPresent
            FROM dbo.TransformacionesUsuarioDetalle AS D
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = D.producto_resultante
            OUTER APPLY (
                SELECT SUM(Q.QtyPresent) AS QtyPresent
                FROM dbo.vwLBSProductQuantityList AS Q
                WHERE Q.ProductID = P.ProductID
                  AND Q.DepotID = (
                      SELECT TOP 1 almacen_id
                      FROM dbo.ConfiguracionTransformaciones
                      WHERE activa = 1
                      ORDER BY id_configuracion
                  )
            ) AS I
            WHERE D.id_transformacion_usuario IN ({parametros})
              AND D.activa = 1
            ORDER BY D.id_transformacion_usuario DESC, D.orden
            """,
            tuple(ids_limpios),
        )

    def tabla_componentes_configuracion_existe(self):
        fila = self.fetchone(
            """
            SELECT OBJECT_ID(
                N'dbo.TransformacionesUsuarioComponente',
                N'U'
            ) AS tabla_id
            """
        )

        if not fila:
            return False

        if isinstance(fila, dict):
            return fila["tabla_id"] is not None

        return fila is not None

    def asegurar_tabla_componentes_configuracion(self):
        self.command(
            """
            IF OBJECT_ID(
                N'dbo.TransformacionesUsuarioComponente',
                N'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.TransformacionesUsuarioComponente (
                    id_componente_usuario INT IDENTITY(1, 1) NOT NULL
                        CONSTRAINT PK_TransformacionesUsuarioComponente
                        PRIMARY KEY,
                    id_transformacion_usuario INT NOT NULL,
                    producto_componente INT NOT NULL,
                    cantidad DECIMAL(18, 6) NOT NULL,
                    unidad NVARCHAR(50) NOT NULL,
                    es_producto_base BIT NOT NULL
                        CONSTRAINT DF_TUC_es_producto_base DEFAULT 0,
                    tipo_componente NVARCHAR(30) NOT NULL
                        CONSTRAINT DF_TUC_tipo_componente DEFAULT 'INSUMO',
                    participa_balance BIT NOT NULL
                        CONSTRAINT DF_TUC_participa_balance DEFAULT 0,
                    orden INT NOT NULL
                        CONSTRAINT DF_TUC_orden DEFAULT 1,
                    activa BIT NOT NULL
                        CONSTRAINT DF_TUC_activa DEFAULT 1,
                    fecha_creacion DATETIME NOT NULL
                        CONSTRAINT DF_TUC_fecha_creacion DEFAULT GETDATE()
                );

                CREATE INDEX IX_TUC_transformacion_activa
                ON dbo.TransformacionesUsuarioComponente (
                    id_transformacion_usuario,
                    activa,
                    orden
                );
            END
            """
        )

    def buscar_componentes_configuraciones_usuario(
        self,
        ids_configuraciones,
    ):
        if not self.tabla_componentes_configuracion_existe():
            return []

        ids_limpios = list(dict.fromkeys(
            int(configuracion_id)
            for configuracion_id in ids_configuraciones
            if configuracion_id
        ))

        if not ids_limpios:
            return []

        parametros = ", ".join("?" for _ in ids_limpios)

        return self.fetchall(
            f"""
            SELECT
                C.id_transformacion_usuario,
                C.id_componente_usuario,
                C.producto_componente,
                P.ProductID,
                C.cantidad,
                C.unidad,
                C.es_producto_base,
                C.tipo_componente,
                C.participa_balance,
                C.orden,
                C.activa,
                P.ProductKey,
                P.ProductName,
                P.Category1,
                P.Unit,
                P.CostPrice,
                ISNULL(I.QtyPresent, 0) AS QtyPresent
            FROM dbo.TransformacionesUsuarioComponente AS C
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = C.producto_componente
            OUTER APPLY (
                SELECT SUM(Q.QtyPresent) AS QtyPresent
                FROM dbo.vwLBSProductQuantityList AS Q
                WHERE Q.ProductID = P.ProductID
                  AND Q.DepotID = (
                      SELECT TOP 1 almacen_id
                      FROM dbo.ConfiguracionTransformaciones
                      WHERE activa = 1
                      ORDER BY id_configuracion
                  )
            ) AS I
            WHERE C.id_transformacion_usuario IN ({parametros})
              AND C.activa = 1
            ORDER BY C.id_transformacion_usuario DESC, C.orden
            """,
            tuple(ids_limpios),
        )

    def buscar_ingredientes_formula(self, producto_formula_id):
        return self.fetchall(
            """
            SELECT
                F.IDComp,
                F.ProductID,
                F.Producto,
                F.ComponenteID,
                F.Componente,
                F.CantidadComp,
                P.ProductKey,
                P.Category1,
                P.Unit
            FROM dbo.zvwFormulasListasPCocinar AS F
            INNER JOIN dbo.orgProduct AS P
                ON P.ProductID = F.ComponenteID
               AND P.DeletedOn IS NULL
            WHERE F.ProductID = ?
            ORDER BY F.IDComp
            """,
            (producto_formula_id,),
        )

    def registrar_configuracion_usuario(self, datos, usuario_id):
        self.asegurar_tabla_componentes_configuracion()
        detalles_json = json.dumps([
            {
                "producto_id": detalle.producto_id,
                "cantidad": float(detalle.cantidad),
                "unidad": detalle.unidad,
                "participa_balance": detalle.participa_balance,
                "orden": detalle.orden,
            }
            for detalle in datos.productos_resultantes
        ])
        componentes_json = json.dumps([
            {
                "producto_id": componente.producto_id,
                "cantidad": float(componente.cantidad),
                "unidad": componente.unidad,
                "es_producto_base": componente.es_producto_base,
                "tipo_componente": componente.tipo_componente,
                "participa_balance": componente.participa_balance,
                "orden": componente.orden,
            }
            for componente in datos.componentes
        ])

        fila = self.fetchone(
            """
            SET NOCOUNT ON;

            DECLARE @id INT;

            BEGIN TRY
                BEGIN TRANSACTION;

                INSERT INTO dbo.TransformacionesUsuario (
                    nombre_transformacion,
                    producto_origen,
                    producto_formula,
                    cantidad_base,
                    porcentaje_merma,
                    usuario_creacion,
                    observaciones
                )
                VALUES (?, ?, ?, ?, ?, ?, ?);

                SET @id = CONVERT(INT, SCOPE_IDENTITY());

                INSERT INTO dbo.TransformacionesUsuarioDetalle (
                    id_transformacion_usuario,
                    producto_resultante,
                    cantidad_resultante,
                    unidad,
                    participa_balance,
                    orden
                )
                SELECT
                    @id,
                    producto_id,
                    cantidad,
                    unidad,
                    participa_balance,
                    orden
                FROM OPENJSON(?)
                WITH (
                    producto_id INT '$.producto_id',
                    cantidad DECIMAL(18, 6) '$.cantidad',
                    unidad NVARCHAR(50) '$.unidad',
                    participa_balance BIT '$.participa_balance',
                    orden INT '$.orden'
                );

                INSERT INTO dbo.TransformacionesUsuarioComponente (
                    id_transformacion_usuario,
                    producto_componente,
                    cantidad,
                    unidad,
                    es_producto_base,
                    tipo_componente,
                    participa_balance,
                    orden
                )
                SELECT
                    @id,
                    producto_id,
                    cantidad,
                    unidad,
                    es_producto_base,
                    tipo_componente,
                    participa_balance,
                    orden
                FROM OPENJSON(?)
                WITH (
                    producto_id INT '$.producto_id',
                    cantidad DECIMAL(18, 6) '$.cantidad',
                    unidad NVARCHAR(50) '$.unidad',
                    es_producto_base BIT '$.es_producto_base',
                    tipo_componente NVARCHAR(30) '$.tipo_componente',
                    participa_balance BIT '$.participa_balance',
                    orden INT '$.orden'
                );

                COMMIT TRANSACTION;

                SELECT @id AS id_transformacion_usuario;
            END TRY
            BEGIN CATCH
                IF @@TRANCOUNT > 0
                    ROLLBACK TRANSACTION;

                THROW;
            END CATCH;
            """,
            (
                datos.nombre_transformacion.strip(),
                datos.producto_origen_id,
                datos.producto_formula_id,
                float(datos.cantidad_base),
                (
                    float(datos.porcentaje_merma)
                    if datos.porcentaje_merma is not None
                    else None
                ),
                usuario_id,
                datos.observaciones,
                detalles_json,
                componentes_json,
            ),
        )
        return int(self.valor_escalar(fila, "id_transformacion_usuario"))

    def actualizar_configuracion_usuario(
        self,
        configuracion_id,
        datos,
        usuario_id,
    ):
        self.asegurar_tabla_componentes_configuracion()
        detalles_json = json.dumps([
            {
                "producto_id": detalle.producto_id,
                "cantidad": float(detalle.cantidad),
                "unidad": detalle.unidad,
                "participa_balance": detalle.participa_balance,
                "orden": detalle.orden,
            }
            for detalle in datos.productos_resultantes
        ])
        componentes_json = json.dumps([
            {
                "producto_id": componente.producto_id,
                "cantidad": float(componente.cantidad),
                "unidad": componente.unidad,
                "es_producto_base": componente.es_producto_base,
                "tipo_componente": componente.tipo_componente,
                "participa_balance": componente.participa_balance,
                "orden": componente.orden,
            }
            for componente in datos.componentes
        ])

        fila = self.fetchone(
            """
            SET NOCOUNT ON;

            DECLARE @actualizados INT = 0;

            BEGIN TRY
                BEGIN TRANSACTION;

                UPDATE dbo.TransformacionesUsuario
                SET nombre_transformacion = ?,
                    producto_origen = ?,
                    producto_formula = ?,
                    cantidad_base = ?,
                    porcentaje_merma = ?,
                    usuario_actualizacion = ?,
                    fecha_actualizacion = GETDATE(),
                    observaciones = ?
                WHERE id_transformacion_usuario = ?
                  AND activa = 1;

                SET @actualizados = @@ROWCOUNT;

                IF @actualizados = 1
                BEGIN
                    UPDATE dbo.TransformacionesUsuarioDetalle
                    SET activa = 0
                    WHERE id_transformacion_usuario = ?;

                    INSERT INTO dbo.TransformacionesUsuarioDetalle (
                        id_transformacion_usuario,
                        producto_resultante,
                        cantidad_resultante,
                        unidad,
                        participa_balance,
                        orden
                    )
                    SELECT
                        ?,
                        producto_id,
                        cantidad,
                        unidad,
                        participa_balance,
                        orden
                    FROM OPENJSON(?)
                    WITH (
                        producto_id INT '$.producto_id',
                        cantidad DECIMAL(18, 6) '$.cantidad',
                        unidad NVARCHAR(50) '$.unidad',
                        participa_balance BIT '$.participa_balance',
                        orden INT '$.orden'
                    );

                    UPDATE dbo.TransformacionesUsuarioComponente
                    SET activa = 0
                    WHERE id_transformacion_usuario = ?;

                    INSERT INTO dbo.TransformacionesUsuarioComponente (
                        id_transformacion_usuario,
                        producto_componente,
                        cantidad,
                        unidad,
                        es_producto_base,
                        tipo_componente,
                        participa_balance,
                        orden
                    )
                    SELECT
                        ?,
                        producto_id,
                        cantidad,
                        unidad,
                        es_producto_base,
                        tipo_componente,
                        participa_balance,
                        orden
                    FROM OPENJSON(?)
                    WITH (
                        producto_id INT '$.producto_id',
                        cantidad DECIMAL(18, 6) '$.cantidad',
                        unidad NVARCHAR(50) '$.unidad',
                        es_producto_base BIT '$.es_producto_base',
                        tipo_componente NVARCHAR(30) '$.tipo_componente',
                        participa_balance BIT '$.participa_balance',
                        orden INT '$.orden'
                    );
                END

                COMMIT TRANSACTION;

                SELECT @actualizados AS actualizados;
            END TRY
            BEGIN CATCH
                IF @@TRANCOUNT > 0
                    ROLLBACK TRANSACTION;

                THROW;
            END CATCH;
            """,
            (
                datos.nombre_transformacion.strip(),
                datos.producto_origen_id,
                datos.producto_formula_id,
                float(datos.cantidad_base),
                (
                    float(datos.porcentaje_merma)
                    if datos.porcentaje_merma is not None
                    else None
                ),
                usuario_id,
                datos.observaciones,
                configuracion_id,
                configuracion_id,
                configuracion_id,
                detalles_json,
                configuracion_id,
                configuracion_id,
                componentes_json,
            ),
        )
        return bool(int(self.valor_escalar(fila, "actualizados") or 0))

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
        peso_merma,
        almacen_id,
        porcentaje_merma_esperado=None,
        observaciones_merma=None,
        id_operacion=None,
        componentes_formula=None,
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
                "tipo_componente": componente.tipo_componente,
                "participa_balance": componente.participa_balance,
            }
            for componente in (componentes_formula or [])
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
                componentes_json,
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
