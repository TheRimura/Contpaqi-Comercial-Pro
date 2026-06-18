from decimal import Decimal

from app.utils.base_de_datos import obtener_base_datos


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
        }
        detalles.setdefault(
            fila["id_transformacion"],
            [],
        ).append(detalle)

    return detalles


def separar_formula(productos_resultantes, producto_base_id):
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


def construir_registros(encabezados, detalles, bases_formula):
    registros = []

    for encabezado in encabezados:
        folio = encabezado["id_transformacion"]
        productos_resultantes = detalles.get(folio, [])
        producto_base_id = bases_formula.get(
            encabezado["producto_origen"]
        )
        (
            producto_base_formula,
            ingredientes_formula,
            productos_visibles,
        ) = separar_formula(
            productos_resultantes,
            producto_base_id,
        )
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

        registros.append({
            "folio": folio,
            "fecha": formatear_fecha(encabezado["fecha_creacion"]),
            "usuario_id": None,
            "usuario": encabezado["usuario_responsable"],
            "tipo_transformacion": (
                "producto_final"
                if es_producto_final
                else "receta_configurada"
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
            "porcentaje_merma_esperado": None,
            "diferencia_merma": None,
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

    detalles = agrupar_detalles(
        base_datos.buscar_detalles_transformaciones([
            fila["id_transformacion"]
            for fila in encabezados
        ])
    )
    bases_formula = {
        fila["ProductID"]: fila["ComponenteID"]
        for fila in base_datos.buscar_bases_formulas([
            encabezado["producto_origen"]
            for encabezado in encabezados
        ])
    }

    return construir_registros(
        encabezados,
        detalles,
        bases_formula,
    )


def obtener_transformacion(transformacion_id):
    registros = listar_transformaciones(transformacion_id)
    return registros[0] if registros else None


def guardar_transformacion(datos, rendimiento):
    base_datos = obtener_base_datos()
    transformacion_id = base_datos.registrar_transformacion(
        producto_origen_id=datos.producto_origen_id,
        cantidad_origen=datos.cantidad_origen,
        usuario=datos.usuario_nombre,
        productos_resultantes=datos.productos_resultantes,
        peso_merma=rendimiento["peso_merma"],
        observaciones_merma=datos.observaciones_merma,
    )

    return obtener_transformacion(transformacion_id)
