from app.repositories.transformaciones import listar_transformaciones


TIPO_TODOS = "todos"
TIPO_SALIDA = "salida"
TIPO_ENTRADA = "entrada"
TIPOS_VALIDOS = {TIPO_TODOS, TIPO_SALIDA, TIPO_ENTRADA}


def crear_movimiento_salida(registro):
    producto = registro.get("producto_origen") or {}

    return {
        "id": f'{registro["folio"]}-S',
        "folio_transformacion": registro["folio"],
        "tipo": TIPO_SALIDA,
        "fecha": registro.get("fecha"),
        "usuario_id": registro.get("usuario_id"),
        "usuario": registro.get("usuario"),
        "producto": producto,
        "cantidad": registro.get("cantidad_origen") or 0,
        "unidad": producto.get("unidad") or "KILO",
        "documento_id": registro.get("documento_salida"),
        "folio_documento": registro.get("folio_salida"),
        "almacen_id": registro.get("almacen_id"),
        "almacen": registro.get("almacen"),
        "estado_erp": registro.get("estado_erp"),
        "error_erp": registro.get("error_erp"),
    }


def crear_movimientos_entrada(registro):
    movimientos = []
    productos = registro.get("productos_resultantes") or []

    for indice, detalle in enumerate(productos, start=1):
        producto = detalle.get("producto") or {}
        movimientos.append({
            "id": f'{registro["folio"]}-E-{indice}',
            "folio_transformacion": registro["folio"],
            "tipo": TIPO_ENTRADA,
            "fecha": registro.get("fecha"),
            "usuario_id": registro.get("usuario_id"),
            "usuario": registro.get("usuario"),
            "producto": producto,
            "cantidad": detalle.get("cantidad") or 0,
            "unidad": detalle.get("unidad") or producto.get("unidad") or "KILO",
            "documento_id": registro.get("documento_entrada"),
            "folio_documento": registro.get("folio_entrada"),
            "almacen_id": registro.get("almacen_id"),
            "almacen": registro.get("almacen"),
            "estado_erp": registro.get("estado_erp"),
            "error_erp": registro.get("error_erp"),
        })

    return movimientos

def listar_movimientos_inventario(tipo=TIPO_TODOS):
    tipo_normalizado = str(tipo or TIPO_TODOS).strip().lower()

    if tipo_normalizado not in TIPOS_VALIDOS:
        raise ValueError("Tipo de movimiento no valido")

    movimientos = []

    for registro in listar_transformaciones():
        if tipo_normalizado in {TIPO_TODOS, TIPO_SALIDA}:
            movimientos.append(crear_movimiento_salida(registro))

        if tipo_normalizado in {TIPO_TODOS, TIPO_ENTRADA}:
            movimientos.extend(crear_movimientos_entrada(registro))

    return movimientos

def calcular_indicadores(movimientos):
    salidas = [
        movimiento
        for movimiento in movimientos
        if movimiento["tipo"] == TIPO_SALIDA
    ]
    entradas = [
        movimiento
        for movimiento in movimientos
        if movimiento["tipo"] == TIPO_ENTRADA
    ]

    return {
        "salidas": len(salidas),
        "entradas": len(entradas),
        "kilos_salida": sum(
            movimiento["cantidad"]
            for movimiento in salidas
            if str(movimiento.get("unidad") or "").upper() == "KILO"
        ),
        "kilos_entrada": sum(
            movimiento["cantidad"]
            for movimiento in entradas
            if str(movimiento.get("unidad") or "").upper() == "KILO"
        ),
        "pendientes": sum(
            1
            for movimiento in movimientos
            if movimiento.get("estado_erp") != "completada"
        ),
    }


