import bcrypt

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.utils.base_de_datos import obtener_base_datos


router = APIRouter(
    prefix="/login",
    tags=["Login"],
)

# El paquete Cayal identifica a MINERC con este UserID.
LLAVE_MAESTRA_CAYAL = 64


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


def coincide_password(password: str, hash_guardado) -> bool:
    if not hash_guardado:
        return False

    try:
        hash_bytes = bytes(hash_guardado)
        return bcrypt.checkpw(password.encode("utf-8"), hash_bytes)
    except (TypeError, ValueError):
        return False


@router.post("/")
def iniciar_sesion(credenciales: Credenciales):
    base_datos = obtener_base_datos()

    resultados = base_datos.fetchall(
        """
        SELECT
            U.UserID,
            U.UserName,
            U.UserGroupID,
            G.GroupName,
            CU.UserPassword AS HashUsuario,
            CM.UserPassword AS HashMaestro
        FROM dbo.engUser AS U
        LEFT JOIN dbo.engUserGroup AS G
            ON G.UserGroupID = U.UserGroupID
        LEFT JOIN dbo.engUserCayal AS CU
            ON CU.UserID = U.UserID
        LEFT JOIN dbo.engUserCayal AS CM
            ON CM.UserID = ?
        WHERE U.UserName = ?
          AND U.DeletedOn IS NULL
        """,
        (
            LLAVE_MAESTRA_CAYAL,
            credenciales.usuario.strip(),
        ),
    )

    if not resultados:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    usuario = resultados[0]

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
        password_valido = coincide_password(
            credenciales.password,
            usuario["HashMaestro"],
        )
        uso_llave_maestra = password_valido

    if not password_valido:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    return {
        "acceso": True,
        "mensaje": "Acceso autorizado",
        "user_id": usuario["UserID"],
        "usuario": usuario["UserName"],
        "user_group_id": usuario["UserGroupID"],
        "grupo": usuario["GroupName"],
        "uso_llave_maestra": uso_llave_maestra,
    }
