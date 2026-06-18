from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routes.login import router as login_router
from app.routes.productos import router as productos_router
from app.routes.transformaciones import router as transformaciones_router
from app.services.sesiones import obtener_sesion_request


RUTA_PROYECTO = Path(__file__).resolve().parent
RUTA_APP = RUTA_PROYECTO / "app"

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


@app.get("/")
def mostrar_login(request: Request):
    if obtener_sesion_request(request):
        return RedirectResponse("/dashboard", status_code=303)

    return FileResponse(RUTA_APP / "templates" / "login.html")


@app.get("/dashboard")
def mostrar_dashboard(request: Request):
    if not obtener_sesion_request(request):
        return RedirectResponse("/", status_code=303)

    return FileResponse(RUTA_APP / "templates" / "dashboard.html")
