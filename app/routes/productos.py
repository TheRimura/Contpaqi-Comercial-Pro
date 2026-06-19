import re

from fastapi import APIRouter, Depends, Query

from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


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


def formatear_producto(producto, porcentajes_merma=None):
    categoria = str(producto.get("Category1") or "").strip().upper()
    porcentaje_merma = (porcentajes_merma or {}).get(categoria, 0)

    return {
        "id": producto["ProductID"],
        "clave": producto["ProductKey"],
        "nombre": producto["ProductName"],
        "categoria": producto["Category1"],
        "unidad": producto["Unit"],
        "costo": producto["CostPrice"],
        "existencia": producto["QtyPresent"],
        "merma_estimada": {
            "porcentaje": porcentaje_merma,
            "descripcion": (
                f"Referencia configurable para {producto['Category1']}"
            ),
            "fuente": "base_de_datos",
        },
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
    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    productos = []

    for componente in componentes:
        producto = productos_por_id.get(componente["ComponenteID"])

        if not producto:
            continue

        producto_formateado = formatear_producto(
            producto,
            porcentajes_merma,
        )
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
    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    resultantes = []

    for equivalencia in equivalencias:
        producto = productos_por_id.get(equivalencia["ProductID2"])

        if not producto:
            continue

        producto_formateado = formatear_producto(
            producto,
            porcentajes_merma,
        )
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
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
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
    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    productos_del_modulo = [
        producto
        for producto in productos
        if coincide_con_busqueda(producto, termino)
    ]

    total = len(productos_del_modulo)
    total_paginas = (total + limite - 1) // limite
    inicio = (pagina - 1) * limite
    fin = inicio + limite

    return {
        "productos": [
            formatear_producto(producto, porcentajes_merma)
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
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
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
