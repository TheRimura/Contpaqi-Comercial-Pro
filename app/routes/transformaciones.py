from fastapi import APIRouter

from app.schemas.transformaciones import CrearTransformacion
from app.services.historial_transformaciones import (
    obtener_historial_transformaciones,
)
from app.utils.base_de_datos import obtener_base_datos


router = APIRouter(
    prefix="/transformaciones",
    tags=["Transformaciones"],
)


def calcular_rendimiento(datos: CrearTransformacion):
    porcentaje_merma_real = datos.peso_merma / datos.cantidad_origen * 100
    diferencia_merma = None

    if datos.porcentaje_merma_esperado is not None:
        diferencia_merma = (
            porcentaje_merma_real - datos.porcentaje_merma_esperado
        )

    return {
        "peso_merma": datos.peso_merma,
        "porcentaje_merma_real": porcentaje_merma_real,
        "porcentaje_merma_esperado": datos.porcentaje_merma_esperado,
        "diferencia_merma": diferencia_merma,
    }


def formatear_producto(producto):
    if not producto:
        return None

    return {
        "id": producto["ProductID"],
        "clave": producto["ProductKey"],
        "nombre": producto["ProductName"],
        "categoria": producto["Category1"],
        "unidad": producto["Unit"],
    }


def consultar_productos_registro(datos: CrearTransformacion):
    base_datos = obtener_base_datos()
    ids_productos = list(dict.fromkeys([
        datos.producto_origen_id,
        *[
            producto.producto_id
            for producto in datos.productos_resultantes
        ],
    ]))
    productos = base_datos.buscar_info_productos(ids_productos)
    productos_por_id = {
        producto["ProductID"]: producto
        for producto in productos
    }

    producto_origen = formatear_producto(
        productos_por_id.get(datos.producto_origen_id)
    )
    productos_resultantes = []

    for producto in datos.productos_resultantes:
        producto_bd = formatear_producto(
            productos_por_id.get(producto.producto_id)
        )

        productos_resultantes.append({
            "producto": producto_bd,
            "cantidad": float(producto.cantidad),
        })

    return producto_origen, productos_resultantes


@router.get("/")
def listar_transformaciones():
    historial = obtener_historial_transformaciones()
    return {
        "registros": historial.listar(),
    }


@router.post("/")
def crear_transformacion(datos: CrearTransformacion):
    historial = obtener_historial_transformaciones()
    rendimiento = calcular_rendimiento(datos)
    producto_origen, productos_resultantes = consultar_productos_registro(
        datos
    )
    registro = historial.agregar(
        datos,
        rendimiento,
        producto_origen,
        productos_resultantes,
    )

    return {
        "mensaje": "Transformacion registrada",
        "folio": registro["folio"],
        "rendimiento": rendimiento,
        "registro": registro,
        "transformacion": datos,
    }
