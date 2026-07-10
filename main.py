from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes.login import router as login_router
from app.routes.relacion_documentos import (
    router as relacion_documentos_router,
)
from app.utils.seguridad import seguridad_sesion


RUTA_PROYECTO = Path(__file__).resolve().parent
RUTA_APP = RUTA_PROYECTO / "app"

PATRON_ASSET_ESTATICO = re.compile(
    r'(?P<prefijo>(?:href|src)=")'
    r'(?P<url>/static/(?P<ruta>[^"?]+))'
    r'(?:\?v=[^"]*)?'
    r'(?P<sufijo>")'
)

app = FastAPI(
    title="CAYAL - Módulo Cárnico",
)

app.mount(
    "/static",
    StaticFiles(directory=RUTA_APP / "static"),
    name="static",
)

app.include_router(login_router)
app.include_router(relacion_documentos_router)


def responder_template(nombre_archivo: str) -> HTMLResponse:
    ruta_template = RUTA_APP / "templates" / nombre_archivo
    contenido = ruta_template.read_text(encoding="utf-8")

    def agregar_version(coincidencia):
        ruta_asset = RUTA_APP / "static" / coincidencia.group("ruta")

        try:
            version = ruta_asset.stat().st_mtime_ns
        except FileNotFoundError:
            return coincidencia.group(0)

        return (
            f'{coincidencia.group("prefijo")}'
            f'{coincidencia.group("url")}?v={version}'
            f'{coincidencia.group("sufijo")}'
        )

    contenido_versionado = PATRON_ASSET_ESTATICO.sub(
        agregar_version,
        contenido,
    )

    return HTMLResponse(contenido_versionado)


@app.get("/", include_in_schema=False)
def mostrar_login(request: Request):
    if seguridad_sesion.obtener_sesion(request):
        return RedirectResponse("/dashboard", status_code=303)

    return responder_template("login.html")


@app.get("/dashboard", include_in_schema=False)
def mostrar_dashboard(request: Request):
    if not seguridad_sesion.obtener_sesion(request):
        return RedirectResponse("/", status_code=303)

    return responder_template("dashboard.html")


@app.get("/salud", tags=["Sistema"])
def comprobar_salud():
    return {
        "estado": "ok",
        "aplicacion": "Módulo Cárnico CAYAL",
    }
