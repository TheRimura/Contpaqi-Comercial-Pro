import unicodedata
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder

from app.schemas.relacion_documentos import (
    CrearRelacionDocumentos,
    CrearTransformacion,
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


@router.get('/transformacion/lineas')
def consultar_lineas_transformacion(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(base_datos.listar_lineas_transformacion())


@router.get('/transformacion/bases')
def consultar_bases_transformacion(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.listar_productos_base_transformacion(linea)
    )


@router.get('/transformacion/precargadas')
def consultar_transformaciones_precargadas(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.listar_transformaciones_precargadas(linea)
    )


@router.get('/transformacion/disponibles')
def consultar_transformaciones_disponibles(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.listar_transformaciones_disponibles()
    )


@router.get('/transformacion/catalogo/{producto_id}')
def consultar_transformacion_catalogo(
    producto_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    detalle = base_datos.obtener_transformacion_catalogo(producto_id)
    if not detalle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='El producto no tiene una transformación válida en orgProduct.',
        )
    return jsonable_encoder(detalle)


@router.get('/transformacion/precargadas/{transformacion_id}')
def consultar_detalle_transformacion_precargada(
    transformacion_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    detalle = base_datos.obtener_transformacion_precargada(transformacion_id)
    if not detalle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='La transformación precargada no existe o está inactiva.',
        )
    return jsonable_encoder(detalle)


@router.get('/transformacion/resultantes')
def consultar_resultantes_transformacion(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    producto_base: str = Query(min_length=1, max_length=250),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.listar_productos_resultantes_transformacion(
            linea,
            producto_base,
        )
    )


@router.get('/transformacion/documentos-sugeridos')
def consultar_documentos_transformacion(
    request: Request,
    producto_base_id: int = Query(gt=0),
    producto_resultante_id: int = Query(gt=0),
    cantidad_base: Optional[float] = Query(default=None, gt=0),
    cantidad_resultante: Optional[float] = Query(default=None, gt=0),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder({
        'salida': base_datos.sugerir_documento_por_producto(
            203, producto_base_id, cantidad_base
        ),
        'entrada': base_datos.sugerir_documento_por_producto(
            202, producto_resultante_id, cantidad_resultante
        ),
    })


@router.get('/transformacion/folios-siguientes')
def consultar_folios_transformacion(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder(
        base_datos.obtener_siguientes_folios_transformacion()
    )


@router.get('/historial/{relacion_id}')
def consultar_detalle_historial(
    relacion_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_historial')
    detalle = base_datos.obtener_detalle_historial_transformacion(
        relacion_id
    )
    if not detalle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='La relación seleccionada ya no está disponible en SSM.',
        )
    return jsonable_encoder(detalle)


@router.get('/transformacion/proveedores-productos')
def consultar_proveedores_productos(
    request: Request,
    producto_base_id: int = Query(gt=0),
    producto_resultante_id: int = Query(gt=0),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    return jsonable_encoder({
        'producto_base': base_datos.obtener_proveedores_producto(
            producto_base_id
        ),
        'producto_resultante': base_datos.obtener_proveedores_producto(
            producto_resultante_id
        ),
    })


@router.post(
    '/transformacion/registrar',
    response_model=RespuestaRelacionDocumentos,
    status_code=status.HTTP_201_CREATED,
)
def registrar_transformacion(
    datos: CrearTransformacion,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = seguridad_sesion.requerir_permiso(
        request, 'registrar_transformaciones'
    )
    usuario_erp = int(sesion.get('user_id') or 0)
    if usuario_erp <= 0:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='La sesión no contiene un usuario ERP válido.',
        )

    configuracion = (
        base_datos.obtener_transformacion_precargada(
            datos.transformacion_config_id
        )
        if datos.transformacion_config_id > 0
        else base_datos.obtener_transformacion_catalogo(
            datos.producto_resultante_id
        )
    )
    if not configuracion:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='La transformación precargada no es válida o está inactiva.',
        )
    porcentaje_merma = float(
        configuracion.get('porcentaje_merma')
        if configuracion.get('porcentaje_merma') is not None
        else 0
    )
    cantidad_resultante_esperada = round(
        datos.cantidad_base * (1 - porcentaje_merma / 100),
        3,
    )
    if abs(datos.cantidad_resultante - cantidad_resultante_esperada) > 0.001:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                'El peso resultante no corresponde a la merma configurada '
                f'del {porcentaje_merma:g}%.'
            ),
        )
    resultado_configurado = configuracion['resultantes'][0]
    if (
        configuracion['linea'].upper() != datos.linea.upper()
        or configuracion['producto_base_id'] != datos.producto_base_id
        or resultado_configurado['product_id'] != datos.producto_resultante_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Los productos no corresponden a la transformación elegida.',
        )

    base_receta = next(
        (
            componente for componente in configuracion['componentes']
            if componente['es_producto_base']
        ),
        None,
    )
    cantidad_base_receta = float(
        (base_receta or {}).get('cantidad') or 0
    )
    factor = (
        datos.cantidad_base / cantidad_base_receta
        if cantidad_base_receta > 0 else 1
    )
    insumos = [
        {
            'producto_id': componente['product_id'],
            'cantidad': round(float(componente['cantidad']) * factor, 6),
        }
        for componente in configuracion['componentes']
        if not componente['es_producto_base']
    ]

    movimientos_entrada = base_datos.buscar_tipo_movimiento_modulo(202)
    movimientos_salida = base_datos.buscar_tipo_movimiento_modulo(203)
    movimiento_entrada = next(
        (
            int(movimiento.get('ItemData') or 0)
            for movimiento in movimientos_entrada
            if int(movimiento.get('ItemData') or 0) == 5
        ),
        0,
    )
    movimiento_salida = next(
        (
            int(movimiento.get('ItemData') or 0)
            for movimiento in movimientos_salida
            if int(movimiento.get('ItemData') or 0) == 2
        ),
        0,
    )
    if movimiento_entrada <= 0 or movimiento_salida <= 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                'SSM no tiene una equivalencia válida entre la entrada '
                'y la salida del movimiento Transformación.'
            ),
        )

    resultado = base_datos.crear_documentos_transformacion(
        producto_base_id=datos.producto_base_id,
        producto_resultante_id=datos.producto_resultante_id,
        cantidad_base=datos.cantidad_base,
        cantidad_resultante=datos.cantidad_resultante,
        usuario_erp=usuario_erp,
        usuario_fisico_id=datos.usuario_fisico_id,
        tipo_movimiento_salida_id=movimiento_salida,
        tipo_movimiento_entrada_id=movimiento_entrada,
        insumos=insumos,
    )
    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='SSM no devolvió los documentos creados.',
        )

    return RespuestaRelacionDocumentos(
        mensaje='La transformación se registró y relacionó correctamente.',
        source_document_id=resultado['SourceDocumentID'],
        destination_document_id=resultado['DestinationDocumentID'],
        folio_salida=resultado['FolioSalida'],
        folio_entrada=resultado['FolioEntrada'],
    )


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
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            'Este movimiento está deshabilitado temporalmente. '
            'Únicamente Transformación se encuentra disponible.'
        ),
    )
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

    es_analisis = movimiento_entrada == 24 and movimiento_salida == 21
    marca_destino_id = datos.destination_brand_id
    if es_analisis and not marca_destino_id and datos.marca_nombre:
        categorias_entrada = sorted({
                    str(partida.get('Category') or '').strip()
                    for partida in base_datos.obtener_partidas_documento_erp(
                        datos.destination_document_id
                    )
                    if str(partida.get('Category') or '').strip()
                })
        marca_destino_id = base_datos.obtener_o_crear_marca_modulo(
            categoria=categorias_entrada[0] if categorias_entrada else '',
            nombre=datos.marca_nombre,
        )
    if es_analisis and (
        datos.proveedor_id <= 0
        or datos.usuario_fisico_id <= 0
        or not marca_destino_id
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                'Los movimientos de Análisis requieren proveedor, '
                'marca y tablajero.'
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
        destination_brand_id=marca_destino_id,
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
