import bcrypt

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.services.sesiones import (
    eliminar_cookie_sesion,
    guardar_cookie_sesion,
    obtener_sesion_request,
)
from app.utils.base_de_datos import obtener_base_datos


router = APIRouter(
    prefix="/login",
    tags=["Login"],
)


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


def preparar_hash(hash_guardado):
    if hash_guardado is None:
        return None

    if isinstance(hash_guardado, bytes):
        return hash_guardado

    if isinstance(hash_guardado, bytearray):
        return bytes(hash_guardado)

    if isinstance(hash_guardado, memoryview):
        return hash_guardado.tobytes()

    if isinstance(hash_guardado, str):
        return hash_guardado.strip().encode("utf-8")

    return bytes(hash_guardado)


def coincide_password(password: str, hash_guardado) -> bool:
    hash_password = preparar_hash(hash_guardado)

    if not hash_password:
        return False

    try:
        return bcrypt.checkpw(password.encode("utf-8"), hash_password)
    except (TypeError, ValueError):
        return False


def buscar_usuario(base_datos, nombre_usuario: str):
    usuarios = base_datos.fetchall(
        """
        SELECT
            U.UserID,
            U.UserName,
            U.UserGroupID,
            G.GroupName,
            CU.UserPassword AS HashUsuario
        FROM dbo.engUser AS U
        LEFT JOIN dbo.engUserGroup AS G
            ON G.UserGroupID = U.UserGroupID
        LEFT JOIN dbo.engUserCayal AS CU
            ON CU.UserID = U.UserID
        WHERE U.UserName = ?
          AND U.DeletedOn IS NULL
        """,
        (nombre_usuario.strip(),),
    )

    if not usuarios:
        return None

    return usuarios[0]


def buscar_hashes_grupo_administrativo(base_datos):
    return base_datos.fetchall(
        """
        SELECT UC.UserPassword
        FROM dbo.engUser AS U
        INNER JOIN dbo.engUserGroup AS G
            ON G.UserGroupID = U.UserGroupID
        INNER JOIN dbo.engUserCayal AS UC
            ON UC.UserID = U.UserID
        WHERE U.DeletedOn IS NULL
          AND UC.UserPassword IS NOT NULL
          AND G.UserGroupID = (
              SELECT TOP 1 G2.UserGroupID
              FROM dbo.engUserGroup AS G2
              WHERE EXISTS (
                  SELECT 1
                  FROM dbo.engUser AS U2
                  INNER JOIN dbo.engUserCayal AS UC2
                      ON UC2.UserID = U2.UserID 
                  WHERE U2.UserGroupID = G2.UserGroupID
                    AND U2.DeletedOn IS NULL
                    AND UC2.UserPassword IS NOT NULL
              )
              ORDER BY G2.VersionSync, G2.UserGroupID
          )
        ORDER BY U.UserID
        """
    )


def password_de_grupo_valido(password: str, hashes_grupo) -> bool:
    for fila in hashes_grupo:
        if coincide_password(password, fila["UserPassword"]):
            return True

    return False


def datos_sesion(usuario, uso_llave_maestra: bool):
    return {
        "user_id": usuario["UserID"],
        "usuario": usuario["UserName"],
        "user_group_id": usuario["UserGroupID"],
        "grupo": usuario["GroupName"],
        "uso_llave_maestra": uso_llave_maestra,
    }


@router.get("/sesion")
def consultar_sesion(request: Request):
    sesion = obtener_sesion_request(request)

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no valida",
        )

    sesion_publica = dict(sesion)
    sesion_publica.pop("exp", None)

    return {
        "acceso": True,
        **sesion_publica,
    }


@router.post("/")
def iniciar_sesion(
    credenciales: Credenciales,
    request: Request,
    response: Response,
):
    base_datos = obtener_base_datos()
    usuario = buscar_usuario(base_datos, credenciales.usuario)

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if usuario["HashUsuario"] is None:
        return {
            "acceso": False,
            "requiere_confirmacion": True,
            "mensaje": "Debes confirmar tu contraseña para acceder",
        }

    password_valido = coincide_password(
        credenciales.password,
        usuario["HashUsuario"],
    )
    uso_llave_maestra = False

    if not password_valido:
        password_valido = password_de_grupo_valido(
            credenciales.password,
            buscar_hashes_grupo_administrativo(base_datos),
        )
        uso_llave_maestra = password_valido

    if not password_valido:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    sesion = datos_sesion(usuario, uso_llave_maestra)
    guardar_cookie_sesion(
        response,
        sesion,
        usar_https=request.url.scheme == "https",
    )

    return {
        "acceso": True,
        "mensaje": "Acceso autorizado",
        **sesion,
    }


@router.post("/logout")
def cerrar_sesion(response: Response):
    eliminar_cookie_sesion(response)

    return {
        "acceso": False,
        "mensaje": "Sesion cerrada",
    }
