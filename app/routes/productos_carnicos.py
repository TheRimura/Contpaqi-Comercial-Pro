from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.productos_carnicos import GuardarProductosCarnicos
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/configuracion-carnicos",
    tags=["Configuracion productos carnicos"],
)

TABLAS_PRODUCTOS_CARNICOS = [
    "dbo.ModuloCarnicoProductoConfigurado",
    "dbo.ModuloCarnicoProductoBitacora",
]

USUARIOS_CONFIGURACION_CARNICOS = {"ABRAHAM"}
GRUPOS_CONFIGURACION_CARNICOS = {
    "ADMIN",
    "ADMINS",
    "ADMINISTRADOR",
    "ADMINISTRADORES",
    "SUPER_ADMIN",
    "SUPER_ADMINISTRADOR",
    "SUPERADMIN",
}
PERMISOS_CONFIGURACION_CARNICOS = {
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


def formatear_fecha(fecha):
    if hasattr(fecha, "strftime"):
        return fecha.strftime("%Y-%m-%d %H:%M:%S")

    return str(fecha or "")


def normalizar_permiso(valor):
    texto = str(valor or "").strip().upper()
    reemplazos = {
        "Ã": "A",
        "Ã‰": "E",
        "Ã": "I",
        "Ã“": "O",
        "Ãš": "U",
        "Ã‘": "N",
    }

    for origen, destino in reemplazos.items():
        texto = texto.replace(origen, destino)

    return texto.replace("-", "_").replace(" ", "_")


def puede_configurar_carnicos(sesion, base_datos):
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
        usuario in USUARIOS_CONFIGURACION_CARNICOS
        or grupo in GRUPOS_CONFIGURACION_CARNICOS
        or bool(permisos & PERMISOS_CONFIGURACION_CARNICOS)
    )


def validar_permiso_configuracion(sesion, base_datos):
    if not puede_configurar_carnicos(sesion, base_datos):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para configurar productos carnicos.",
        )


def producto_configurado_json(fila):
    activo = bool(fila["activo"])
    product_id = fila["product_id"]
    id_configuracion = fila["id_producto_carnico"]
    identificador = (
        str(product_id)
        if product_id
        else f"cfg-{id_configuracion}"
    )

    return {
        "id_configuracion": id_configuracion,
        "id": identificador,
        "product_id": product_id,
        "clave": fila["clave"] or f"CFG-{id_configuracion}",
        "proveedor_id": fila["proveedor_id"],
        "proveedor": fila["proveedor_nombre"] or "",
        "nombre": fila["nombre_producto"],
        "categoria": fila["categoria"] or "",
        "categoria_resultante": fila["categoria_resultante"] or "",
        "unidad": fila["unidad"] or "KILO",
        "porcentaje_merma": numero(fila["porcentaje_merma"] or 0),
        "activo": activo,
        "oculto": not activo,
        "fecha_creacion": formatear_fecha(fila["fecha_creacion"]),
        "fecha_actualizacion": formatear_fecha(
            fila["fecha_actualizacion"]
        ),
    }


@router.get("/productos")
def listar_productos_carnicos(
    incluir_inactivos: bool = Query(default=True),
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    puede_ver_inactivos = puede_configurar_carnicos(sesion, base_datos)

    filas = base_datos.buscar_productos_carnicos_configurados(
        incluir_inactivos=incluir_inactivos and puede_ver_inactivos,
    )

    return {
        "productos": [
            producto_configurado_json(fila)
            for fila in filas
        ],
        "tablas": TABLAS_PRODUCTOS_CARNICOS,
    }


@router.put("/productos")
def guardar_productos_carnicos(
    datos: GuardarProductosCarnicos,
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
):
    base_datos = obtener_base_datos()
    validar_permiso_configuracion(sesion, base_datos)

    if not datos.usuario_confirmacion_nombre.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Confirma el cambio con el nombre del usuario.",
        )

    productos = [
        producto.model_dump(mode="json")
        for producto in datos.productos
    ]
    base_datos.guardar_productos_carnicos_configurados(
        productos,
        sesion.get("user_id"),
        datos.usuario_confirmacion_nombre.strip(),
    )

    filas = base_datos.buscar_productos_carnicos_configurados(
        incluir_inactivos=True,
    )

    return {
        "mensaje": "Configuracion de productos carnicos guardada",
        "productos": [
            producto_configurado_json(fila)
            for fila in filas
        ],
        "tablas": TABLAS_PRODUCTOS_CARNICOS,
    }


@router.get("/bitacora")
def listar_bitacora_productos_carnicos(
    sesion: dict = Depends(seguridad_sesion.requerir_sesion),
    limite: int = Query(default=50, ge=1, le=200),
):
    base_datos = obtener_base_datos()
    validar_permiso_configuracion(sesion, base_datos)

    return {
        "registros": [
            {
                "id": fila["id_bitacora"],
                "accion": fila["accion"],
                "usuario_id": fila["usuario_id"],
                "usuario_sesion": fila["usuario_sesion"],
                "usuario_confirmacion_nombre": (
                    fila["usuario_confirmacion_nombre"]
                ),
                "detalle": fila["detalle"],
                "fecha": formatear_fecha(fila["fecha"]),
            }
            for fila in base_datos.buscar_bitacora_productos_carnicos(
                limite
            )
        ],
        "tablas": TABLAS_PRODUCTOS_CARNICOS,
    }
