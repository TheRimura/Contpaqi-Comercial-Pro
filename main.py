import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from app.routes.login import router as login_router
from app.routes.modulo_carnico import router as modulo_carnico_router
from app.routes.relacion_documentos import router as relacion_router
from app.utils.base_de_datos import obtener_base_datos
from app.utils.seguridad import seguridad_sesion


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / 'app'
STATIC_DIR = APP_DIR / 'static'

app = FastAPI(
    title='CAYAL - Módulo Cárnico Web',
    version='1.0.0',
)

app.mount(
    '/static',
    StaticFiles(directory=STATIC_DIR),
    name='static',
)
templates = Jinja2Templates(directory=APP_DIR / 'templates')

app.include_router(login_router)
app.include_router(modulo_carnico_router)
app.include_router(relacion_router)


def obtener_version_assets() -> int:
    versiones = []

    for ruta in (
        STATIC_DIR / 'css' / 'styles.css',
        STATIC_DIR / 'js' / 'app.js',
    ):
        try:
            versiones.append(ruta.stat().st_mtime_ns)
        except FileNotFoundError:
            continue

    return max(versiones) if versiones else 0


@app.exception_handler(RuntimeError)
async def manejar_runtime_error(_: Request, error: RuntimeError):
    return JSONResponse(
        status_code=503,
        content={'detail': str(error)},
    )


@app.get('/', include_in_schema=False)
def mostrar_login(request: Request):
    if seguridad_sesion.obtener_sesion(request):
        return RedirectResponse('/dashboard', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='login.html',
        context={'asset_version': obtener_version_assets()},
    )


@app.get('/dashboard', include_in_schema=False)
def mostrar_dashboard(request: Request):
    sesion = seguridad_sesion.obtener_sesion(request)
    if not sesion:
        return RedirectResponse('/', status_code=303)
    return templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={
            'sesion': sesion,
            'asset_version': obtener_version_assets(),
        },
    )


@app.get('/salud', tags=['Sistema'])
def comprobar_salud():
    try:
        conexion = obtener_base_datos().probar_conexion()
        detalle = 'Conexión SQL Server disponible.'
    except Exception as error:
        conexion = False
        detalle = str(error)

    return {
        'aplicacion': 'Módulo Cárnico CAYAL',
        'api': True,
        'base_de_datos': conexion,
        'detalle': detalle,
    }
