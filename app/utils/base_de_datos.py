from functools import lru_cache
from platform import node

import pyodbc

from cayal.comandos_base_datos import ComandosBaseDatos


ESTATUS_EQUIVALENCIA_ACTIVA = 1


class BaseDatos(ComandosBaseDatos):
    def __init__(self):
        super().__init__(

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
                ProductID,
                ProductKey,
                ProductName,
                Category1,
                Unit,
                CostPrice,
                CAST(0 AS float) AS QtyPresent,
                ProductTypeIDCayal
            FROM dbo.orgProduct
            WHERE ProductID IN ({parametros})
              AND DeletedOn IS NULL
            ORDER BY ProductName
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
        cadena_conexion = getattr(
            self,
            "_BaseDatos__conexion_base_de_datos",
            None,
        )

        if not cadena_conexion:
            raise RuntimeError(
                "No fue posible obtener la conexion de base de datos"
            )

        return pyodbc.connect(cadena_conexion)

    def registrar_transformacion(
        self,
        producto_origen_id,
        cantidad_origen,
        usuario,
        productos_resultantes,
        peso_merma,
        observaciones_merma=None,
    ):
        with self._abrir_conexion() as conexion:
            cursor = conexion.cursor()

            try:
                cursor.execute("SET XACT_ABORT ON")
                cursor.execute(
                    """
                    INSERT INTO dbo.Transformaciones (
                        producto_origen,
                        cantidad_origen,
                        usuario_responsable
                    )
                    OUTPUT INSERTED.id_transformacion
                    VALUES (?, ?, ?)
                    """,
                    (
                        producto_origen_id,
                        float(cantidad_origen),
                        usuario,
                    ),
                )
                transformacion_id = int(cursor.fetchone()[0])

                cursor.executemany(
                    """
                    INSERT INTO dbo.DetalleTransformaciones (
                        id_transformacion,
                        producto_resultado,
                        cantidad_resultado
                    )
                    VALUES (?, ?, ?)
                    """,
                    [
                        (
                            transformacion_id,
                            producto.producto_id,
                            float(producto.cantidad),
                        )
                        for producto in productos_resultantes
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
                T.cantidad_origen,
                T.usuario_responsable,
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
