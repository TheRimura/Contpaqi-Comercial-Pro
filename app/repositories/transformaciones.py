from decimal import Decimal

from app.repositories.movimientos_erp import IntegracionMovimientosERP
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
        total_entrada = sum(
            producto["cantidad"]
            for producto in productos_resultantes
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
            "total_entrada": total_entrada,
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
            "folio_salida": encabezado["folio_salida"],
            "folio_entrada": encabezado["folio_entrada"],
            "almacen_id": encabezado["almacen_id"],
            "almacen": encabezado["almacen"],
            "estado_erp": encabezado["estado_erp"],
            "error_erp": encabezado["error_erp"],
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
    }
    existentes = base_datos.buscar_ids_productos_existentes(ids_productos)
    faltantes = ids_productos - existentes

    if faltantes:
        raise ErrorTransformacion(
            "Hay productos inexistentes o eliminados: "
            + ", ".join(str(producto_id) for producto_id in sorted(faltantes))
        )

    productos_principales = {
        datos.producto_origen_id,
        datos.producto_seleccionado_id or datos.producto_origen_id,
    }
    productos_del_modulo = base_datos.buscar_ids_productos_modulo(
        productos_principales
    )
    fuera_del_modulo = productos_principales - productos_del_modulo

    if fuera_del_modulo:
        raise ErrorTransformacion(
            "El producto no pertenece a Pollo, Cerdo o Res Local"
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

    validar_equivalencias(base_datos, datos)


def guardar_transformacion(datos, rendimiento):
    base_datos = obtener_base_datos()
    validar_transformacion(base_datos, datos)
    configuracion = base_datos.buscar_configuracion_transformaciones()
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
        peso_merma=rendimiento["peso_merma"],
        almacen_id=configuracion["almacen_id"],
        porcentaje_merma_esperado=datos.porcentaje_merma_esperado,
        observaciones_merma=datos.observaciones_merma,
        id_operacion=datos.id_operacion,
    )
    IntegracionMovimientosERP(base_datos).procesar(
        transformacion_id,
        datos,
    )

    return obtener_transformacion(transformacion_id)
