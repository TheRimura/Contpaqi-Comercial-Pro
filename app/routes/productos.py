import re

from fastapi import APIRouter, Query

from app.utils.base_de_datos import obtener_base_datos


router = APIRouter(
    prefix="/productos",
    tags=["Productos"],
)


def coincide_con_busqueda(producto, termino):
    texto_producto = str(producto.get("ProductName") or "").upper()
    texto_busqueda = termino.strip().upper()

    if texto_busqueda.isalpha():
        patron = rf"(^|[^A-Z0-9]){re.escape(texto_busqueda)}([^A-Z0-9]|$)"
        return re.search(patron, texto_producto) is not None

    return texto_busqueda in texto_producto


def tiene_clave_interna(producto):
    clave = str(producto.get("ProductKey") or "").strip()
    return len(clave) == 6 and clave.isdigit()


def pertenece_al_modulo(producto):
    tipo_cayal = int(producto.get("ProductTypeIDCayal") or 0)
    return tipo_cayal > 0 or tiene_clave_interna(producto)


def formatear_producto(producto):
    return {
        "id": producto["ProductID"],
        "clave": producto["ProductKey"],
        "nombre": producto["ProductName"],
        "categoria": producto["Category1"],
        "unidad": producto["Unit"],
        "costo": producto["CostPrice"],
        "existencia": producto["QtyPresent"],
    }


@router.get("/")
def buscar_productos(
    busqueda: str = Query(min_length=2, max_length=100),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=50),
):
    base_datos = obtener_base_datos()
    termino = busqueda.strip()

    coincidencias = base_datos.buscar_productos_por_nombre(termino)

    if not coincidencias:
        return {
            "productos": [],
            "pagina": pagina,
            "limite": limite,
            "total": 0,
            "total_paginas": 0,
        }

    ids_productos = [
        fila["ProductID"]
        for fila in coincidencias
    ]

    productos = base_datos.buscar_info_productos(ids_productos)
    productos_del_modulo = [
        producto
        for producto in productos
        if pertenece_al_modulo(producto)
        and coincide_con_busqueda(producto, termino)
    ]

    total = len(productos_del_modulo)
    total_paginas = (total + limite - 1) // limite
    inicio = (pagina - 1) * limite
    fin = inicio + limite

    return {
        "productos": [
            formatear_producto(producto)
            for producto in productos_del_modulo[inicio:fin]
        ],
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
    }


@router.get("/{producto_id}/resultantes")
def buscar_productos_resultantes(producto_id: int):
    base_datos = obtener_base_datos()

    equivalencias = base_datos.buscar_resultantes_transformacion(
        producto_id
    )

    if not equivalencias:
        return {
            "producto_origen_id": producto_id,
            "productos": [],
        }

    ids_resultantes = [
        fila["ProductID2"]
        for fila in equivalencias
    ]

    productos = base_datos.buscar_info_productos(ids_resultantes)
    productos_por_id = {
        producto["ProductID"]: producto
        for producto in productos
    }

    resultantes = []

    for equivalencia in equivalencias:
        producto = productos_por_id.get(equivalencia["ProductID2"])

        if not producto:
            continue

        producto_formateado = formatear_producto(producto)
        producto_formateado["cantidad_origen"] = equivalencia["Cant1"]
        producto_formateado["cantidad_resultante"] = equivalencia["Cant2"]
        resultantes.append(producto_formateado)

    return {
        "producto_origen_id": producto_id,
        "productos": resultantes,
    }
