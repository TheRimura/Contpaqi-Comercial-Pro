from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.repositories.transformaciones import (
    ErrorTransformacion,
    guardar_transformacion,
    listar_transformaciones as consultar_transformaciones,
)
from app.schemas.transformaciones import CrearTransformacion
from app.repositories.movimientos_erp import ErrorIntegracionERP
from app.utils.seguridad import seguridad_sesion


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


def calcular_indicadores(registros):
    fecha_actual = datetime.now()
    registros_mes = []

    for registro in registros:
        try:
            fecha = datetime.fromisoformat(registro["fecha"])
        except (TypeError, ValueError):
            continue

        if (
            fecha.year == fecha_actual.year
            and fecha.month == fecha_actual.month
        ):
            registros_mes.append(registro)

    kilos_procesados = sum(
        registro["cantidad_origen"]
        for registro in registros_mes
    )
    kilos_obtenidos = sum(
        registro["total_entrada"]
        for registro in registros_mes
    )
    merma_acumulada = sum(
        registro["peso_merma"]
        for registro in registros_mes
    )
    rendimiento = (
        kilos_obtenidos / kilos_procesados * 100
        if kilos_procesados
        else 0
    )

    return {
        "transformaciones": len(registros_mes),
        "kilos_procesados": kilos_procesados,
        "merma_acumulada": merma_acumulada,
        "rendimiento": rendimiento,
    }


@router.get("/")
def listar_transformaciones(
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=50),
):
    registros = consultar_transformaciones()
    total = len(registros)
    total_paginas = (total + limite - 1) // limite
    inicio = (pagina - 1) * limite
    fin = inicio + limite

    return {
        "registros": registros[inicio:fin],
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
        "indicadores": calcular_indicadores(registros),
    }


@router.post("/")
def crear_transformacion(
    datos: CrearTransformacion,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
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
    except ErrorIntegracionERP as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(error),
        ) from error

    return {
        "mensaje": (
            "Transformacion registrada y enviada para afectar inventario"
        ),
        "folio": registro["folio"],
        "rendimiento": rendimiento,
        "registro": registro,
        "transformacion": datos,
    }



