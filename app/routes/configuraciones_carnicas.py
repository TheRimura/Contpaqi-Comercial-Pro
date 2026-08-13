from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder

from app.schemas.configuracion import (
    ConfiguracionCreada,
    ConfiguracionesCreadas,
    CrearConfiguracionTransformacion,
    EventoAuditoriaConfiguracion,
    OcultarProductoCatalogo,
    MensajeConfiguracion,
)
from app.utils.base_de_datos import BaseDatos, obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(prefix='/api/configuracion', tags=['Configuración'])


@router.post('/catalogo/ocultar', response_model=MensajeConfiguracion)
def ocultar_producto_catalogo(
    datos: OcultarProductoCatalogo,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = seguridad_sesion.requerir_permiso(
        request, 'eliminar_productos_catalogo'
    )
    try:
        base_datos.ocultar_producto_catalogo(
            producto_id=datos.producto_id,
            es_configuracion=datos.es_configuracion,
            transformacion_id=datos.transformacion_id,
            nombre=datos.nombre,
            linea=datos.linea,
            usuario_id=int(sesion['user_id']),
            usuario_nombre=str(sesion.get('usuario') or 'Usuario'),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {'mensaje': 'Producto ocultado correctamente.'}


@router.get('/auditoria')
def consultar_auditoria(
    request: Request,
    limite: int = Query(default=100, ge=1, le=500),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_auditoria')
    return jsonable_encoder(
        base_datos.listar_auditoria_configuraciones(limite)
    )


@router.post('/auditoria/eventos', status_code=status.HTTP_201_CREATED)
def registrar_evento_auditoria(
    datos: EventoAuditoriaConfiguracion,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = seguridad_sesion.requerir_permiso(
        request, 'eliminar_productos_catalogo'
    )
    auditoria_id = base_datos.registrar_auditoria_configuracion(
        configuracion_id=datos.configuracion_id,
        configuracion_nombre=datos.configuracion_nombre,
        accion=datos.accion,
        usuario_id=int(sesion['user_id']),
        usuario_nombre=str(sesion.get('usuario') or 'Usuario'),
        motivo=datos.motivo,
        valores_anteriores=datos.valores_anteriores,
        valores_nuevos=datos.valores_nuevos,
    )
    return {'auditoria_id': auditoria_id}


@router.get('/productos-base')
def productos_base(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    termino: str = Query(default='', max_length=100),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    return jsonable_encoder(
        base_datos.buscar_productos_base_configuracion(linea, termino)
    )

@router.get('/productos-resultantes')
def productos_resultantes(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    termino: str = Query(default='', max_length=100),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    return jsonable_encoder(
        base_datos.buscar_productos_resultantes_configuracion(linea, termino)
    )

@router.get('/base-sugerida')
def base_sugerida(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    nombre: str = Query(min_length=3, max_length=150),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    return jsonable_encoder(
        base_datos.buscar_base_sugerida_configuracion(linea, nombre)
    )


@router.get('/componentes')
def componentes_configuracion(
    request: Request,
    linea: str = Query(min_length=1, max_length=100),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    return jsonable_encoder(
        base_datos.buscar_componentes_configuracion(linea)
    )


@router.get('/formula/{producto_id}')
def formula_producto(
    producto_id: int,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    formulas = base_datos.buscar_formulas_relacionadas_configuracion(
        producto_id
    )
    componentes = [
        {
            **componente,
            'formula_id': formula['formula_id'],
            'formula': formula['formula'],
        }
        for formula in formulas
        for componente in formula['componentes']
    ]
    return jsonable_encoder(componentes)


@router.post(
    '/transformaciones',
    response_model=ConfiguracionCreada,
    status_code=status.HTTP_201_CREATED,
)
def crear_transformacion(
    datos: CrearConfiguracionTransformacion,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = seguridad_sesion.requerir_permiso(
        request, 'crear_configuracion'
    )
    try:
        transformacion_id = base_datos.crear_configuracion_transformacion(
            datos=datos,
            usuario_id=int(sesion['user_id']),
            usuario_nombre=str(sesion.get('usuario') or 'Usuario'),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        'mensaje': 'Configuración guardada correctamente.',
        'transformacion_id': transformacion_id,
    }


@router.post(
    '/transformaciones/lote',
    response_model=ConfiguracionesCreadas,
    status_code=status.HTTP_201_CREATED,
)
def crear_transformaciones_lote(
    request: Request,
    datos: list[CrearConfiguracionTransformacion] = Body(
        min_length=1,
        max_length=20,
    ),
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    sesion = seguridad_sesion.requerir_permiso(
        request, 'crear_configuracion'
    )
    nombres = {
        (registro.linea.strip().upper(), registro.nombre.strip().upper())
        for registro in datos
    }
    if len(nombres) != len(datos):
        raise HTTPException(
            status_code=400,
            detail='La lista contiene una transformación repetida.',
        )

    transformaciones_ids = []
    for indice, registro in enumerate(datos, start=1):
        try:
            transformaciones_ids.append(
                base_datos.crear_configuracion_transformacion(
                    datos=registro,
                    usuario_id=int(sesion['user_id']),
                    usuario_nombre=str(sesion.get('usuario') or 'Usuario'),
                )
            )
        except ValueError as error:
            base_datos.eliminar_configuraciones_incompletas(
                transformaciones_ids
            )
            raise HTTPException(
                status_code=400,
                detail=(
                    f'No se pudo guardar la transformación {indice} '
                    f'({registro.nombre}): {error}'
                ),
            ) from error
        except Exception:
            base_datos.eliminar_configuraciones_incompletas(
                transformaciones_ids
            )
            raise
    return {
        'mensaje': f'{len(transformaciones_ids)} configuraciones guardadas.',
        'transformaciones_ids': transformaciones_ids,
    }
