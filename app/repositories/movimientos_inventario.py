from app.repositories.transformaciones import formatear_fecha
from app.utils.base_de_datos import obtener_base_datos


TIPO_TODOS = "todos"
TIPO_SALIDA = "salida"
TIPO_ENTRADA = "entrada"
TIPOS_VALIDOS = {TIPO_TODOS, TIPO_SALIDA, TIPO_ENTRADA}


def numero(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0


def crear_producto(fila):
    if not fila.get("ProductID"):
        return None

    return {
        "id": fila["ProductID"],
        "clave": fila["ProductKey"],
        "nombre": fila["ProductName"],
        "categoria": fila["Category1"],
        "unidad": fila["Unit"] or "KILO",
    }


def tipo_movimiento_desde_modulo(module_id):
    return TIPO_ENTRADA if int(module_id or 0) == 202 else TIPO_SALIDA


def estado_documento(fila):
    if fila.get("SourceDocumentID") or fila.get("DestinationDocumentID"):
        return "relacionado"

    return "sin_relacion"


def crear_movimiento(fila):
    tipo = tipo_movimiento_desde_modulo(fila["ModuleID"])
    proveedor_id = fila.get("SupplierID")
    empleado_id = fila.get("PhysicalUserID")

    return {
        "id": f'{fila["DocumentID"]}-{fila.get("DocumentItemID") or 0}',
        "folio_transformacion": None,
        "tipo": tipo,
        "fecha": formatear_fecha(fila.get("CreatedOn")),
        "fecha_documento": formatear_fecha(fila.get("DateDocument")),
        "fecha_movimiento": formatear_fecha(fila.get("MovementDate")),
        "usuario_id": fila.get("CreatedBy"),
        "usuario": fila.get("UserName") or "-",
        "producto": crear_producto(fila),
        "cantidad": numero(fila.get("Quantity")),
        "unidad": fila.get("Unit") or "KILO",
        "documento_id": fila.get("DocumentID"),
        "folio_documento": fila.get("Folio"),
        "tipo_movimiento_id": fila.get("TipoMovimientoID"),
        "tipo_movimiento": fila.get("TipoMovimiento"),
        "almacen_id": fila.get("DepotID"),
        "almacen": fila.get("DepotName"),
        "estado_erp": estado_documento(fila),
        "error_erp": None,
        "documento_origen": fila.get("SourceDocumentID"),
        "documento_destino": fila.get("DestinationDocumentID"),
        "folio_relacionado": fila.get("Custom1"),
        "proveedor": {
            "id": proveedor_id,
            "nombre": fila.get("SupplierName"),
        } if proveedor_id else None,
        "empleado_movimiento": {
            "id": empleado_id,
            "nombre": fila.get("PhysicalUserName"),
        } if empleado_id else None,
    }


def listar_movimientos_inventario(tipo=TIPO_TODOS):
    tipo_normalizado = str(tipo or TIPO_TODOS).strip().lower()

    if tipo_normalizado not in TIPOS_VALIDOS:
        raise ValueError("Tipo de movimiento no valido")

    return [
        crear_movimiento(fila)
        for fila in obtener_base_datos()
            .buscar_movimientos_inventario_independientes(tipo_normalizado)
    ]


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
            if movimiento.get("estado_erp") != "relacionado"
        ),
    }
