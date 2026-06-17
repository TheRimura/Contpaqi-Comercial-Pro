from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from threading import Lock


def numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def separar_detalle_formula(datos, productos_resultantes):
    if not datos.producto_base_formula_id:
        return None, [], productos_resultantes

    producto_base = None
    ingredientes = []

    for producto in productos_resultantes:
        producto_id = producto.get("producto", {}).get("id")

        if producto_id == datos.producto_base_formula_id:
            producto_base = producto
        else:
            ingredientes.append(producto)

    visibles = [producto_base] if producto_base else []

    return producto_base, ingredientes, visibles


class HistorialTransformaciones:
    def __init__(self):
        self._registros = []
        self._siguiente_folio = 1
        self._bloqueo = Lock()

    def agregar(
        self,
        datos,
        rendimiento,
        producto_origen,
        productos_resultantes,
    ):
        (
            producto_base_formula,
            ingredientes_formula,
            productos_visibles,
        ) = separar_detalle_formula(datos, productos_resultantes)
        total_salida = sum(
            numero(producto["cantidad"])
            for producto in productos_resultantes
        )

        with self._bloqueo:
            registro = {
                "folio": self._siguiente_folio,
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "usuario_id": datos.usuario_id,
                "usuario": datos.usuario_nombre,
                "tipo_transformacion": datos.tipo_transformacion,
                "producto_ya_transformado": datos.producto_ya_transformado,
                "producto_origen": producto_origen,
                "cantidad_origen": numero(datos.cantidad_origen),
                "producto_base_formula": producto_base_formula,
                "ingredientes_formula": ingredientes_formula,
                "productos_resultantes": productos_visibles,
                "total_salida": total_salida,
                "peso_merma": numero(rendimiento["peso_merma"]),
                "porcentaje_merma_real": numero(
                    rendimiento["porcentaje_merma_real"]
                ),
                "porcentaje_merma_esperado": numero(
                    rendimiento["porcentaje_merma_esperado"]
                ),
                "diferencia_merma": numero(
                    rendimiento["diferencia_merma"]
                ),
                "observaciones_merma": datos.observaciones_merma,
            }

            self._registros.append(registro)
            self._siguiente_folio += 1

        return deepcopy(registro)

    def listar(self):
        return [
            deepcopy(registro)
            for registro in reversed(self._registros)
        ]


@lru_cache(maxsize=1)
def obtener_historial_transformaciones():
    return HistorialTransformaciones()
