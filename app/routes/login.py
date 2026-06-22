import bcrypt

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/login",
    tags=["Login"],
)


class Credenciales(BaseModel):
    usuario: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


class Autenticador:
    def __init__(self, base_datos):
        self._base_datos = base_datos

    @staticmethod
    def _preparar_hash(hash_guardado):
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

    @classmethod
    def _coincide_password(cls, password, hash_guardado):
        hash_password = cls._preparar_hash(hash_guardado)

        if not hash_password:
            return False

        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                hash_password,
            )
        except (TypeError, ValueError):
            return False

    def _password_maestro_valido(self, password):
        return any(
            self._coincide_password(password, fila["UserPassword"])
            for fila in self._base_datos.buscar_hashes_grupo_maestro()
        )

    def autenticar(self, credenciales):
        usuarios = self._base_datos.buscar_info_usuario_user_name(
            credenciales.usuario.strip()
        )

        if not usuarios:
            return None

        usuario = usuarios[0]
        hash_usuario = self._base_datos.buscar_hash_usuario(
            usuario["UserID"]
        )
        uso_llave_maestra = not self._coincide_password(
            credenciales.password,
            hash_usuario,
        )

        if (
            uso_llave_maestra
            and not self._password_maestro_valido(
                credenciales.password
            )
        ):
            return None

        return {
            "user_id": usuario["UserID"],
            "usuario": usuario["UserName"],
            "user_group_id": usuario["UserGroupID"],
            "uso_llave_maestra": uso_llave_maestra,
        }


autenticador = Autenticador(obtener_base_datos())


@router.get("/sesion")
def consultar_sesion(request: Request):
    sesion = seguridad_sesion.obtener_sesion(request)

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
    sesion = autenticador.autenticar(credenciales)

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    seguridad_sesion.guardar_cookie(
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
    seguridad_sesion.eliminar_cookie(response)

    return {
        "acceso": False,
        "mensaje": "Sesion cerrada",
    }
