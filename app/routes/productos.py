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


def producto_desde_configuracion(configuracion, prefijo, porcentajes_merma):
    producto_id = configuracion.get(f"{prefijo}_id")

    if not producto_id:
        return None

    return formatear_producto(
        {
            "ProductID": producto_id,
            "ProductKey": configuracion.get(f"{prefijo}_clave"),
            "ProductName": configuracion.get(f"{prefijo}_nombre"),
            "Category1": configuracion.get(f"{prefijo}_categoria"),
            "Unit": configuracion.get(f"{prefijo}_unidad"),
            "CostPrice": configuracion.get(f"{prefijo}_costo"),
            "QtyPresent": configuracion.get(f"{prefijo}_existencia") or 0,
        },
        porcentajes_merma,
    )


def componentes_desde_formula(ingredientes, producto_base_id):
    componentes = []

    for ingrediente in ingredientes:
        es_producto_base = (
            ingrediente["ComponenteID"] == producto_base_id
        )
        componentes.append({
            "producto_id": ingrediente["ComponenteID"],
            "clave": ingrediente["ProductKey"],
            "nombre": ingrediente["Componente"],
            "categoria": ingrediente["Category1"],
            "unidad": ingrediente["Unit"],
            "cantidad": ingrediente["CantidadComp"],
            "es_producto_base": es_producto_base,
            "tipo_componente": (
                "PRODUCTO_BASE"
                if es_producto_base
                else "INSUMO"
            ),
            "participa_balance": es_producto_base,
        })

    return componentes


def componentes_desde_configuracion(componentes):
    return [
        {
            "producto_id": componente["producto_componente"],
            "clave": componente["ProductKey"],
            "nombre": componente["ProductName"],
            "categoria": componente["Category1"],
            "unidad": componente["unidad"] or componente["Unit"],
            "cantidad": componente["cantidad"],
            "es_producto_base": bool(componente["es_producto_base"]),
            "tipo_componente": componente["tipo_componente"],
            "participa_balance": bool(componente["participa_balance"]),
        }
        for componente in componentes
    ]


def respuesta_configuracion_usuario(base_datos, producto_id):
    configuracion = base_datos.buscar_configuracion_usuario_para_producto(
        producto_id
    )

    if not configuracion:
        return None

    detalles = base_datos.buscar_detalles_configuraciones_usuario([
        configuracion["id_transformacion_usuario"]
    ])

    if not detalles:
        return None

    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    producto_origen = producto_desde_configuracion(
        configuracion,
        "origen",
        porcentajes_merma,
    )
    producto_formula = producto_desde_configuracion(
        configuracion,
        "formula",
        porcentajes_merma,
    )
    componentes = componentes_desde_configuracion(
        base_datos.buscar_componentes_configuraciones_usuario([
            configuracion["id_transformacion_usuario"]
        ])
    )

    if not componentes and configuracion["producto_formula"]:
        ingredientes = base_datos.buscar_ingredientes_formula(
            configuracion["producto_formula"]
        )
        componentes = componentes_desde_formula(
            ingredientes,
            configuracion["producto_origen"],
        )

    resultantes = []

    for detalle in detalles:
        producto_formateado = formatear_producto(
            detalle,
            porcentajes_merma,
        )
        producto_formateado["cantidad_origen"] = (
            configuracion["cantidad_base"]
        )
        producto_formateado["cantidad_resultante"] = (
            detalle["cantidad_resultante"]
        )
        producto_formateado["tipo_relacion"] = "configuracion_usuario"
        producto_formateado["configuracion_id"] = (
            configuracion["id_transformacion_usuario"]
        )
        resultantes.append(producto_formateado)

    return {
        "producto_origen_id": configuracion["producto_origen"],
        "producto_seleccionado_id": producto_id,
        "fuente": "TransformacionesUsuario",
        "tipo_relacion": "configuracion_usuario",
        "configuracion": {
            "id": configuracion["id_transformacion_usuario"],
            "nombre": configuracion["nombre_transformacion"],
            "cantidad_base": configuracion["cantidad_base"],
            "porcentaje_merma": configuracion["porcentaje_merma"],
        },
        "producto_origen": producto_origen,
        "producto_formula": producto_formula,
        "componentes": componentes,
        "productos": resultantes,
    }


def respuesta_formula_producto(base_datos, producto_id):
    ingredientes = base_datos.buscar_ingredientes_formula(producto_id)

    if not ingredientes:
        return None

    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    categorias_modulo = set(porcentajes_merma)
    bases = [
        ingrediente
        for ingrediente in ingredientes
        if (
            str(ingrediente["Category1"] or "").strip().upper()
            in categorias_modulo
        )
    ]

    if not bases:
        return None

    base = bases[0]
    productos = {
        fila["ProductID"]: fila
        for fila in base_datos.buscar_productos_por_ids([
            producto_id,
            base["ComponenteID"],
        ])
    }
    producto_origen = productos.get(base["ComponenteID"])
    producto_formula = productos.get(producto_id)

    if not producto_origen or not producto_formula:
        return None

    producto_origen = formatear_producto(
        producto_origen,
        porcentajes_merma,
    )
    producto_formula = formatear_producto(
        producto_formula,
        porcentajes_merma,
    )
    producto_resultante = {
        **producto_formula,
        "cantidad_origen": base["CantidadComp"],
        "cantidad_resultante": base["CantidadComp"],
        "tipo_relacion": "formula_producto",
    }
    componentes = componentes_desde_formula(
        ingredientes,
        base["ComponenteID"],
    )

    return {
        "producto_origen_id": producto_origen["id"],
        "producto_seleccionado_id": producto_id,
        "fuente": "zvwFormulasListasPCocinar",
        "tipo_relacion": "formula_producto",
        "configuracion": None,
        "producto_origen": producto_origen,
        "producto_formula": producto_formula,
        "componentes": componentes,
        "productos": [producto_resultante],
    }


def respuesta_equivalencias(base_datos, producto_id):
    equivalencias = base_datos.buscar_resultantes_transformacion(producto_id)

    if not equivalencias:
        return None

    porcentajes_merma = base_datos.buscar_porcentajes_merma()
    resultantes = []

    for equivalencia in equivalencias:
        producto_formateado = formatear_producto(
            equivalencia,
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

    productos = base_datos.buscar_productos_por_nombre(termino)

    if not productos:
        return {
            "productos": [],
            "pagina": pagina,
            "limite": limite,
            "total": 0,
            "total_paginas": 0,
        }

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
    configuracion_usuario = respuesta_configuracion_usuario(
        base_datos,
        producto_id,
    )

    if configuracion_usuario:
        return configuracion_usuario

    formula = respuesta_formula_producto(base_datos, producto_id)

    if formula:
        return formula

    equivalencias = respuesta_equivalencias(base_datos, producto_id)

    if equivalencias:
        return equivalencias

    return {
        "producto_origen_id": producto_id,
        "fuente": None,
        "tipo_relacion": None,
        "productos": [],
    }
