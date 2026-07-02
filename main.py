from pathlib import Path
import re

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes.configuraciones import router as configuraciones_router
from app.routes.login import router as login_router
from app.routes.productos import router as productos_router
from app.routes.transformaciones import router as transformaciones_router
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
    title="CAYAL - Transformación Cárnica",
)

app.mount(
    "/static",
    StaticFiles(directory=RUTA_APP / "static"),
    name="static",
)

app.include_router(login_router)
app.include_router(productos_router)
app.include_router(transformaciones_router)
app.include_router(configuraciones_router)


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

    return HTMLResponse(PATRON_ASSET_ESTATICO.sub(agregar_version, contenido))


@app.get("/")
def mostrar_login(request: Request):
    if seguridad_sesion.obtener_sesion(request):
        return RedirectResponse("/dashboard", status_code=303)

    return responder_template("login.html")


@app.get("/dashboard")
def mostrar_dashboard(request: Request):
    if not seguridad_sesion.obtener_sesion(request):
        return RedirectResponse("/", status_code=303)

    return responder_template("dashboard.html")
