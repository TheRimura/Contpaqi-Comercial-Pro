from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.configuraciones_transformacion import (
    CrearConfiguracionTransformacion,
)
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/configuraciones-transformacion",
    tags=["Configuraciones de transformacion"],
)

USUARIOS_BITACORA_CONFIGURACIONES = set()
GRUPOS_BITACORA_CONFIGURACIONES = {
    "ADMIN",
    "ADMINS",
    "ADMINISTRADOR",
    "ADMINISTRADORES",
    "SUPER_ADMIN",
    "SUPER_ADMINISTRADOR",
    "SUPER_ADMINISTRADORES",
    "SUPERADMIN",
    "SUPERADMINS",
}
PERMISOS_BITACORA_CONFIGURACIONES = {
    "ADMIN",
    "ADMINISTRADOR",
    "SUPER_ADMIN",
    "SUPERADMIN",
    "CONFIGURACION_CARNICOS",
    "MODULO_CARNICO_CONFIGURACION",
}


def numero(valor):
    if isinstance(valor, Decimal):
        return float(valor)

    return valor


def producto(id_producto, clave, nombre, categoria, unidad):
    if not id_producto:
        return None

    return {
        "id": id_producto,
        "clave": clave,
        "nombre": nombre,
        "categoria": categoria,
        "unidad": unidad,
    }


def formatear_fecha(fecha):
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%Y-%m-%d %H:%M:%S")

    return str(fecha or "")


def normalizar_permiso(valor):
    texto = str(valor or "").strip().upper()
    reemplazos = {
        "Á": "A",
        "É": "E",
        "Í": "I",
        "Ó": "O",
        "Ú": "U",
        "Ñ": "N",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    return texto.replace("-", "_").replace(" ", "_")


def puede_ver_bitacora_configuracion(sesion, base_datos):
    usuario = normalizar_permiso(sesion.get("usuario"))
    grupo = normalizar_permiso(
        base_datos.buscar_nombre_grupo_usuario(
            sesion.get("user_group_id")
        )
    )
    permisos = {
        normalizar_permiso(permiso)
        for permiso in sesion.get("permisos", [])
    }

    return (
        usuario in USUARIOS_BITACORA_CONFIGURACIONES
        or grupo in GRUPOS_BITACORA_CONFIGURACIONES
        or bool(permisos & PERMISOS_BITACORA_CONFIGURACIONES)
    )


def agrupar_detalles(filas):
    detalles = {}

    for fila in filas:
        detalles.setdefault(
            fila["id_transformacion_usuario"],
            [],
        ).append({
            "id": fila["id_detalle_usuario"],
            "producto": producto(
                fila["producto_resultante"],
                fila["ProductKey"],
                fila["ProductName"],
                fila["Category1"],
                fila["Unit"],
            ),
            "cantidad": numero(fila["cantidad_resultante"]),
            "unidad": fila["unidad"],
            "participa_balance": bool(fila["participa_balance"]),
            "orden": fila["orden"],
            "activa": bool(fila["activa"]),
        })

    return detalles


def agrupar_componentes(filas):
    componentes = {}

    for fila in filas:
        componentes.setdefault(
            fila["id_transformacion_usuario"],
            [],
        ).append({
            "id": fila["id_componente_usuario"],
            "producto": producto(
                fila["producto_componente"],
                fila["ProductKey"],
                fila["ProductName"],
                fila["Category1"],
                fila["Unit"],
            ),
            "cantidad": numero(fila["cantidad"]),
            "unidad": fila["unidad"],
            "es_producto_base": bool(fila["es_producto_base"]),
            "tipo_componente": fila["tipo_componente"],
            "participa_balance": bool(fila["participa_balance"]),
            "orden": fila["orden"],
            "activa": bool(fila["activa"]),
        })

    return componentes


def formatear_configuracion(fila, detalles, componentes):
    return {
        "id": fila["id_transformacion_usuario"],
        "nombre": fila["nombre_transformacion"],
        "proveedor": {
            "id": fila["proveedor_id"],
            "nombre": fila["proveedor_nombre"],
        },
        "producto_origen": producto(
            fila["producto_origen"],
            fila["origen_clave"],
            fila["origen_nombre"],
            fila["origen_categoria"],
            fila["origen_unidad"],
        ),
        "producto_formula": producto(
            fila["producto_formula"],
            fila["formula_clave"],
            fila["formula_nombre"],
            fila["formula_categoria"],
            fila["formula_unidad"],
        ),
        "cantidad_base": numero(fila["cantidad_base"]),
        "porcentaje_merma": numero(fila["porcentaje_merma"]),
        "usuario_creacion": {
            "id": fila["usuario_creacion"],
            "nombre": fila["usuario_creacion_nombre"],
        },
        "fecha_creacion": formatear_fecha(fila["fecha_creacion"]),
        "usuario_actualizacion": {
            "id": fila["usuario_actualizacion"],
            "nombre": fila["usuario_actualizacion_nombre"],
        } if fila["usuario_actualizacion"] else None,
        "fecha_actualizacion": formatear_fecha(
            fila["fecha_actualizacion"]
        ),
        "activa": bool(fila["activa"]),
        "productos_resultantes": detalles.get(
            fila["id_transformacion_usuario"],
            [],
        ),
        "componentes": componentes.get(
            fila["id_transformacion_usuario"],
            [],
        ),
    }


def validar_productos(base_datos, datos):
    ids = {
        datos.producto_origen_id,
        *[
            detalle.producto_id
            for detalle in datos.productos_resultantes
        ],
        *[
            componente.producto_id
            for componente in datos.componentes
        ],
    }

    if datos.producto_formula_id:
        ids.add(datos.producto_formula_id)

    existentes = base_datos.buscar_ids_productos_existentes(ids)
    faltantes = ids - existentes

    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Hay productos inexistentes o eliminados: "
                + ", ".join(str(id_producto) for id_producto in faltantes)
            ),
        )


@router.get("/")
def listar_configuraciones(
        pagina: int = Query(default=1, ge=1),
    limite: int = Query(default=10, ge=1, le=50),
):
    base_datos = obtener_base_datos()
    encabezados = base_datos.buscar_configuraciones_usuario(
        pagina,
        limite,
    )
    detalles = agrupar_detalles(
        base_datos.buscar_detalles_configuraciones_usuario([
            fila["id_transformacion_usuario"]
            for fila in encabezados
        ])
    )
    componentes = agrupar_componentes(
        base_datos.buscar_componentes_configuraciones_usuario([
            fila["id_transformacion_usuario"]
            for fila in encabezados
        ])
    )
    total = base_datos.contar_configuraciones_usuario()
    total_paginas = (total + limite - 1) // limite

    return {
        "configuraciones": [
            formatear_configuracion(fila, detalles, componentes)
            for fila in encabezados
        ],
        "pagina": pagina,
        "limite": limite,
        "total": total,
        "total_paginas": total_paginas,
    }


@router.get("/bitacora")
def listar_bitacora_configuraciones(
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
    limite: int = Query(default=50, ge=1, le=200),
):
    base_datos = obtener_base_datos()

    if not puede_ver_bitacora_configuracion(sesion, base_datos):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para consultar esta bitacora.",
        )

    return {
        "registros": [
            {
                "id": fila["id_bitacora"],
                "configuracion_id": fila["id_transformacion_usuario"],
                "configuracion": fila["nombre_transformacion"],
                "accion": fila["accion"],
                "usuario_id": fila["usuario_id"],
                "usuario_confirmacion_nombre": (
                    fila["usuario_confirmacion_nombre"]
                ),
                "detalle": fila["detalle"],
                "fecha": formatear_fecha(fila["fecha"]),
            }
            for fila in base_datos.buscar_bitacora_configuraciones(
                limite
            )
        ]
    }


@router.post("/")
def crear_configuracion(
    datos: CrearConfiguracionTransformacion,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    validar_productos(base_datos, datos)
    configuracion_id = base_datos.registrar_configuracion_usuario(
        datos,
        sesion["user_id"],
    )

    return {
        "mensaje": "Configuracion guardada",
        "id": configuracion_id,
    }


@router.put("/{configuracion_id}")
def actualizar_configuracion(
    configuracion_id: int,
    datos: CrearConfiguracionTransformacion,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    if not (datos.usuario_confirmacion_nombre or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Confirma el cambio con el nombre del usuario.",
        )

    validar_productos(base_datos, datos)
    actualizada = base_datos.actualizar_configuracion_usuario(
        configuracion_id,
        datos,
        sesion["user_id"],
    )

    if not actualizada:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuracion no encontrada",
        )

    return {
        "mensaje": "Configuracion actualizada",
        "id": configuracion_id,
    }


@router.get("/formula/{producto_id}/ingredientes")
def consultar_ingredientes_formula(
    producto_id: int,
):
    filas = obtener_base_datos().buscar_ingredientes_formula(producto_id)

    return {
        "producto_formula_id": producto_id,
        "ingredientes": [
            {
                "id": fila["ComponenteID"],
                "clave": fila["ProductKey"],
                "nombre": fila["Componente"],
                "categoria": fila["Category1"],
                "unidad": fila["Unit"],
                "cantidad": numero(fila["CantidadComp"]),

            }
            for fila in filas
        ],
    }
