import secrets
from contextlib import asynccontextmanager
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
from app.routes.relacion_documentos import router as relacion_router
from app.routes.configuraciones_carnicas import router as configuracion_router
from app.settings import AJUSTES_MODULO
from app.utils.base_de_datos import obtener_base_datos
from app.utils.inicializador_base_datos import (
    inicializar_base_datos_modulo,
)
from app.utils.seguridad import seguridad_sesion


__version__ = "1.2.7"


BASE_DIR = Path(__file__).resolve().parent
APP_DIR = BASE_DIR / 'app'
STATIC_DIR = APP_DIR / 'static'


@asynccontextmanager
async def ciclo_vida_aplicacion(aplicacion: FastAPI):
    # El servidor web solo valida. Las migraciones se ejecutan de forma
    # explícita con scripts/inicializar_base_datos.py.
    reporte = inicializar_base_datos_modulo(aplicar_cambios=False)
    aplicacion.state.inicializacion_base_datos = reporte
    print(
        "[BD] Módulo cárnico listo en "
        f"{reporte.servidor}/{reporte.base_datos}. "
        f"Tablas creadas: {len(reporte.tablas_creadas)}; "
        f"reutilizadas: {len(reporte.tablas_reutilizadas)}."
    )
    yield


app = FastAPI(
    title='CAYAL - Relación de documentos de almacén',
    version=__version__,
    lifespan=ciclo_vida_aplicacion,
)

@app.middleware('http')
async def revalidar_archivos_estaticos(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
    return response


app.mount(
    '/static',
    StaticFiles(directory=STATIC_DIR),
    name='static',
)
templates = Jinja2Templates(directory=APP_DIR / 'templates')

app.include_router(login_router)
app.include_router(relacion_router)
app.include_router(configuracion_router)


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
    )


@app.get('/dashboard', include_in_schema=False)
def mostrar_dashboard(request: Request):
    sesion = seguridad_sesion.obtener_sesion(request)
    if not sesion:
        return RedirectResponse('/', status_code=303)

    permisos = seguridad_sesion.permisos_publicos(sesion)

    lineas = [
        {'Category1': 'CERDO'},
        {'Category1': 'POLLO'},
        {'Category1': 'RES LOCAL'},
    ]
    transformaciones = []
    historial = []
    resumen_historial = {
        'transformaciones': 0,
        'kilos_procesados': 0.0,
        'merma_acumulada': 0.0,
        'rendimiento': 0.0,
    }
    # Los catálogos, configuraciones y el historial se consultan bajo

    response = templates.TemplateResponse(
        request=request,
        name='dashboard.html',
        context={
            'sesion': sesion,
            'permisos': permisos,
            'ajustes': AJUSTES_MODULO,
            'lineas': lineas,
            'transformaciones': transformaciones,
            'historial': historial,
            'resumen_historial': resumen_historial,
        },
    )
    if not sesion.get('csrf'):
        sesion_actualizada = dict(sesion)
        sesion_actualizada.pop('exp', None)
        sesion_actualizada['csrf'] = secrets.token_urlsafe(32)
        seguridad_sesion.guardar_cookie(
            response,
            sesion_actualizada,
            usar_https=request.url.scheme == 'https',
        )
    return response


@app.get('/salud', tags=['Sistema'])
def comprobar_salud():
    try:
        conexion = obtener_base_datos().probar_conexion()
        detalle = 'Conexión SQL Server disponible.'
    except Exception:
        conexion = False
        detalle = 'Base de datos no disponible.'

    return {
        'aplicacion': 'Módulo Cárnico CAYAL',
        'version': __version__,
        'api': True,
        'base_de_datos': conexion,
        'detalle': detalle,
    }
