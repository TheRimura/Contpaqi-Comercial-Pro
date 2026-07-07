import json
from functools import cache
from platform import node


from cayal.comandos_base_datos import ComandosBaseDatos



class BaseDatos(ComandosBaseDatos):
    MODULO_ENTRADA = 202
    MODULO_SALIDA = 203
    MOVIMIENTOS_ENTRADA_RELACIONABLES = (
        0, 3, 5, 7, 13, 14, 16, 17, 19, 24, 26, 31
    )
    MOVIMIENTOS_SALIDA_RELACIONABLES = (
        0, 2, 6, 8, 9, 10, 12, 13, 14, 21, 23, 28
    )

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

    def buscar_nombre_grupo_usuario(self, user_group_id):
        if not user_group_id:
            return None

        fila = self.fetchone(
            """
            SELECT TOP 1 GroupName
            FROM dbo.engUserGroup
            WHERE UserGroupID = ?
            """,
            (int(user_group_id),),
        )

        if not fila:
            return None

        return self.valor_escalar(fila, "GroupName")

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
        self.asegurar_metadatos_configuracion_usuario()
        configuracion = self.buscar_configuracion_transformaciones()
        filas = self.fetchall(
            """
            SELECT TOP 1
                TU.id_transformacion_usuario,
                TU.nombre_transformacion,
                TU.proveedor_id,
                TU.proveedor_nombre,
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
        self.asegurar_metadatos_configuracion_usuario()
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
        self.asegurar_metadatos_configuracion_usuario()
        inicio = (int(pagina) - 1) * int(limite)

        return self.fetchall(
            """
            SELECT
                TU.id_transformacion_usuario,
                TU.nombre_transformacion,
                TU.proveedor_id,
                TU.proveedor_nombre,
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

    def asegurar_metadatos_configuracion_usuario(self):
        self.asegurar_tabla_componentes_configuracion()
        self.command(
            """
            IF COL_LENGTH(
                'dbo.TransformacionesUsuario',
                'proveedor_id'
            ) IS NULL
            BEGIN
                ALTER TABLE dbo.TransformacionesUsuario
                ADD proveedor_id INT NULL;
            END;

            IF COL_LENGTH(
                'dbo.TransformacionesUsuario',
                'proveedor_nombre'
            ) IS NULL
            BEGIN
                ALTER TABLE dbo.TransformacionesUsuario
                ADD proveedor_nombre NVARCHAR(250) NULL;
            END;

            IF OBJECT_ID(
                N'dbo.TransformacionesUsuarioBitacora',
                N'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.TransformacionesUsuarioBitacora (
                    id_bitacora INT IDENTITY(1, 1) NOT NULL
                        CONSTRAINT PK_TransformacionesUsuarioBitacora
                        PRIMARY KEY,
                    id_transformacion_usuario INT NOT NULL,
                    accion NVARCHAR(50) NOT NULL,
                    usuario_id BIGINT NULL,
                    usuario_confirmacion_nombre NVARCHAR(150) NULL,
                    detalle NVARCHAR(500) NULL,
                    fecha DATETIME2 NOT NULL
                        CONSTRAINT DF_TUB_fecha DEFAULT GETDATE()
                );

                CREATE INDEX IX_TUB_configuracion_fecha
                ON dbo.TransformacionesUsuarioBitacora (
                    id_transformacion_usuario,
                    fecha DESC
                );
            END;
            """,
            (),
        )

    def registrar_bitacora_configuracion(
        self,
        configuracion_id,
        accion,
        usuario_id,
        usuario_confirmacion_nombre=None,
        detalle=None,
    ):
        self.asegurar_metadatos_configuracion_usuario()
        self.command(
            """
            INSERT INTO dbo.TransformacionesUsuarioBitacora (
                id_transformacion_usuario,
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(configuracion_id),
                accion,
                usuario_id,
                usuario_confirmacion_nombre,
                detalle,
            ),
        )

    def buscar_bitacora_configuraciones(self, limite=50):
        self.asegurar_metadatos_configuracion_usuario()
        return self.fetchall(
            """
            SELECT TOP (?)
                B.id_bitacora,
                B.id_transformacion_usuario,
                B.accion,
                B.usuario_id,
                B.usuario_confirmacion_nombre,
                B.detalle,
                B.fecha,
                U.nombre_transformacion
            FROM dbo.TransformacionesUsuarioBitacora AS B
            LEFT JOIN dbo.TransformacionesUsuario AS U
                ON U.id_transformacion_usuario =
                    B.id_transformacion_usuario
            ORDER BY B.fecha DESC, B.id_bitacora DESC
            """,
            (int(limite),),
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
        self.asegurar_metadatos_configuracion_usuario()
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
                    proveedor_id,
                    proveedor_nombre,
                    producto_origen,
                    producto_formula,
                    cantidad_base,
                    porcentaje_merma,
                    usuario_creacion,
                    observaciones
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);

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
                datos.proveedor_id,
                datos.proveedor_nombre.strip(),
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
        configuracion_id = int(
            self.valor_escalar(fila, "id_transformacion_usuario")
        )
        self.registrar_bitacora_configuracion(
            configuracion_id,
            "creacion",
            usuario_id,
            datos.usuario_confirmacion_nombre,
            "Configuracion creada",
        )
        return configuracion_id

    def actualizar_configuracion_usuario(
        self,
        configuracion_id,
        datos,
        usuario_id,
    ):
        self.asegurar_metadatos_configuracion_usuario()
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
                    proveedor_id = ?,
                    proveedor_nombre = ?,
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
                datos.proveedor_id,
                datos.proveedor_nombre.strip(),
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
        actualizada = bool(int(self.valor_escalar(fila, "actualizados") or 0))

        if actualizada:
            self.registrar_bitacora_configuracion(
                configuracion_id,
                "actualizacion",
                usuario_id,
                datos.usuario_confirmacion_nombre,
                "Configuracion actualizada",
            )

        return actualizada

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

    def asegurar_tabla_relacion_documentos_erp(self):
        self.command(
            """
            IF OBJECT_ID(
                N'dbo.docDocumentWarehouseRelation',
                N'U'
            ) IS NULL
            BEGIN
                CREATE TABLE dbo.docDocumentWarehouseRelation (
                    DocumentWarehouseRelationID INT IDENTITY(1, 1)
                        CONSTRAINT PK_docDocumentWarehouseRelation
                        PRIMARY KEY,
                    SourceDocumentID INT NOT NULL,
                    DestinationDocumentID INT NOT NULL,
                    SupplierID INT NULL,
                    PhysicalUserID INT NULL,
                    MovementDate DATE NULL,
                    ERPUserID INT NULL,
                    SourceBrandID INT NULL,
                    DestinationBrandID INT NULL,
                    CreatedOn DATETIME2 NOT NULL
                        CONSTRAINT DF_docDocumentWarehouseRelation_CreatedOn
                        DEFAULT SYSUTCDATETIME()
                );

                CREATE UNIQUE INDEX UX_docDocumentWarehouseRelation_pair
                    ON dbo.docDocumentWarehouseRelation (
                        SourceDocumentID,
                        DestinationDocumentID
                    );
            END
            """,
            (),
        )

    def buscar_movimientos_inventario_independientes(self, tipo="todos"):
        self.asegurar_tabla_relacion_documentos_erp()

        tipo_normalizado = str(tipo or "todos").strip().lower()
        condiciones_tipo = []

        if tipo_normalizado in {"todos", "salida"}:
            condiciones_tipo.append(
                "(D.ModuleID = 203 AND TRY_CONVERT(INT, D.CustomCbo) "
                f"IN ({', '.join(str(m) for m in self.MOVIMIENTOS_SALIDA_RELACIONABLES)}))"
            )

        if tipo_normalizado in {"todos", "entrada"}:
            condiciones_tipo.append(
                "(D.ModuleID = 202 AND TRY_CONVERT(INT, D.CustomCbo) "
                f"IN ({', '.join(str(m) for m in self.MOVIMIENTOS_ENTRADA_RELACIONABLES)}))"
            )

        if not condiciones_tipo:
            return []

        filtro_tipo = " OR ".join(condiciones_tipo)

        return self.fetchall(
            f"""
            SELECT TOP 500
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') + ISNULL(D.Folio, '') AS Folio,
                D.CreatedOn,
                D.DateDocument,
                D.CreatedBy,
                ISNULL(U.UserName, '') AS UserName,
                TRY_CONVERT(INT, D.CustomCbo) AS TipoMovimientoID,
                ISNULL(C.ItemValue, '') AS TipoMovimiento,
                D.DepotID,
                ISNULL(A.DepotName, '') AS DepotName,
                D.SourceDocumentID,
                D.DestinationDocumentID,
                ISNULL(D.Custom1, '') AS Custom1,
                I.DocumentItemID,
                I.ProductID,
                I.Quantity,
                P.ProductKey,
                P.ProductName,
                P.Category1,
                ISNULL(I.Unit, P.Unit) AS Unit,
                R.SupplierID,
                ISNULL(PROV.OfficialName, '') AS SupplierName,
                R.PhysicalUserID,
                ISNULL(EMP.OfficialName, '') AS PhysicalUserName,
                R.MovementDate
            FROM dbo.docDocument AS D
            LEFT JOIN dbo.docDocumentItem AS I
                ON I.DocumentID = D.DocumentID
               AND I.DeletedOn IS NULL
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = I.ProductID
            LEFT JOIN dbo.engUser AS U
                ON U.UserID = D.CreatedBy
            LEFT JOIN dbo.orgDepot AS A
                ON A.DepotID = D.DepotID
            LEFT JOIN dbo.engRefCombo AS C
                ON C.ItemData = TRY_CONVERT(INT, D.CustomCbo)
               AND C.CboGroupName = CASE
                    WHEN D.ModuleID = 202 THEN 'Tipo de entrada'
                    WHEN D.ModuleID = 203 THEN 'Tipo de salida'
                    ELSE ''
               END
            OUTER APPLY
            (
                SELECT TOP 1 Rel.*
                FROM dbo.docDocumentWarehouseRelation AS Rel
                WHERE Rel.SourceDocumentID = D.DocumentID
                   OR Rel.DestinationDocumentID = D.DocumentID
                ORDER BY Rel.DocumentWarehouseRelationID DESC
            ) AS R
            LEFT JOIN dbo.orgBusinessEntity AS PROV
                ON PROV.BusinessEntityID = R.SupplierID
            LEFT JOIN dbo.zvwEmpleadosCayalMenu AS EMP
                ON EMP.UserID = R.PhysicalUserID
            WHERE D.ModuleID IN (202, 203)
              AND D.DeletedOn IS NULL
              AND D.CancelledOn IS NULL
              AND ({filtro_tipo})
            ORDER BY D.CreatedOn DESC, D.DocumentID DESC, I.DocumentItemID
            """,
            (),
        )

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
        self.asegurar_tabla_relacion_documentos_erp()
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
                R.SupplierID,
                ISNULL(PROV.OfficialName, '') AS SupplierName,
                R.PhysicalUserID,
                ISNULL(EMP.OfficialName, '') AS PhysicalUserName,
                R.MovementDate,
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
            OUTER APPLY
            (
                SELECT TOP 1 Rel.*
                FROM dbo.docDocumentWarehouseRelation AS Rel
                WHERE (
                        T.documento_salida IS NOT NULL
                    AND Rel.SourceDocumentID = T.documento_salida
                )
                   OR (
                        T.documento_entrada IS NOT NULL
                    AND Rel.DestinationDocumentID = T.documento_entrada
                )
                ORDER BY Rel.DocumentWarehouseRelationID DESC
            ) AS R
            LEFT JOIN dbo.orgBusinessEntity AS PROV
                ON PROV.BusinessEntityID = R.SupplierID
            LEFT JOIN dbo.zvwEmpleadosCayalMenu AS EMP
                ON EMP.UserID = R.PhysicalUserID
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

    def documento_previamente_relacionado(self, document_id):
        relacionado = self.fetchone(
            """
            SELECT CASE
                WHEN ISNULL(SourceDocumentID, 0) <> 0
                  OR ISNULL(DestinationDocumentID, 0) <> 0
                  OR ISNULL(Custom1, '') <> ''
                THEN 1
                ELSE 0
            END AS Relacionado
            FROM dbo.docDocument
            WHERE DocumentID = ?
            """,
            (int(document_id),),
        )

        return int(self.valor_escalar(relacionado, "Relacionado") or 0) == 1

    def buscar_folio_documento(self, document_id):
        folio = self.fetchone(
            """
            SELECT ISNULL(FolioPrefix, '') + ISNULL(Folio, '') AS Folio
            FROM dbo.docDocument
            WHERE DocumentID = ?
            """,
            (int(document_id),),
        )

        return self.valor_escalar(folio, "Folio") or ""

    def buscar_tipo_movimiento_documento(self, document_id):
        movimiento_id = self.fetchone(
            """
            SELECT ISNULL(CustomCbo, 0) AS MovimientoID
            FROM dbo.docDocument
            WHERE DocumentID = ?
            """,
            (int(document_id),),
        )

        return int(self.valor_escalar(movimiento_id, "MovimientoID") or 0)

    def movimiento_es_relacionable(self, tipo_movimiento_id, module_id):
        module_id = int(module_id or 0)
        tipo_movimiento_id = int(tipo_movimiento_id or 0)

        if module_id == self.MODULO_ENTRADA:
            return tipo_movimiento_id in self.MOVIMIENTOS_ENTRADA_RELACIONABLES

        if module_id == self.MODULO_SALIDA:
            return tipo_movimiento_id in self.MOVIMIENTOS_SALIDA_RELACIONABLES

        return False

    def buscar_tipo_movimiento_modulo(self, module_id, incluir_todos=False):
        module_id = int(module_id or 0)

        if module_id == self.MODULO_ENTRADA:
            filtro = "" if incluir_todos else """
                AND ItemData IN (3, 5, 7, 13, 14, 16, 17, 19, 24, 26, 31)
            """
            grupo = "Tipo de entrada"
        elif module_id == self.MODULO_SALIDA:
            filtro = "" if incluir_todos else """
                AND ItemData IN (2, 6, 8, 9, 10, 12, 13, 14, 21, 23, 28)
            """
            grupo = "Tipo de salida"
        else:
            return []

        return self.fetchall(
            f"""
            SELECT ItemData, ItemValue
            FROM
            (
                SELECT ItemData, ItemValue
                FROM dbo.engRefCombo
                WHERE CboGroupName = ?
                  {filtro}

                UNION ALL

                SELECT 0 AS ItemData, 'NO CLASIFICADO' AS ItemValue
            ) AS Tabla
            ORDER BY ItemValue
            """,
            (grupo,),
        )

    def buscar_documentos_relacionables(self, module_id):
        module_id = int(module_id or 0)

        if module_id == self.MODULO_ENTRADA:
            target_module = self.MODULO_SALIDA
            movimientos = self.MOVIMIENTOS_SALIDA_RELACIONABLES
        elif module_id == self.MODULO_SALIDA:
            target_module = self.MODULO_ENTRADA
            movimientos = self.MOVIMIENTOS_ENTRADA_RELACIONABLES
        else:
            return []

        movimientos_sql = ", ".join(str(movimiento) for movimiento in movimientos)

        return self.fetchall(
            f"""
            SELECT
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.FolioPrefix, '') + ISNULL(D.Folio, '') AS DocFolio,
                ISNULL(U.UserName, '') AS UserName,
                CAST(D.CreatedOn AS DATE) AS CreatedOn,
                CASE WHEN D.CancelledOn IS NULL THEN 0 ELSE 1 END AS Cancelled,
                ISNULL(D.SourceDocumentID, 0) AS SourceDocumentID,
                ISNULL(D.DestinationDocumentID, 0) AS DestinationDocumentID,
                ISNULL(D.CustomCbo, 0) AS CustomCbo,
                ISNULL(D.Custom1, '') AS Custom1
            FROM dbo.docDocument D
            LEFT JOIN dbo.engUser U
                ON U.UserID = D.CreatedBy
            WHERE D.ModuleID = ?
              AND D.DeletedOn IS NULL
              AND D.CancelledOn IS NULL
              AND ISNULL(D.SourceDocumentID, 0) = 0
              AND ISNULL(D.DestinationDocumentID, 0) = 0
              AND ISNULL(D.Custom1, '') = ''
              AND ISNULL(D.CustomCbo, 0) IN ({movimientos_sql})
              AND CAST(D.CreatedOn AS DATE) = CAST(GETDATE() AS DATE)
            ORDER BY D.CreatedOn DESC
            """,
            (target_module,),
        )

    def obtener_proveedores_documentos(self):
        return self.fetchall(
            """
            SELECT DISTINCT
                S.BusinessEntityID,
                E.OfficialName
            FROM dbo.docDocument D
            INNER JOIN dbo.orgBusinessEntity E
                ON D.BusinessEntityID = E.BusinessEntityID
            INNER JOIN dbo.orgSupplier S
                ON E.BusinessEntityID = S.BusinessEntityID
            WHERE S.DeletedOn IS NULL
              AND D.ModuleID = 152
              AND D.CancelledOn IS NULL
              AND D.DeletedOn IS NULL
              AND S.SupplierID IS NOT NULL
            ORDER BY E.OfficialName
            """,
            (),
        )

    def obtener_usuarios_fisicos(self):
        return self.fetchall(
            """
            SELECT
                UserID,
                OfficialName
            FROM dbo.zvwEmpleadosCayalMenu
            ORDER BY OfficialName
            """,
            (),
        )

    def obtener_relacion_documento(self, document_id):
        filas = self.fetchall(
            """
            SELECT TOP 1
                D.DocumentID,
                D.ModuleID,
                ISNULL(D.Custom1, '') AS FolioRelacionadoCustom1,
                S.DocumentID AS SourceDocumentID,
                E.DocumentID AS DestinationDocumentID,
                ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, '') AS SourceFolio,
                ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, '') AS DestinationFolio,
                ISNULL(S.CustomCbo, 0) AS TipoMovimientoOrigenID,
                ISNULL(E.CustomCbo, 0) AS TipoMovimientoDestinoID,
                ISNULL(US.UserName, '') AS SourceUserName,
                ISNULL(UE.UserName, '') AS DestinationUserName,
                R.DocumentWarehouseRelationID,
                R.SupplierID,
                R.PhysicalUserID,
                R.MovementDate,
                R.ERPUserID,
                R.SourceBrandID,
                R.DestinationBrandID,
                ISNULL(BS.BrandName, '') AS SourceBrandName,
                ISNULL(BD.BrandName, '') AS DestinationBrandName,
                ISNULL(PROV.OfficialName, '') AS SupplierName,
                ISNULL(EMP.OfficialName, '') AS PhysicalUserName
            FROM dbo.docDocument D
            OUTER APPLY
            (
                SELECT TOP 1 R.*
                FROM dbo.docDocumentWarehouseRelation R
                WHERE R.SourceDocumentID = D.DocumentID
                   OR R.DestinationDocumentID = D.DocumentID
                ORDER BY R.DocumentWarehouseRelationID DESC
            ) R
            LEFT JOIN dbo.docDocument S
                ON S.DocumentID = CASE
                    WHEN R.SourceDocumentID IS NOT NULL THEN R.SourceDocumentID
                    WHEN D.ModuleID = 203 THEN D.DocumentID
                    WHEN D.ModuleID = 202 THEN D.SourceDocumentID
                    ELSE D.SourceDocumentID
                END
               AND S.ModuleID = 203
            LEFT JOIN dbo.docDocument E
                ON E.DocumentID = CASE
                    WHEN R.DestinationDocumentID IS NOT NULL THEN R.DestinationDocumentID
                    WHEN D.ModuleID = 202 THEN D.DocumentID
                    WHEN D.ModuleID = 203 THEN D.DestinationDocumentID
                    ELSE D.DestinationDocumentID
                END
               AND E.ModuleID = 202
            LEFT JOIN dbo.orgBusinessEntity PROV
                ON PROV.BusinessEntityID = R.SupplierID
            LEFT JOIN dbo.zvwEmpleadosCayalMenu EMP
                ON EMP.UserID = R.PhysicalUserID
            LEFT JOIN dbo.catBrand BS
                ON BS.BrandID = R.SourceBrandID
            LEFT JOIN dbo.catBrand BD
                ON BD.BrandID = R.DestinationBrandID
            LEFT JOIN dbo.engUser US
                ON US.UserID = S.CreatedBy
            LEFT JOIN dbo.engUser UE
                ON UE.UserID = E.CreatedBy
            WHERE D.DocumentID = ?
            """,
            (int(document_id),),
        )

        return filas[0] if filas else None

    def relacionar_documentos_erp(
        self,
        source_document_id,
        destination_document_id,
        folio_source_document_id,
        folio_destination_document_id,
        tipo_movimiento_origen_id,
        tipo_movimiento_destino_id,
        proveedor_id,
        usuario_fisico_id,
        fecha_movimiento,
        user_id_erp,
        source_brand_id=None,
        destination_brand_id=None,
    ):
        self.asegurar_tabla_relacion_documentos_erp()
        self.command(
            """
            DECLARE @Origen INT = ?;
            DECLARE @FolioOrigen NVARCHAR(125) = ?;
            DECLARE @Destino INT = ?;
            DECLARE @FolioDestino NVARCHAR(125) = ?;
            DECLARE @TipoMovimientoIDOrigen INT = ?;
            DECLARE @TipoMovimientoIDDestino INT = ?;
            DECLARE @ProveedorID INT = ?;
            DECLARE @UsuarioFisicoID INT = ?;
            DECLARE @FechaMovimiento DATE = ?;
            DECLARE @UserIDERP INT = ?;
            DECLARE @SourceBrandID INT = ?;
            DECLARE @DestinationBrandID INT = ?;

            UPDATE dbo.docDocument
            SET
                DestinationDocumentID = @Destino,
                CustomCbo = @TipoMovimientoIDOrigen,
                Custom1 = @FolioDestino
            WHERE DocumentID = @Origen
              AND ModuleID = 203;

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = @Origen,
                CustomCbo = @TipoMovimientoIDDestino,
                Custom1 = @FolioOrigen
            WHERE DocumentID = @Destino
              AND ModuleID = 202;

            INSERT INTO dbo.docDocumentWarehouseRelation
            (
                SourceDocumentID,
                DestinationDocumentID,
                SupplierID,
                PhysicalUserID,
                MovementDate,
                ERPUserID,
                SourceBrandID,
                DestinationBrandID,
                CreatedOn
            )
            SELECT
                @Origen,
                @Destino,
                @ProveedorID,
                @UsuarioFisicoID,
                @FechaMovimiento,
                @UserIDERP,
                @SourceBrandID,
                @DestinationBrandID,
                GETDATE()
            WHERE NOT EXISTS
            (
                SELECT 1
                FROM dbo.docDocumentWarehouseRelation
                WHERE SourceDocumentID = @Origen
                  AND DestinationDocumentID = @Destino
            );
            """,
            (
                int(source_document_id),
                folio_source_document_id,
                int(destination_document_id),
                folio_destination_document_id,
                int(tipo_movimiento_origen_id),
                int(tipo_movimiento_destino_id),
                int(proveedor_id),
                int(usuario_fisico_id),
                fecha_movimiento,
                int(user_id_erp),
                source_brand_id,
                destination_brand_id,
            ),
        )

    def buscar_document_id_por_folio(self, folio, module_id=None):
        if not folio:
            return 0

        folio = str(folio).strip().upper()
        consulta = self.fetchone(
            """
            SELECT TOP 1
                DocumentID
            FROM dbo.docDocument
            WHERE DeletedOn IS NULL
              AND CancelledOn IS NULL
              AND ISNULL(FolioPrefix, '') + ISNULL(Folio, '') = ?
              AND (? IS NULL OR ModuleID = ?)
            ORDER BY DocumentID DESC
            """,
            (folio, module_id, module_id),
        )

        return int(self.valor_escalar(consulta, "DocumentID") or 0)

    def homologar_tipo_movimiento_documento(self, document_id):
        self.command(
            """
            DECLARE @DocumentID INT = ?;
            DECLARE @ModuleID INT;
            DECLARE @Custom1 NVARCHAR(125);
            DECLARE @Custom1Normalizado NVARCHAR(125);

            SELECT
                @ModuleID = ModuleID,
                @Custom1 = LTRIM(RTRIM(ISNULL(Custom1, '')))
            FROM dbo.docDocument
            WHERE DocumentID = @DocumentID;

            SET @Custom1Normalizado = UPPER(@Custom1);
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, ' ', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, '-', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, '_', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, '.', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, '/', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, '\\', '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, CHAR(9), '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, CHAR(10), '');
            SET @Custom1Normalizado = REPLACE(@Custom1Normalizado, CHAR(13), '');

            IF ISNULL(@Custom1Normalizado, '') = ''
                RETURN;

            DECLARE @EntradaDocumentID INT = 0;
            DECLARE @SalidaDocumentID INT = 0;

            IF @ModuleID = 202
            BEGIN
                SET @EntradaDocumentID = @DocumentID;

                SELECT TOP 1
                    @SalidaDocumentID = S.DocumentID
                FROM dbo.docDocument S
                WHERE S.ModuleID = 203
                  AND S.DeletedOn IS NULL
                  AND S.CancelledOn IS NULL
                  AND UPPER(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            ISNULL(S.FolioPrefix, '') + ISNULL(S.Folio, ''),
                            ' ', ''), '-', ''), '_', ''), '.', ''), '/', ''), '\\', ''),
                            CHAR(9), ''), CHAR(10), ''), CHAR(13), '')
                      ) = @Custom1Normalizado
                ORDER BY S.DocumentID DESC;
            END
            ELSE IF @ModuleID = 203
            BEGIN
                SET @SalidaDocumentID = @DocumentID;

                SELECT TOP 1
                    @EntradaDocumentID = E.DocumentID
                FROM dbo.docDocument E
                WHERE E.ModuleID = 202
                  AND E.DeletedOn IS NULL
                  AND E.CancelledOn IS NULL
                  AND UPPER(
                        REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(REPLACE(
                            ISNULL(E.FolioPrefix, '') + ISNULL(E.Folio, ''),
                            ' ', ''), '-', ''), '_', ''), '.', ''), '/', ''), '\\', ''),
                            CHAR(9), ''), CHAR(10), ''), CHAR(13), '')
                      ) = @Custom1Normalizado
                ORDER BY E.DocumentID DESC;
            END
            ELSE
            BEGIN
                RETURN;
            END;

            IF ISNULL(@EntradaDocumentID, 0) = 0
               OR ISNULL(@SalidaDocumentID, 0) = 0
                RETURN;

            DECLARE @EntradaFolio NVARCHAR(125);
            DECLARE @SalidaFolio NVARCHAR(125);

            SELECT
                @EntradaFolio = ISNULL(FolioPrefix, '') + ISNULL(Folio, '')
            FROM dbo.docDocument
            WHERE DocumentID = @EntradaDocumentID
              AND ModuleID = 202;

            SELECT
                @SalidaFolio = ISNULL(FolioPrefix, '') + ISNULL(Folio, '')
            FROM dbo.docDocument
            WHERE DocumentID = @SalidaDocumentID
              AND ModuleID = 203;

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = @SalidaDocumentID,
                DestinationDocumentID = 0,
                Custom1 = @SalidaFolio
            WHERE DocumentID = @EntradaDocumentID
              AND ModuleID = 202
              AND (
                    ISNULL(SourceDocumentID, 0) = 0
                 OR ISNULL(Custom1, '') <> ISNULL(@SalidaFolio, '')
              );

            UPDATE dbo.docDocument
            SET
                SourceDocumentID = 0,
                DestinationDocumentID = @EntradaDocumentID,
                Custom1 = @EntradaFolio
            WHERE DocumentID = @SalidaDocumentID
              AND ModuleID = 203
              AND (
                    ISNULL(DestinationDocumentID, 0) = 0
                 OR ISNULL(Custom1, '') <> ISNULL(@EntradaFolio, '')
              );
            """,
            (int(document_id),),
        )

    def obtener_marcas_por_categoria(self, categoria):
        return self.fetchall(
            """
            SELECT
                B.BrandID,
                B.BrandName
            FROM catProductBrandCategory C
            INNER JOIN catProductBrandCategoryRelation R
                ON R.ProductBrandCategoryID = C.ProductBrandCategoryID
            INNER JOIN catBrand B
                ON B.BrandID = R.BrandID
            WHERE C.ProductBrandCategoryName = ?
              AND C.DeletedOn IS NULL
              AND R.DeletedOn IS NULL
              AND B.DeletedOn IS NULL
            ORDER BY B.BrandName
            """,
            (categoria,),
        )

    def obtener_partidas_documento_erp(self, document_id):
        partidas = self.buscar_partidas_documento(int(document_id))
        nuevas_partidas = []

        for partida in partidas:
            cantidad = float(partida.get("Quantity") or 0)
            costo = float(partida.get("CostPrice") or 0)
            total = float(partida.get("total") or cantidad * costo)
            nuevas_partidas.append({
                "ProductID": partida.get("ProductID"),
                "Category": partida.get("Category1"),
                "ProductKey": partida.get("ProductKey"),
                "ProductName": partida.get("ProductName"),
                "Quantity": cantidad,
                "CostPrice": costo,
                "total": total,
            })

        return nuevas_partidas

@cache
def obtener_base_datos():
    return BaseDatos()
