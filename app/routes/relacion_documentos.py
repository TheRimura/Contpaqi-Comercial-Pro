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
    prefix='/api/relaciones-documentos',
    tags=['Relación de documentos ERP'],
)


def exigir_sesion(request: Request) -> dict:
    return seguridad_sesion.requerir_sesion(request)


def normalizar_texto(valor) -> str:
    texto = str(valor or '').strip().upper()
    texto = unicodedata.normalize('NFKD', texto)
    return ' '.join(
        ''.join(
            caracter
            for caracter in texto
            if not unicodedata.combining(caracter)
        ).split()
    )


def resolver_movimientos(
    texto_movimiento: str,
    entradas: list[dict],
    salidas: list[dict],
) -> tuple[int, int]:
    buscado = normalizar_texto(texto_movimiento)
    entrada_id = next(
        (
            int(registro.get('ItemData') or 0)
            for registro in entradas
            if normalizar_texto(registro.get('ItemValue')) == buscado
        ),
        0,
    )
    salida_id = next(
        (
            int(registro.get('ItemData') or 0)
            for registro in salidas
            if normalizar_texto(registro.get('ItemValue')) == buscado
        ),
        0,
    )
    return entrada_id, salida_id


def construir_catalogo_movimientos(base_datos: BaseDatos) -> list[dict]:
    entradas = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_ENTRADA
    )
    salidas = base_datos.buscar_tipo_movimiento_modulo(
        base_datos.MODULO_SALIDA
    )
    salidas_por_texto = {
        normalizar_texto(registro.get('ItemValue')): registro
        for registro in salidas
    }
    resultado = []

    for entrada in entradas:
        texto = entrada.get('ItemValue') or ''
        salida = salidas_por_texto.get(normalizar_texto(texto))
        entrada_id = int(entrada.get('ItemData') or 0)
        salida_id = int((salida or {}).get('ItemData') or 0)

        if entrada_id > 0 and salida_id > 0:
            resultado.append({
                'ItemValue': texto,
                'EntradaID': entrada_id,
                'SalidaID': salida_id,
            })

    return resultado


@router.get('/catalogos')
def consultar_catalogos(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder({
        'movimientos': construir_catalogo_movimientos(base_datos),
        'proveedores': base_datos.obtener_proveedores_documentos(),
        'usuarios_fisicos': base_datos.obtener_usuarios_fisicos(),
    })


@router.get('/documentos-disponibles/{module_id}')
def consultar_documentos_disponibles(
    module_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    if module_id not in (
        base_datos.MODULO_ENTRADA,
        base_datos.MODULO_SALIDA,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='El módulo debe ser 202 o 203.',
        )
    return jsonable_encoder(
        base_datos.buscar_documentos_disponibles(module_id)
    )


@router.get('/documentos/{document_id}')
def consultar_documento(
    document_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    documento = base_datos.obtener_relacion_documento(document_id)
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='No se encontró el documento.',
        )
    return jsonable_encoder(documento)


@router.get('/documentos/{document_id}/partidas')
def consultar_partidas(
    document_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.obtener_partidas_documento_erp(document_id)
    )


@router.get('/buscar-por-folio')
def buscar_por_folio(
    request: Request,
    folio: str = Query(min_length=1, max_length=125),
    module_id: Optional[int] = Query(default=None),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return {
        'DocumentID': base_datos.buscar_document_id_por_folio(
            folio,
            module_id,
        )
    }


@router.get('/marcas')
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
    '',
    response_model=RespuestaRelacionDocumentos,
    status_code=status.HTTP_201_CREATED,
)
def crear_relacion(
    datos: CrearRelacionDocumentos,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = exigir_sesion(request)
    usuario_erp = int(sesion.get('user_id') or 0)
    if usuario_erp <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='La sesión no contiene un usuario ERP válido.',
        )

    salida = base_datos.obtener_relacion_documento(
        datos.source_document_id
    )
    entrada = base_datos.obtener_relacion_documento(
        datos.destination_document_id
    )

    if not salida or int(salida.get('ModuleID') or 0) != 203:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='El documento origen debe ser una salida 203.',
        )
    if not entrada or int(entrada.get('ModuleID') or 0) != 202:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='El documento destino debe ser una entrada 202.',
        )

    if base_datos.documento_previamente_relacionado(
        datos.source_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='El documento de salida ya fue relacionado.',
        )
    if base_datos.documento_previamente_relacionado(
        datos.destination_document_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='El documento de entrada ya fue relacionado.',
        )

    movimientos_entrada = base_datos.buscar_tipo_movimiento_modulo(202)
    movimientos_salida = base_datos.buscar_tipo_movimiento_modulo(203)
    movimiento_entrada, movimiento_salida = resolver_movimientos(
        datos.tipo_movimiento,
        movimientos_entrada,
        movimientos_salida,
    )

    if movimiento_entrada <= 0 or movimiento_salida <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                'El movimiento no tiene equivalencia válida entre '
                'entrada y salida.'
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
            detail='No se pudo obtener el folio de los documentos.',
        )

    base_datos.relacionar_documentos_erp(
        source_document_id=datos.source_document_id,
        destination_document_id=datos.destination_document_id,
        folio_source_document_id=folio_salida,
        folio_destination_document_id=folio_entrada,
        tipo_movimiento_origen_id=movimiento_salida,
        tipo_movimiento_destino_id=movimiento_entrada,
        proveedor_id=datos.proveedor_id,
        usuario_fisico_id=datos.usuario_fisico_id,
        fecha_movimiento=datos.fecha_movimiento,
        user_id_erp=usuario_erp,
        source_brand_id=datos.source_brand_id,
        destination_brand_id=datos.destination_brand_id,
    )

    return RespuestaRelacionDocumentos(
        mensaje='Los documentos se relacionaron correctamente.',
        source_document_id=datos.source_document_id,
        destination_document_id=datos.destination_document_id,
        folio_salida=folio_salida,
        folio_entrada=folio_entrada,
    )


@router.post('/{document_id}/homologar')
def homologar(
    document_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    base_datos.homologar_tipo_movimiento_documento(document_id)
    return {'mensaje': 'Homologación ejecutada correctamente.'}
