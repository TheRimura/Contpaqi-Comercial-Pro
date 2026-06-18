import re

from fastapi import APIRouter, Depends, Query

from app.services.sesiones import requerir_sesion
from app.services.reglas_merma import obtener_merma_estimada
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


def pertenece_al_modulo(producto):
    tipo_cayal = int(producto.get("ProductTypeIDCayal") or 0)
    return tipo_cayal > 0


def formatear_producto(producto):
    return {
        "id": producto["ProductID"],
        "clave": producto["ProductKey"],
        "nombre": producto["ProductName"],
        "categoria": producto["Category1"],
        "unidad": producto["Unit"],
        "costo": producto["CostPrice"],
        "existencia": producto["QtyPresent"],
        "merma_estimada": obtener_merma_estimada(producto),
    }


def producto_maneja_peso(producto):
    unidad = str(producto.get("Unit") or "").strip().upper()
    return unidad == "KILO"


def buscar_productos_por_ids(base_datos, ids_productos):
    if not ids_productos:
        return {}

    productos = base_datos.buscar_info_productos(ids_productos)

    return {
        producto["ProductID"]: producto
        for producto in productos
    }


def respuesta_formula(base_datos, producto_id):
    componentes = base_datos.buscar_componentes_formula(producto_id)

    if not componentes:
        return None

    productos_por_id = buscar_productos_por_ids(
        base_datos,
        [
            fila["ComponenteID"]
            for fila in componentes
        ],
    )
    productos = []

    for componente in componentes:
        producto = productos_por_id.get(componente["ComponenteID"])

        if not producto:
            continue

        producto_formateado = formatear_producto(producto)
        producto_formateado["cantidad_formula"] = componente[
            "CantidadComp"
        ]
        producto_formateado["participa_balance"] = producto_maneja_peso(
            producto
        )
        producto_formateado["tipo_relacion"] = "componente_formula"
        productos.append(producto_formateado)

    return {
        "producto_origen_id": producto_id,
        "fuente": "zvwFormulasListasPCocinar",
        "tipo_relacion": "formula_lista_para_cocinar",
        "productos": productos,
    }


def respuesta_equivalencias(base_datos, producto_id):
    equivalencias = base_datos.buscar_resultantes_transformacion(producto_id)

    if not equivalencias:
        return None

    productos_por_id = buscar_productos_por_ids(
        base_datos,
        [
            fila["ProductID2"]
            for fila in equivalencias
        ],
    )
    resultantes = []

    for equivalencia in equivalencias:
        producto = productos_por_id.get(equivalencia["ProductID2"])

        if not producto:
            continue

        producto_formateado = formatear_producto(producto)
        producto_formateado["cantidad_origen"] = equivalencia["Cant1"]
        producto_formateado["cantidad_resultante"] = equivalencia["Cant2"]
        producto_formateado["tipo_relacion"] = "equivalencia"
        resultantes.append(producto_formateado)

    return {
        "producto_origen_id": producto_id,
        "fuente": "zvwEquivalenciasTransKoben",
        "tipo_relacion": "equivalencia_transformacion",
        "productos": resultantes,
    }


@router.get("/")
def buscar_productos(
    sesion: dict = Depends(requerir_sesion),
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
def buscar_productos_resultantes(
    producto_id: int,
    sesion: dict = Depends(requerir_sesion),
):
    base_datos = obtener_base_datos()
    receta = respuesta_formula(base_datos, producto_id)

    if receta:
        return receta

    equivalencias = respuesta_equivalencias(base_datos, producto_id)

    if equivalencias:
        return equivalencias

    return {
        "producto_origen_id": producto_id,
        "fuente": None,
        "tipo_relacion": None,
        "productos": [],
    }
