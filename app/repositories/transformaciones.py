from decimal import Decimal

from app.utils.base_de_datos import obtener_base_datos


class ErrorTransformacion(ValueError):
    pass


def numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def formatear_fecha(fecha):
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%Y-%m-%d %H:%M:%S")

    return str(fecha or "")


def crear_producto(
    producto_id,
    clave,
    nombre,
    categoria,
    unidad,
):
    if not nombre:
        return None

    return {
        "id": producto_id,
        "clave": clave,
        "nombre": nombre,
        "categoria": categoria,
        "unidad": unidad,
    }


def agrupar_detalles(filas):
    detalles = {}

    for fila in filas:
        detalle = {
            "producto": crear_producto(
                fila["producto_resultado"],
                fila["ProductKey"],
                fila["ProductName"],
                fila["Category1"],
                fila["Unit"],
            ),
            "cantidad": numero(fila["cantidad_resultado"]),
            "unidad": fila["unidad_resultado"] or fila["Unit"] or "KILO",
        }
        detalles.setdefault(
            fila["id_transformacion"],
            [],
        ).append(detalle)

    return detalles


def agrupar_componentes(filas):
    componentes = {}

    for fila in filas:
        componente = {
            "producto": crear_producto(
                fila["producto_componente"],
                fila["ProductKey"],
                fila["ProductName"],
                fila["Category1"],
                fila["Unit"],
            ),
            "cantidad": numero(fila["cantidad"]),
            "unidad": fila["unidad"] or fila["Unit"] or "",
            "es_producto_base": bool(fila["es_producto_base"]),
        }
        componentes.setdefault(
            fila["id_transformacion"],
            [],
        ).append(componente)

    return componentes


def separar_formula_anterior(productos_resultantes, producto_base_id):
    if not producto_base_id:
        return None, [], productos_resultantes

    producto_base = None
    ingredientes = []

    for detalle in productos_resultantes:
        producto = detalle.get("producto") or {}

        if producto.get("id") == producto_base_id:
            producto_base = detalle
        else:
            ingredientes.append(detalle)

    if not producto_base:
        return None, [], productos_resultantes

    return producto_base, ingredientes, [producto_base]


def construir_registros(
    encabezados,
    detalles,
    componentes,
    bases_formula,
):
    registros = []

    for encabezado in encabezados:
        folio = encabezado["id_transformacion"]
        productos_resultantes = detalles.get(folio, [])
        componentes_registrados = componentes.get(folio, [])

        if componentes_registrados:
            producto_base_formula = next(
                (
                    componente
                    for componente in componentes_registrados
                    if componente["es_producto_base"]
                ),
                None,
            )
            ingredientes_formula = [
                componente
                for componente in componentes_registrados
                if not componente["es_producto_base"]
            ]
            productos_visibles = productos_resultantes
        else:
            producto_base_id = bases_formula.get(
                encabezado["producto_seleccionado"]
                or encabezado["producto_origen"]
            )
            (
                producto_base_formula,
                ingredientes_formula,
                productos_visibles,
            ) = separar_formula_anterior(
                productos_resultantes,
                producto_base_id,
            )

        tipo_guardado = encabezado["tipo_transformacion"]
        es_producto_final = tipo_guardado == "producto_final"

        if not tipo_guardado:
            es_producto_final = (
                len(productos_resultantes) == 1
                and (
                    productos_resultantes[0].get("producto") or {}
                ).get("id") == encabezado["producto_origen"]
            )

        cantidad_origen = numero(encabezado["cantidad_origen"])
        peso_merma = numero(encabezado["peso_merma"] or 0)
        porcentaje_merma = (
            peso_merma / cantidad_origen * 100
            if cantidad_origen
            else 0
        )
        porcentaje_esperado = numero(
            encabezado["porcentaje_merma_esperado"]
        )

        registros.append({
            "folio": folio,
            "fecha": formatear_fecha(encabezado["fecha_creacion"]),
            "usuario_id": encabezado["usuario_id"],
            "usuario": encabezado["usuario_responsable"],
            "tipo_transformacion": (
                tipo_guardado
                or (
                    "producto_final"
                    if es_producto_final
                    else "receta_configurada"
                )
            ),
            "producto_ya_transformado": es_producto_final,
            "producto_origen": crear_producto(
                encabezado["producto_origen"],
                encabezado["origen_clave"],
                encabezado["origen_nombre"],
                encabezado["origen_categoria"],
                encabezado["origen_unidad"],
            ),
            "cantidad_origen": cantidad_origen,
            "producto_base_formula": producto_base_formula,
            "ingredientes_formula": ingredientes_formula,
            "productos_resultantes": productos_visibles,
            "total_salida": sum(
                producto["cantidad"]
                for producto in productos_resultantes
            ),
            "peso_merma": peso_merma,
            "porcentaje_merma_real": porcentaje_merma,
            "porcentaje_merma_esperado": porcentaje_esperado,
            "diferencia_merma": (
                porcentaje_merma - porcentaje_esperado
                if porcentaje_esperado is not None
                else None
            ),
            "observaciones_merma": encabezado["motivo"],
            "documento_salida": encabezado["documento_salida"],
            "documento_entrada": encabezado["documento_entrada"],
        })

    return registros


def listar_transformaciones(transformacion_id=None):
    base_datos = obtener_base_datos()
    encabezados = base_datos.buscar_historial_transformaciones(
        transformacion_id
    )

    if not encabezados:
        return []

    ids_transformaciones = [
        fila["id_transformacion"]
        for fila in encabezados
    ]
    detalles = agrupar_detalles(
        base_datos.buscar_detalles_transformaciones(
            ids_transformaciones
        )
    )
    componentes = agrupar_componentes(
        base_datos.buscar_componentes_transformaciones(
            ids_transformaciones
        )
    )
    bases_formula = {
        fila["ProductID"]: fila["ComponenteID"]
        for fila in base_datos.buscar_bases_formulas([
            encabezado["producto_seleccionado"]
            or encabezado["producto_origen"]
            for encabezado in encabezados
        ])
    }

    return construir_registros(
        encabezados,
        detalles,
        componentes,
        bases_formula,
    )


def obtener_transformacion(transformacion_id):
    registros = listar_transformaciones(transformacion_id)
    return registros[0] if registros else None


def validar_productos_existentes(base_datos, datos):
    ids_productos = {
        datos.producto_origen_id,
        datos.producto_seleccionado_id or datos.producto_origen_id,
        *[
            producto.producto_id
            for producto in datos.productos_resultantes
        ],
        *[
            producto.producto_id
            for producto in datos.componentes_formula
        ],
    }
    existentes = base_datos.buscar_ids_productos_existentes(ids_productos)
    faltantes = ids_productos - existentes

    if faltantes:
        raise ErrorTransformacion(
            "Hay productos inexistentes o eliminados: "
            + ", ".join(str(producto_id) for producto_id in sorted(faltantes))
        )


def validar_formula(base_datos, datos):
    componentes_configurados = base_datos.buscar_componentes_formula(
        datos.producto_seleccionado_id
    )

    if not componentes_configurados:
        raise ErrorTransformacion(
            "El producto no tiene una formula configurada"
        )

    cantidades_configuradas = {
        fila["ComponenteID"]: Decimal(str(fila["CantidadComp"]))
        for fila in componentes_configurados
    }
    componentes_recibidos = {
        componente.producto_id: componente
        for componente in datos.componentes_formula
    }

    if set(componentes_recibidos) != set(cantidades_configuradas):
        raise ErrorTransformacion(
            "Los componentes no coinciden con la formula configurada"
        )

    base = next(
        componente
        for componente in datos.componentes_formula
        if componente.es_producto_base
    )
    bases_configuradas = base_datos.buscar_bases_formulas([
        datos.producto_seleccionado_id
    ])
    base_configurada_id = (
        bases_configuradas[0]["ComponenteID"]
        if bases_configuradas
        else None
    )

    if base.producto_id != base_configurada_id:
        raise ErrorTransformacion(
            "El producto base no coincide con la formula configurada"
        )

    productos_formula = {
        producto["ProductID"]: producto
        for producto in base_datos.buscar_info_productos(
            componentes_recibidos.keys()
        )
    }

    for producto_id, componente in componentes_recibidos.items():
        unidad_configurada = str(
            productos_formula[producto_id]["Unit"] or ""
        ).strip().upper()

        if componente.unidad.strip().upper() != unidad_configurada:
            raise ErrorTransformacion(
                "La unidad de un componente no coincide con el producto"
            )

    cantidad_base_configurada = cantidades_configuradas[base.producto_id]
    factor = datos.cantidad_origen / cantidad_base_configurada
    tolerancia = Decimal("0.01")

    for producto_id, componente in componentes_recibidos.items():
        cantidad_esperada = cantidades_configuradas[producto_id] * factor

        if abs(componente.cantidad - cantidad_esperada) > tolerancia:
            raise ErrorTransformacion(
                "Las cantidades no corresponden a la formula configurada"
            )


def validar_equivalencias(base_datos, datos):
    equivalencias = base_datos.buscar_resultantes_transformacion(
        datos.producto_origen_id
    )
    ids_permitidos = {
        fila["ProductID2"]
        for fila in equivalencias
    }
    ids_recibidos = {
        producto.producto_id
        for producto in datos.productos_resultantes
    }

    if not ids_permitidos or not ids_recibidos.issubset(ids_permitidos):
        raise ErrorTransformacion(
            "Los productos no corresponden a una transformacion configurada"
        )


def validar_transformacion(base_datos, datos):
    validar_productos_existentes(base_datos, datos)

    if datos.tipo_transformacion == "producto_final":
        return

    if datos.componentes_formula:
        validar_formula(base_datos, datos)
        return

    validar_equivalencias(base_datos, datos)


def guardar_transformacion(datos, rendimiento):
    base_datos = obtener_base_datos()
    validar_transformacion(base_datos, datos)
    transformacion_id = base_datos.registrar_transformacion(
        producto_origen_id=datos.producto_origen_id,
        producto_seleccionado_id=(
            datos.producto_seleccionado_id
            or datos.producto_origen_id
        ),
        cantidad_origen=datos.cantidad_origen,
        usuario=datos.usuario_nombre,
        usuario_id=datos.usuario_id,
        tipo_transformacion=datos.tipo_transformacion,
        productos_resultantes=datos.productos_resultantes,
        componentes_formula=datos.componentes_formula,
        peso_merma=rendimiento["peso_merma"],
        porcentaje_merma_esperado=datos.porcentaje_merma_esperado,
        observaciones_merma=datos.observaciones_merma,
        id_operacion=datos.id_operacion,
    )

    return obtener_transformacion(transformacion_id)
