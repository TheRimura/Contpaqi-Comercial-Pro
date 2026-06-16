from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routes.login import router as login_router
from app.routes.productos import router as productos_router
from app.routes.transformaciones import router as transformaciones_router


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
def mostrar_login():
    return FileResponse(RUTA_APP / "templates" / "login.html")


@app.get("/dashboard")
def mostrar_dashboard():
    return FileResponse(RUTA_APP / "templates" / "dsahboad.html")