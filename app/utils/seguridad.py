import base64
import hashlib
import hmac
import json
import time
from functools import cache, cached_property

from fastapi import HTTPException, Request, Response, status

from app.utils.base_de_datos import obtener_base_datos


class SeguridadSesion:
    def __init__(self, base_datos):
        self._base_datos = base_datos

    @cached_property
    def _configuracion(self):
        return self._base_datos.buscar_configuracion_seguridad()

    @staticmethod
    def _base64_url(datos):
        return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")

    @staticmethod
    def _decodificar_base64_url(texto):
        relleno = "=" * (-len(texto) % 4)
        return base64.urlsafe_b64decode(texto + relleno)

    def _firmar(self, texto):
        firma = hmac.new(
            self._configuracion["clave_firma"].encode("utf-8"),
            texto.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        return self._base64_url(firma)

    def crear_token(self, datos_usuario):
        payload = {
            **datos_usuario,
            "exp": (
                int(time.time())
                + int(
                    self._configuracion[
                        "duracion_sesion_segundos"
                    ]
                )
            ),
        }
        contenido = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        payload_b64 = self._base64_url(contenido)
        return f"{payload_b64}.{self._firmar(payload_b64)}"

    def leer_token(self, token):
        if not token or len(token) > 4096 or "." not in token:
            return None

        payload_b64, firma_recibida = token.split(".", 1)

        if not hmac.compare_digest(
            firma_recibida,
            self._firmar(payload_b64),
        ):
            return None

        try:
            payload = json.loads(
                self._decodificar_base64_url(payload_b64).decode("utf-8")
            )
            expiracion = int(payload.get("exp", 0))
        except (ValueError, TypeError, UnicodeDecodeError):
            return None

        if not isinstance(payload, dict) or expiracion < int(time.time()):
            return None

        return payload

    def obtener_sesion(self, request):
        return self.leer_token(
            request.cookies.get(
                self._configuracion["nombre_cookie"]
            )
        )

    def requerir_sesion(self, request: Request):
        sesion = self.obtener_sesion(request)

        if not sesion:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesion no valida",
            )

        return sesion

    def guardar_cookie(
        self,
        response: Response,
        datos_usuario,
        usar_https,
    ):
        response.set_cookie(
            key=self._configuracion["nombre_cookie"],
            value=self.crear_token(datos_usuario),
            max_age=int(
                self._configuracion["duracion_sesion_segundos"]
            ),
            httponly=True,
            secure=usar_https,
            samesite="lax",
            path="/",
        )

    def eliminar_cookie(self, response: Response):
        response.delete_cookie(
            key=self._configuracion["nombre_cookie"],
            httponly=True,
            samesite="lax",
            path="/",
        )

@cache
def obtener_seguridad():
    return SeguridadSesion(obtener_base_datos())


seguridad_sesion = obtener_seguridad()
