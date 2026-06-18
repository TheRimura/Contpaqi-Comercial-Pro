import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import HTTPException, Request, Response, status


NOMBRE_COOKIE_SESION = "cayal_sesion"
DURACION_SESION_SEGUNDOS = 8 * 60 * 60
RUTA_CLAVE_LOCAL = (
    Path(__file__).resolve().parents[1]
    / "config"
    / ".session_secret"
)


def _cargar_clave_firma() -> bytes:
    clave_entorno = os.getenv("CAYAL_SESSION_SECRET", "").strip()

    if clave_entorno:
        return clave_entorno.encode("utf-8")

    if RUTA_CLAVE_LOCAL.exists():
        clave_local = RUTA_CLAVE_LOCAL.read_text(
            encoding="utf-8"
        ).strip()

        if len(clave_local) >= 32:
            return clave_local.encode("utf-8")

    clave_nueva = secrets.token_urlsafe(48)

    try:
        if RUTA_CLAVE_LOCAL.exists():
            RUTA_CLAVE_LOCAL.write_text(
                clave_nueva,
                encoding="utf-8",
            )
        else:
            with RUTA_CLAVE_LOCAL.open(
                "x",
                encoding="utf-8",
            ) as archivo:
                archivo.write(clave_nueva)
    except FileExistsError:
        return RUTA_CLAVE_LOCAL.read_text(
            encoding="utf-8"
        ).strip().encode("utf-8")

    return clave_nueva.encode("utf-8")


_CLAVE_FIRMA = _cargar_clave_firma()


def _base64_url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def _decodificar_base64_url(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def _firmar(texto: str) -> str:
    firma = hmac.new(
        _CLAVE_FIRMA,
        texto.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return _base64_url(firma)


def crear_token_sesion(datos_usuario: dict) -> str:
    payload = {
        **datos_usuario,
        "exp": int(time.time()) + DURACION_SESION_SEGUNDOS,
    }
    contenido = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_b64 = _base64_url(contenido)

    return f"{payload_b64}.{_firmar(payload_b64)}"


def leer_token_sesion(token: str | None):
    if not token or len(token) > 4096 or "." not in token:
        return None

    payload_b64, firma_recibida = token.split(".", 1)
    firma_correcta = _firmar(payload_b64)

    if not hmac.compare_digest(firma_recibida, firma_correcta):
        return None

    try:
        payload = json.loads(
            _decodificar_base64_url(payload_b64).decode("utf-8")
        )
    except (ValueError, UnicodeDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    try:
        expiracion = int(payload.get("exp", 0))
    except (TypeError, ValueError):
        return None

    if expiracion < int(time.time()):
        return None

    return payload


def obtener_sesion_request(request: Request):
    return leer_token_sesion(
        request.cookies.get(NOMBRE_COOKIE_SESION)
    )


def requerir_sesion(request: Request):
    sesion = obtener_sesion_request(request)

    if not sesion:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion no valida",
        )

    return sesion


def guardar_cookie_sesion(
    response: Response,
    datos_usuario: dict,
    usar_https: bool,
):
    response.set_cookie(
        key=NOMBRE_COOKIE_SESION,
        value=crear_token_sesion(datos_usuario),
        max_age=DURACION_SESION_SEGUNDOS,
        httponly=True,
        secure=usar_https,
        samesite="lax",
        path="/",
    )


def eliminar_cookie_sesion(response: Response):
    response.delete_cookie(
        key=NOMBRE_COOKIE_SESION,
        httponly=True,
        samesite="lax",
        path="/",
    )
