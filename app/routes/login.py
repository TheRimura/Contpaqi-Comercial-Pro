import bcrypt
import secrets
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.schemas import CredencialesAcceso, SesionCerrada, SesionPublica
from app.settings import AJUSTES_MODULO, PERMISOS_MODULO
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


router = APIRouter(
    prefix="/login",
    tags=["Login"],
)


class Autenticador:
    def __init__(self, base_datos):
        self._base_datos = base_datos

    @staticmethod
    def _preparar_hash(hash_guardado):
        if hash_guardado is None:
            return None

        if isinstance(hash_guardado, memoryview):
            hash_guardado = hash_guardado.tobytes()
        elif isinstance(hash_guardado, bytearray):
            hash_guardado = bytes(hash_guardado)

        if isinstance(hash_guardado, bytes):
            valor = hash_guardado.strip()

            if valor.lower().startswith(b"0x"):
                try:
                    return bytes.fromhex(valor[2:].decode("ascii"))
                except (ValueError, UnicodeDecodeError):
                    return None

            return valor

        if isinstance(hash_guardado, str):
            valor = hash_guardado.strip()

            if valor.lower().startswith("0x"):
                try:
                    return bytes.fromhex(valor[2:])
                except ValueError:
                    return None

            return valor.encode("utf-8")

        try:
            return bytes(hash_guardado)
        except (TypeError, ValueError):
            return None

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
            self._coincide_password(
                password,
                fila.get("UserPassword"),
            )
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
            "user_id": int(usuario["UserID"]),
            "usuario": str(usuario["UserName"]),
            "user_group_id": usuario.get("UserGroupID"),
            "uso_llave_maestra": uso_llave_maestra,
        }


autenticador = Autenticador(obtener_base_datos())


class LimiteIntentosAcceso:
    """Limita intentos fallidos por dirección y usuario dentro del proceso."""

    def __init__(self):
        self._intentos = defaultdict(deque)
        self._bloqueo = Lock()

    @staticmethod
    def _clave(request: Request, usuario: str) -> tuple[str, str]:
        ip = request.client.host if request.client else "desconocida"
        return ip, usuario.strip().upper()

    def _limpiar_vencidos(self, intentos: deque, ahora: float) -> None:
        limite = ahora - AJUSTES_MODULO.ventana_intentos_login_segundos
        while intentos and intentos[0] <= limite:
            intentos.popleft()

    def esta_bloqueado(self, request: Request, usuario: str) -> bool:
        clave = self._clave(request, usuario)
        ahora = time.monotonic()
        with self._bloqueo:
            intentos = self._intentos[clave]
            self._limpiar_vencidos(intentos, ahora)
            return len(intentos) >= AJUSTES_MODULO.maximo_intentos_login

    def registrar_fallo(self, request: Request, usuario: str) -> None:
        clave = self._clave(request, usuario)
        ahora = time.monotonic()
        with self._bloqueo:
            intentos = self._intentos[clave]
            self._limpiar_vencidos(intentos, ahora)
            intentos.append(ahora)

    def limpiar(self, request: Request, usuario: str) -> None:
        with self._bloqueo:
            self._intentos.pop(self._clave(request, usuario), None)


limite_intentos_acceso = LimiteIntentosAcceso()


@router.get("/sesion", response_model=SesionPublica)
def consultar_sesion(request: Request):
    sesion = seguridad_sesion.requerir_sesion(request)

    sesion_publica = dict(sesion)
    sesion_publica.pop("exp", None)

    return {
        "acceso": True,
        **sesion_publica,
    }


@router.post("/", response_model=SesionPublica)
def iniciar_sesion(
    credenciales: CredencialesAcceso,
    request: Request,
    response: Response,
):
    if limite_intentos_acceso.esta_bloqueado(request, credenciales.usuario):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos. Espera antes de volver a ingresar.",
            headers={
                "Retry-After": str(
                    AJUSTES_MODULO.ventana_intentos_login_segundos
                )
            },
        )
    sesion = autenticador.autenticar(credenciales)

    if not sesion:
        limite_intentos_acceso.registrar_fallo(request, credenciales.usuario)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
        )

    if not PERMISOS_MODULO.grupo_tiene_permiso(
        int(sesion.get("user_group_id") or 0),
        "acceso_modulo",
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Acceso no autorizado para tu grupo de usuario."
            ),
        )

    limite_intentos_acceso.limpiar(request, credenciales.usuario)
    sesion["csrf"] = secrets.token_urlsafe(32)
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


@router.post("/logout", response_model=SesionCerrada)
def cerrar_sesion(response: Response):
    # Cerrar sesión no modifica información operativa. Debe funcionar
    # incluso con cookies antiguas o vencidas para no atrapar al usuario.
    seguridad_sesion.eliminar_cookie(response)

    return {
        "acceso": False,
        "mensaje": "Sesión cerrada",
    }
