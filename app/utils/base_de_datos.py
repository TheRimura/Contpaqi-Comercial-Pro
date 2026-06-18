from functools import lru_cache
from platform import node

import pyodbc

from cayal.comandos_base_datos import ComandosBaseDatos


ESTATUS_EQUIVALENCIA_ACTIVA = 1


class BaseDatos(ComandosBaseDatos):
    def __init__(self):
        self._servidor = node()
        self._base_de_datos = "ComercialSP"
        super().__init__(
            servidor=self._servidor,
            base_de_datos=self._base_de_datos,
        )

    def buscar_productos_por_nombre(self, termino):
        return self.fetchall(
            """
            SELECT ProductID
            FROM dbo.orgProduct
            WHERE DeletedOn IS NULL
              AND AvailableForSale = 1
              AND ProductName LIKE ?
            ORDER BY ProductName
            """,
            (f"%{termino}%",),
        )

    def buscar_info_productos(self, ids_productos, **kwargs):
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
            LEFT JOIN dbo.vwLBSProductQuantityList AS I
                ON I.ProductID = P.ProductID
               AND I.DepotID = 2
            WHERE P.ProductID IN ({parametros})
              AND P.DeletedOn IS NULL
            ORDER BY P.ProductName
            """,
            tuple(ids_limpios),
        )

    def buscar_resultantes_transformacion(self, producto_origen_id):
        return self.fetchall(
            """
            SELECT ProductID2, Cant1, Cant2
            FROM dbo.zvwEquivalenciasTransKoben
            WHERE ProductID1 = ?
              AND Status = ?
            ORDER BY ID
            """,
            (producto_origen_id, ESTATUS_EQUIVALENCIA_ACTIVA),
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

    def _abrir_conexion(self):
        drivers = [
            driver
            for driver in pyodbc.drivers()
            if "SQL Server" in driver
        ]
        preferidos = [
            driver
            for driver in drivers
            if "ODBC Driver 18" in driver
        ] or [
            driver
            for driver in drivers
            if "ODBC Driver 17" in driver
        ]

        if not drivers:
            raise RuntimeError(
                "No se encontro un controlador ODBC para SQL Server"
            )

        driver = preferidos[-1] if preferidos else drivers[-1]
        cadena_conexion = (
            f"DRIVER={{{driver}}};"
            f"SERVER={self._servidor};"
            f"DATABASE={self._base_de_datos};"
            "Trusted_Connection=Yes;"
            "TrustServerCertificate=Yes;"
        )
        return pyodbc.connect(cadena_conexion)

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
        porcentaje_merma_esperado=None,
        observaciones_merma=None,
        id_operacion=None,
    ):
        with self._abrir_conexion() as conexion:
            cursor = conexion.cursor()

            try:
                cursor.execute("SET XACT_ABORT ON")
                cursor.execute(
                    """
                    SELECT id_transformacion
                    FROM dbo.Transformaciones
                    WHERE id_operacion = ?
                    """,
                    (str(id_operacion),),
                )
                existente = cursor.fetchone()

                if existente:
                    conexion.rollback()
                    return int(existente[0])

                cursor.execute(
                    """
                    INSERT INTO dbo.Transformaciones (
                        producto_origen,
                        producto_seleccionado,
                        cantidad_origen,
                        usuario_responsable,
                        usuario_id,
                        tipo_transformacion,
                        porcentaje_merma_esperado,
                        id_operacion
                    )
                    OUTPUT INSERTED.id_transformacion
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
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
                        str(id_operacion),
                    ),
                )
                transformacion_id = int(cursor.fetchone()[0])

                cursor.executemany(
                    """
                    INSERT INTO dbo.DetalleTransformaciones (
                        id_transformacion,
                        producto_resultado,
                        cantidad_resultado,
                        unidad_resultado
                    )
                    VALUES (?, ?, ?, ?)
                    """,
                    [
                        (
                            transformacion_id,
                            producto.producto_id,
                            float(producto.cantidad),
                            producto.unidad,
                        )
                        for producto in productos_resultantes
                    ],
                )

                if componentes_formula:
                    cursor.executemany(
                        """
                        INSERT INTO dbo.ComponentesTransformacion (
                            id_transformacion,
                            producto_componente,
                            cantidad,
                            unidad,
                            es_producto_base
                        )
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        [
                            (
                                transformacion_id,
                                componente.producto_id,
                                float(componente.cantidad),
                                componente.unidad,
                                int(componente.es_producto_base),
                            )
                            for componente in componentes_formula
                        ],
                    )

                cursor.execute(
                    """
                    INSERT INTO dbo.Mermas (
                        id_transformacion,
                        peso_merma,
                        motivo
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        transformacion_id,
                        float(peso_merma),
                        observaciones_merma,
                    ),
                )
                conexion.commit()
                return transformacion_id
            except pyodbc.IntegrityError:
                conexion.rollback()
                cursor.execute(
                    """
                    SELECT id_transformacion
                    FROM dbo.Transformaciones
                    WHERE id_operacion = ?
                    """,
                    (str(id_operacion),),
                )
                existente = cursor.fetchone()

                if existente:
                    return int(existente[0])

                raise
            except Exception:
                conexion.rollback()
                raise

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
                P.ProductKey AS origen_clave,
                P.ProductName AS origen_nombre,
                P.Category1 AS origen_categoria,
                P.Unit AS origen_unidad,
                M.peso_merma,
                M.motivo
            FROM dbo.Transformaciones AS T
            LEFT JOIN dbo.orgProduct AS P
                ON P.ProductID = T.producto_origen
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


@lru_cache(maxsize=1)
def obtener_base_datos():
    return BaseDatos()
