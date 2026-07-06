from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.repositories.movimientos_inventario import (
    TIPOS_VALIDOS,
    calcular_indicadores,
    listar_movimientos_inventario,
)
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/movimientos-inventario",
    tags=["Movimientos de inventario"],
)


@router.get("/")
def listar_movimientos(
    tipo: str = Query(default="todos", max_length=20),
    pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=50),
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    tipo_normalizado = tipo.strip().lower()

    if tipo_normalizado not in TIPOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Tipo no valido. Usa todos, salida o entrada.",
        )

    try:
        movimientos = listar_movimientos_inventario(tipo_normalizado)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    total = len(movimientos)
    total_paginas = (total + limite - 1) // limite
    inicio = (pagina - 1) * limite
    fin = inicio + limite

    return {
        "movimientos": movimientos[inicio:fin],
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
        "tipo": tipo_normalizado,
        "indicadores": calcular_indicadores(movimientos),
    }
