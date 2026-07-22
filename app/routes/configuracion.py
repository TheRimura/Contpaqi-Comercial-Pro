from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.encoders import jsonable_encoder

from app.schemas.configuracion import CrearConfiguracionTransformacion
from app.utils.base_de_datos import BaseDatos, obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(prefix='/api/configuracion', tags=['Configuración'])


@router.get('/proveedores-carnicos')
def proveedores_carnicos(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    seguridad_sesion.requerir_permiso(request, 'ver_configuracion')
    return jsonable_encoder(base_datos.obtener_proveedores_carnicos())


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
    return jsonable_encoder(
        base_datos.buscar_formula_producto_configuracion(producto_id)
    )


@router.post('/transformaciones', status_code=status.HTTP_201_CREATED)
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
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {
        'mensaje': 'Configuración guardada correctamente.',
        'transformacion_id': transformacion_id,
    }
