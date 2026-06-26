from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.configuraciones_transformacion import (
    CrearConfiguracionTransformacion,
)
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/configuraciones-transformacion",
    tags=["Configuraciones de transformacion"],
)


def numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def producto(id_producto, clave, nombre, categoria, unidad):
    if not id_producto:
        return None

    return {
        "id": id_producto,
        "clave": clave,
        "nombre": nombre,
        "categoria": categoria,
        "unidad": unidad,
    }


def formatear_fecha(fecha):
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%Y-%m-%d %H:%M:%S")

    return str(fecha or "")


def agrupar_detalles(filas):
    detalles = {}

    for fila in filas:
        detalles.setdefault(
            fila["id_transformacion_usuario"],
            [],
        ).append({
            "id": fila["id_detalle_usuario"],
            "producto": producto(
                fila["producto_resultante"],
                fila["ProductKey"],
                fila["ProductName"],
                fila["Category1"],
                fila["Unit"],
            ),
            "cantidad": numero(fila["cantidad_resultante"]),
            "unidad": fila["unidad"],
            "participa_balance": bool(fila["participa_balance"]),
            "orden": fila["orden"],
            "activa": bool(fila["activa"]),
        })

    return detalles


def formatear_configuracion(fila, detalles):
    return {
        "id": fila["id_transformacion_usuario"],
        "nombre": fila["nombre_transformacion"],
        "producto_origen": producto(
            fila["producto_origen"],
            fila["origen_clave"],
            fila["origen_nombre"],
            fila["origen_categoria"],
            fila["origen_unidad"],
        ),
        "producto_formula": producto(
            fila["producto_formula"],
            fila["formula_clave"],
            fila["formula_nombre"],
            fila["formula_categoria"],
            fila["formula_unidad"],
        ),
        "cantidad_base": numero(fila["cantidad_base"]),
        "porcentaje_merma": numero(fila["porcentaje_merma"]),
        "usuario_creacion": {
            "id": fila["usuario_creacion"],
            "nombre": fila["usuario_creacion_nombre"],
        },
        "fecha_creacion": formatear_fecha(fila["fecha_creacion"]),
        "usuario_actualizacion": {
            "id": fila["usuario_actualizacion"],
            "nombre": fila["usuario_actualizacion_nombre"],
        } if fila["usuario_actualizacion"] else None,
        "fecha_actualizacion": formatear_fecha(
            fila["fecha_actualizacion"]
        ),
        "activa": bool(fila["activa"]),
        "observaciones": fila["observaciones"],
        "productos_resultantes": detalles.get(
            fila["id_transformacion_usuario"],
            [],
        ),
    }


def validar_productos(base_datos, datos):
    ids = {
        datos.producto_origen_id,
        *[
            detalle.producto_id
            for detalle in datos.productos_resultantes
        ],
    }

    if datos.producto_formula_id:
        ids.add(datos.producto_formula_id)

    existentes = base_datos.buscar_ids_productos_existentes(ids)
    faltantes = ids - existentes

    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Hay productos inexistentes o eliminados: "
                + ", ".join(str(id_producto) for id_producto in faltantes)
            ),
        )


@router.get("/")
def listar_configuraciones(
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=50),
):
    base_datos = obtener_base_datos()
    encabezados = base_datos.buscar_configuraciones_usuario(
        pagina,
        limite,
    )
    detalles = agrupar_detalles(
        base_datos.buscar_detalles_configuraciones_usuario([
            fila["id_transformacion_usuario"]
            for fila in encabezados
        ])
    )
    total = base_datos.contar_configuraciones_usuario()
    total_paginas = (total + limite - 1) // limite

    return {
        "configuraciones": [
            formatear_configuracion(fila, detalles)
            for fila in encabezados
        ],
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
    }


@router.post("/")
def crear_configuracion(
    datos: CrearConfiguracionTransformacion,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    validar_productos(base_datos, datos)
    configuracion_id = base_datos.registrar_configuracion_usuario(
        datos,
        sesion["user_id"],
    )

    return {
        "mensaje": "Configuracion guardada",
        "id": configuracion_id,
    }


@router.get("/formula/{producto_id}/ingredientes")
def consultar_ingredientes_formula(
    producto_id: int,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    filas = obtener_base_datos().buscar_ingredientes_formula(producto_id)

    return {
        "producto_formula_id": producto_id,
        "ingredientes": [
            {
                "id": fila["ComponenteID"],
                "clave": fila["ProductKey"],
                "nombre": fila["Componente"],
                "categoria": fila["Category1"],
                "unidad": fila["Unit"],
                "cantidad": numero(fila["CantidadComp"]),
            }
            for fila in filas
        ],
    }
