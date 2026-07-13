from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder

from app.schemas.modulo_carnico import (
    GuardarProductosCarnicos,
    RegistrarSalidaCarnica,
    RegistrarTransformacionCarnica,
)
from app.repositories.modulo_carnico_repository import ModuloCarnicoRepository
from app.utils.base_de_datos import BaseDatos, obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/api/carnico",
    tags=["Modulo carnico"],
)


def exigir_sesion(request: Request) -> dict:
    return seguridad_sesion.requerir_sesion(request)


def obtener_repositorio(
    base_datos: BaseDatos = Depends(obtener_base_datos),
) -> ModuloCarnicoRepository:
    return ModuloCarnicoRepository(base_datos)


def numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def serializar_producto(fila: dict) -> dict:
    return {
        "id_configuracion": fila["id_producto_carnico"],
        "product_id": fila["product_id"],
        "clave": fila["clave"] or "",
        "proveedor_id": fila["proveedor_id"],
        "proveedor_nombre": fila["proveedor_nombre"] or "",
        "nombre_producto": fila["nombre_producto"],
        "categoria": fila["categoria"] or "",
        "categoria_resultante": fila["categoria_resultante"] or "",
        "unidad": fila["unidad"] or "KILO",
        "porcentaje_merma": numero(fila["porcentaje_merma"] or 0),
        "activo": bool(fila["activo"]),
        "fecha_creacion": str(fila["fecha_creacion"] or ""),
        "fecha_actualizacion": str(fila["fecha_actualizacion"] or ""),
    }


@router.get("/resumen")
def obtener_resumen(
    request: Request,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    exigir_sesion(request)
    return jsonable_encoder({
        "resumen": repositorio.resumen_mensual(),
        "registros": repositorio.listar_historial(limite=12),
    })


@router.get("/permisos")
def consultar_permisos(
    request: Request,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    sesion = exigir_sesion(request)
    return {
        "puede_configurar": repositorio.usuario_puede_configurar(sesion)
    }


@router.get("/productos-erp")
def buscar_productos_erp(
    request: Request,
    q: str = "",
    limite: int = 15,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    exigir_sesion(request)
    return jsonable_encoder({
        "productos": repositorio.buscar_productos_erp(q, limite)
    })


@router.get("/productos")
def listar_productos(
    request: Request,
    incluir_inactivos: bool = True,
    base_datos: BaseDatos = Depends(obtener_base_datos),
):
    exigir_sesion(request)
    base_datos.asegurar_tablas_modulo_carnico()
    return jsonable_encoder({
        "productos": [
            serializar_producto(fila)
            for fila in base_datos.buscar_productos_carnicos_configurados(
                incluir_inactivos=incluir_inactivos
            )
        ]
    })


@router.put("/productos")
def guardar_productos(
    datos: GuardarProductosCarnicos,
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    sesion = exigir_sesion(request)
    if not repositorio.usuario_puede_configurar(sesion):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar configuracion.",
        )
    base_datos.asegurar_tablas_modulo_carnico()
    base_datos.guardar_productos_carnicos_configurados(
        productos=[producto.model_dump(mode="json") for producto in datos.productos],
        usuario_id=sesion.get("user_id"),
        usuario_confirmacion_nombre=datos.usuario_confirmacion_nombre,
    )
    return listar_productos(
        request=request,
        incluir_inactivos=True,
        base_datos=base_datos,
    )


@router.get("/bitacora")
def listar_bitacora(
    request: Request,
    base_datos: BaseDatos = Depends(obtener_base_datos),
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    sesion = exigir_sesion(request)
    if not repositorio.usuario_puede_configurar(sesion):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para consultar la bitacora.",
        )
    base_datos.asegurar_tablas_modulo_carnico()
    return jsonable_encoder({
        "registros": base_datos.buscar_bitacora_productos_carnicos()
    })


@router.post("/transformaciones", status_code=status.HTTP_201_CREATED)
def registrar_transformacion(
    datos: RegistrarTransformacionCarnica,
    request: Request,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    sesion = exigir_sesion(request)
    try:
        registro_id = repositorio.registrar_transformacion(
            datos=datos,
            sesion=sesion,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return jsonable_encoder({
        "mensaje": "Transformacion carnica registrada.",
        "id_registro": registro_id,
        "resumen": repositorio.resumen_mensual(),
        "registros": repositorio.listar_historial(limite=12),
    })


@router.post("/salidas", status_code=status.HTTP_201_CREATED)
def registrar_salida(
    datos: RegistrarSalidaCarnica,
    request: Request,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    sesion = exigir_sesion(request)
    try:
        registro_id = repositorio.registrar_salida(
            datos=datos,
            sesion=sesion,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from error

    return jsonable_encoder({
        "mensaje": "Salida carnica registrada.",
        "id_registro": registro_id,
        "resumen": repositorio.resumen_mensual(),
        "registros": repositorio.listar_historial(limite=12),
    })


@router.get("/transformaciones")
def listar_transformaciones(
    request: Request,
    repositorio: ModuloCarnicoRepository = Depends(obtener_repositorio),
):
    exigir_sesion(request)
    return jsonable_encoder({
        "resumen": repositorio.resumen_mensual(),
        "registros": repositorio.listar_historial(limite=50),
    })
