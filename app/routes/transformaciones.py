from fastapi import APIRouter, Depends, HTTPException, status

from app.repositories.transformaciones import (
    ErrorTransformacion,
    guardar_transformacion,
    listar_transformaciones as consultar_transformaciones,
)
from app.schemas.transformaciones import CrearTransformacion
from app.services.sesiones import requerir_sesion


router = APIRouter(
    prefix="/transformaciones",
    tags=["Transformaciones"],
)


def calcular_rendimiento(datos: CrearTransformacion):
    porcentaje_merma_real = datos.peso_merma / datos.cantidad_origen * 100
    diferencia_merma = None

    if datos.porcentaje_merma_esperado is not None:
        diferencia_merma = (
            porcentaje_merma_real - datos.porcentaje_merma_esperado
        )

    return {
        "peso_merma": datos.peso_merma,
        "porcentaje_merma_real": porcentaje_merma_real,
        "porcentaje_merma_esperado": datos.porcentaje_merma_esperado,
        "diferencia_merma": diferencia_merma,
    }


@router.get("/")
def listar_transformaciones(sesion: dict = Depends(requerir_sesion)):
    return {
        "registros": consultar_transformaciones(),
    }


@router.post("/")
def crear_transformacion(
    datos: CrearTransformacion,
    sesion: dict = Depends(requerir_sesion),
):
    datos = datos.model_copy(update={
        "usuario_id": sesion.get("user_id"),
        "usuario_nombre": sesion.get("usuario"),
    })
    rendimiento = calcular_rendimiento(datos)
    try:
        registro = guardar_transformacion(
            datos,
            rendimiento,
        )
    except ErrorTransformacion as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return {
        "mensaje": "Transformacion registrada",
        "folio": registro["folio"],
        "rendimiento": rendimiento,
        "registro": registro,
        "transformacion": datos,
    }
