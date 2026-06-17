import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import HTTPException, Request, Response, status


NOMBRE_COOKIE_SESION = "cayal_sesion"
DURACION_SESION_SEGUNDOS = 8 * 60 * 60
_CLAVE_FIRMA = secrets.token_bytes(32)


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
    if not token or "." not in token:
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

    if int(payload.get("exp", 0)) < int(time.time()):
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
    )


def eliminar_cookie_sesion(response: Response):
    response.delete_cookie(
        key=NOMBRE_COOKIE_SESION,
        httponly=True,
        samesite="lax",
    )
