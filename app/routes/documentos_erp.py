import unicodedata
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.documentos_erp import CrearRelacionDocumentosERP
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/documentos-erp",
    tags=["Documentos ERP"],
)


def normalizar_texto(valor):
    if valor is None:
        return ""

    texto = str(valor).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )
    return " ".join(texto.split())


def valor_json(valor):
    if isinstance(valor, Decimal):
        return float(valor)

    if hasattr(valor, "isoformat"):
        return valor.isoformat()

    return valor


def fila_json(fila):
    if isinstance(fila, dict):
        items = fila.items()
    elif hasattr(fila, "items"):
        items = fila.items()
    else:
        items = dict(fila).items()

    return {
        clave: valor_json(valor)
        for clave, valor in items
    }


def resolver_module_id(modulo):
    texto = str(modulo).strip().lower()

    if texto in {"entrada", "202"}:
        return 202

    if texto in {"salida", "203"}:
        return 203

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail="Modulo no valido. Usa entrada, salida, 202 o 203.",
    )


def resolver_movimientos_por_texto(base_datos, item_value):
    texto_normalizado = normalizar_texto(item_value)

    if not texto_normalizado or texto_normalizado == normalizar_texto(
        "NO CLASIFICADO"
    ):
        return 0, 0

    movimientos_entrada = base_datos.buscar_tipo_movimiento_modulo(202)
    movimientos_salida = base_datos.buscar_tipo_movimiento_modulo(203)
    entrada = next(
        (
            movimiento
            for movimiento in movimientos_entrada
            if normalizar_texto(movimiento.get("ItemValue", "")) ==
            texto_normalizado
        ),
        None,
    )
    salida = next(
        (
            movimiento
            for movimiento in movimientos_salida
            if normalizar_texto(movimiento.get("ItemValue", "")) ==
            texto_normalizado
        ),
        None,
    )

    return (
        int(entrada.get("ItemData", 0) or 0) if entrada else 0,
        int(salida.get("ItemData", 0) or 0) if salida else 0,
    )


@router.get("/tipos-movimiento")
def listar_tipos_movimiento(
    modulo: str = Query(default="salida"),
    incluir_todos: bool = Query(default=False),
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    module_id = resolver_module_id(modulo)

    return {
        "module_id": module_id,
        "tipos": [
            fila_json(fila)
            for fila in base_datos.buscar_tipo_movimiento_modulo(
                module_id,
                incluir_todos,
            )
        ],
    }


@router.get("/tipos-movimiento/equivalencia")
def resolver_equivalencia_tipo_movimiento(
    texto: str = Query(min_length=1, max_length=120),
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    entrada_id, salida_id = resolver_movimientos_por_texto(
        obtener_base_datos(),
        texto,
    )

    return {
        "entrada_id": entrada_id,
        "salida_id": salida_id,
    }


@router.get("/documentos-relacionables")
def listar_documentos_relacionables(
    modulo: str = Query(default="salida"),
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    module_id = resolver_module_id(modulo)

    return {
        "module_id": module_id,
        "documentos": [
            fila_json(fila)
            for fila in base_datos.buscar_documentos_relacionables(module_id)
        ],
    }


@router.get("/proveedores")
def listar_proveedores(
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    return {
        "proveedores": [
            fila_json(fila)
            for fila in obtener_base_datos().obtener_proveedores_documentos()
        ],
    }


@router.get("/empleados")
def listar_empleados(
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    return {
        "empleados": [
            fila_json(fila)
            for fila in obtener_base_datos().obtener_usuarios_fisicos()
        ],
    }


@router.get("/{document_id}/relacion")
def consultar_relacion_documento(
    document_id: int,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    relacion = obtener_base_datos().obtener_relacion_documento(document_id)

    if not relacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Documento no encontrado",
        )

    return {
        "relacion": fila_json(relacion),
    }


@router.get("/{document_id}/partidas")
def consultar_partidas_documento(
    document_id: int,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    return {
        "partidas": obtener_base_datos().obtener_partidas_documento_erp(
            document_id
        ),
    }


@router.post("/{document_id}/homologar")
def homologar_relacion_documento(
    document_id: int,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    obtener_base_datos().homologar_tipo_movimiento_documento(document_id)

    return {
        "mensaje": "Homologacion ejecutada",
        "document_id": document_id,
    }


@router.get("/marcas/{categoria}")
def consultar_marcas_categoria(
    categoria: str,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    return {
        "marcas": [
            fila_json(fila)
            for fila in obtener_base_datos().obtener_marcas_por_categoria(
                categoria
            )
        ],
    }


@router.post("/relaciones")
def crear_relacion_documentos(
    datos: CrearRelacionDocumentosERP,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()

    if base_datos.documento_previamente_relacionado(
        datos.source_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento de salida ya esta relacionado.",
        )

    if base_datos.documento_previamente_relacionado(
        datos.destination_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento de entrada ya esta relacionado.",
        )

    tipo_entrada = datos.tipo_movimiento_destino_id
    tipo_salida = datos.tipo_movimiento_origen_id

    if datos.tipo_movimiento_texto:
        tipo_entrada, tipo_salida = resolver_movimientos_por_texto(
            base_datos,
            datos.tipo_movimiento_texto,
        )

    if not tipo_salida:
        tipo_salida = base_datos.buscar_tipo_movimiento_documento(
            datos.source_document_id
        )

    if not tipo_entrada:
        tipo_entrada = base_datos.buscar_tipo_movimiento_documento(
            datos.destination_document_id
        )

    if not base_datos.movimiento_es_relacionable(tipo_salida, 203):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El tipo de movimiento de salida no es relacionable.",
        )

    if not base_datos.movimiento_es_relacionable(tipo_entrada, 202):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El tipo de movimiento de entrada no es relacionable.",
        )

    folio_salida = (
        datos.folio_source_document_id or
        base_datos.buscar_folio_documento(datos.source_document_id)
    )
    folio_entrada = (
        datos.folio_destination_document_id or
        base_datos.buscar_folio_documento(datos.destination_document_id)
    )

    base_datos.relacionar_documentos_erp(
        source_document_id=datos.source_document_id,
        destination_document_id=datos.destination_document_id,
        folio_source_document_id=folio_salida,
        folio_destination_document_id=folio_entrada,
        tipo_movimiento_origen_id=tipo_salida,
        tipo_movimiento_destino_id=tipo_entrada,
        proveedor_id=datos.proveedor_id,
        usuario_fisico_id=datos.usuario_fisico_id,
        fecha_movimiento=datos.fecha_movimiento or date.today(),
        user_id_erp=sesion["user_id"],
        source_brand_id=datos.source_brand_id,
        destination_brand_id=datos.destination_brand_id,
    )

    return {
        "mensaje": "Documentos relacionados correctamente",
        "source_document_id": datos.source_document_id,
        "destination_document_id": datos.destination_document_id,
        "folio_salida": folio_salida,
        "folio_entrada": folio_entrada,
        "tipo_movimiento_origen_id": tipo_salida,
        "tipo_movimiento_destino_id": tipo_entrada,
    }

