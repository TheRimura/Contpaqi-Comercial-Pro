import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder

from app.schemas.relacion_documentos import (
    CrearRelacionDocumentos,
    RespuestaRelacionDocumentos,
)
from app.utils.base_de_datos import BaseDatos, obtener_base_datos
from app.utils.seguridad import seguridad_sesion

router = APIRouter(
    prefix="/relacion_documentos",
    tags=["relacion_documentos"],
)

def exigir_sesion(request: Request) -> dict:
    sesion = seguridad_sesion.obtener_sesion(request)

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no valida. Inicia Sesion Nuevamente",
        )
    return sesion

def obtener_usuario_id(sesion: dict) -> int:
    claves =(
        "user_id"
        "usuario_id"
        "id_usuario"
        "userID"
    )

    for clave in claves:
        valor = sesion.get(clave)

        if valor is None:
            continue

        try:
            usuario_id = int(valor)
        except (TypeError, ValueError):
            continue

        if usuario_id > 0:
            return usuario_id

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="La Sesion no contiene un usuario ERP valido",
    )

def normalizar_texto(valor) -> str:
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD",texto)
    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )
    return " ".join(texto.split())

def resolver_movimientos(
    texto_movimiento: str,
    movimientos_entrada: list[dict],
    movimientos_salida: list[dict],
) -> tuple[int, int]:
    texto_normalizado = normalizar_texto(texto_movimiento)

    if not texto_normalizado or texto_normalizado == "NO CLASIFICADO":
        return 0, 0

    entrada_id = 0
    salida_id = 0

    for movimiento in movimientos_entrada:
        if normalizar_texto(movimiento.get("ItemValue")) == texto_normalizado:
            entrada_id = int(movimiento.get("ItemData") or 0)
            break

    for movimiento in movimientos_salida:
        if normalizar_texto(movimiento.get("ItemValue")) == texto_normalizado:
            salida_id = int(movimiento.get("ItemData") or 0)
            break

    return entrada_id, salida_id


def construir_catalogo_movimientos(
        base_datos: BaseDatos,
) -> list[dict]:
    entradas = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_ENTRADA
    )
    salidas = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_SALIDA
    )

    salidas_por_texto = {
        normalizar_texto(registro.get("ItemValue")): registro
        for registro in salidas
    }

    movimientos = []

    for entrada in entradas:
        texto = entrada.get("ItemValue") or ""
        salida = salidas_por_texto.get(normalizar_texto(texto))

        if not salida:
            continue

        entrada_id = int(entrada.get("ItemData") or 0)
        salida_id = int(salida.get("ItemData") or 0)

        if entrada_id <= 0 or salida_id <= 0:
            continue

        movimientos.append(
            {
                "ItemValue": texto,
                "EntradaID": entrada_id,
                "SalidaID": salida_id,
            }
        )

    return movimientos


@router.get("/catalogos")
def consultar_catalogos(
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    return jsonable_encoder(
        {
            "movimientos": construir_catalogo_movimientos(base_datos),
            "proveedores": base_datos.obtener_proveedores_documentos(),
            "usuarios_fisicos": base_datos.obtener_usuarios_fisicos(),
        }
    )


@router.get("/documentos-disponibles/{module_id}")
def consultar_documentos_disponibles(
        module_id: int,
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    if module_id == base_datos.MODULO_SALIDA:
        documentos = base_datos.buscar_documentos_relacionables(
            base_datos.MODULO_ENTRADA
        )
    elif module_id == base_datos.MODULO_ENTRADA:
        documentos = base_datos.buscar_documentos_relacionables(
            base_datos.MODULO_SALIDA
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El módulo debe ser 202 para entrada o 203 para salida.",
        )

    return jsonable_encoder(documentos)


@router.get("/documentos/{document_id}")
def consultar_relacion_documento(
        document_id: int,
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    relacion = base_datos.obtener_relacion_documento(document_id)

    if not relacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el documento.",
        )

    return jsonable_encoder(relacion)


@router.get("/documentos/{document_id}/partidas")
def consultar_partidas_documento(
        document_id: int,
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    return jsonable_encoder(
        base_datos.obtener_partidas_documento_erp(document_id)
    )


@router.get("/buscar-por-folio")
def buscar_documento_por_folio(
        request: Request,
        folio: str = Query(min_length=1, max_length=125),
        module_id: Optional[int] = Query(default=None),
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    document_id = base_datos.buscar_document_id_por_folio(
        folio,
        module_id,
    )

    return {"DocumentID": document_id}


@router.get("/marcas")
def consultar_marcas(
        request: Request,
        categoria: str = Query(min_length=1, max_length=150),
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    return jsonable_encoder(
        base_datos.obtener_marcas_por_categoria(categoria)
    )


@router.post(
    "",
    response_model=RespuestaRelacionDocumentos,
    status_code=status.HTTP_201_CREATED,
)
def crear_relacion_documentos(
        datos: CrearRelacionDocumentos,
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = exigir_sesion(request)
    usuario_id_erp = obtener_usuario_id(sesion)

    if datos.source_document_id == datos.destination_document_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El documento de salida y el documento de entrada "
                "no pueden ser el mismo."
            ),
        )

    documento_salida = base_datos.obtener_relacion_documento(
        datos.source_document_id
    )
    documento_entrada = base_datos.obtener_relacion_documento(
        datos.destination_document_id
    )

    if not documento_salida:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el documento de salida.",
        )

    if not documento_entrada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se encontró el documento de entrada.",
        )

    if int(documento_salida.get("ModuleID") or 0) != base_datos.MODULO_SALIDA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento origen debe pertenecer al módulo de salida 203.",
        )

    if int(documento_entrada.get("ModuleID") or 0) != base_datos.MODULO_ENTRADA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El documento destino debe pertenecer al módulo de entrada 202.",
        )

    if base_datos.documento_previamente_relacionado(
            datos.source_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento de salida ya fue relacionado.",
        )

    if base_datos.documento_previamente_relacionado(
            datos.destination_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El documento de entrada ya fue relacionado.",
        )

    movimientos_entrada = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_ENTRADA
    )
    movimientos_salida = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_SALIDA
    )

    movimiento_entrada_id, movimiento_salida_id = resolver_movimientos(
        datos.tipo_movimiento,
        movimientos_entrada,
        movimientos_salida,
    )

    if movimiento_entrada_id <= 0 or movimiento_salida_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "El movimiento seleccionado no tiene una equivalencia "
                "válida entre entrada y salida."
            ),
        )

    folio_salida = base_datos.buscar_folio_documento(
        datos.source_document_id
    )
    folio_entrada = base_datos.buscar_folio_documento(
        datos.destination_document_id
    )

    if not folio_salida or not folio_entrada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No se pudo obtener el folio de uno de los documentos.",
        )

    base_datos.relacionar_documentos_erp(
        source_document_id=datos.source_document_id,
        destination_document_id=datos.destination_document_id,
        folio_source_document_id=folio_salida,
        folio_destination_document_id=folio_entrada,
        tipo_movimiento_origen_id=movimiento_salida_id,
        tipo_movimiento_destino_id=movimiento_entrada_id,
        proveedor_id=datos.proveedor_id,
        usuario_fisico_id=datos.usuario_fisico_id,
        fecha_movimiento=datos.fecha_movimiento,
        user_id_erp=usuario_id_erp,
        source_brand_id=datos.source_brand_id,
        destination_brand_id=datos.destination_brand_id,
    )

    return RespuestaRelacionDocumentos(
        mensaje="Los documentos se relacionaron correctamente.",
        source_document_id=datos.source_document_id,
        destination_document_id=datos.destination_document_id,
        folio_salida=folio_salida,
        folio_entrada=folio_entrada,
    )


@router.post("/{document_id}/homologar")
def homologar_relacion_historica(
        document_id: int,
        request: Request,
        base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)

    base_datos.homologar_tipo_movimiento_documento(document_id)

    return {
        "mensaje": "El proceso de homologación se ejecutó correctamente."
    }
