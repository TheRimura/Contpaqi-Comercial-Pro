from functools import lru_cache
from platform import node

from cayal.comandos_base_datos import ComandosBaseDatos


ESTATUS_EQUIVALENCIA_ACTIVA = 1


class BaseDatos(ComandosBaseDatos):
    def __init__(self):
        super().__init__(
            servidor=node(),
            base_de_datos="ComercialSP"
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


@lru_cache(maxsize=1)
def obtener_base_datos():
    return BaseDatos()
